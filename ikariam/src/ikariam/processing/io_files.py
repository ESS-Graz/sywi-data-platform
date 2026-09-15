"""File-level I/O for CSV inputs stored alongside the raw extracts.

`building_costs.csv` is the only CSV the pipeline reads; all outputs are
written to LanceDB — see `io_lance.py`.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl


def read_building_costs(path: Path) -> pl.DataFrame:
    """Load `building_costs.csv` (semicolon-delimited)."""
    df = pl.read_csv(path, separator=";", encoding="utf8")
    expected = {
        "building_type", "building_level",
        "cost_holz", "cost_quartz", "cost_kristall", "cost_wein", "cost_schwefel",
    }
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"building_costs missing columns: {missing}")
    return df.with_columns(
        pl.col("building_type").cast(pl.Int64),
        pl.col("building_level").cast(pl.Int64),
        pl.col("cost_holz").cast(pl.Float64).fill_null(0.0),
        pl.col("cost_quartz").cast(pl.Float64).fill_null(0.0),
        pl.col("cost_kristall").cast(pl.Float64).fill_null(0.0),
        pl.col("cost_wein").cast(pl.Float64).fill_null(0.0),
        pl.col("cost_schwefel").cast(pl.Float64).fill_null(0.0),
    )
