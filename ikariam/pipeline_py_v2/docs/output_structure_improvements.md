# Output structure — critique & improvement backlog

> Captured during the SQL-alignment planning round. **Deferred** until the Python pipeline is semantically correct against the SQL gold standard. Come back here after that's done.

## Context

The Python port currently produces five CSVs that mirror V1 R byte-for-byte:
`A_DS.csv` (21,822 rows), `AVI_DS.csv` (41,079 rows), `I_DS.csv` (5,351 rows),
`Teilnahme_AV.csv` (21,829 rows), `Master_Avi.csv` (41,086 rows).

Exploration confirmed **no external downstream consumers** — no paper, notebook, or analysis script anywhere under `~/coding/phd/` reads these files. They exist only for the pipeline's own round-trip validation. Byte-compat with V1 R is a self-imposed constraint.

`PIPELINE_SPECIFICATION_V2.md` already proposes the biggest missing capability: **temporal panel data** across all 36 snapshots rather than a single latest-snapshot projection.

## Diagnosis

### What works
- **German domain terminology** is correct: `Spieldauer`, `Buerger_Ges`, `Baumeister_Highscore`, `Geblev`, `Rathauslev`, `Don_*_Ges` are Ikariam game terms used in research writeups. Keep them.
- **Three grains are sensible**: player, player×island, island. Natural analytical units.
- **Filter semantics are defensible**: `Spieldauer >= 2 days` drops noise.

### What's broken or wasteful

1. **Panel data is thrown away.** We compute 36 snapshots of state in intermediate frames (`avatar_enriched`, `city_player_island`, `island_enriched`, `donation_enriched`), then collapse to *one* snapshot per entity. The most interesting research questions — how does donation behavior evolve with tenure? do new vs. veteran players build differently? — need the weekly trajectory.

2. **`Teilnahme_AV` and `Master_Avi` are pure redundancy.** Every column in `Teilnahme_AV` is also in `A_DS` (renamed `avatar_id`→`id`). Every column in `Master_Avi` is also in `AVI_DS`. Legacy from V1 R.

3. **CSV is a poor primary format.** No dtypes (polars has to re-infer on read and we saw it misclassify columns). No null / empty distinction. 10–50× larger than parquet. Every consumer re-parses.

4. **Inconsistent column naming.** Mix of `owner_id` / `first_seen` / `snapshots_present` (snake_case English) with `Buerger_Ges` / `Baumeister_Highscore` / `Anzahl_Teilnahme` (PascalCase / German). Same concept differently spelled: `Anzahl_vorhanden` vs. `Cities_Vorhanden`.

5. **No data dictionary.** `Don_Saegewerk_Ges`, `Geblev`, `QKWS_lagernd` are opaque without a glossary.

6. **No run manifest.** Nothing records *when* the pipeline ran, *against what input*, *with what configuration*. Reproducibility gap.

7. **Preserved V1 R bugs are silently embedded.** `duration_adjustment` is always 0.86, wonder split diverges from SQL, upgrade cost tables use a formula. Future readers of the CSVs have no way to know. (Fixed in SQL-alignment phase.)

8. **No country column on A_DS or AVI_DS.** I_DS has it. Inconsistent — will bite when the pipeline expands to EN/FR/GR/TR.

## Recommended changes (prioritized)

### Tier 1 — high value, low risk

**1a. Add panel outputs** (the biggest unlock)

New files alongside the existing latest-snapshot outputs:

| New file | Grain | Source |
|---|---|---|
| `panel_avatar.{csv,parquet}` | (avatar_id, snapshot_id) | `avatar_enriched` + `city3_av` + `donation3_av` joins per snapshot |
| `panel_avatar_island.{csv,parquet}` | (avatar_id, island_id, snapshot_id) | `city_player_island` + `donation_enriched` + `island_enriched` |
| `panel_island.{csv,parquet}` | (island_id, snapshot_id) | `island_enriched` + `city4_i` + `donation4_i` |

The transforms already compute these — we currently throw them away in `_latest_by()`. Reuse.

**1b. Emit Parquet alongside CSV**

Same schemas. One line per output in `io_files.py`: `df.write_parquet(path.with_suffix(".parquet"))`. Researchers get fast typed reads; Excel users still get CSV.

**1c. Data dictionary** `output/data_dictionary.yaml`

Machine-readable YAML: for each column across all outputs, record `name`, `grain`, `unit`, `translation`, `derivation`, `known_issues`.

**1d. Run manifest** `output/manifest.json`

```json
{
  "pipeline_version": "<git sha>",
  "run_timestamp_utc": "...",
  "config": { ... },
  "input": { "snapshots": 36, "date_range": [...], "raw_row_counts": {...} },
  "output": { "A_DS": 21822, ... },
  "known_divergences_from_sql": [ ... ]
}
```

### Tier 2 — cleanup

**2a. `Spieldauer` filter as parameter** — `--min-days` flag, default 2. Allows sensitivity analysis and unfiltered outputs.

**2b. `country` column** on A_DS and AVI_DS.

**2c. Document preserved legacy behaviors** in the data dictionary.

### Tier 3 — defer further

**3a. Drop `Teilnahme_AV.csv` and `Master_Avi.csv`** — pure redundancy but breaks byte-compat; do only after SQL alignment settles.

**3b. Star-schema split** — `dim_avatar`, `dim_island`, `fact_*_week`. Clean modeling, but premature without an active analysis.

**3c. Single DuckDB file** `output/ikariam.duckdb` — nice for exploration; low value until there's active research querying it.

**3d. Column naming cleanup** — breaks downstream queries; low value relative to effort.

## Non-goals

- Changing the existing 5 CSV outputs' schemas (byte-compat stays). Additions only.
- Renaming German domain terms (research vocabulary).
- Running or aligning to the SQL pipeline — handled in a separate work stream (the SQL-alignment phase).

## Critical files for Tier 1 implementation

- `src/ikariam_pipeline/transforms/final_datasets.py` — gains a panel code path without `_latest_by()` collapse and without the Spieldauer filter.
- `src/ikariam_pipeline/io_files.py` — add `write_parquet`, `write_manifest`.
- `src/ikariam_pipeline/schema.py` — column-order constants for the three panel outputs.
- `src/ikariam_pipeline/run_pipeline.py` — wire new outputs.
- New: `src/ikariam_pipeline/data_dictionary.py` or `output/data_dictionary.yaml`.

## Verification

1. All existing tests still pass (byte-compat preserved).
2. `uv run python scripts/run.py` now produces 5 original CSVs + 3 panel Parquets + 3 panel CSVs + `manifest.json` + `data_dictionary.yaml`.
3. Panel row counts ≈ 36 × entity count: `panel_avatar` ≈ 108,027, `panel_island` ≈ 192,636, `panel_avatar_island` ≈ 81,958.
4. A single active avatar's `Buerger_Ges` in `panel_avatar` across snapshots shows a monotonic-ish growth curve.
5. `manifest.json` has git sha, timestamp, all config values.
