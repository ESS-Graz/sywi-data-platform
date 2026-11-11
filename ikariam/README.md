# Ikariam Data

Snapshots of the browser game Ikariam (2013–2014, 20 servers in 10 countries), cleaned into tables for analysis. This README explains how to query them and what to watch out for. The pipeline that builds the tables is in this directory too; see [For Pipeline Developers](#for-pipeline-developers) at the end.

## Getting Started with the Data

The tables are on the university's S3 storage. You query them in place with DuckDB; nothing has to be downloaded and Docker is not needed.

1. Install [uv](https://github.com/astral-sh/uv), [just](https://github.com/casey/just) and the [DuckDB CLI](https://duckdb.org/docs/installation/) (version 2.0 or newer). The [main README](../README.md#prerequisites) has the install commands; Docker, also listed there, is only needed to run the pipeline.
2. Clone the repository:
   ```bash
   git clone https://github.com/ESS-Graz/sywi-data-platform.git
   cd sywi-data-platform
   ```
3. Put the `.env.local` file you received into the repository root. It holds your S3 keys and must contain these lines:
   ```bash
   LANCE_REMOTE_URI=ikariam=s3://ikariam/ikariam.lancedb
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   AWS_ENDPOINT_URL=https://data.systems-sciences.uni-graz.at
   AWS_REGION=us-east-1
   ```
4. Run a first query file. It lists every server with its snapshot days and player count:
   ```bash
   just db -f ikariam/sql/explore/01_coverage.sql
   ```

### Working in a Session

`just db` opens an interactive DuckDB session with the tables attached as `ikariam`. Run it from the repository root:

```sql
SHOW TABLES FROM ikariam;                        -- list the tables
DESCRIBE ikariam.player_snapshot;                -- columns and their types
SELECT * FROM ikariam.player_snapshot LIMIT 10;  -- look at some rows

-- Save a result as CSV (for R, Python or Excel); the file lands in the repository root
COPY (SELECT country_code, server, count(*) AS players
      FROM ikariam.player_snapshot GROUP BY ALL) TO 'players_per_server.csv';

.quit                                            -- leave the session
```

`SHOW TABLES` also lists many `raw_*` tables (`raw_avatar_de`, `raw_city_de`, …). They hold the unprocessed game data per country; for analysis use the six tables under [Primary Tables](#primary-tables).

`.read ikariam/sql/explore/00_setup.sql` adds short names without the `ikariam.` prefix (`player_snapshot`, `city_snapshot`, `island_snapshot`, `donations`, `construction`) and the views `latest_player` and `latest_donations`. The example queries in this README use these short names, so run that line first.

What each table and column means is listed in the [data catalog](https://data.systems-sciences.uni-graz.at/catalog/). It needs a login.

Example analyses to start from, each runnable with `just db -f`:

| File | Content |
|---|---|
| `sql/explore/01_coverage.sql` | Servers, snapshot days and players per server |
| `sql/explore/02_players.sql` | Player profiles on each server's latest snapshot |
| `sql/explore/03_donations.sql` | How concentrated donations are, and where they go |
| `sql/explore/04_construction.sql` | Most built building types and construction spending per month (about 30 s) |
| `sql/explore/05_retention.sql` | How many players of a server's first snapshot are still there on the last |

### From Python or R

The Python package [`sywi-duckdb`](../libs/sywi_duckdb/README.md) reads the same `.env.local` and attaches the tables the same way (`ikariam.player_snapshot`). There is also an R package, [`sywi.duckdb`](../libs/sywi.duckdb/README.md), but it is still untested, and it does not yet understand the `ikariam=` form of `LANCE_REMOTE_URI` shown above.

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

## Repeated Island Columns in city_snapshot

`city_snapshot` has one row per city. Its island columns (`wonder_level`, `sawmill_level`, `island_city_count`, …) describe the island the city is on, so they repeat on every city of that island. City columns such as population, buildings or stored resources can be summed freely. For an island column, take one value per island (`ANY_VALUE` when grouping by `country_code, server, island_id, snapshot_id`) instead of a sum.

Donations are not in `city_snapshot`: the game records them per player and island, not per city. They are in `donation_analytics_player_island_snapshot`, with one row per player, island and snapshot.

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
- `donation_analytics_player_island_snapshot` and `island_snapshot` count only
  islands where the player has a city at that snapshot, because there is no
  city row to attach the rest to.

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

## Useful Queries

The latest row per player, city or island and summaries over all snapshots are not stored as tables. These queries compute them from the primary tables (run `.read ikariam/sql/explore/00_setup.sql` first for the short table names).

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

### 3. city_latest
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

### 4. player_island_latest
A player's cities on one island, summed, from each city's latest snapshot. The donations on that island are in the `donations` table.
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
    -- Island columns are the same on every city of the island
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
Get the historical summary of a player's presence on an island, from their cities in `city_snapshot`.
```sql
SELECT 
    country_code,
    server,
    player_id,
    island_id,
    COUNT(DISTINCT snapshot_id) AS snapshots_observed_count,
    MIN(snapshot_date) AS first_snapshot_date,
    MAX(snapshot_date) AS last_snapshot_date,
    COUNT(DISTINCT city_id || '_' || snapshot_id) AS player_city_observation_count
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

## For Pipeline Developers

### Running the Pipeline

The job `ikariam_full_pipeline` runs every asset in dependency order, ending with the LanceDB export. In the Dagster UI it is under **Jobs**. The export deletes and rewrites the database at the output location below.

### Output Location

The tables are written to LanceDB. By default that is `ikariam/output/ikariam.lancedb`.
Set `IKARIAM_LANCEDB_PATH` to write somewhere else, either a local directory or an
object-store URI such as `s3://ikariam/ikariam.lancedb`. For S3, LanceDB takes the
endpoint and credentials from the standard `AWS_*` variables (`AWS_ENDPOINT`,
`AWS_REGION`, `AWS_ALLOW_HTTP`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`). In
production the output goes to the `ikariam` bucket on SeaweedFS.
