# Do Players Who Never Donate Become Less Successful?

Short answer: **yes, strongly in the observed data**, but this is still an observational result, not proof of causality.

The cleanest test is to compare players after they have already reached **4 cities**. That avoids the trivial explanation that many non-donors are just one-city beginners who churn immediately.

## Key Result

Among players who reached at least 4 cities:

| donation timing | players | retained to final | city growth after 4 cities | population growth after 4 cities | building-resource growth after 4 cities | avg last building resources |
|---|---:|---:|---:|---:|---:|---:|
| already donated by 4 cities | 17,503 | 15.8% | 1.22 | 2,940 | 9,586,204 | 9,866,959 |
| started donating after 4 cities | 715 | 27.6% | 1.37 | 3,375 | 8,272,544 | 8,571,650 |
| never donated | 579 | 16.2% | 0.16 | 167 | 489,463 | 810,326 |

The baseline at the moment of reaching 4 cities was not wildly different:

| donation timing | players | avg cities at milestone | avg population at milestone | avg building resources at milestone | avg age days at milestone |
|---|---:|---:|---:|---:|---:|
| never donated | 579 | 4.04 | 1,764 | 320,863 | 352.6 |
| started donating after 4 cities | 715 | 4.04 | 2,031 | 299,106 | 419.0 |
| already donated by 4 cities | 17,503 | 4.02 | 1,980 | 280,755 | 514.7 |

Interpretation: players who reach 4 cities but never start donating look like they **stall**. Their later building-resource growth is tiny compared with players who donate.

## DuckDB Query

Run from `/home/david/coding/sywi_data_plattform/ikariam/output`:

```sql
LOAD lance;
ATTACH 'ikariam.lancedb' AS ikariam (TYPE lance);

WITH reached4 AS (
  SELECT *
  FROM (
    SELECT
      *,
      row_number() OVER (
        PARTITION BY country_code, player_id
        ORDER BY snapshot_date
      ) AS rn
    FROM ikariam.main.player_snapshot
    WHERE city_count >= 4
  )
  WHERE rn = 1
),
player_flags AS (
  SELECT
    country_code,
    player_id,
    max(CASE WHEN donations_total > 0 THEN 1 ELSE 0 END) AS ever_donated
  FROM ikariam.main.player_snapshot
  GROUP BY country_code, player_id
),
last_rows AS (
  SELECT *
  FROM (
    SELECT
      *,
      row_number() OVER (
        PARTITION BY country_code, player_id
        ORDER BY snapshot_date DESC
      ) AS rn
    FROM ikariam.main.player_snapshot
  )
  WHERE rn = 1
),
cohort AS (
  SELECT
    r.country_code,
    r.player_id,
    CASE
      WHEN f.ever_donated = 0 THEN 'never_donated'
      WHEN r.donations_total > 0 THEN 'already_donated_by_4_cities'
      ELSE 'started_donating_after_4_cities'
    END AS donation_timing,
    r.snapshot_date AS reached4_date,
    l.snapshot_date AS last_seen,
    r.city_count::DOUBLE AS cities_at_4,
    l.city_count::DOUBLE AS last_cities,
    r.population_total AS pop_at_4,
    l.population_total AS last_population,
    r.resources_in_buildings_total AS buildings_at_4,
    l.resources_in_buildings_total AS last_buildings
  FROM reached4 r
  JOIN player_flags f USING (country_code, player_id)
  JOIN last_rows l USING (country_code, player_id)
)
SELECT
  donation_timing,
  count(*) AS players,
  round(
    100.0 * sum(CASE WHEN last_seen = DATE '2014-11-13' THEN 1 ELSE 0 END) / count(*),
    1
  ) AS retained_final_pct,
  round(avg(last_cities - cities_at_4), 2) AS city_growth_after_4,
  round(avg(last_population - pop_at_4), 0) AS population_growth_after_4,
  round(avg(last_buildings - buildings_at_4), 0) AS building_growth_after_4,
  round(avg(last_population), 0) AS avg_last_population,
  round(avg(last_buildings), 0) AS avg_last_buildings
FROM cohort
GROUP BY donation_timing
ORDER BY avg_last_buildings DESC;
```

## Caveat

This does **not** prove that failing to donate causes failure. Donation is also a proxy for engagement, social integration, and island cooperation. A cautious conclusion is:

> Players who never start donating, even after reaching 4 cities, are much less likely to continue developing. Donation behavior is a strong early warning signal for stagnation.
