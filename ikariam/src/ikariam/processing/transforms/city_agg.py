"""Step 06: aggregate city enrichment to player-island-snapshot grain."""

from __future__ import annotations

import polars as pl

from ..utils import safe_percent

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
    "citizens", "scientists", "priests", "resource_workers", "tradegood_workers",
    "Buerger_Ges", "Resworkers_Holz_Lux",
    "Geblev", "Rathauslev", "GovReslev",
    "capital",
) + RESOURCE_SUM_COLUMNS

FIRST_COLUMNS: tuple[str, ...] = (
    "snapshot_date", "country",
    "Anz_Cities_per_Av", "Anz_Ins_per_Av", "Anz_Cities_per_DB",
    "account_age_days", "registered_at",
    "estimated_research_cost_factor",
    "estimated_research_cost_factor_source",
    "research_evidence_tier",
)

AVG_COLUMNS: tuple[str, ...] = (
    "Proz_resource_workers_pro_Buerger_Ges",
    "Proz_tradegood_workers_pro_Buerger_Ges",
)


def aggregate_to_player_island(city_enriched: pl.DataFrame) -> pl.DataFrame:
    present_sum = [c for c in SUM_COLUMNS if c in city_enriched.columns]
    present_first = [c for c in FIRST_COLUMNS if c in city_enriched.columns]
    present_avg = [c for c in AVG_COLUMNS if c in city_enriched.columns]

    aggs: list[pl.Expr] = [pl.len().alias("cities_on_island")]
    aggs.extend(pl.col(c).sum().alias(c) for c in present_sum)
    aggs.extend(pl.col(c).first().alias(c) for c in present_first)
    aggs.extend(pl.col(c).mean().alias(c) for c in present_avg)

    grouped = city_enriched.group_by(
        ["owner_id", "island_id", "snapshot_id"], maintain_order=True
    ).agg(aggs)

    # Recalculate percentages from summed values
    grouped = grouped.with_columns(
        safe_percent(pl.col("resource_workers"), pl.col("Buerger_Ges")).alias(
            "Proz_resource_workers_pro_Buerger_Ges"
        ),
        safe_percent(pl.col("tradegood_workers"), pl.col("Buerger_Ges")).alias(
            "Proz_tradegood_workers_pro_Buerger_Ges"
        ),
    )

    avg_map = {
        "Avg_Buerger_Ges": "Buerger_Ges",
        "Avg_Rathauslev": "Rathauslev",
        "Avg_Resource_workers": "resource_workers",
        "Avg_Tradegood_workers": "tradegood_workers",
    }
    grouped = grouped.with_columns(
        [
            pl.col(src).mean().over(["owner_id", "snapshot_id"]).alias(dst)
            for dst, src in avg_map.items()
        ]
    )

    return grouped
