"""Donation analytics at player-island-snapshot grain.

This is the canonical analytics layer for donation-derived ratios. It keeps
row-level facts and interpretable denominators together without copying the
legacy SQL's database-wide broadcast constants into every row.

Wonder donation resource columns are explicitly named `*_allocated`: the raw
donation data has a wonder total but not the exact eligible luxury good paid.
The allocation follows Ikariam's rule that miracles/wonders take resources not
produced on the island, split evenly across those eligible luxury goods.
"""

from __future__ import annotations

import polars as pl

from ..utils import safe_divide, safe_percent


def build_donation_analytics_player_island_snapshot(
    donation_enriched: pl.DataFrame,
    city_player_island: pl.DataFrame,
    player_enriched: pl.DataFrame,
) -> pl.DataFrame:
    """Build one row per player-island-snapshot with donation analytics.

    The input `donation_enriched` already contains synthetic zero rows for
    player-island-snapshot combinations that have cities but no donations, so
    this table can safely use its row set as the canonical donation-analysis
    grain.
    """
    base = donation_enriched.select(
        pl.col("avatar_id").alias("player_id"),
        "island_id",
        "snapshot_id",
        "snapshot_date",
        pl.col("country").alias("country_code"),
        pl.col("Don_Ges").alias("donations_total"),
        pl.col("Don_Saegewerk_Ges").alias("sawmill_donations_total"),
        pl.col("Don_Luxusminen_Ges").alias("luxury_mine_donations_total"),
        pl.col("Don_Wonder_Ges").alias("wonder_donations_total"),
        pl.col("Don_Luxus_Ges").alias("wonder_and_luxury_mine_donations_total"),
        pl.col("Don_Wonder_Wein").alias("wonder_wine_donations_allocated"),
        pl.col("Don_Wonder_Stein").alias("wonder_marble_donations_allocated"),
        pl.col("Don_Wonder_Kristall").alias("wonder_crystal_donations_allocated"),
        pl.col("Don_Wonder_Schwefel").alias("wonder_sulfur_donations_allocated"),
        pl.col("Don_Luxus_Wein").alias("luxury_mine_wine_donations"),
        pl.col("Don_Luxus_Stein").alias("luxury_mine_marble_donations"),
        pl.col("Don_Luxus_Kristall").alias("luxury_mine_crystal_donations"),
        pl.col("Don_Luxus_Schwefel").alias("luxury_mine_sulfur_donations"),
    )

    city = city_player_island.select(
        pl.col("owner_id").alias("player_id"),
        "island_id",
        "snapshot_id",
        pl.col("cities_on_island").alias("player_island_city_count"),
        pl.col("Buerger_Ges").alias("population_total"),
        pl.col("Rathauslev").alias("town_hall_levels_total"),
        pl.col("Geblev").alias("building_levels_total"),
        pl.col("resource_workers").alias("resource_workers_total"),
        pl.col("tradegood_workers").alias("tradegood_workers_total"),
        pl.col("priests").alias("priests_total"),
        pl.col("Holz_Ges_verb_lag").alias("wood_total"),
        pl.col("Wein_Ges_verb_lag").alias("wine_total"),
        pl.col("Stein_Ges_verb_lag").alias("marble_total"),
        pl.col("Kristall_Ges_verb_lag").alias("crystal_total"),
        pl.col("Schwefel_Ges_verb_lag").alias("sulfur_total"),
        pl.col("Res_Ges_verb_lag").alias("resources_total"),
    )
    player_keys = ["player_id", "snapshot_id"]
    island_keys = ["island_id", "snapshot_id"]
    city = city.with_columns(
        pl.col("player_island_city_count").sum().over(player_keys).alias("player_total_city_count"),
        pl.col("player_id").n_unique().over(island_keys).alias("island_player_count"),
        pl.col("player_island_city_count").sum().over(island_keys).alias("island_city_count"),
    )

    player = player_enriched.select(
        pl.col("id").alias("player_id"),
        "snapshot_id",
        pl.col("Spieldauer").alias("account_age_days"),
    )

    result = base.join(city, on=["player_id", "island_id", "snapshot_id"], how="left").join(
        player, on=["player_id", "snapshot_id"], how="left"
    )
    numeric_fill_columns = [
        column
        for column, dtype in zip(result.columns, result.dtypes, strict=True)
        if dtype.is_numeric()
    ]
    result = result.with_columns(pl.col(column).fill_null(0) for column in numeric_fill_columns)

    island_keys = ["country_code", "snapshot_id", "island_id"]
    result = result.with_columns(
        pl.col("donations_total").sum().over(island_keys).alias("island_donations_total"),
        pl.col("sawmill_donations_total").sum().over(island_keys).alias("island_sawmill_donations_total"),
        pl.col("luxury_mine_donations_total")
        .sum()
        .over(island_keys)
        .alias("island_luxury_mine_donations_total"),
        pl.col("wonder_donations_total").sum().over(island_keys).alias("island_wonder_donations_total"),
    )
    result = result.with_columns(
        safe_divide(pl.col("island_donations_total"), pl.col("island_player_count")).alias(
            "island_avg_donations_per_player"
        ),
        safe_divide(
            pl.col("island_sawmill_donations_total"), pl.col("island_player_count")
        ).alias("island_avg_sawmill_donations_per_player"),
        safe_divide(
            pl.col("island_luxury_mine_donations_total"), pl.col("island_player_count")
        ).alias("island_avg_luxury_mine_donations_per_player"),
        safe_divide(
            pl.col("island_wonder_donations_total"), pl.col("island_player_count")
        ).alias("island_avg_wonder_donations_per_player"),
        safe_divide(
            pl.col("island_donations_total") - pl.col("donations_total"),
            pl.col("island_player_count") - 1,
        ).alias("island_peer_donations_avg"),
        safe_divide(
            pl.col("island_sawmill_donations_total") - pl.col("sawmill_donations_total"),
            pl.col("island_player_count") - 1,
        ).alias("island_peer_sawmill_donations_avg"),
        safe_divide(
            pl.col("island_luxury_mine_donations_total") - pl.col("luxury_mine_donations_total"),
            pl.col("island_player_count") - 1,
        ).alias("island_peer_luxury_mine_donations_avg"),
        safe_divide(
            pl.col("island_wonder_donations_total") - pl.col("wonder_donations_total"),
            pl.col("island_player_count") - 1,
        ).alias("island_peer_wonder_donations_avg"),
    )
    result = result.with_columns(
        (pl.col("donations_total") - pl.col("island_peer_donations_avg")).alias(
            "donations_minus_island_peer_avg"
        ),
        safe_percent(pl.col("sawmill_donations_total"), pl.col("donations_total")).alias(
            "sawmill_donation_share_pct"
        ),
        safe_percent(pl.col("luxury_mine_donations_total"), pl.col("donations_total")).alias(
            "luxury_mine_donation_share_pct"
        ),
        safe_percent(pl.col("wonder_donations_total"), pl.col("donations_total")).alias(
            "wonder_donation_share_pct"
        ),
        safe_divide(pl.col("donations_total"), pl.col("player_island_city_count")).alias(
            "donations_per_city"
        ),
        safe_divide(pl.col("donations_total"), pl.col("population_total")).alias(
            "donations_per_citizen"
        ),
        safe_divide(pl.col("donations_total"), pl.col("town_hall_levels_total")).alias(
            "donations_per_town_hall_level"
        ),
        safe_divide(pl.col("sawmill_donations_total"), pl.col("resource_workers_total")).alias(
            "sawmill_donations_per_resource_worker"
        ),
        safe_divide(
            pl.col("luxury_mine_donations_total"), pl.col("tradegood_workers_total")
        ).alias("luxury_mine_donations_per_tradegood_worker"),
        safe_divide(pl.col("wonder_donations_total"), pl.col("priests_total")).alias(
            "wonder_donations_per_priest"
        ),
        safe_divide(pl.col("donations_total"), pl.col("account_age_days")).alias(
            "donations_per_account_age_day"
        ),
    )
    result = result.with_columns(
        safe_percent(
            pl.col("sawmill_donations_total") + pl.col("luxury_mine_donations_total"),
            pl.col("wood_total")
            + pl.col("sawmill_donations_total")
            + pl.col("luxury_mine_donations_total"),
        ).alias("wood_donation_resource_share_pct"),
        safe_percent(
            pl.col("wonder_wine_donations_allocated"),
            pl.col("wine_total") + pl.col("wonder_wine_donations_allocated"),
        ).alias("wine_wonder_donation_resource_share_pct"),
        safe_percent(
            pl.col("wonder_marble_donations_allocated"),
            pl.col("marble_total") + pl.col("wonder_marble_donations_allocated"),
        ).alias("marble_wonder_donation_resource_share_pct"),
        safe_percent(
            pl.col("wonder_crystal_donations_allocated"),
            pl.col("crystal_total") + pl.col("wonder_crystal_donations_allocated"),
        ).alias("crystal_wonder_donation_resource_share_pct"),
        safe_percent(
            pl.col("wonder_sulfur_donations_allocated"),
            pl.col("sulfur_total") + pl.col("wonder_sulfur_donations_allocated"),
        ).alias("sulfur_wonder_donation_resource_share_pct"),
        safe_percent(
            pl.col("donations_total"),
            pl.col("resources_total") + pl.col("donations_total"),
        ).alias("donations_resource_share_pct"),
    )

    return result.sort(["player_id", "island_id", "snapshot_date", "snapshot_id"])
