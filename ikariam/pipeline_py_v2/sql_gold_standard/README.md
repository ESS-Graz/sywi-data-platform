# SQL gold-standard outputs

This directory holds the five CSVs produced by running the original
`Alle_Queries_DE_hintereinander.sql` against MariaDB (the 36 DE snapshot DBs).
They are the **authoritative ground truth** for Python pipeline correctness.

## Producing the CSVs

1. **Ensure MariaDB is running** with the 36 DE snapshot DBs loaded
   (see the project-root README).

2. **Seed the master DB** with one snapshot's raw tables.
   `de_1311_14` is the canonical choice — it matches the existing
   `0_Originals_for_Checks/ZJ36_de_1311_14_*.csv` reference files:
   ```bash
   docker exec ikariam-mysql mysql -uroot -proot -e "
     DROP DATABASE IF EXISTS ikariam_sql_gold;
     CREATE DATABASE ikariam_sql_gold;
     USE ikariam_sql_gold;
     CREATE TABLE avatar   AS SELECT * FROM de_1311_14.avatar;
     CREATE TABLE city     AS SELECT * FROM de_1311_14.city;
     CREATE TABLE donation AS SELECT * FROM de_1311_14.donation;
     CREATE TABLE island   AS SELECT * FROM de_1311_14.island;
   "
   ```

3. **Run the SQL pipeline** (takes ~15 minutes due to 16K+ UPDATE statements):
   ```bash
   docker exec -i ikariam-mysql \
     mysql -uroot -proot ikariam_sql_gold \
     < internal/ikariam/data/Alle_Queries_DE_hintereinander.sql
   ```

4. **Export the tables** to this directory:
   ```bash
   uv run python scripts/export_sql_gold.py
   ```

## Files produced

- `A_DS.csv` — 136 cols, ~21,829 rows (avatar level)
- `AVI_DS.csv` — ~225 cols, ~41,087 rows (avatar × island)
- `I_DS.csv` — ~110 cols, ~5,352 rows (island level)
- `Teilnahme_AV.csv` — 3 cols, ~21,829 rows (participation)
- `Master_Avi.csv` — 4 cols, ~41,087 rows ((player, island) pairs)

Column naming: SQL uses `t_`, `a_`, `c_`, `d_`, `i_` prefixes to disambiguate
source tables after the big JOIN in `Q44_Create_ADS` / `Q45_Create_AVI` /
`Q46_Create_IDS`. Our Python port uses plain column names on a 31/32/51-column
subset (see `scripts/audit_vs_sql.py` for the prefix→plain mapping).

## Known characteristics of the SQL outputs

- **`a_Spieldauer` is in seconds**, not days. `Q3` sets it to seconds
  (`1415923200 − registration_time`); `Q18` divides by 86400 to convert to days
  — but the reference files predate Q18's division, so SQL outputs have seconds.
  Our audit script divides by 86400 before comparing.
- **Duration adjustment applied to `c_*_verbaut`**: the SQL's `Q15` multiplies
  each `Holz_verbaut`, `Kristall_verbaut` etc. by a band factor in-place.
  Python's unadjusted values will diverge here until we fix that.
- **Wonder split is flipped** vs. V1 R: matching tradegood gets 0, non-matching
  gets `1 − wonder_split_factor = 0.333` each.
- **Player filter is different**: SQL's `Q28` removes avatars with
  `registration_time < 1366797600`. V1 R used `Spieldauer >= 2 days`.
- **Upgrade cost tables are hand-entered**, not computed from a formula.

These are the divergences the Python port needs to close.
