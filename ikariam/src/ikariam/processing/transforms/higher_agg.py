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


def aggregate_by_avatar(city_player_island: pl.DataFrame) -> pl.DataFrame:
    g = city_player_island.group_by(
        ["owner_id", "snapshot_id", "snapshot_date", "country"]
    ).agg(
        pl.col("island_id").n_unique().alias("total_islands"),
        pl.col("cities_on_island").sum().alias("total_cities"),
        pl.col("citizens").sum().alias("citizens"),
        pl.col("scientists").sum().alias("scientists"),
        pl.col("priests").sum().alias("priests"),
        pl.col("resource_workers").sum().alias("resource_workers"),
        pl.col("tradegood_workers").sum().alias("tradegood_workers"),
        pl.col("Buerger_Ges").sum().alias("Buerger_Ges"),
        pl.col("Holz_verbaut").sum().alias("Holz_verbaut"),
        pl.col("Kristall_verbaut").sum().alias("Kristall_verbaut"),
        pl.col("Stein_verbaut").sum().alias("Stein_verbaut"),
        pl.col("Schwefel_verbaut").sum().alias("Schwefel_verbaut"),
        pl.col("Wein_verbaut").sum().alias("Wein_verbaut"),
        pl.col("Res_Ges_verbaut").sum().alias("Res_Ges_verbaut"),
        pl.col("Baumeister_Highscore").sum().alias("Baumeister_Highscore"),
        pl.col("Holz_lagernd").sum().alias("Holz_lagernd"),
        pl.col("Kristall_lagernd").sum().alias("Kristall_lagernd"),
        pl.col("Stein_lagernd").sum().alias("Stein_lagernd"),
        pl.col("Schwefel_lagernd").sum().alias("Schwefel_lagernd"),
        pl.col("Wein_lagernd").sum().alias("Wein_lagernd"),
        pl.col("Res_Ges_lagernd").sum().alias("Res_Ges_lagernd"),
        pl.col("Holz_Ges_verb_lag").sum().alias("Holz_Ges_verb_lag"),
        pl.col("Kristall_Ges_verb_lag").sum().alias("Kristall_Ges_verb_lag"),
        pl.col("Stein_Ges_verb_lag").sum().alias("Stein_Ges_verb_lag"),
        pl.col("Schwefel_Ges_verb_lag").sum().alias("Schwefel_Ges_verb_lag"),
        pl.col("Wein_Ges_verb_lag").sum().alias("Wein_Ges_verb_lag"),
        pl.col("Res_Ges_verb_lag").sum().alias("Res_Ges_verb_lag"),
        pl.col("Geblev").sum().alias("Geblev"),
        pl.col("Rathauslev").sum().alias("Rathauslev"),
        pl.col("Buerger_Ges").mean().alias("Avg_Buerger_Ges"),
        pl.col("Holz_Ges_verb_lag").mean().alias("Avg_Holz_Ges_verb_lag"),
        pl.col("Baumeister_Highscore").mean().alias("Avg_Baumeister"),
    )
    return g.with_columns(
        safe_percent(pl.col("resource_workers"), pl.col("Buerger_Ges")).alias(
            "Proz_resource_workers"
        ),
        safe_percent(pl.col("tradegood_workers"), pl.col("Buerger_Ges")).alias(
            "Proz_tradegood_workers"
        ),
    )


def aggregate_by_island(city_player_island: pl.DataFrame) -> pl.DataFrame:
    return city_player_island.group_by(
        ["island_id", "snapshot_id", "snapshot_date", "country"]
    ).agg(
        pl.col("owner_id").n_unique().alias("total_players"),
        pl.col("cities_on_island").sum().alias("total_cities"),
        pl.col("citizens").sum().alias("citizens"),
        pl.col("scientists").sum().alias("scientists"),
        pl.col("priests").sum().alias("priests"),
        pl.col("resource_workers").sum().alias("resource_workers"),
        pl.col("tradegood_workers").sum().alias("tradegood_workers"),
        pl.col("Buerger_Ges").sum().alias("Buerger_Ges"),
        pl.col("Holz_verbaut").sum().alias("Holz_verbaut"),
        pl.col("Kristall_verbaut").sum().alias("Kristall_verbaut"),
        pl.col("Stein_verbaut").sum().alias("Stein_verbaut"),
        pl.col("Schwefel_verbaut").sum().alias("Schwefel_verbaut"),
        pl.col("Wein_verbaut").sum().alias("Wein_verbaut"),
        pl.col("Res_Ges_verbaut").sum().alias("Res_Ges_verbaut"),
        pl.col("Baumeister_Highscore").sum().alias("Baumeister_Highscore"),
        pl.col("Holz_lagernd").sum().alias("Holz_lagernd"),
        pl.col("Kristall_lagernd").sum().alias("Kristall_lagernd"),
        pl.col("Stein_lagernd").sum().alias("Stein_lagernd"),
        pl.col("Schwefel_lagernd").sum().alias("Schwefel_lagernd"),
        pl.col("Wein_lagernd").sum().alias("Wein_lagernd"),
        pl.col("Res_Ges_lagernd").sum().alias("Res_Ges_lagernd"),
        pl.col("Holz_Ges_verb_lag").sum().alias("Holz_Ges_verb_lag"),
        pl.col("Kristall_Ges_verb_lag").sum().alias("Kristall_Ges_verb_lag"),
        pl.col("Stein_Ges_verb_lag").sum().alias("Stein_Ges_verb_lag"),
        pl.col("Schwefel_Ges_verb_lag").sum().alias("Schwefel_Ges_verb_lag"),
        pl.col("Wein_Ges_verb_lag").sum().alias("Wein_Ges_verb_lag"),
        pl.col("Res_Ges_verb_lag").sum().alias("Res_Ges_verb_lag"),
        pl.col("Geblev").sum().alias("Geblev"),
        pl.col("Rathauslev").sum().alias("Rathauslev"),
        pl.col("Buerger_Ges").mean().alias("Avg_Buerger_per_player"),
        pl.col("Holz_Ges_verb_lag").mean().alias("Avg_Holz_per_player"),
        pl.col("Baumeister_Highscore").mean().alias("Avg_Baumeister_per_player"),
    )


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
