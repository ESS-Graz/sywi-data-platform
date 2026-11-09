-- Shared setup, read by every analysis file: short names for the ikariam tables.
-- `just db` has already attached the remote database as `ikariam` (LANCE_REMOTE_URI in
-- .env.local must contain ikariam=s3://ikariam/ikariam.lancedb). Nothing is downloaded here.
-- Temporary views live only in this session, so reading this file twice is fine.
CREATE OR REPLACE TEMP VIEW player_snapshot AS FROM ikariam.player_snapshot;
CREATE OR REPLACE TEMP VIEW city_snapshot AS FROM ikariam.city_snapshot;
CREATE OR REPLACE TEMP VIEW island_snapshot AS FROM ikariam.island_snapshot;
CREATE OR REPLACE TEMP VIEW donations AS FROM ikariam.donation_analytics_player_island_snapshot;
CREATE OR REPLACE TEMP VIEW construction AS FROM ikariam.building_construction_event;

-- Every server (country_code + server) has its own last snapshot day.
-- Most servers only have a single snapshot, so "latest" is often their only day.
CREATE OR REPLACE TEMP VIEW latest_player AS
SELECT p.*
FROM player_snapshot p
JOIN (SELECT country_code, server, max(snapshot_date) AS last_day
      FROM player_snapshot GROUP BY ALL) l
  ON p.country_code = l.country_code AND p.server = l.server AND p.snapshot_date = l.last_day;

CREATE OR REPLACE TEMP VIEW latest_donations AS
SELECT d.*
FROM donations d
JOIN (SELECT country_code, server, max(snapshot_date) AS last_day
      FROM donations GROUP BY ALL) l
  ON d.country_code = l.country_code AND d.server = l.server AND d.snapshot_date = l.last_day;
