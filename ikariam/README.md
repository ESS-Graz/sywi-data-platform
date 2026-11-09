# Ikariam Pipeline Data Model

This directory contains the pipeline for processing Ikariam data snapshots into clean, analytics-ready tables.

## Primary Tables

All raw snapshot data is aggregated and cleaned into four primary snapshot tables stored in LanceDB:

- `player_snapshot` (grain: one row per player per snapshot)
- `city_snapshot` (grain: one row per city per snapshot)
- `island_snapshot` (grain: one row per island per snapshot)
- `donation_analytics_player_island_snapshot` (grain: one row per player, island, and snapshot)

Two event ledgers record construction history at a finer grain:

- `building_construction_event` (grain: one row per building level ever constructed)
- `building_demolition_event` (grain: one row per building level that stopped standing)

## Player Filter

The pipeline keeps only players registered at or after the start of their own server. Accounts
registered earlier are admin or test accounts; this removes 122 of 205,316 accounts. The start times
are in `data/raw/ikariam/server_starts.csv`, taken from the sheet `Servers` in
[`docs/snapshots_verification.xlsx`](docs/snapshots_verification.xlsx). AR 11 is taken as 10:00 UTC
(issue I08 in that workbook). The run fails if a server in the data has no start time.

## Running the Pipeline

The job `ikariam_full_pipeline` runs every asset in dependency order, ending with the LanceDB export. In the Dagster UI it is under **Jobs**. The export deletes and rewrites the database at the output location below.

## Output Location

The tables are written to LanceDB. By default that is `ikariam/output/ikariam.lancedb`.
Set `IKARIAM_LANCEDB_PATH` to write somewhere else, either a local directory or an
object-store URI such as `s3://ikariam/ikariam.lancedb`. For S3, LanceDB takes the
endpoint and credentials from the standard `AWS_*` variables (`AWS_ENDPOINT`,
`AWS_REGION`, `AWS_ALLOW_HTTP`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`). In
production the output goes to the `ikariam` bucket on SeaweedFS.

Query the S3 copy with the DuckDB 2.0 CLI using the files in `sql/explore/`
(`./run.sh 02_players.sql`).

## Data Denormalization & Normalization Philosophy

To support rich analytical workloads, we deliberately choose a denormalized design for the `city_snapshot` table:

- **Intentionally Repeated Metrics**: Player-island level donations (e.g., `donations_total`) and island metadata (e.g., `wonder_level`, `wonder_belief`, mine levels) are repeated across all cities owned by a player on the same island.
- **Rationale**: Denormalization simplifies downstream analysis by keeping related city, player, and island contexts in a single, extensive snapshot dataset, eliminating the need for complex multi-table joins.
- **Aggregation Rules**:
  - When aggregating city-level columns (e.g., population, resource levels) to player or island level, use standard sums (`SUM`).
  - When aggregating player-island level columns (e.g., player donations) to the player level, use the maximum (`MAX`) across the cities on that island to avoid double-counting.

> [!NOTE]
> **Note on Data Duplication**:
> Duplication in this dataset is **intentional** to make analysis easier. Users of the dataset should keep this in mind when querying: always aggregate player-island level metrics using `MAX` rather than `SUM` when rolling up to the player or server levels.

## Donation Totals

The raw donation data holds, for every player, island and donation type, the
**running total** donated so far, not the donations of one week. The amounts
never decrease from one snapshot to the next. Every `*_donations_total` column
is therefore "donated up to this snapshot": use the latest snapshot for a
lifetime total, and never sum a donation column across snapshots.

The running total stays in the data after the player's city has left the island
(mostly relocated cities). Which islands count depends on the table:

- `player_snapshot` counts every island, including islands where the player no
  longer has a city.
- `city_snapshot`, `donation_analytics_player_island_snapshot` and
  `island_snapshot` count only islands where the player has a city at that
  snapshot, because there is no city row to attach the rest to.

So a player's total in `player_snapshot` can be higher than the sum over their
islands in the player-island tables. Across the current data the difference is
5.70 of 219.5 billion gold (2.6%).

## Donation Analytics

Donation ratios and island peer averages live in `donation_analytics_player_island_snapshot`.
This table keeps donation facts, denominators, intensity ratios, composition shares, and island peer averages at their natural player-island-snapshot grain.

It intentionally does not reproduce legacy database-wide broadcast constants such as total server donations copied onto every row. Those values are report summaries, not row-level analytics.

## Account Age and Building Costs

`account_age_days` is calculated independently for every snapshot as the
calendar-day difference between `snapshot_date` and the player's UTC
registration date. Building costs are intentionally split into distinct
concepts:

- `building_base_cost_*` is the undiscounted cumulative lookup cost of the
  buildings visible in that snapshot. This includes the town hall, whose level
  is the city's own `level` column rather than one of the 17 numbered building
  slots; `building_levels_total` counts it too.
- `estimated_building_cost_*` applies the player-snapshot research factor
  inferred from age and cumulative building evidence.
- `*_stored` remains the observed inventory, while
  `estimated_*_resource_value` combines that inventory with the estimated
  building cost.

The estimate is not historical expenditure. Use
`estimated_research_cost_factor`, `estimated_research_cost_factor_source`, and
`research_evidence_tier` to identify how it was inferred.

## Vintage-Priced Construction

`estimated_building_cost_*` applies one *current* factor to every level, which
credits today's discounts to buildings raised before those discounts existed.
Two further columns price each level at the discount state active when it was
actually built, reconstructed from consecutive snapshots:

- `historical_building_cost_*` — paid for the levels **still standing**.
- `lifetime_construction_spend_*` — paid for **every level ever built**,
  including levels later demolished, so it never decreases.

A level that appears between two snapshots is priced at the midpoint of the
city's factor at those two observations; the exact moment within the interval is
not observable. Standing value is accounted for as construction minus
demolition, so a later rebuild never changes an earlier snapshot's value.

Levels already present the first time a building is seen cannot be dated. They
are priced at that first observation's factor and reported separately via
`opening_stock_base_cost_total`.

Both measures aggregate by plain summation at every grain. Coverage is a ratio
and is recomputed per row rather than summed.

### Coverage: how far the historical prices can be trusted

`observed_construction_coverage` is the share of a row's building value that
could be dated to an interval between two snapshots:

    coverage = 1 - opening_stock_base_cost_total / building_base_cost_total

Value means undiscounted building cost, so expensive levels count for more than
cheap ones. The lower the coverage, the more the historical measures rest on the
first-observation assumption above.

Vintage pricing needs several snapshots of a server, so coverage is only
meaningful where those exist. Value-weighted over all rows of the current data:

| Servers | Snapshots | Coverage |
|---|---|---|
| DE 23, EN 22, FR 21, GR 19, TR 25 | 36-37 | 97.2% |
| AE 18, BR 27 | 6, the first about six months after the server's start | 36.6% |
| AR 11, RU 17, US 19 and the ten comparison servers | 1 | 0% |

With a single snapshot, no level can be dated. On those 13 servers the vintage
pricing does not really work: every level is priced at the one observed factor,
so `historical_building_cost_*` adds no information beyond
`estimated_building_cost_*`. Do not read their 0% as a data error, and do not
include them in a statement about overall coverage. Use the historical measures
for analysis on the five long-running servers, and with caution on AE and BR.

A row with no buildings has no value to date; its coverage reads 1.0 and says
nothing, so exclude these rows (`building_base_cost_total = 0`) when averaging.

## Reconstructing Dropped Summary and Latest Tables

To minimize storage and pipeline maintenance, we do not materialize the obsolete static "latest" or "summary" tables in LanceDB. Instead, they can be easily computed dynamically using standard SQL queries in DuckDB (or any SQL engine) from the primary tables.

Player, city and island IDs are only unique within a server: the same ID can appear on several servers, so these queries always include `server` in their keys.

### 1. player_latest
Get the latest snapshot row for each player.
```sql
SELECT * FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY country_code, server, player_id
               ORDER BY snapshot_date DESC, snapshot_id DESC
           ) as rn
    FROM player_snapshot
) WHERE rn = 1;
```

### 2. island_latest
Get the latest snapshot row for each island.
```sql
SELECT * FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY country_code, server, island_id
               ORDER BY snapshot_date DESC, snapshot_id DESC
           ) as rn
    FROM island_snapshot
) WHERE rn = 1;
```

### 3. city_latest (previously player_island_latest at city level)
Get the latest snapshot row for each city. A city can change island between snapshots, so the island is not part of the key.
```sql
SELECT * FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY country_code, server, city_id
               ORDER BY snapshot_date DESC, snapshot_id DESC
           ) as rn
    FROM city_snapshot
) WHERE rn = 1;
```

### 4. player_island_latest (Aggregated to Player-Island level)
To reconstruct the player-island level latest states (summing population/buildings/resources across a player's cities on that island, and taking the maximum of their island-level donations):
```sql
WITH latest_cities AS (
    SELECT * FROM (
        SELECT *,
               ROW_NUMBER() OVER (
                   PARTITION BY country_code, server, city_id
                   ORDER BY snapshot_date DESC, snapshot_id DESC
               ) as rn
        FROM city_snapshot
    ) WHERE rn = 1
)
SELECT 
    country_code,
    server,
    player_id,
    island_id,
    SUM(population_total) AS population_total,
    SUM(building_base_cost_wood) AS building_base_cost_wood,
    SUM(building_base_cost_total) AS building_base_cost_total,
    SUM(estimated_building_cost_total) AS estimated_building_cost_total,
    SUM(resources_stored_total) AS resources_stored_total,
    SUM(estimated_resource_value_total) AS estimated_resource_value_total,
    SUM(building_levels_total) AS building_levels_total,
    -- Aggregating player-island level donations using MAX to avoid double counting across cities
    MAX(wonder_donations_total) AS wonder_donations_total,
    MAX(sawmill_donations_total) AS sawmill_donations_total,
    MAX(luxury_mine_donations_total) AS luxury_mine_donations_total,
    MAX(donations_total) AS donations_total,
    -- Island metadata remains consistent
    ANY_VALUE(wonder_type_id) AS wonder_type_id,
    ANY_VALUE(wonder_level) AS wonder_level,
    ANY_VALUE(luxury_resource_type) AS luxury_resource_type,
    ANY_VALUE(luxury_mine_level) AS luxury_mine_level,
    ANY_VALUE(sawmill_level) AS sawmill_level,
    ANY_VALUE(island_city_count) AS island_city_count
FROM latest_cities
GROUP BY country_code, server, player_id, island_id;
```

### 5. player_summary
Get the cross-snapshot historical summary per player.
```sql
SELECT 
    country_code,
    server,
    player_id,
    COUNT(DISTINCT snapshot_id) AS snapshots_observed_count,
    MIN(snapshot_date) AS first_snapshot_date,
    MAX(snapshot_date) AS last_snapshot_date,
    MIN(registered_at_unix) AS registered_at_unix,
    DATEDIFF('day', MIN(snapshot_date), MAX(snapshot_date)) AS observation_span_days
FROM player_snapshot
GROUP BY country_code, server, player_id;
```

### 6. player_island_summary
Get the historical summary of a player's activity on an island. Since we track at the city level in `city_snapshot`, we group by `player_id` and `island_id`, and take the `MAX` of the player's total donations on that island.
```sql
SELECT 
    country_code,
    server,
    player_id,
    island_id,
    COUNT(DISTINCT snapshot_id) AS snapshots_observed_count,
    MIN(snapshot_date) AS first_snapshot_date,
    MAX(snapshot_date) AS last_snapshot_date,
    COUNT(DISTINCT city_id || '_' || snapshot_id) AS player_city_observation_count,
    MAX(donations_total) AS max_donations_total
FROM city_snapshot
GROUP BY country_code, server, player_id, island_id;
```

### 7. island_summary
Get the cross-snapshot historical summary per island.
```sql
SELECT 
    country_code,
    server,
    island_id,
    COUNT(DISTINCT snapshot_id) AS snapshots_observed_count,
    MIN(snapshot_date) AS first_snapshot_date,
    MAX(snapshot_date) AS last_snapshot_date
FROM island_snapshot
GROUP BY country_code, server, island_id;
```

## Raw data lineage

How the raw dumps in `data/raw/ikariam/` came about (dumps, MySQL, DuckDB, parquet), which server and
date each snapshot has, and what the raw data still contains: see
[`docs/raw_data_to_parquet.md`](docs/raw_data_to_parquet.md).
