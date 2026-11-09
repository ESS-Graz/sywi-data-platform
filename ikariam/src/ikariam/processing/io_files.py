"""File-level I/O for CSV inputs stored alongside the raw extracts.

The pipeline reads two CSVs: `building_costs.csv` and `server_starts.csv`.
All outputs are written to LanceDB — see `io_lance.py`.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl


def read_building_costs(path: Path) -> pl.DataFrame:
    """Load `building_costs.csv` (semicolon-delimited)."""
    df = pl.read_csv(path, separator=";", encoding="utf8")

    key_columns = ["building_type", "building_level"]
    cost_columns = [
        "cost_holz", "cost_quartz", "cost_kristall", "cost_wein", "cost_schwefel",
    ]
    missing = set(key_columns + cost_columns) - set(df.columns)
    if missing:
        raise ValueError(f"building_costs missing columns: {missing}")

    empty = [c for c in key_columns + cost_columns if df.get_column(c).null_count()]
    if empty:
        raise ValueError(f"building_costs has empty cells in: {empty}")

    return df.with_columns(
        pl.col(key_columns).cast(pl.Int64),
        pl.col(cost_columns).cast(pl.Float64),
    )


def read_server_starts(path: Path) -> pl.DataFrame:
    """Load `server_starts.csv` (semicolon-delimited): one documented start time per server.

    Returns country (upper case), server and start_unix (seconds, UTC).
    """
    df = pl.read_csv(path, separator=";", encoding="utf8", schema_overrides={"country": pl.String})

    columns = ["country", "server", "start_utc"]
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(f"server_starts missing columns: {missing}")

    empty = [c for c in columns if df.get_column(c).null_count()]
    if empty:
        raise ValueError(f"server_starts has empty cells in: {empty}")

    df = df.select(
        pl.col("country").str.to_uppercase(),
        pl.col("server").cast(pl.Int64),
        pl.col("start_utc").str.to_datetime("%Y-%m-%d %H:%M:%S", time_zone="UTC").dt.epoch("s").alias("start_unix"),
    )

    duplicates = df.filter(pl.struct("country", "server").is_duplicated())
    if duplicates.height:
        raise ValueError(f"server_starts lists a server twice: {duplicates.select('country', 'server').unique().to_dicts()}")

    return df
