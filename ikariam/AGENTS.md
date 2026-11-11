# Ikariam: Agent Instructions

Snapshots of the browser game Ikariam (2013–2014, 20 servers in 10 countries). The general workflow (DuckDB CLI via `just db -f`, remote first, Python only for plots) is in the root `AGENTS.md`. `README.md` in this folder describes the tables and columns in detail. Read the sections named below before analysing the matching topic.

## Access

- `LANCE_REMOTE_URI` in `.env.local` must contain `ikariam=s3://ikariam/ikariam.lancedb`. The tables are then `ikariam.<table>`.
- Start every SQL file with `.read ikariam/sql/explore/00_setup.sql`. It adds the short names `player_snapshot`, `city_snapshot`, `island_snapshot`, `donations`, `construction` and the views `latest_player`, `latest_donations`. In Python, run the views yourself: `conn.execute(open("ikariam/sql/explore/00_setup.sql").read())` works when the script runs from the repository root.
- `sql/explore/01_…05_*.sql` are worked examples (coverage, players, donations, construction, retention). Copy their style.
- Ignore the `raw_*` tables (unprocessed data per country). Analyse the primary tables: `player_snapshot`, `city_snapshot`, `island_snapshot`, `donation_analytics_player_island_snapshot`, `building_construction_event`, `building_demolition_event`.
- `building_construction_event` and `city_snapshot` are large. Filter by `country_code, server` early, or ask the user about a local copy (`just pull <table>`).

## Traps that give wrong numbers

- **IDs are unique only per server.** Always key by `country_code, server` plus `player_id`, `city_id` or `island_id`.
- **Snapshots differ per server.** Only DE 23, EN 22, FR 21, GR 19 and TR 25 have 36–37 snapshots; AE 18 and BR 27 have 6; the other 13 servers have one. Time series, retention and growth only make sense on servers with several snapshots, and "latest" is per server (`latest_player`).
- **Donation columns are running totals** (`*_donations_total`). Take the latest snapshot for a lifetime total; never sum them across snapshots. README: *Donation Totals*.
- **Island columns repeat on every city** of an island in `city_snapshot` (`wonder_level`, `sawmill_level`, …). Take `ANY_VALUE` per `country_code, server, island_id, snapshot_id`, never `SUM`. README: *Repeated Island Columns in city_snapshot*.
- **Donations are not in `city_snapshot`.** They are per player and island in `donation_analytics_player_island_snapshot`.
- **Building cost columns are estimates, not observed spending.** They are named `<which levels>_cost_<which discount>_<resource>`: `standing` or `ever_built` levels, priced `undiscounted`, at `today`'s discount or at the discount `at_build`. README: *Building Costs*.
- **`at_build` costs are only trustworthy on the five long-running servers.** Check `preexisting_share` (0 = reliable, 1 = guess, NULL = no buildings). To combine rows, weight it by `standing_cost_undiscounted_total`; never average the shares directly. README: *`preexisting_share`*.
- **Admin and test accounts are already removed** (players registered before their server's start). Do not filter them again. README: *Player Filter*.

## Further documentation

- Column descriptions: the data catalog at https://data.systems-sciences.uni-graz.at/catalog/ (needs a login, so ask the user if a column is unclear) or `DESCRIBE`.
- Raw data lineage and the per-server snapshot dates: `docs/raw_data_to_parquet.md`.
- `docs/` also holds audits of the building cost tables. Read them only for questions about costs or discounts.

## Pipeline work

Changing the pipeline (`src/ikariam/`, `tests/`) is a different task from analysis. The tables are rebuilt by the job `ikariam_full_pipeline`, which overwrites the whole database at `IKARIAM_LANCEDB_PATH`. Never run it against `s3://ikariam/…` unless the user asks you to. Run the tests with `cd ikariam && uv run pytest`.
