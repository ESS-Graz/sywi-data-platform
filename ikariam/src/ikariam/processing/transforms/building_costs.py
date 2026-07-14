"""Step 03: join building costs to city data.

For each of the 17 building positions (p{i}t/p{i}l), look up the cumulative
cost by (type, level) and add 5 new cost columns g{i}{h,k,q,s,w}. Missing
lookups → 0 (buildings with type=0 or level=0).

Output: city_with_costs = city_raw + 85 cost columns.

**Implementation note**: a long/wide reshape (unpivot → single join →
pivot) sounds like a single-pass alternative to 17 joins. In practice it
touches ~5.7M long rows (334K cities × 17 positions) and pivots 5 times —
slower than the 17 lookup joins. We keep the 17-join pattern but lift the
type-casts and null-fills out of the loop to run once at the end.
"""

from __future__ import annotations

import polars as pl

_RESOURCES: tuple[tuple[str, str], ...] = (
    ("h", "cost_holz"),
    ("k", "cost_kristall"),
    ("q", "cost_quartz"),
    ("s", "cost_schwefel"),
    ("w", "cost_wein"),
)


def join_building_costs(city_raw: pl.DataFrame, building_costs: pl.DataFrame) -> pl.DataFrame:
    all_p_cols = [f"p{pos}{k}" for pos in range(1, 18) for k in ("t", "l")]
    present_p_cols = [c for c in all_p_cols if c in city_raw.columns]

    # Cast all 34 position columns (p{i}t, p{i}l) once, up front.
    df = city_raw.with_columns(
        pl.col(c).cast(pl.Int64, strict=False) for c in present_p_cols
    )

    bc = building_costs.select(
        pl.col("building_type").cast(pl.Int64),
        pl.col("building_level").cast(pl.Int64),
        "cost_holz", "cost_kristall", "cost_quartz", "cost_schwefel", "cost_wein",
    )

    # 17 left joins (one per position). Each iteration renames the lookup's
    # join keys + cost columns to this position's naming so we can join on
    # p{pos}t / p{pos}l directly and land the costs at the right alias.
    for pos in range(1, 18):
        bc_pos = bc.rename({
            "building_type": f"p{pos}t",
            "building_level": f"p{pos}l",
            "cost_holz":      f"g{pos}h",
            "cost_kristall":  f"g{pos}k",
            "cost_quartz":    f"g{pos}q",
            "cost_schwefel":  f"g{pos}s",
            "cost_wein":      f"g{pos}w",
        })
        df = df.join(bc_pos, on=[f"p{pos}t", f"p{pos}l"], how="left")

    # Single pass at the end to fill the 85 cost columns' nulls (from the
    # left-join's non-match rows → 0). Done once instead of 17 times.
    all_g_cols = [f"g{pos}{suf}" for pos in range(1, 18) for suf, _ in _RESOURCES]
    return df.with_columns(pl.col(c).fill_null(0.0) for c in all_g_cols)
