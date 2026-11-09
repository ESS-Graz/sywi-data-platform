"""Step 09: higher-level aggregations — by player and by island.

Produces four tables:
- city3AV: (owner_id, snapshot_id) aggregates across all islands
- city4I: (island_id, snapshot_id) aggregates across all players
- donation3AV: (avatar_id, snapshot_id) donation aggregates
- donation4I: (island_id, snapshot_id) donation aggregates
"""

from __future__ import annotations

import polars as pl

from ..utils import safe_percent
from .construction_events import CONSTRUCTION_SUM_COLUMNS
from .donations import split_donation_types


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
    + CONSTRUCTION_SUM_COLUMNS
)


def _sum_resource_columns() -> list[pl.Expr]:
    return [pl.col(column).sum().alias(column) for column in RESOURCE_COLUMNS]


def aggregate_by_player(city_player_island: pl.DataFrame) -> pl.DataFrame:
    aggs: list[pl.Expr] = [
        pl.col("island_id").n_unique().alias("total_islands"),
        pl.col("cities_on_island").sum().alias("total_cities"),
        pl.col("Buerger_Ges").sum().alias("Buerger_Ges"),
        pl.col("Geblev").sum().alias("Geblev"),
    ]

    aggs.extend(_sum_resource_columns())

    return city_player_island.group_by(
        ["owner_id", "snapshot_id", "snapshot_date", "country", "server"]
    ).agg(aggs)


def aggregate_by_island(city_player_island: pl.DataFrame) -> pl.DataFrame:
    aggs: list[pl.Expr] = [
        pl.col("owner_id").n_unique().alias("total_players"),
        pl.col("cities_on_island").sum().alias("total_cities"),
        pl.col("Buerger_Ges").sum().alias("Buerger_Ges"),
        pl.col("Geblev").sum().alias("Geblev"),
        pl.col("Buerger_Ges").mean().alias("Avg_Buerger_per_player"),
    ]

    aggs.extend(_sum_resource_columns())

    return city_player_island.group_by(
        ["island_id", "snapshot_id", "snapshot_date", "country", "server"]
    ).agg(aggs)


def donations_by_player(donation_raw: pl.DataFrame) -> pl.DataFrame:
    """Player-snapshot donation totals over every island.

    Reads the raw donation rows rather than ``donation_enriched``, so islands
    where the player no longer has a city (mostly relocated cities, whose old
    amount stays in the data) still count towards the player's total.
    """
    totals = split_donation_types(donation_raw).group_by(
        ["avatar_id", "snapshot_id", "snapshot_date", "country", "server"]
    ).agg(
        pl.col("Don_Wonder").sum().alias("Don_Wonder_Ges"),
        pl.col("Don_Saegewerk").sum().alias("Don_Saegewerk_Ges"),
        pl.col("Don_Luxusminen").sum().alias("Don_Luxusminen_Ges"),
        pl.col("Don_Ges_raw").sum().alias("Don_Ges"),
    )

    return totals.with_columns(
        (pl.col("Don_Wonder_Ges") + pl.col("Don_Luxusminen_Ges")).alias("Don_Luxus_Ges")
    )


def donations_by_island(donation_enriched: pl.DataFrame) -> pl.DataFrame:
    g = donation_enriched.group_by(
        ["island_id", "snapshot_id", "snapshot_date", "country", "server"]
    ).agg(
        pl.col("avatar_id").n_unique().alias("total_players"),
        (pl.col("Don_Ges") > 0).sum().alias("donating_players"),
        pl.col("Don_Wonder_Ges").sum().alias("Don_Wonder_Ges"),
        pl.col("Don_Saegewerk_Ges").sum().alias("Don_Saegewerk_Ges"),
        pl.col("Don_Luxusminen_Ges").sum().alias("Don_Luxusminen_Ges"),
        pl.col("Don_Ges").sum().alias("Don_Ges"),
        pl.col("Don_Ges").mean().alias("Avg_Don_per_player"),
    )

    return g.with_columns(
        safe_percent(pl.col("donating_players"), pl.col("total_players")).alias(
            "donation_participation_rate"
        ),
    )
