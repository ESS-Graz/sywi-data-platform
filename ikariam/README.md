# Ikariam Pipeline Data Model

This directory contains the pipeline for processing Ikariam data snapshots into clean, analytics-ready tables.

## Primary Tables

All raw snapshot data is aggregated and cleaned into four primary snapshot tables stored in LanceDB:
- `player_snapshot` (grain: one row per player per snapshot)
- `city_snapshot` (grain: one row per city per snapshot)
- `island_snapshot` (grain: one row per island per snapshot)
- `donation_analytics_player_island_snapshot` (grain: one row per player, island, and snapshot)

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

## Donation Analytics

Donation ratios and island peer averages live in `donation_analytics_player_island_snapshot`.
This table keeps donation facts, denominators, intensity ratios, composition shares, and island peer averages at their natural player-island-snapshot grain.

It intentionally does not reproduce legacy database-wide broadcast constants such as total server donations copied onto every row. Those values are report summaries, not row-level analytics.

## Reconstructing Dropped Summary and Latest Tables

To minimize storage and pipeline maintenance, we do not materialize the obsolete static "latest" or "summary" tables in LanceDB. Instead, they can be easily computed dynamically using standard SQL queries in DuckDB (or any SQL engine) from the primary tables.

### 1. player_latest
Get the latest snapshot row for each player.
```sql
SELECT * FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY country_code, player_id
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
               PARTITION BY country_code, island_id
               ORDER BY snapshot_date DESC, snapshot_id DESC
           ) as rn
    FROM island_snapshot
) WHERE rn = 1;
```

### 3. city_latest (previously player_island_latest at city level)
Get the latest snapshot row for each city.
```sql
SELECT * FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY country_code, player_id, island_id, city_id
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
                   PARTITION BY country_code, city_id
                   ORDER BY snapshot_date DESC, snapshot_id DESC
               ) as rn
        FROM city_snapshot
    ) WHERE rn = 1
)
SELECT 
    country_code,
    player_id,
    island_id,
    SUM(population_total) AS population_total,
    SUM(wood_in_buildings) AS wood_in_buildings,
    SUM(resources_in_buildings_total) AS resources_in_buildings_total,
    SUM(building_resource_score) AS building_resource_score,
    SUM(resources_stored_total) AS resources_stored_total,
    SUM(resources_in_buildings_and_storage_total) AS resources_in_buildings_and_storage_total,
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
GROUP BY country_code, player_id, island_id;
```

### 5. player_summary
Get the cross-snapshot historical summary per player.
```sql
SELECT 
    country_code,
    player_id,
    COUNT(DISTINCT snapshot_id) AS snapshots_observed_count,
    MIN(snapshot_date) AS first_snapshot_date,
    MAX(snapshot_date) AS last_snapshot_date,
    MIN(registered_at_unix) AS registered_at_unix,
    DATEDIFF('day', MIN(snapshot_date), MAX(snapshot_date)) AS observation_span_days
FROM player_snapshot
GROUP BY country_code, player_id;
```

### 6. player_island_summary
Get the historical summary of a player's activity on an island. Since we track at the city level in `city_snapshot`, we group by `player_id` and `island_id`, and take the `MAX` of the player's total donations on that island.
```sql
SELECT 
    country_code,
    player_id,
    island_id,
    COUNT(DISTINCT snapshot_id) AS snapshots_observed_count,
    MIN(snapshot_date) AS first_snapshot_date,
    MAX(snapshot_date) AS last_snapshot_date,
    COUNT(DISTINCT city_id || '_' || snapshot_id) AS player_city_observation_count,
    MAX(donations_total) AS max_donations_total
FROM city_snapshot
GROUP BY country_code, player_id, island_id;
```

### 7. island_summary
Get the cross-snapshot historical summary per island.
```sql
SELECT 
    country_code,
    island_id,
    COUNT(DISTINCT snapshot_id) AS snapshots_observed_count,
    MIN(snapshot_date) AS first_snapshot_date,
    MAX(snapshot_date) AS last_snapshot_date
FROM island_snapshot
GROUP BY country_code, island_id;
```
