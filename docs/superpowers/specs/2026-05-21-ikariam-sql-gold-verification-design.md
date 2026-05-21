# Ikariam SQL Gold Verification Design

## Context

The current Ikariam Dagster pipeline writes existing, fresh output to
`ikariam/output/ikariam.lancedb`. The public LanceDB contract is intentionally
canonical and compact:

- `player_snapshot`
- `city_snapshot`
- `island_snapshot`
- country-partitioned raw tables such as `raw_avatar_de`, `raw_city_de`,
  `raw_donation_de`, and `raw_island_de`

The SQL gold standard uses the legacy final SQL outputs in
`ikariam/data/gold_standard`:

- `Teilnahme_AV.csv`
- `Master_Avi.csv`
- `A_DS.csv`
- `AVI_DS.csv`
- `I_DS.csv`

Those datasets do not have the same shape as the current LanceDB public
tables. Verification must therefore reconstruct SQL-shaped views from the
existing LanceDB data before comparing values.

## Goals

1. Add a clean, auditable verifier that compares existing LanceDB output to the
   gold CSVs.
2. Add a SQL-to-Dagster audit artifact that maps the legacy SQL sections to the
   current pipeline modules and marks gaps explicitly.
3. Avoid rerunning Dagster as part of this verifier. The default target is the
   existing fresh LanceDB data.

## Non-Goals

- Do not regenerate the SQL gold CSVs.
- Do not change the pipeline transformations as part of the first verifier.
- Do not hide unmapped SQL columns. Unmapped fields are reported as coverage
  gaps, not silently ignored.

## Proposed Files

- `ikariam/scripts/verify_lancedb_against_gold.py`
- `ikariam/docs/sql_to_dagster_audit.md`
- `ikariam/docs/lancedb_vs_sql_gold.md`
- `ikariam/output/verification/lancedb_vs_sql_gold/`

## CLI Behavior

Default command:

```bash
uv run python scripts/verify_lancedb_against_gold.py
```

The script runs from the `ikariam` project directory and defaults to:

- LanceDB path: `output/ikariam.lancedb`
- gold CSV path: `data/gold_standard`
- markdown report: `docs/lancedb_vs_sql_gold.md`
- detail output directory: `output/verification/lancedb_vs_sql_gold`

Optional arguments should allow overriding those paths.

## Comparison Architecture

The verifier has four layers:

1. Load inputs:
   Read LanceDB tables and gold CSVs with stable schemas where possible.

2. Build SQL-shaped views:
   Derive `Teilnahme_AV`, `Master_Avi`, `A_DS`, `AVI_DS`, and `I_DS`-shaped
   frames from the existing LanceDB tables. These builders are explicit and
   named after the legacy output they reconstruct.

3. Compare mapped fields:
   Each output defines:
   - key columns
   - SQL column to Lance-derived column or expression mapping
   - numeric tolerance
   - null handling rules

4. Report results:
   Write a markdown summary and machine-readable mismatch samples.

## Output-Specific Grain

- `Teilnahme_AV`: one row per player.
- `Master_Avi`: one row per player-island pair.
- `A_DS`: one row per player.
- `AVI_DS`: one row per player-island pair.
- `I_DS`: one row per island.

The first implementation should compare row counts, key coverage, and mapped
columns. It should also report every SQL column that has no mapping yet.

## Comparison Rules

- Join on declared keys, not row order.
- Report SQL-only keys and Lance-only keys separately.
- Compare numeric values with a default absolute tolerance of `1e-6`.
- Compare strings and identifiers exactly after consistent null normalization.
- Write mismatch samples with: output name, key, column, SQL value, Lance value,
  absolute difference, and comparison status.
- Exit nonzero when mapped comparisons fail, key coverage fails, or required
  inputs are missing.
- Do not fail only because a SQL column is currently unmapped; instead mark
  coverage as incomplete in the report.

## SQL-to-Dagster Audit

Add `ikariam/docs/sql_to_dagster_audit.md` as a living audit table with:

- SQL section/query number
- legacy table or columns produced
- current Dagster module/function
- status: `matched`, `intentional_change`, `missing`, or `needs_investigation`
- evidence or notes

The first audit pass should cover the major legacy sections:

- Q3 account age / `Spieldauer`
- Q4-Q7 `Teilnahme_AV` and `Master_Avi`
- city building-cost and resource calculations
- donation filtering, zero rows, and wonder/luxury split
- avatar, avatar-island, and island aggregations
- Q44-Q46 final outputs `A_DS`, `AVI_DS`, and `I_DS`

## Testing

Add focused tests for the verifier where practical:

- comparison helper behavior for exact, numeric tolerance, null mismatch, and
  key mismatch cases
- SQL-shaped reconstruction on tiny synthetic DataFrames
- CLI/report smoke test with temporary CSV and Lance-like inputs if that can be
  kept lightweight

Do not rely on the tests alone as proof of gold parity. The actual verifier run
against `output/ikariam.lancedb` and `data/gold_standard` is the primary
evidence.

## Acceptance Criteria

- The verifier can be run against the existing LanceDB output without
  materializing Dagster.
- It writes a readable markdown report and detailed mismatch artifacts.
- The report separates passed mapped comparisons, failed mapped comparisons,
  key coverage issues, and unmapped SQL columns.
- The SQL audit document identifies what is already matched, what is missing,
  and what needs investigation.
- The implementation leaves unrelated existing LanceDB worktree changes alone.
