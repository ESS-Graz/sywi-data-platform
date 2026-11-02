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
