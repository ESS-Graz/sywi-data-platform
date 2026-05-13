# Are `latest` And `summary` Tables Necessary?

Short answer: **not strictly**. They are fully derivable from the three snapshot tables:

- `player_snapshot`
- `player_island_snapshot`
- `island_snapshot`

I checked the materialized tables against DuckDB-derived versions:

| table | derived rows | materialized rows | mismatches |
|---|---:|---:|---:|
| `player_latest` | 144,847 | 144,847 | 0 |
| `player_island_latest` | 257,383 | 257,383 | 0 |
| `island_latest` | 26,755 | 26,755 | 0 |
| `player_summary` | 144,847 | 144,847 | 0 |
| `player_island_summary` | 257,383 | 257,383 | 0 |
| `island_summary` | 26,755 | 26,755 | 0 |

The six derived tables take about **162 MB**:

| table | size |
|---|---:|
| `player_latest` | 43 MB |
| `player_island_latest` | 64 MB |
| `island_latest` | 11 MB |
| `player_summary` | 12 MB |
| `player_island_summary` | 30 MB |
| `island_summary` | 1.8 MB |

The three base snapshot tables take about **1.0 GB**, so the derived tables add roughly **16%** storage overhead.

## Derive `player_latest`

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

SELECT *
FROM ikariam.main.player_snapshot
QUALIFY row_number() OVER (
  PARTITION BY country_code, player_id
  ORDER BY snapshot_date DESC, snapshot_id DESC
) = 1;
```

## Derive `island_latest`

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

SELECT *
FROM ikariam.main.island_snapshot
QUALIFY row_number() OVER (
  PARTITION BY country_code, island_id
  ORDER BY snapshot_date DESC, snapshot_id DESC
) = 1;
```

## Derive `player_island_latest`

This one has a special rule: the player-island measurement comes from the player's last observed row on that island, but island metadata comes from the island's own latest snapshot.

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

WITH player_island_last AS (
  SELECT
    country_code,
    player_id,
    island_id,
    snapshot_id,
    snapshot_date,
    player_city_count_on_island,
    population_total,
    wood_in_buildings,
    resources_in_buildings_total,
    building_resource_score,
    resources_stored_total,
    resources_in_buildings_and_storage_total,
    building_levels_total,
    wonder_donations_total,
    sawmill_donations_total,
    luxury_mine_donations_total,
    donations_total
  FROM ikariam.main.player_island_snapshot
  QUALIFY row_number() OVER (
    PARTITION BY country_code, player_id, island_id
    ORDER BY snapshot_date DESC, snapshot_id DESC
  ) = 1
),
island_last AS (
  SELECT
    country_code,
    island_id,
    wonder_type_id,
    luxury_resource_type,
    luxury_mine_level,
    sawmill_level,
    raw_city_count AS island_city_count
  FROM ikariam.main.island_snapshot
  QUALIFY row_number() OVER (
    PARTITION BY country_code, island_id
    ORDER BY snapshot_date DESC, snapshot_id DESC
  ) = 1
)
SELECT
  p.*,
  i.wonder_type_id,
  i.luxury_resource_type,
  i.luxury_mine_level,
  i.sawmill_level,
  i.island_city_count
FROM player_island_last p
LEFT JOIN island_last i USING (country_code, island_id);
```

## Derive `player_summary`

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

SELECT
  country_code,
  player_id,
  count(DISTINCT snapshot_id) AS snapshots_observed_count,
  min(snapshot_date) AS first_snapshot_date,
  max(snapshot_date) AS last_snapshot_date,
  min(registered_at_unix) AS registered_at_unix,
  date_diff('day', min(snapshot_date), max(snapshot_date)) AS observation_span_days
FROM ikariam.main.player_snapshot
GROUP BY country_code, player_id;
```

## Derive `player_island_summary`

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

SELECT
  country_code,
  player_id,
  island_id,
  count(DISTINCT snapshot_id) AS snapshots_observed_count,
  min(snapshot_date) AS first_snapshot_date,
  max(snapshot_date) AS last_snapshot_date,
  sum(player_city_count_on_island) AS player_city_observation_count
FROM ikariam.main.player_island_snapshot
GROUP BY country_code, player_id, island_id;
```

## Derive `island_summary`

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

SELECT
  country_code,
  island_id,
  count(DISTINCT snapshot_id) AS snapshots_observed_count,
  min(snapshot_date) AS first_snapshot_date,
  max(snapshot_date) AS last_snapshot_date
FROM ikariam.main.island_snapshot
GROUP BY country_code, island_id;
```

## Recommendation

For a clean analytics lake, keep only the three snapshot tables as canonical data and expose the six derived tables as **DuckDB views/macros**.

Materializing the derived tables is still useful if:

- non-technical users want simple table names,
- dashboards repeatedly query `latest`,
- external tools cannot easily define views,
- you want one-file/table discoverability in LanceDB.

But analytically, they are redundant. The snapshot tables are the source of truth.
