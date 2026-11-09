# Ikariam: from raw dumps to parquet

Status 2026-11-05. This describes how the original database dumps become the
`parquet_raw/` files that the pipeline reads from `data/raw/ikariam/`. Paths are those of the
archive `ikariam-raw-archive-2026-11-05` (`dumps/`, `scripts/`, `docs/`, `reference/`, `checksums/`).
The evidence for every snapshot, one row each, is in the workbook `snapshots_verification.xlsx`
(sheets `Snapshots`, `Servers`, `Vergleichsserver`, `Issues`, `Sources`).

## 1. Result

| | |
|---|---|
| Input | 209 unique phpMyAdmin dumps (215 files, 1.31 GB), one per server and snapshot, 2013-04 to 2014-11 |
| Output | `parquet_raw/country=<cc>/server=<n>/snapshot_date=<YYYY-MM-DD>/{avatar,city,donation,island}_0.parquet` |
| Size | 836 files, 299 MB; avatar 790,268 rows, city 2,334,562, donation 3,364,161, island 1,118,359 |
| Servers | 20: five series servers (DE 23, EN 22, FR 21, GR 19, TR 25), AE 18, BR 27, AR 11, RU 17, US 19, and ten "Vergleichsserver" worlds (DE 24/25, EN 23/24, FR 22/23, GR 20/21, TR 26/27) |

```
original dumps (*.sql)  --raw_load_dumps.sh-->  MySQL 5.7, one database per snapshot
  dumps/                    (snapshot_name.sh       <cc>_<server>_<YYMMDD>
                             names each database)         |
                                                    raw_views.sql  (stack view per table)
                                                          |
parquet_raw/  <--raw_export.sql (DuckDB COPY + checks)-----+
     |
     +-- copied to  sywi_data_plattform/data/raw/ikariam/   --> ikariam pipeline (Dagster)
```

## 2. Input

- Location: `dumps/` in five folders (the original ones): `0_Originaldaten` (85 files, 2013-04-25 to
  08-15, DE EN FR GR TR), `0_Originaldaten_2` (65, 2013-08-29 to 2014-02-13, plus AE and BR),
  `0_Originaldaten_3` (44, 2014-03-13 to 11-13), `0_Originaldaten_Country_Comparison_10/140814`
  (10, the 2014-08-14 dumps of all ten countries; AE/AR/BR/RU/US exist only here) and
  `0_Originaldaten_Vergleichsserver_5` (11).
- File name `YYMMDD_CC_server.sql`. Six names exist in two folders (five `140814_*`, `131213_DE_25`),
  byte-identical, loaded once. The eight `backup10*.sql` files in the Country_Comparison folder are
  derived tables, not raw, and are skipped.
- Each dump holds `avatar`, `city`, `donation`, `island` (`logGovernmentChanges` is empty everywhere
  and not exported). Header lines give the phpMyAdmin export time (`Erstellungszeit`) and the source
  database (`Datenbank: backup_ikariam_<cc>_<n>`). 52 older dumps start with `USE <db>;`; all
  start with a UTF-8 BOM. `131219_FR_21.sql` has no header and ends with a failing restore statement.

## 3. Which server and which date (rules in `snapshot_name.sh`)

1. **Country and server** come from the dump header; the file name is the fallback. This corrects
   `130815_EN_23` (really EN 22) and `130509_FR_23` (really FR 21). `WARN` is printed on any disagreement.
2. **Snapshot date** = the date in the file name. The header export time is *not* the snapshot
   date: it can be days later (17 regular dumps are 4 to 49 days later); the last registration in
   each dump lies on the file-name date or the day before (never more than 33 hours before the end
   of that day, 0 registrations after it).
3. **Exception, the ten Vergleichsserver dumps** (`130830_*`, `131213_*`): the file-name date is the
   *start date of the world* (DE 25 even started 2013-12-23). The data were dumped on
   **2014-01-16** (all headers; latest registration that morning). They get `140116`. They are ten
   different worlds seen on the same day, not a time series.

Not corrected, only to be aware of: DE has 36 snapshots, the others 37 (DE lacks 2014-05-15, and has
2013-07-02 where the others have 07-04); only 35 dates have all five countries (workbook sheet `Issues`, I05).

## 4. Procedure

Needs Docker, a `mysql` client and the `duckdb` CLI, run from `scripts/` (the scripts
read `../dumps` and write `../parquet_raw`).

```bash
./raw_load_dumps.sh        # fresh MySQL 5.7 container ikariam-raw-mysql on :3307; loads 209 dumps (4 in parallel); runs raw_views.sql
rm -rf ../parquet_raw         # removes the previous export; COPY ... OVERWRITE_OR_IGNORE would keep stale partitions
duckdb < raw_export.sql    # MySQL -> hive-partitioned zstd parquet, then the checks (about 2 min)
```

- `raw_load_dumps.sh` drops the old container and volume, starts `mysql:5.7` (utf8, relaxed
  durability for the bulk load), and loads each dump into its own database named by
  `snapshot_name.sh`. BOM and `USE` line are stripped; each dump runs in one transaction with
  `mysql --force`, so the failing trailing statement cannot roll back the last table.
- `raw_views.sql` creates `ikariam_all.<table>` views (`UNION ALL` of all snapshot databases,
  `snapshot` column = database name).
- `raw_export.sql` attaches MySQL read-only, writes each table with
  `PARTITION_BY (country, server, snapshot_date)` (derived from the database name), keeps
  `tinyint(1)` as a number, stops at the first error (`.bail on`).

## 5. Output

- Country, server and date exist **only in the folder path**; the files hold exactly the MySQL columns
  with MySQL types (`registration_time` UINTEGER, `formOfGovernment` TINYINT, ...). Read with
  `read_parquet('parquet_raw/**/avatar_*.parquet', hive_partitioning = true)`.
- Tables: avatar (6 columns), city (49), donation (4), island (11). Meaning of the columns and codes:
  `Legende Datensatz.docx` and `Originalvariablen_Ikariam_Tabellen.docx` (archive: `reference/collector_notes/`, read only).
- `registration_time` is a UTC epoch; `Erstellungszeit` is the exporting server's local time (zone not
  stated); `snapshot_date` is a calendar date (zone not documented, the pipeline compares the UTC date).

## 6. Checks

At the end of `raw_export.sql` (UTC dates): **abort** if any player registered after the snapshot's
date; list snapshots whose last registration is more than 3 days before it (none expected).
Tested: both pass on the current tree; on the old dates the first aborts with exit code 1 and names
the offending snapshots. The pipeline repeats the first check in `prepare_validated_avatars`
(runs on all rows before any filter); it passes for all 790,268 players in 209 snapshots. A re-run
should reproduce row counts per table and, with `EXCEPT ALL` in both directions, all values.
`parquet_raw_checksums.sha256` in the archive proves only the integrity of that copy (parquet
files are not byte-reproducible).

## 7. What the raw data still contains (cleaning is the pipeline's job)

- **Pre-launch admin accounts**: 4 or 5 distinct accounts per server registered before the world's
  start (earliest 2008-07-18). Per-server start times (confirmed by the first real registration,
  14 seconds to 26 minutes after the start) are in the workbook sheet `Servers`. The pipeline
  removes these accounts; see "Player Filter" in the [README](../README.md).
- `avatar.research_points` is always 0; `formOfGovernment` 8 and 9 never occur; `gender` is 0/1
  (undocumented). Building type `0` (or level 0) is an empty slot and type `31` is the Black Market
  (accepted in the pipeline's `docs/manual_review_handoff.md`).
- The next two world rounds (Vergleichsserver) were cut by the collector at 2013-10-15 and
  2013-12-31 for analyses; the dumps hold everyone up to 2014-01-16.
- `building_costs.csv` in `data/raw/ikariam/` is a separate input, not from the dumps.

## 8. Open points

| | |
|---|---|
| DE dump of 2014-05-15 | does not exist on any disk we have; the old drives (K:, D:, M:) or the operator might have it |
| AR start hour | 09:00 or 10:00 on 2013-05-02; affects one player |
| Analysis end date of the Vergleichsserver | 2013-10-15 / 2013-12-31 versus 2014-01-17 12:00 (notes disagree) |
| `Spieldauer` reference time | the 2020 script is unfinished; final definition unknown |
| Time zone of `snapshot_date` | not documented |
| Pipeline | reverse date check (last registration far before the date) and per-server start not yet implemented |

## 9. Provenance and archive layout

Dates and servers of every snapshot, with the evidence for each decision: workbook `snapshots_verification.xlsx`.
The collector's own notes (2013-2020, partly unverified, not used by any script) are in
`reference/collector_notes/`; `reference/README.md` lists what is known to be wrong in them.

```
dumps/        original .sql files (source)         scripts/    load, name, export (creates parquet_raw)
docs/         this file + the workbook             checksums/  sha256 of the 836 parquet files of 2026-11-04
reference/    collector's notes, read only         MANIFEST.sha256, README.md
```

Changes of 2026-11-04: ten Vergleichsserver folders renamed to 2014-01-16 in `parquet_raw/` and in
the pipeline's input copy; `snapshot_name.sh` added; loader and export script updated.
