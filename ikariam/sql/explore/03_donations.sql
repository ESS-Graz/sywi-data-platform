.read ikariam/sql/explore/00_setup.sql

-- How concentrated are donations? Share given by the top 1% / 10% of donors per server
WITH per_player AS (
    SELECT country_code, server, player_id, sum(donations_total) AS total
    FROM latest_donations
    GROUP BY ALL
    HAVING sum(donations_total) > 0
),
ranked AS (
    SELECT *, row_number() OVER (PARTITION BY country_code, server ORDER BY total DESC) AS rnk,
           count(*) OVER (PARTITION BY country_code, server) AS n
    FROM per_player
)
SELECT country_code, server, any_value(n) AS donors,
       round(100 * sum(total) FILTER (WHERE rnk <= n * 0.01) / sum(total), 1) AS top1_pct,
       round(100 * sum(total) FILTER (WHERE rnk <= n * 0.10) / sum(total), 1) AS top10_pct
FROM ranked
GROUP BY ALL
HAVING any_value(n) > 500
ORDER BY donors DESC;

-- Where do donations go? (billions, all servers, latest snapshot per server)
SELECT round(sum(wonder_donations_total) / 1e9, 2) AS wonder_bn,
       round(sum(luxury_mine_donations_total) / 1e9, 2) AS luxury_mine_bn,
       round(sum(sawmill_donations_total) / 1e9, 2) AS sawmill_bn
FROM latest_donations;
