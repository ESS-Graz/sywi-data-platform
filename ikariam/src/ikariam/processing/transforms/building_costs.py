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
    missing_p_cols = sorted(set(all_p_cols) - set(city_raw.columns))
    if missing_p_cols:
        raise ValueError(f"Missing building position columns: {missing_p_cols}")

    # Cast all 34 position columns (p{i}t, p{i}l) once, up front.
    df = city_raw.with_columns(
        pl.col(c).cast(pl.Int64, strict=False) for c in all_p_cols
    )

    bc = building_costs.select(
        pl.col("building_type").cast(pl.Int64),
        pl.col("building_level").cast(pl.Int64),
        "cost_holz", "cost_kristall", "cost_quartz", "cost_schwefel", "cost_wein",
    )

    used_buildings = (
        pl.concat(
            [
                df.select(
                    pl.col(f"p{pos}t").alias("building_type"),
                    pl.col(f"p{pos}l").alias("building_level"),
                )
                for pos in range(1, 18)
            ]
        )
        .filter((pl.col("building_type") > 0) & (pl.col("building_level") > 0))
        .unique()
    )
    missing_buildings = used_buildings.join(
        bc.select("building_type", "building_level").unique(),
        on=["building_type", "building_level"],
        how="anti",
    ).sort(["building_type", "building_level"])
    if not missing_buildings.is_empty():
        missing_pairs = ", ".join(
            f"({building_type}, {building_level})"
            for building_type, building_level in missing_buildings.iter_rows()
        )
        raise ValueError(f"Missing building cost lookups: {missing_pairs}")

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
