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

## Account Age

`account_age_days` is calculated independently for every snapshot as the
calendar-day difference between `snapshot_date` and the player's UTC
registration date.

## Building Costs

All cost columns are **estimates**: the data shows which buildings stand, not
what was paid. The cost columns differ in only two ways: **which levels** they
count and **which discount** they apply. The names follow the pattern
`<which levels>_cost_<which discount>_<resource>`:

| | Full price, no discount (`undiscounted`) | Discount at this snapshot (`today`) | Discount when the level was built (`at_build`) |
|---|---|---|---|
| **Levels standing now** (`standing`) | `standing_cost_undiscounted_*` | `standing_cost_today_*` | `standing_cost_at_build_*` |
| **Every level ever built** (`ever_built`) | – | – | `ever_built_cost_at_build_*` |

- `standing_cost_undiscounted_*`: what would the standing buildings cost at full
  price? Includes the town hall, whose level is the city's own `level` column
  rather than one of the 17 numbered building slots; `building_levels_total`
  counts it too.
- `standing_cost_today_*`: the same buildings at this snapshot's discount
  (`cost_factor_today_*`: player research plus the city's reduction
  buildings). Old buildings get today's discount although it did not exist when
  they were built, so this understates the real cost.
- `standing_cost_at_build_*`: what did the standing buildings cost, each level
  at the discount the city had when it was built? The best estimate of the real
  cost. Check `preexisting_share` before using it.
- `ever_built_cost_at_build_*`: what did every level ever built cost, including
  levels later demolished? It never decreases. The gap to
  `standing_cost_at_build_*` is the value lost to demolition.

For the total amount of a resource bound in a city, add the stock to the
building value you need, for example
`standing_cost_at_build_wood + wood_stored`.

Research is not in the data either. `estimated_research_cost_factor`,
`estimated_research_cost_factor_source` and `research_evidence_tier` show how
the research part of the discount was inferred.

All cost columns aggregate by plain summation at every grain.

### How `at_build` is calculated

`building_construction_event` follows every building position of every city
across snapshots. A level that is missing at one snapshot and present at the
next was built in between. It is priced at the midpoint of the city's
`cost_factor_today_*` at those two snapshots (`cost_factor_at_build_*`); the
exact moment within the interval is not observable. A level that disappears
becomes a row in `building_demolition_event`, written off at the cost it was
built for. So:

    standing_cost_at_build  = construction events - demolition events
    ever_built_cost_at_build = construction events

A later rebuild therefore never changes an earlier snapshot's value.

**New cities.** A city that first appears after its server's first snapshot was
founded since the server's previous snapshot, so its levels are dated to that
interval as well (`built_after_snapshot_date` is that server snapshot). The
city did not exist at the start of the interval, so the starting discount is
the owner's research factor at that snapshot, with no reduction buildings. A
player without any city at that snapshot had not started yet and gets no
research discount (factor 1.0).

### Example

A city with one warehouse. In the full price list, level 1 costs 100 wood,
level 2 costs 200 and level 3 costs 300. The city existed at the server's
first snapshot s1.

| | What happens | `cost_factor_today` | `undiscounted` | `today` | `at_build` | `ever_built` | `preexisting_share` |
|---|---|---|---|---|---|---|---|
| s1 | level 1 already there when the data starts | 1.0 | 100 | 100 | **100** (guess) | 100 | 1.0 |
| s2 | level 2 appears; the factor went from 1.0 to 0.9, midpoint 0.95 | 0.9 | 300 | 270 | 100 + **190** = 290 | 290 | 0.33 |
| s3 | level 3 appears, built at 0.9 | 0.9 | 600 | 540 | 290 + **270** = 560 | 560 | 0.17 |
| s4 | level 3 torn down | 0.9 | 300 | 270 | 560 − 270 = 290 | **560** (stays) | 0.33 |

(All columns are the `standing_cost_*_wood` and `ever_built_cost_at_build_wood`
of this city.)

- `today` gives level 1 a discount it never had (90 instead of 100 at s2), so it
  understates the real cost.
- `at_build` prices every level at its own discount: the best estimate.
- `ever_built` never goes down; the 270 lost to the demolition is its gap to
  `at_build`.
- `preexisting_share` shrinks as levels are built while observed, and rises
  again when such a level is torn down.

Had the city been founded between s1 and s2 instead, nothing in it would be
preexisting: its levels would be dated to that interval.

### `preexisting_share`: how far `at_build` can be trusted

Levels already standing at the **server's first snapshot** are **preexisting**
(`is_preexisting` in the event tables). Their build time is unknown, so their
`at_build` cost uses the discount of that snapshot, which is a guess.
`preexisting_share` is the share of `standing_cost_undiscounted_total` that is
preexisting:

- **0**: every standing level was built while observed, so `at_build` is reliable.
- **1**: every standing level was already there, so `at_build` is a guess.
- **NULL**: nothing stands; `avg()` skips these rows on its own.

Expensive levels count for more than cheap ones. To combine rows (for example
all cities of a server), weight by the undiscounted cost instead of averaging
the shares:

```sql
sum(preexisting_share * standing_cost_undiscounted_total)
    / sum(standing_cost_undiscounted_total)
```

How much is preexisting depends on when a server's first snapshot was taken:

| Servers | Snapshots | Preexisting |
|---|---|---|
| DE 23, EN 22, FR 21, GR 19, TR 25 | 36-37, the first one day after the server's start | almost nothing |
| AE 18, BR 27 | 6, the first about six months after the server's start | everything built in the first six months |
| AR 11, RU 17, US 19 and the ten comparison servers | 1 | everything (100%) |

With a single snapshot no level can be dated, so on those 13 servers
`standing_cost_at_build_*` equals `standing_cost_today_*`. Their 100% is not a
data error. Use the `at_build` columns on the five long-running servers, and
with caution on AE and BR.

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
    SUM(standing_cost_undiscounted_wood) AS standing_cost_undiscounted_wood,
    SUM(standing_cost_undiscounted_total) AS standing_cost_undiscounted_total,
    SUM(standing_cost_today_total) AS standing_cost_today_total,
    SUM(resources_stored_total) AS resources_stored_total,
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
