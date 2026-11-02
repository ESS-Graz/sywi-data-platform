"""Step 06: aggregate city enrichment to player-island-snapshot grain."""

from __future__ import annotations

import polars as pl

from .construction_events import CONSTRUCTION_SUM_COLUMNS

RESOURCE_NAMES: tuple[str, ...] = ("wood", "crystal", "marble", "sulfur", "wine")
RESOURCE_SUM_COLUMNS: tuple[str, ...] = (
    tuple(f"building_base_cost_{resource}" for resource in RESOURCE_NAMES)
    + ("building_base_cost_total",)
    + tuple(f"estimated_building_cost_{resource}" for resource in RESOURCE_NAMES)
    + ("estimated_building_cost_total",)
    + tuple(f"{resource}_stored" for resource in RESOURCE_NAMES)
    + ("resources_stored_total",)
    + tuple(f"estimated_{resource}_resource_value" for resource in RESOURCE_NAMES)
    + ("estimated_resource_value_total",)
)

SUM_COLUMNS: tuple[str, ...] = (
    "priests", "resource_workers", "tradegood_workers",
    "Buerger_Ges", "Geblev", "Rathauslev",
) + RESOURCE_SUM_COLUMNS + CONSTRUCTION_SUM_COLUMNS

FIRST_COLUMNS: tuple[str, ...] = ("snapshot_date", "country")


def aggregate_to_player_island(city_enriched: pl.DataFrame) -> pl.DataFrame:
    present_sum = [c for c in SUM_COLUMNS if c in city_enriched.columns]
    present_first = [c for c in FIRST_COLUMNS if c in city_enriched.columns]

    aggs: list[pl.Expr] = [pl.len().alias("cities_on_island")]
    aggs.extend(pl.col(c).sum().alias(c) for c in present_sum)
    aggs.extend(pl.col(c).first().alias(c) for c in present_first)

    return city_enriched.group_by(
        ["owner_id", "island_id", "snapshot_id"], maintain_order=True
    ).agg(aggs)
