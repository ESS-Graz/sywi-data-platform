"""Step 09: higher-level aggregations — by avatar and by island.

Produces four tables:
- city3AV: (owner_id, snapshot_id) aggregates across all islands
- city4I: (island_id, snapshot_id) aggregates across all players
- donation3AV: (avatar_id, snapshot_id) donation aggregates
- donation4I: (island_id, snapshot_id) donation aggregates
"""

from __future__ import annotations

import polars as pl

from ..utils import safe_percent


RESOURCE_NAMES: tuple[str, ...] = ("wood", "crystal", "marble", "sulfur", "wine")
RESOURCE_COLUMNS: tuple[str, ...] = (
    tuple(f"building_base_cost_{resource}" for resource in RESOURCE_NAMES)
    + ("building_base_cost_total",)
    + tuple(f"estimated_building_cost_{resource}" for resource in RESOURCE_NAMES)
    + ("estimated_building_cost_total",)
    + tuple(f"{resource}_stored" for resource in RESOURCE_NAMES)
    + ("resources_stored_total",)
    + tuple(f"estimated_{resource}_resource_value" for resource in RESOURCE_NAMES)
    + ("estimated_resource_value_total",)
)


def _sum_resource_columns() -> list[pl.Expr]:
    return [pl.col(column).sum().alias(column) for column in RESOURCE_COLUMNS]


def aggregate_by_avatar(city_player_island: pl.DataFrame) -> pl.DataFrame:
    aggs: list[pl.Expr] = [
        pl.col("island_id").n_unique().alias("total_islands"),
        pl.col("cities_on_island").sum().alias("total_cities"),
        pl.col("citizens").sum().alias("citizens"),
        pl.col("scientists").sum().alias("scientists"),
        pl.col("priests").sum().alias("priests"),
        pl.col("resource_workers").sum().alias("resource_workers"),
        pl.col("tradegood_workers").sum().alias("tradegood_workers"),
        pl.col("Buerger_Ges").sum().alias("Buerger_Ges"),
        pl.col("Geblev").sum().alias("Geblev"),
        pl.col("Rathauslev").sum().alias("Rathauslev"),
        pl.col("Buerger_Ges").mean().alias("Avg_Buerger_Ges"),
        pl.col("account_age_days").first().alias("account_age_days"),
        pl.col("registered_at").first().alias("registered_at"),
        pl.col("estimated_research_cost_factor")
        .first()
        .alias("estimated_research_cost_factor"),
        pl.col("estimated_research_cost_factor_source")
        .first()
        .alias("estimated_research_cost_factor_source"),
        pl.col("research_evidence_tier").first().alias("research_evidence_tier"),
    ]
    aggs.extend(_sum_resource_columns())
    g = city_player_island.group_by(
        ["owner_id", "snapshot_id", "snapshot_date", "country"]
    ).agg(aggs)
    return g.with_columns(
        safe_percent(pl.col("resource_workers"), pl.col("Buerger_Ges")).alias(
            "Proz_resource_workers"
        ),
        safe_percent(pl.col("tradegood_workers"), pl.col("Buerger_Ges")).alias(
            "Proz_tradegood_workers"
        ),
    )


def aggregate_by_island(city_player_island: pl.DataFrame) -> pl.DataFrame:
    aggs: list[pl.Expr] = [
        pl.col("owner_id").n_unique().alias("total_players"),
        pl.col("cities_on_island").sum().alias("total_cities"),
        pl.col("citizens").sum().alias("citizens"),
        pl.col("scientists").sum().alias("scientists"),
        pl.col("priests").sum().alias("priests"),
        pl.col("resource_workers").sum().alias("resource_workers"),
        pl.col("tradegood_workers").sum().alias("tradegood_workers"),
        pl.col("Buerger_Ges").sum().alias("Buerger_Ges"),
        pl.col("Geblev").sum().alias("Geblev"),
        pl.col("Rathauslev").sum().alias("Rathauslev"),
        pl.col("Buerger_Ges").mean().alias("Avg_Buerger_per_player"),
    ]
    aggs.extend(_sum_resource_columns())
    return city_player_island.group_by(
        ["island_id", "snapshot_id", "snapshot_date", "country"]
    ).agg(aggs)


def donations_by_avatar(donation_enriched: pl.DataFrame) -> pl.DataFrame:
    g = donation_enriched.group_by(
        ["avatar_id", "snapshot_id", "snapshot_date", "country"]
    ).agg(
        pl.col("island_id").n_unique().alias("total_islands"),
        pl.col("Don_Wonder_Ges").sum().alias("Don_Wonder_Ges"),
        pl.col("Don_Saegewerk_Ges").sum().alias("Don_Saegewerk_Ges"),
        pl.col("Don_Luxusminen_Ges").sum().alias("Don_Luxusminen_Ges"),
        pl.col("Don_Ges").sum().alias("Don_Ges"),
        pl.col("Don_Wein_Ges").sum().alias("Don_Wein_Ges"),
        pl.col("Don_Stein_Ges").sum().alias("Don_Stein_Ges"),
        pl.col("Don_Kristall_Ges").sum().alias("Don_Kristall_Ges"),
        pl.col("Don_Schwefel_Ges").sum().alias("Don_Schwefel_Ges"),
        pl.col("Don_Luxus_Ges").sum().alias("Don_Luxus_Ges"),
        pl.col("Don_Ges").mean().alias("Avg_Don_per_island"),
    )
    return g.with_columns(
        safe_percent(pl.col("Don_Wonder_Ges"), pl.col("Don_Ges")).alias("Don_Wonder_Proz"),
        safe_percent(pl.col("Don_Saegewerk_Ges"), pl.col("Don_Ges")).alias("Don_Saegewerk_Proz"),
        safe_percent(pl.col("Don_Luxusminen_Ges"), pl.col("Don_Ges")).alias("Don_Luxusminen_Proz"),
    )


def donations_by_island(donation_enriched: pl.DataFrame) -> pl.DataFrame:
    g = donation_enriched.group_by(
        ["island_id", "snapshot_id", "snapshot_date", "country"]
    ).agg(
        pl.col("avatar_id").n_unique().alias("total_players"),
        (pl.col("Don_Ges") > 0).sum().alias("donating_players"),
        pl.col("Don_Wonder_Ges").sum().alias("Don_Wonder_Ges"),
        pl.col("Don_Saegewerk_Ges").sum().alias("Don_Saegewerk_Ges"),
        pl.col("Don_Luxusminen_Ges").sum().alias("Don_Luxusminen_Ges"),
        pl.col("Don_Ges").sum().alias("Don_Ges"),
        pl.col("Don_Wein_Ges").sum().alias("Don_Wein_Ges"),
        pl.col("Don_Stein_Ges").sum().alias("Don_Stein_Ges"),
        pl.col("Don_Kristall_Ges").sum().alias("Don_Kristall_Ges"),
        pl.col("Don_Schwefel_Ges").sum().alias("Don_Schwefel_Ges"),
        pl.col("Don_Luxus_Ges").sum().alias("Don_Luxus_Ges"),
        pl.col("Don_Ges").mean().alias("Avg_Don_per_player"),
    )
    return g.with_columns(
        safe_percent(pl.col("Don_Wonder_Ges"), pl.col("Don_Ges")).alias("Don_Wonder_Proz"),
        safe_percent(pl.col("Don_Saegewerk_Ges"), pl.col("Don_Ges")).alias("Don_Saegewerk_Proz"),
        safe_percent(pl.col("Don_Luxusminen_Ges"), pl.col("Don_Ges")).alias("Don_Luxusminen_Proz"),
        safe_percent(pl.col("donating_players"), pl.col("total_players")).alias(
            "donation_participation_rate"
        ),
    )
