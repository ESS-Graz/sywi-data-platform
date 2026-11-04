"""Load raw Ikariam parquet exports laid out as Hive partitions.

Layout: ``<raw_data_dir>/country=<xx>/server=<nn>/snapshot_date=<YYYY-MM-DD>/<table>_*.parquet``
Polars reads ``country``, ``server`` and ``snapshot_date`` from the folder names.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import polars.selectors as cs

from .config import Config

RAW_TABLES: tuple[str, ...] = ("avatar", "city", "donation", "island")

HIVE_SCHEMA = {"country": pl.String, "server": pl.Int64, "snapshot_date": pl.Date}


def _scan_file(path: Path) -> pl.LazyFrame:
    return (
        pl.scan_parquet(path, hive_partitioning=True, hive_schema=HIVE_SCHEMA)
        # The export uses the narrowest integer type per column, which can differ
        # between files. Widen to Int64 so every file shares one schema.
        .with_columns(cs.integer().cast(pl.Int64))
    )


def load_raw_table(cfg: Config, table: str) -> pl.DataFrame:
    if table not in RAW_TABLES:
        raise ValueError(f"Unsupported raw table: {table}")
    if not cfg.countries:
        layout = f"{cfg.raw_data_dir}/country=<xx>/server=<nn>/snapshot_date=<date>/*.parquet"
        raise FileNotFoundError(f"No Ikariam countries configured or discoverable. Expected raw files under {layout}")

    files: list[Path] = []
    for country in cfg.countries:
        country_dir = cfg.raw_data_dir / f"country={country.lower()}"
        if not country_dir.exists():
            raise FileNotFoundError(f"Missing raw data directory for country {country}: {country_dir}")
        files += sorted(country_dir.glob(f"server=*/snapshot_date=*/{table}_*.parquet"))
    if not files:
        countries = ", ".join(cfg.countries)
        raise FileNotFoundError(f"No {table}_*.parquet files found for countries {countries} under {cfg.raw_data_dir}")

    # Every file must have the same columns and types; concat fails loudly
    # rather than padding gaps with nulls.
    raw = pl.concat([_scan_file(f) for f in files], how="vertical")
    return raw.select(
        pl.all().exclude(*HIVE_SCHEMA),
        pl.format(
            "{}{}_{}",
            pl.col("country"),
            pl.col("server"),
            pl.col("snapshot_date").dt.strftime("%d%m_%y"),
        ).alias("snapshot_id"),
        pl.col("snapshot_date"),
        pl.col("country").str.to_uppercase(),
        pl.col("server"),
    ).collect()
