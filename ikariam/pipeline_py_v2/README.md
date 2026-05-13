# Ikariam Pipeline v2 — panel data in LanceDB with DuckDB views

Successor to `pipeline_py/` (SQL-aligned cross-section CSVs). v2 keeps the
SQL-aligned transforms verbatim but changes the output shape: instead of
five CSVs at the latest snapshot, it writes three **weekly panel tables**
to LanceDB and derives cross-sections and summaries as DuckDB tables.

## Outputs

```
output/
├── ikariam.lancedb/                       # 9 Lance tables — one storage format
│   ├── player_snapshot.lance/             # (player_id, snapshot_id) — 107,852 rows
│   ├── player_island_snapshot.lance/      # (player_id, island_id, snapshot_id)
│   ├── island_snapshot.lance/             # (island_id, snapshot_id) — 192,636
│   ├── player_latest.lance/               # latest row per player
│   ├── player_island_latest.lance/        # latest row per player-island pair
│   ├── island_latest.lance/               # latest row per island
│   ├── player_summary.lance/              # per-player cross-snapshot aggregates
│   ├── player_island_summary.lance/       # per-pair aggregates
│   └── island_summary.lance/              # per-island aggregates
└── manifest.json                       # run metadata (sha, timestamp, config, counts)
```

Column docs are embedded in the Lance Arrow schema metadata
(`table.schema.field("x").metadata`) — the documentation travels with the data.
The raw database table is named `avatar`; public v2 outputs call that entity
`player`, so raw `avatar.id` becomes output `player_id`.

## Running

```bash
# Prereq: MariaDB with 36 DE snapshot DBs loaded (see sql_gold_standard/README.md).
uv sync
uv run python scripts/run.py            # hits MariaDB; takes ~10s
uv run python scripts/run.py --use-cache   # uses raw_cache/*.parquet (no DB)
```

## Reading the outputs

```python
# Direct Lance access (polars/pandas)
import lancedb, polars as pl
db = lancedb.connect("output/ikariam.lancedb")
players = pl.from_arrow(db["player_snapshot"].to_arrow())        # 107k panel rows
latest  = pl.from_arrow(db["player_latest"].to_arrow())          # 1 row per player
summary = pl.from_arrow(db["player_summary"].to_arrow())         # aggregates

# Column docs travel with the schema:
db["player_snapshot"].to_arrow().schema.field("account_age_days").metadata
# {b'description': b'Account age at reference timestamp', b'unit': b'days'}

# Optional: SQL via DuckDB (register Lance tables at read time)
import duckdb
con = duckdb.connect()
for name in ("player_snapshot", "player_latest", "player_summary"):
    con.register(name, db[name].to_arrow())
con.sql("""
  SELECT s.player_id, s.snapshots_observed_count, l.population_total, l.account_age_days
  FROM player_summary s JOIN player_latest l USING (player_id)
  WHERE s.snapshots_observed_count > 30
""").pl()
```

## What's new vs v1 (`pipeline_py/`)

- **CSV output dropped.** Primary format is Lance + DuckDB.
- **Teilnahme_AV and Master_Avi gone.** Their columns are recovered via
  `player_summary` / `player_island_summary`.
- **Full weekly trajectory preserved.** v1 collapsed to latest snapshot;
  v2 keeps every observation and exposes `*_latest` views on top.
- **Column docs inline in schema metadata** instead of a separate YAML.
- **`manifest.json`** records run metadata and known divergences.
- Transforms (building costs, wonder split, duration adjustment, prelaunch player
  filter, donation-without-city filter, …) are identical to v1's SQL-aligned
  version — see `docs/sql_vs_python_audit.md` for the audit report.

## Layout

- `src/ikariam_pipeline/` — transforms (pure functions), io, orchestration
- `sql/views.sql` — view definitions, executed against DuckDB at build time
- `sql_gold_standard/` — reference CSVs from the SQL pipeline
- `tests/test_sql_golden_lance.py` — diffs DuckDB `*_latest` views vs the SQL
  CSVs; asserts `<1e-6` numeric tolerance on every mapped column
