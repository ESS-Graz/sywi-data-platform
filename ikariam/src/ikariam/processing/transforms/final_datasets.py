"""Build the three canonical snapshot datasets that land as Lance tables.

Every row is an entity-snapshot observation: the full weekly trajectory, no
collapse to latest. Raw input table names are preserved upstream, but these
public outputs use canonical lower_snake_case names.

No account-age filter or latest-snapshot collapse here: those are query-time
concerns. The configured registration-cohort filter has already been applied
by the upstream Dagster assets, so every row in the panels comes from a
validated player.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl


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


@dataclass(frozen=True, slots=True)
class PanelTables:
    player_snapshot: pl.DataFrame
    city_snapshot: pl.DataFrame
    island_snapshot: pl.DataFrame


def build_player_snapshot_table(
    player_enriched: pl.DataFrame,
    city3_av: pl.DataFrame,
    donation3_av: pl.DataFrame,
) -> pl.DataFrame:
    """One row per (player_id, snapshot_id).

    Merges the per-player-per-snapshot aggregates (city3_av, donation3_av)
    onto the per-player-per-snapshot base (player_enriched).
    """
    base = player_enriched.rename({"id": "player_id"}).select(
        "player_id",
        "snapshot_id",
        "snapshot_date",
        pl.col("country").alias("country_code"),
        pl.col("registration_time").alias("registered_at_unix"),
        "registered_at",
        "gold",
        "research_points",
        pl.col("formOfGovernment").alias("government_form"),
        "gender",
        "account_age_days",
        "estimated_research_cost_factor",
        "estimated_research_cost_factor_source",
        "research_evidence_tier",
    )

    city_agg = city3_av.select(
        pl.col("owner_id").alias("player_id"),
        "snapshot_id",
        pl.col("total_islands").alias("island_count"),
        pl.col("total_cities").alias("city_count"),
        pl.col("Buerger_Ges").alias("population_total"),
        *RESOURCE_COLUMNS,
        pl.col("Geblev").alias("building_levels_total"),
    )
    base = base.join(city_agg, on=["player_id", "snapshot_id"], how="left")

    don_agg = donation3_av.select(
        pl.col("avatar_id").alias("player_id"),
        "snapshot_id",
        pl.col("Don_Wonder_Ges").alias("wonder_donations_total"),
        pl.col("Don_Saegewerk_Ges").alias("sawmill_donations_total"),
        pl.col("Don_Luxusminen_Ges").alias("luxury_mine_donations_total"),
        pl.col("Don_Ges").alias("donations_total"),
        pl.col("Don_Luxus_Ges").alias("wonder_and_luxury_mine_donations_total"),
    )
    base = base.join(don_agg, on=["player_id", "snapshot_id"], how="left")

    # Fill numeric nulls with 0 for weeks where this player had no cities
    # or no donations (they're absent from city3_av / donation3_av).
    base = base.with_columns(
        [
            pl.col(c).fill_null(0)
            for c, dt in zip(base.columns, base.dtypes, strict=True)
            if dt.is_numeric()
            and c
            not in {
                "registered_at_unix",
                "account_age_days",
                "estimated_research_cost_factor",
            }
        ]
    )
    return base.sort(["player_id", "snapshot_date", "snapshot_id"])


def build_city_snapshot_table(
    city_enriched: pl.DataFrame,
    donation_enriched: pl.DataFrame,
    island_enriched: pl.DataFrame,
) -> pl.DataFrame:
    """One row per (city_id, snapshot_id).

    The natural grain of `city_enriched` — every week where a city existed.
    Joined with the matching donation enrichment and island metadata.
    """
    base = city_enriched.select(
        pl.col("id").alias("city_id"),
        pl.col("owner_id").alias("player_id"),
        "island_id",
        "snapshot_id",
        "snapshot_date",
        pl.col("country").alias("country_code"),
        pl.col("capital").cast(pl.Boolean).alias("is_capital"),
        pl.col("Rathauslev").alias("town_hall_level"),
        "citizens",
        "scientists",
        "priests",
        "resource_workers",
        "tradegood_workers",
        pl.col("Buerger_Ges").alias("population_total"),
        "estimated_research_cost_factor",
        "estimated_research_cost_factor_source",
        "research_evidence_tier",
        *(f"{resource}_reduction_building_level" for resource in RESOURCE_NAMES),
        *(f"estimated_{resource}_cost_factor" for resource in RESOURCE_NAMES),
        *RESOURCE_COLUMNS,
        pl.col("Geblev").alias("building_levels_total"),
    )

    don = donation_enriched.select(
        pl.col("avatar_id").alias("player_id"),
        "island_id",
        "snapshot_id",
        pl.col("Don_Wonder_Ges").alias("wonder_donations_total"),
        pl.col("Don_Saegewerk_Ges").alias("sawmill_donations_total"),
        pl.col("Don_Luxusminen_Ges").alias("luxury_mine_donations_total"),
        pl.col("Don_Ges").alias("donations_total"),
    )
    base = base.join(don, on=["player_id", "island_id", "snapshot_id"], how="left")

    isl = island_enriched.select(
        pl.col("id").alias("island_id"),
        "snapshot_id",
        "wonder_type_id",
        "wonder_level",
        "wonder_belief",
        pl.col("tradegood").alias("luxury_resource_type"),
        pl.col("tradegood_level").alias("luxury_mine_level"),
        pl.col("resource_level").alias("sawmill_level"),
        pl.col("city_count").alias("island_city_count"),
        pl.col("resource_donated").alias("sawmill_donated_cumulative"),
        pl.col("tradegood_donated").alias("luxury_mine_donated_cumulative"),
        pl.col("wonder_donated").alias("wonder_donated_cumulative"),
        pl.col("cost_Nextlev_resource").alias("sawmill_next_level_cost"),
        pl.col("cost_Nextlev_tradegood").alias("luxury_mine_next_level_cost"),
        pl.col("cost_Nextlev_wonder").alias("wonder_next_level_cost"),
        pl.col("Sub_Noetig_nextlev_resource").alias("sawmill_next_level_remaining_cost"),
        pl.col("Sub_Noetig_nextlev_tradegood").alias("luxury_mine_next_level_remaining_cost"),
        pl.col("Sub_Noetig_nextlev_wonder").alias("wonder_next_level_remaining_cost"),
    )
    base = base.join(isl, on=["island_id", "snapshot_id"], how="left")

    base = base.with_columns(
        [
            pl.col(c).fill_null(0)
            for c, dt in zip(base.columns, base.dtypes, strict=True)
            if dt.is_numeric()
            and c != "estimated_research_cost_factor"
            and not c.startswith("estimated_building_cost_")
            and not c.startswith("estimated_")
        ]
    )
    return base.sort(["city_id", "snapshot_date", "snapshot_id"])


def build_island_snapshot_table(
    island_enriched: pl.DataFrame,
    city4_i: pl.DataFrame,
    donation4_i: pl.DataFrame,
) -> pl.DataFrame:
    """One row per (island_id, snapshot_id).

    Island raw + derived metrics (upgrade costs, next-level deltas, city-
    and donation-aggregates across all players on that island that week).
    """
    base = island_enriched.rename({"id": "island_id"}).select(
        "island_id",
        "snapshot_id",
        "snapshot_date",
        pl.col("country").alias("country_code"),
        "island_snapshot_key",
        "wonder_type_id",
        "wonder_level",
        "wonder_belief",
        pl.col("tradegood").alias("luxury_resource_type"),
        pl.col("tradegood_level").alias("luxury_mine_level"),
        pl.col("resource_level").alias("sawmill_level"),
        pl.col("city_count").alias("raw_city_count"),
        pl.col("resource_donated").alias("sawmill_donated_cumulative"),
        pl.col("tradegood_donated").alias("luxury_mine_donated_cumulative"),
        pl.col("wonder_donated").alias("wonder_donated_cumulative"),
        pl.col("cost_Nextlev_resource").alias("sawmill_next_level_cost"),
        pl.col("cost_Nextlev_tradegood").alias("luxury_mine_next_level_cost"),
        pl.col("cost_Nextlev_wonder").alias("wonder_next_level_cost"),
        pl.col("Sub_Noetig_nextlev_resource").alias("sawmill_next_level_remaining_cost"),
        pl.col("Sub_Noetig_nextlev_tradegood").alias(
            "luxury_mine_next_level_remaining_cost"
        ),
        pl.col("Sub_Noetig_nextlev_wonder").alias("wonder_next_level_remaining_cost"),
    )

    city_agg = city4_i.select(
        "island_id",
        "snapshot_id",
        pl.col("total_players").alias("player_count"),
        pl.col("total_cities").alias("city_count"),
        pl.col("Buerger_Ges").alias("population_total"),
        *RESOURCE_COLUMNS,
        pl.col("Geblev").alias("building_levels_total"),
        pl.col("Avg_Buerger_per_player").alias("avg_population_per_player"),
    )
    base = base.join(city_agg, on=["island_id", "snapshot_id"], how="left")

    don_agg = donation4_i.select(
        "island_id",
        "snapshot_id",
        pl.col("donating_players").alias("donating_player_count"),
        pl.col("Don_Wonder_Ges").alias("wonder_donations_total"),
        pl.col("Don_Saegewerk_Ges").alias("sawmill_donations_total"),
        pl.col("Don_Luxusminen_Ges").alias("luxury_mine_donations_total"),
        pl.col("Don_Ges").alias("donations_total"),
        pl.col("Avg_Don_per_player").alias("avg_donations_per_player"),
        pl.col("donation_participation_rate").alias("donating_player_share_pct"),
    )
    base = base.join(don_agg, on=["island_id", "snapshot_id"], how="left")

    base = base.with_columns(
        [
            pl.col(c).fill_null(0)
            for c, dt in zip(base.columns, base.dtypes, strict=True)
            if dt.is_numeric()
        ]
    )
    return base.sort(["island_id", "snapshot_date", "snapshot_id"])


def build_panels(
    player_enriched: pl.DataFrame,
    city_enriched: pl.DataFrame,
    city3_av: pl.DataFrame,
    city4_i: pl.DataFrame,
    donation_enriched: pl.DataFrame,
    donation3_av: pl.DataFrame,
    donation4_i: pl.DataFrame,
    island_enriched: pl.DataFrame,
) -> PanelTables:
    return PanelTables(
        player_snapshot=build_player_snapshot_table(
            player_enriched, city3_av, donation3_av
        ),
        city_snapshot=build_city_snapshot_table(
            city_enriched, donation_enriched, island_enriched
        ),
        island_snapshot=build_island_snapshot_table(island_enriched, city4_i, donation4_i),
    )
