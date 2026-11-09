.read ikariam/sql/explore/00_setup.sql

-- Which servers exist, and how many snapshot days do we have for each?
SELECT country_code, server,
       min(snapshot_date) AS first_day, max(snapshot_date) AS last_day,
       count(DISTINCT snapshot_date) AS n_days, count(DISTINCT player_id) AS players
FROM player_snapshot
GROUP BY ALL
ORDER BY players DESC;
