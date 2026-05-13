"""Raw parquet loading for the Dagster Ikariam pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import polars as pl

from .config import Config, Snapshot

RAW_TABLES: tuple[str, ...] = ("avatar", "city", "donation", "island")


@dataclass(frozen=True, slots=True)
class RawTables:
    avatar: pl.DataFrame
    city: pl.DataFrame
    donation: pl.DataFrame
    island: pl.DataFrame


def snapshot_id_for(country: str, snapshot_date: date) -> str:
    return f"{country.lower()}_{snapshot_date:%d%m_%y}"


def discover_snapshots(raw_data_dir: Path, countries: tuple[str, ...]) -> tuple[Snapshot, ...]:
    snapshots: list[Snapshot] = []
    for country in countries:
        country_dir = raw_data_dir / country.lower()
        if not country_dir.exists():
            country_dir = raw_data_dir / country.upper()
        if not country_dir.exists():
            raise FileNotFoundError(f"Missing raw data directory for country {country}: {country_dir}")

        for snapshot_dir in sorted(p for p in country_dir.iterdir() if p.is_dir()):
            snapshot_date = date.fromisoformat(snapshot_dir.name)
            snapshots.append(
                Snapshot(
                    snapshot_id=snapshot_id_for(country, snapshot_date),
                    snapshot_date=snapshot_date,
                    country=country.upper(),
                )
            )

    return tuple(sorted(snapshots, key=lambda s: (s.country, s.snapshot_date)))


def _snapshot_dir(raw_data_dir: Path, snapshot: Snapshot) -> Path:
    lower = raw_data_dir / snapshot.country.lower() / snapshot.snapshot_date.isoformat()
    if lower.exists():
        return lower
    return raw_data_dir / snapshot.country.upper() / snapshot.snapshot_date.isoformat()


def _read_table(snapshot_dir: Path, snapshot: Snapshot, table: str) -> pl.DataFrame:
    path = snapshot_dir / f"{table}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing raw parquet: {path}")

    return pl.read_parquet(path).with_columns(
        pl.lit(snapshot.snapshot_id).alias("snapshot_id"),
        pl.lit(snapshot.snapshot_date).alias("snapshot_date"),
        pl.lit(snapshot.country).alias("country"),
    )


def load_raw_table(cfg: Config, table: str) -> pl.DataFrame:
    if table not in RAW_TABLES:
        raise ValueError(f"Unsupported raw table: {table}")
    if not cfg.countries:
        raise FileNotFoundError(
            "No Ikariam countries configured or discoverable. Expected raw files under "
            f"{cfg.raw_data_dir}/<country>/<snapshot_date>/*.parquet"
        )

    frames: list[pl.DataFrame] = []
    for snapshot in discover_snapshots(cfg.raw_data_dir, cfg.countries):
        frames.append(_read_table(_snapshot_dir(cfg.raw_data_dir, snapshot), snapshot, table))

    if not frames:
        raise FileNotFoundError(f"No {table}.parquet files found under {cfg.raw_data_dir}")
    return pl.concat(frames, how="diagonal_relaxed")


def load_raw_tables(cfg: Config) -> RawTables:
    tables = {table: load_raw_table(cfg, table) for table in RAW_TABLES}
    return RawTables(
        avatar=tables["avatar"],
        city=tables["city"],
        donation=tables["donation"],
        island=tables["island"],
    )
