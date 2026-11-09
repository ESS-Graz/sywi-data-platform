.read ikariam/sql/explore/00_setup.sql

-- Most built building types, excluding the buildings every city starts with.
-- (Takes ~30 s: this table has 35 million rows.)
SELECT building_type, count(*) AS builds,
       round(avg(building_level), 1) AS avg_level, max(building_level) AS max_level,
       round(sum(paid_cost_wood) / 1e9, 2) AS wood_bn,
       round(sum(paid_cost_marble) / 1e9, 2) AS marble_bn
FROM construction
WHERE NOT is_opening_stock
GROUP BY 1
ORDER BY builds DESC
LIMIT 12;

-- Resources spent on construction per month (billions).
-- Caution: Aug 2014 looks inflated. Builds are dated by the snapshot that first saw them,
-- so a long gap between snapshots probably piles several weeks of builds onto one date
-- (not verified).
SELECT date_trunc('month', built_by_snapshot_date)::DATE AS mon, count(*) AS builds,
       round(sum(paid_cost_wood) / 1e9, 2) AS wood,
       round(sum(paid_cost_marble) / 1e9, 2) AS marble,
       round(sum(paid_cost_crystal) / 1e9, 2) AS crystal,
       round(sum(paid_cost_sulfur) / 1e9, 2) AS sulfur,
       round(sum(paid_cost_wine) / 1e9, 2) AS wine
FROM construction
WHERE NOT is_opening_stock
GROUP BY 1
ORDER BY 1;
