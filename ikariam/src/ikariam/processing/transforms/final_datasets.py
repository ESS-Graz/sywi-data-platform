"""Build the three canonical snapshot datasets that land as Lance tables.

Every row is an entity-snapshot observation: the full weekly trajectory, no
collapse to latest. Raw input table names are preserved upstream, but these
public outputs use canonical lower_snake_case names.

No account-age filter or latest-snapshot collapse here: those are query-time
concerns. The prelaunch player registration-time filter has already been
applied to `raw.*` tables in `run_pipeline._filter_prelaunch_players`, so
every row in the panels already comes from a valid player.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl


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
        pl.col("Registration_time_normal").alias("registered_at"),
        "gold",
        "research_points",
        pl.col("formOfGovernment").alias("government_form"),
        "gender",
        pl.col("Spieldauer").alias("account_age_days"),
        pl.col("duration_adjustment").alias("account_age_adjustment_factor"),
    )

    city_agg = city3_av.select(
        pl.col("owner_id").alias("player_id"),
        "snapshot_id",
        pl.col("total_islands").alias("island_count"),
        pl.col("total_cities").alias("city_count"),
        pl.col("Buerger_Ges").alias("population_total"),
        pl.col("Holz_verbaut").alias("wood_in_buildings"),
        pl.col("Kristall_verbaut").alias("crystal_in_buildings"),
        pl.col("Stein_verbaut").alias("marble_in_buildings"),
        pl.col("Schwefel_verbaut").alias("sulfur_in_buildings"),
        pl.col("Wein_verbaut").alias("wine_in_buildings"),
        pl.col("Res_Ges_verbaut").alias("resources_in_buildings_total"),
        pl.col("Baumeister_Highscore").alias("building_resource_score"),
        pl.col("Res_Ges_lagernd").alias("resources_stored_total"),
        pl.col("Res_Ges_verb_lag").alias("resources_in_buildings_and_storage_total"),
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
            if dt.is_numeric() and c not in {"registered_at_unix"}
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
        pl.col("Holz_verbaut").alias("wood_in_buildings"),
        pl.col("Kristall_verbaut").alias("crystal_in_buildings"),
        pl.col("Stein_verbaut").alias("marble_in_buildings"),
        pl.col("Schwefel_verbaut").alias("sulfur_in_buildings"),
        pl.col("Wein_verbaut").alias("wine_in_buildings"),
        pl.col("Res_Ges_verbaut").alias("resources_in_buildings_total"),
        pl.col("Baumeister_Highscore").alias("building_resource_score"),
        pl.col("Holz_lagernd").alias("wood_stored"),
        pl.col("Kristall_lagernd").alias("crystal_stored"),
        pl.col("Stein_lagernd").alias("marble_stored"),
        pl.col("Schwefel_lagernd").alias("sulfur_stored"),
        pl.col("Wein_lagernd").alias("wine_stored"),
        pl.col("Res_Ges_lagernd").alias("resources_stored_total"),
        pl.col("Holz_Ges_verb_lag").alias("wood_total"),
        pl.col("Kristall_Ges_verb_lag").alias("crystal_total"),
        pl.col("Stein_Ges_verb_lag").alias("marble_total"),
        pl.col("Schwefel_Ges_verb_lag").alias("sulfur_total"),
        pl.col("Wein_Ges_verb_lag").alias("wine_total"),
        pl.col("Res_Ges_verb_lag").alias("resources_in_buildings_and_storage_total"),
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
        pl.col("Holz_verbaut").alias("wood_in_buildings"),
        pl.col("Res_Ges_verbaut").alias("resources_in_buildings_total"),
        pl.col("Baumeister_Highscore").alias("building_resource_score"),
        pl.col("Res_Ges_lagernd").alias("resources_stored_total"),
        pl.col("Res_Ges_verb_lag").alias("resources_in_buildings_and_storage_total"),
        pl.col("Geblev").alias("building_levels_total"),
        pl.col("Avg_Buerger_per_player").alias("avg_population_per_player"),
        pl.col("Avg_Baumeister_per_player").alias(
            "avg_building_resource_score_per_player"
        ),
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
