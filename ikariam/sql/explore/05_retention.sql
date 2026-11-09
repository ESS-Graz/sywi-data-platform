.read ikariam/sql/explore/00_setup.sql

-- Of the players present on a server's first snapshot day, how many are still there on the last?
-- Only meaningful for servers with several snapshot days (n_days > 1); a server with a
-- single snapshot trivially shows 100%, so those are filtered out.
WITH bounds AS (
    SELECT country_code, server, min(snapshot_date) AS first_day, max(snapshot_date) AS last_day
    FROM player_snapshot
    GROUP BY ALL
    HAVING count(DISTINCT snapshot_date) > 1
),
presence AS (
    SELECT p.country_code, p.server, p.player_id,
           bool_or(p.snapshot_date = b.first_day) AS at_start,
           bool_or(p.snapshot_date = b.last_day) AS at_end
    FROM player_snapshot p
    JOIN bounds b USING (country_code, server)
    GROUP BY ALL
)
SELECT country_code, server,
       count(*) FILTER (WHERE at_start) AS players_at_start,
       count(*) FILTER (WHERE at_start AND at_end) AS still_there,
       round(100.0 * count(*) FILTER (WHERE at_start AND at_end)
             / count(*) FILTER (WHERE at_start), 1) AS retention_pct
FROM presence
GROUP BY ALL
HAVING count(*) FILTER (WHERE at_start) > 100
ORDER BY players_at_start DESC;
