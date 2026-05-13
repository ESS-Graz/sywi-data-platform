# DuckDB + Lance: Ikariam Dataset Showcase

These queries are ready to paste into the DuckDB CLI from this directory:

```bash
cd /home/david/coding/sywi_data_plattform/ikariam/output
duckdb
```

## 1. Load The Lance Dataset

```sql
INSTALL lance; -- run once if the extension is not installed yet
LOAD lance;

ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);
SHOW ALL TABLES;
```

## 2. Snapshot Coverage

Shows that the output preserves the full raw snapshot range per country.

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

SELECT
  country_code,
  count(DISTINCT snapshot_id) AS snapshots,
  min(snapshot_date) AS first_snapshot,
  max(snapshot_date) AS last_snapshot,
  count(*) AS player_snapshot_rows,
  count(DISTINCT player_id) AS distinct_players
FROM ikariam.main.player_snapshot
GROUP BY country_code
ORDER BY country_code;
```

## 3. Table Sizes

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

SELECT 'player_snapshot' AS table_name, count(*) AS rows FROM ikariam.main.player_snapshot
UNION ALL
SELECT 'player_island_snapshot', count(*) FROM ikariam.main.player_island_snapshot
UNION ALL
SELECT 'island_snapshot', count(*) FROM ikariam.main.island_snapshot
UNION ALL
SELECT 'player_latest', count(*) FROM ikariam.main.player_latest
UNION ALL
SELECT 'player_island_latest', count(*) FROM ikariam.main.player_island_latest
UNION ALL
SELECT 'island_latest', count(*) FROM ikariam.main.island_latest
ORDER BY rows DESC;
```

## 4. Final Snapshot Server Comparison

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

SELECT
  country_code,
  count(*) AS active_players,
  sum(city_count) AS cities,
  round(sum(population_total), 0) AS population,
  round(sum(resources_in_buildings_total), 0) AS resources_in_buildings,
  round(sum(donations_total), 0) AS donations_total,
  round(sum(donations_total) / count(*), 0) AS donations_per_player,
  round(sum(donations_total) / sum(city_count), 0) AS donations_per_city
FROM ikariam.main.player_snapshot
WHERE snapshot_date = DATE '2014-11-13'
GROUP BY country_code
ORDER BY donations_per_player DESC;
```

## 5. Donation Mix By Country

Shows whether countries invested more into sawmills, luxury mines, or wonders.

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

WITH final_players AS (
  SELECT *
  FROM ikariam.main.player_snapshot
  WHERE snapshot_date = DATE '2014-11-13'
)
SELECT
  country_code,
  round(sum(donations_total), 0) AS donations_total,
  round(100.0 * sum(sawmill_donations_total) / sum(donations_total), 1) AS sawmill_pct,
  round(100.0 * sum(luxury_mine_donations_total) / sum(donations_total), 1) AS luxury_mine_pct,
  round(100.0 * sum(wonder_donations_total) / sum(donations_total), 1) AS wonder_pct
FROM final_players
GROUP BY country_code
ORDER BY donations_total DESC;
```

## 6. Donation Becomes Normal For Mature Players

This shows the strong threshold around 4+ cities.

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

SELECT
  CASE
    WHEN city_count = 1 THEN '1 city'
    WHEN city_count BETWEEN 2 AND 3 THEN '2-3 cities'
    WHEN city_count BETWEEN 4 AND 6 THEN '4-6 cities'
    WHEN city_count BETWEEN 7 AND 9 THEN '7-9 cities'
    ELSE '10+ cities'
  END AS player_size,
  count(*) AS players,
  sum(CASE WHEN donations_total > 0 THEN 1 ELSE 0 END) AS donors,
  round(100.0 * sum(CASE WHEN donations_total > 0 THEN 1 ELSE 0 END) / count(*), 1) AS donor_pct,
  round(quantile_cont(donations_total, 0.50), 0) AS median_donations,
  round(quantile_cont(donations_total, 0.90), 0) AS p90_donations
FROM ikariam.main.player_snapshot
WHERE snapshot_date = DATE '2014-11-13'
GROUP BY player_size
ORDER BY min(city_count);
```

## 7. Donation Concentration With Window Functions

How much of all donations came from the top 1%, 5%, and 10% of players?

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

WITH final_players AS (
  SELECT country_code, player_id, donations_total
  FROM ikariam.main.player_snapshot
  WHERE snapshot_date = DATE '2014-11-13'
),
ranked AS (
  SELECT
    *,
    row_number() OVER (
      PARTITION BY country_code
      ORDER BY donations_total DESC
    ) AS donation_rank,
    count(*) OVER (PARTITION BY country_code) AS player_count,
    sum(donations_total) OVER (PARTITION BY country_code) AS country_donations
  FROM final_players
)
SELECT
  country_code,
  round(max(country_donations), 0) AS donations_total,
  round(
    100.0 * sum(CASE WHEN donation_rank <= ceil(player_count * 0.01) THEN donations_total ELSE 0 END)
    / max(country_donations),
    1
  ) AS top_1_pct_share,
  round(
    100.0 * sum(CASE WHEN donation_rank <= ceil(player_count * 0.05) THEN donations_total ELSE 0 END)
    / max(country_donations),
    1
  ) AS top_5_pct_share,
  round(
    100.0 * sum(CASE WHEN donation_rank <= ceil(player_count * 0.10) THEN donations_total ELSE 0 END)
    / max(country_donations),
    1
  ) AS top_10_pct_share
FROM ranked
GROUP BY country_code
ORDER BY top_10_pct_share DESC;
```

## 8. Which Island Resource Types Attract Donations?

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

SELECT
  CASE luxury_resource_type
    WHEN 1 THEN 'wine'
    WHEN 2 THEN 'marble'
    WHEN 3 THEN 'crystal'
    WHEN 4 THEN 'sulfur'
    ELSE luxury_resource_type::VARCHAR
  END AS luxury_resource,
  count(*) AS islands,
  sum(city_count) AS cities,
  round(sum(donations_total), 0) AS donations_total,
  round(avg(CASE WHEN city_count > 0 THEN donations_total END), 0) AS avg_donations_occupied_island,
  round(avg(CASE WHEN city_count > 0 THEN donating_player_share_pct END), 1) AS avg_donor_share_pct
FROM ikariam.main.island_latest
GROUP BY luxury_resource_type
ORDER BY donations_total DESC;
```

## 9. Top Islands By Final Donation Volume

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

SELECT
  country_code,
  island_id,
  player_count,
  city_count,
  round(population_total, 0) AS population,
  round(donations_total, 0) AS donations_total,
  sawmill_level,
  luxury_mine_level,
  wonder_level
FROM ikariam.main.island_latest
ORDER BY donations_total DESC
LIMIT 20;
```

## 10. Cumulative Donation Growth Over Time

Useful for exporting to a charting tool.

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

SELECT
  country_code,
  snapshot_date,
  round(sum(donations_total), 0) AS donations_total,
  round(sum(sawmill_donations_total), 0) AS sawmill_donations,
  round(sum(luxury_mine_donations_total), 0) AS luxury_mine_donations,
  round(sum(wonder_donations_total), 0) AS wonder_donations
FROM ikariam.main.island_snapshot
GROUP BY country_code, snapshot_date
ORDER BY snapshot_date, country_code;
```

## 11. Export One Query To CSV

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

COPY (
  SELECT
    country_code,
    snapshot_date,
    round(sum(donations_total), 0) AS donations_total
  FROM ikariam.main.island_snapshot
  GROUP BY country_code, snapshot_date
  ORDER BY snapshot_date, country_code
) TO 'donation_growth_by_country.csv' (HEADER, DELIMITER ',');
```
