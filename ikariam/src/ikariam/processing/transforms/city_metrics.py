"""Step 05: derive city-level resources, population, and building levels.

Building lookup costs remain observable base costs.  A separate estimated-cost
family applies, per resource, the player-snapshot research reduction plus the
city's own reduction-building level at that snapshot.  It estimates what the
current buildings would cost under that snapshot's discount state, not what
was historically spent.  Stored resources are added only to that estimated
family.  Keeping these concepts separate prevents the old age-adjusted
``*_verbaut`` values from being mistaken for either raw lookup costs or
observed resources.
"""

from __future__ import annotations

import polars as pl

from .building_costs import (
    HISTORICAL_REDUCTION_BUILDING_MAX_LEVEL,
    REDUCTION_LEVEL_COLUMNS,
)


RESOURCE_NAMES: tuple[str, ...] = ("wood", "crystal", "marble", "sulfur", "wine")
# Pulley, Geometry, and Spirit Level together reduce construction costs by 14%.
MAX_RESEARCH_REDUCTION_POINTS = 14
MIN_ESTIMATED_COST_FACTOR = (
    100 - MAX_RESEARCH_REDUCTION_POINTS - HISTORICAL_REDUCTION_BUILDING_MAX_LEVEL
) / 100


def _level_cols() -> list[pl.Expr]:
    """Slot levels, counted only where the position actually holds a building."""
    return [
        pl.when(pl.col(f"p{i}t") > 0).then(pl.col(f"p{i}l")).otherwise(0)
        for i in range(1, 18)
    ]


def compute_city_metrics(
    city_with_costs: pl.DataFrame, player_enriched: pl.DataFrame
) -> pl.DataFrame:
    missing_level_columns = sorted(
        set(REDUCTION_LEVEL_COLUMNS.values()) - set(city_with_costs.columns)
    )
    if missing_level_columns:
        raise ValueError(
            f"Missing reduction building level columns: {missing_level_columns}"
        )

    df = city_with_costs.with_columns(
        pl.col("citizens").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("resource_workers").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("tradegood_workers").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("scientists").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("resource").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("tradegood1").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("tradegood2").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("tradegood3").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("tradegood4").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("level").cast(pl.Int64, strict=False).fill_null(0),
    )

    if "priests" in df.columns:
        df = df.with_columns(pl.col("priests").cast(pl.Float64, strict=False).fill_null(0.0))
    else:
        df = df.with_columns(pl.lit(0.0).alias("priests"))

    # The building-cost transform already provides cumulative city totals.
    df = df.with_columns(
        pl.sum_horizontal(
            [pl.col(f"building_base_cost_{resource}") for resource in RESOURCE_NAMES]
        ).alias("building_base_cost_total")
    )

    # Stored resource totals depend only on the raw city inventory columns.
    df = df.with_columns(
        pl.col("resource").alias("wood_stored"),
        pl.col("tradegood1").alias("wine_stored"),
        pl.col("tradegood2").alias("marble_stored"),
        pl.col("tradegood3").alias("crystal_stored"),
        pl.col("tradegood4").alias("sulfur_stored"),
    )

    df = df.with_columns(
        pl.sum_horizontal(
            [pl.col(f"{resource}_stored") for resource in RESOURCE_NAMES]
        ).alias("resources_stored_total")
    )

    # Attach the single player-snapshot estimate and its provenance.
    player_slice = player_enriched.select(
        pl.col("id").alias("owner_id"),
        pl.col("snapshot_id"),
        "estimated_research_cost_factor",
        "estimated_research_cost_factor_source",
        "research_evidence_tier",
    )

    df = df.join(player_slice, on=["owner_id", "snapshot_id"], how="left")

    # Research is player-wide; each reduction building lowers one resource by
    # one percentage point per level, only in its own city at this snapshot.
    # Whole percentage points keep factors such as 0.86 - 0.20 exact.
    research_reduction_points = (
        (1 - pl.col("estimated_research_cost_factor")) * 100
    ).round(0)

    factor_columns = [f"estimated_{resource}_cost_factor" for resource in RESOURCE_NAMES]

    df = df.with_columns(
        [
            (
                (
                    100
                    - research_reduction_points
                    - pl.col(REDUCTION_LEVEL_COLUMNS[resource])
                )
                / 100
            ).alias(f"estimated_{resource}_cost_factor")
            for resource in RESOURCE_NAMES
        ]
    )

    invalid_factors = df.filter(
        pl.any_horizontal(
            [
                (pl.col(column) < MIN_ESTIMATED_COST_FACTOR) | (pl.col(column) > 1.0)
                for column in factor_columns
            ]
        )
    )
    if not invalid_factors.is_empty():
        sample = invalid_factors.select(
            [column for column in ("id", "snapshot_id") if column in df.columns]
        ).head(5)
        raise ValueError(
            f"Estimated cost factors outside [{MIN_ESTIMATED_COST_FACTOR}, 1.0]: rows={invalid_factors.height}; sample_keys={sample.to_dicts()}"
        )

    # Estimated building cost is explicit rather than overwriting base cost.
    df = df.with_columns(
        [
            (
                pl.col(f"building_base_cost_{resource}")
                * pl.col(f"estimated_{resource}_cost_factor")
            ).alias(f"estimated_building_cost_{resource}")
            for resource in RESOURCE_NAMES
        ]
    )

    df = df.with_columns(
        pl.sum_horizontal(
            [pl.col(f"estimated_building_cost_{resource}") for resource in RESOURCE_NAMES]
        ).alias("estimated_building_cost_total")
    )

    # Estimated resource value combines estimated building costs and observed
    # storage, while retaining every input component for reconciliation.
    df = df.with_columns(
        [
            (
                pl.col(f"estimated_building_cost_{resource}")
                + pl.col(f"{resource}_stored")
            ).alias(f"estimated_{resource}_resource_value")
            for resource in RESOURCE_NAMES
        ]
    )

    df = df.with_columns(
        pl.sum_horizontal(
            [pl.col(f"estimated_{resource}_resource_value") for resource in RESOURCE_NAMES]
        ).alias("estimated_resource_value_total")
    )

    # --- Population and building levels. ---
    df = df.with_columns(
        (
            pl.col("citizens")
            + pl.col("resource_workers")
            + pl.col("tradegood_workers")
            + pl.col("scientists")
            + pl.col("priests")
        ).alias("Buerger_Ges"),
    )

    df = df.with_columns(
        # Building levels include the town hall, which has no numbered slot and
        # is also published separately as town_hall_level.
        (pl.sum_horizontal(_level_cols()) + pl.col("level")).alias("Geblev"),
        pl.col("level").alias("Rathauslev"),
    )

    return df
