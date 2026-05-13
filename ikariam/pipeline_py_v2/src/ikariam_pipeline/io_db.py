"""MariaDB snapshot loader.

Loads avatar/city/donation/island across all 36 snapshot DBs.

**Load strategy**: 144 small parallel queries (4 tables × 36 snapshots, 8
worker threads). A Tier-2 experiment consolidated each table into a single
UNION ALL across all snapshots — it was ~2× SLOWER than the parallel
small-query approach on this setup (MariaDB + connectorx). Kept as
documentation; do not reintroduce without benchmarking.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import structlog

from .config import Config, Snapshot

logger = structlog.get_logger()


RAW_TABLES: tuple[str, ...] = ("avatar", "city", "donation", "island")

# MySQL TINYINT(1) columns come back as Boolean via connectorx regardless of
# actual values (formOfGovernment=0..6, city.level=0..30+, etc.), which
# truncates any value > 1 to `true`. Work around by fetching an explicit
# CAST(col AS SIGNED) alongside the original and preferring the cast copy.
_TINYINT_COLS: dict[str, tuple[str, ...]] = {
    "avatar": ("formOfGovernment",),
    "city": ("capital", "level"),
    "donation": ("type",),
    "island": ("tradegood", "tradegood_level", "city_count"),
}


@dataclass(frozen=True, slots=True)
class RawTables:
    avatar: pl.DataFrame
    city: pl.DataFrame
    donation: pl.DataFrame
    island: pl.DataFrame


def _uri_for(snapshot_id: str, cfg: Config) -> str:
    db = cfg.db
    return f"mysql://{db.user}:{db.password}@{db.host}:{db.port}/{snapshot_id}"


def _read_table(
    snapshot: Snapshot, table: str, cfg: Config
) -> pl.DataFrame:
    uri = _uri_for(snapshot.snapshot_id, cfg)
    tinyint_cols = _TINYINT_COLS.get(table, ())
    extras = "".join(f", CAST(`{c}` AS SIGNED) AS `{c}__int`" for c in tinyint_cols)
    query = f"SELECT *{extras} FROM `{table}`"
    df = pl.read_database_uri(query=query, uri=uri, engine="connectorx")

    # Replace the TINYINT(1)-as-bool column with the true integer copy.
    for c in tinyint_cols:
        int_col = f"{c}__int"
        if c in df.columns and int_col in df.columns:
            df = df.drop(c).rename({int_col: c})

    return df.with_columns(
        pl.lit(snapshot.snapshot_id).alias("snapshot_id"),
        pl.lit(snapshot.snapshot_date).alias("snapshot_date"),
        pl.lit(snapshot.country).alias("country"),
    )


def _load_table_all_snapshots(
    table: str, cfg: Config, max_workers: int
) -> pl.DataFrame:
    frames: list[pl.DataFrame] = [pl.DataFrame()] * len(cfg.snapshots)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_read_table, snap, table, cfg): i
            for i, snap in enumerate(cfg.snapshots)
        }
        for fut in as_completed(futures):
            i = futures[fut]
            frames[i] = fut.result()
    out = pl.concat(frames, how="diagonal_relaxed")
    logger.info("loaded_table", table=table, rows=out.height, snapshots=len(cfg.snapshots))
    return out


def load_all_raw_from_db(cfg: Config, max_workers: int = 8) -> RawTables:
    """Load avatar/city/donation/island from all snapshot DBs in parallel."""
    tables = {t: _load_table_all_snapshots(t, cfg, max_workers) for t in RAW_TABLES}
    return RawTables(
        avatar=tables["avatar"],
        city=tables["city"],
        donation=tables["donation"],
        island=tables["island"],
    )


def _cache_path(cache_dir: Path, snapshot_id: str, table: str) -> Path:
    return cache_dir / snapshot_id / f"{table}.parquet"


def cache_raw_to_parquet(raw: RawTables, cfg: Config, cache_dir: Path) -> None:
    """Split unified frames back per-snapshot and persist to parquet."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    tables_map: dict[str, pl.DataFrame] = {
        "avatar": raw.avatar, "city": raw.city,
        "donation": raw.donation, "island": raw.island,
    }
    for snap in cfg.snapshots:
        snap_dir = cache_dir / snap.snapshot_id
        snap_dir.mkdir(parents=True, exist_ok=True)
        for table, df in tables_map.items():
            part = df.filter(pl.col("snapshot_id") == snap.snapshot_id)
            part.write_parquet(_cache_path(cache_dir, snap.snapshot_id, table))
    logger.info("parquet_cache_written", dir=str(cache_dir))


def load_all_raw_from_cache(cfg: Config, cache_dir: Path) -> RawTables:
    """Read pre-cached parquets. Raises FileNotFoundError if missing."""
    tables: dict[str, list[pl.DataFrame]] = {t: [] for t in RAW_TABLES}
    for snap in cfg.snapshots:
        for table in RAW_TABLES:
            p = _cache_path(cache_dir, snap.snapshot_id, table)
            if not p.exists():
                raise FileNotFoundError(f"Missing cache parquet: {p}")
            tables[table].append(pl.read_parquet(p))
    combined = {t: pl.concat(frames, how="diagonal_relaxed") for t, frames in tables.items()}
    logger.info("loaded_from_cache", dir=str(cache_dir))
    return RawTables(
        avatar=combined["avatar"],
        city=combined["city"],
        donation=combined["donation"],
        island=combined["island"],
    )


def load_all_raw(cfg: Config, cache_dir: Path | None = None) -> RawTables:
    """Load raw tables. If cache_dir is set and non-empty, read parquet;
    otherwise hit MariaDB and (if cache_dir provided) persist the cache."""
    if cache_dir is not None and (cache_dir / cfg.snapshots[0].snapshot_id).exists():
        return load_all_raw_from_cache(cfg, cache_dir)
    raw = load_all_raw_from_db(cfg)
    if cache_dir is not None:
        cache_raw_to_parquet(raw, cfg, cache_dir)
    return raw
