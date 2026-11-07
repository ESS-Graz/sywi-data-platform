-- Shared setup, read by every analysis file: loads the Lance extension and
-- exposes the ikariam LanceDB tables on S3 as views. Nothing is downloaded here.
INSTALL lance;
LOAD lance;

-- S3 access. The credentials are read from the environment (see run.sh), never stored here.
-- The Lance reader only honors a TYPE lance secret, not DuckDB's regular TYPE s3 secret.
CREATE SECRET ikariam_s3 (
    TYPE lance, PROVIDER config,
    aws_access_key_id getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key getenv('AWS_SECRET_ACCESS_KEY'),
    aws_region 'us-east-1',
    aws_endpoint 'https://data.systems-sciences.uni-graz.at',
    aws_virtual_hosted_style_request 'false',
    SCOPE 's3://ikariam/'
);

CREATE VIEW player_snapshot AS SELECT * FROM 's3://ikariam/ikariam.lancedb/player_snapshot.lance';
CREATE VIEW city_snapshot AS SELECT * FROM 's3://ikariam/ikariam.lancedb/city_snapshot.lance';
CREATE VIEW donations AS SELECT * FROM 's3://ikariam/ikariam.lancedb/donation_analytics_player_island_snapshot.lance';
CREATE VIEW construction AS SELECT * FROM 's3://ikariam/ikariam.lancedb/building_construction_event.lance';

-- Every server (country_code + server) has its own last snapshot day.
-- Most servers only have a single snapshot, so "latest" is often their only day.
CREATE VIEW latest_player AS
SELECT p.*
FROM player_snapshot p
JOIN (SELECT country_code, server, max(snapshot_date) AS last_day
      FROM player_snapshot GROUP BY ALL) l
  ON p.country_code = l.country_code AND p.server = l.server AND p.snapshot_date = l.last_day;

CREATE VIEW latest_donations AS
SELECT d.*
FROM donations d
JOIN (SELECT country_code, server, max(snapshot_date) AS last_day
      FROM donations GROUP BY ALL) l
  ON d.country_code = l.country_code AND d.server = l.server AND d.snapshot_date = l.last_day;
