"""Step 08: compute island upgrade costs and aggregate per-island stats.

- Wonder upgrade costs: levels 1-4 → cumulative costs [8800, 30800, 72600, 135500].
  Level 0 → cost of level 1. Level >= 4 → null.
- Resource / tradegood (sawmill / luxury mine) costs: level 1-49 via
  round(200 * 1.08^level * level).
- Sub_Noetig_nextlev_* = max(0, cost - donated), with null → 0.
- Aggregates city and donation data by island.
"""

from __future__ import annotations

import polars as pl

from ..utils import safe_divide, safe_percent

WONDER_COSTS: tuple[tuple[int, int], ...] = (
    (1, 8800),
    (2, 30800),
    (3, 72600),
    (4, 135500),
)


def _resource_cost_table() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "level": list(range(1, 50)),
            "cost": [round(200 * (1.08**lvl) * lvl) for lvl in range(1, 50)],
        }
    ).with_columns(pl.col("level").cast(pl.Int64), pl.col("cost").cast(pl.Int64))


def _wonder_cost_table() -> pl.DataFrame:
    return pl.DataFrame(
        {"level": [lvl for lvl, _ in WONDER_COSTS], "cost": [c for _, c in WONDER_COSTS]}
    ).with_columns(pl.col("level").cast(pl.Int64), pl.col("cost").cast(pl.Int64))


def enrich_islands(
    island_raw: pl.DataFrame,
    city_player_island: pl.DataFrame,
    donation_enriched: pl.DataFrame,
) -> pl.DataFrame:
    df = island_raw.with_columns(
        pl.col("wonder_level").cast(pl.Int64, strict=False),
        pl.col("resource_level").cast(pl.Int64, strict=False),
        pl.col("tradegood_level").cast(pl.Int64, strict=False),
        pl.col("wonder_donated").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("resource_donated").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("tradegood_donated").cast(pl.Float64, strict=False).fill_null(0.0),
        (pl.col("id") + pl.lit("_") + pl.col("snapshot_id")).alias("island_snapshot_key"),
    )

    wonder_costs = _wonder_cost_table().rename({"cost": "cost_Nextlev_wonder"})
    df = df.join(wonder_costs, left_on="wonder_level", right_on="level", how="left")
    df = df.with_columns(
        pl.when((pl.col("wonder_level") == 0) & pl.col("cost_Nextlev_wonder").is_null())
        .then(pl.lit(WONDER_COSTS[0][1]))
        .otherwise(pl.col("cost_Nextlev_wonder"))
        .alias("cost_Nextlev_wonder")
    )
    df = df.with_columns(
        pl.when(pl.col("wonder_level") >= 4)
        .then(None)
        .otherwise(pl.col("cost_Nextlev_wonder"))
        .alias("cost_Nextlev_wonder")
    )

    resource_costs = _resource_cost_table().rename({"cost": "cost_Nextlev_resource"})
    df = df.join(resource_costs, left_on="resource_level", right_on="level", how="left")

    tradegood_costs = _resource_cost_table().rename({"cost": "cost_Nextlev_tradegood"})
    df = df.join(tradegood_costs, left_on="tradegood_level", right_on="level", how="left")

    def remaining(cost: str, donated: str) -> pl.Expr:
        raw = pl.col(cost) - pl.col(donated)
        return (
            pl.when(pl.col(cost).is_null())
            .then(pl.lit(0.0))
            .otherwise(pl.max_horizontal(pl.lit(0.0), raw))
        )

    df = df.with_columns(
        remaining("cost_Nextlev_wonder", "wonder_donated").alias("Sub_Noetig_nextlev_wonder"),
        remaining("cost_Nextlev_resource", "resource_donated").alias("Sub_Noetig_nextlev_resource"),
        remaining("cost_Nextlev_tradegood", "tradegood_donated").alias(
            "Sub_Noetig_nextlev_tradegood"
        ),
    )

    city_agg = city_player_island.group_by(["island_id", "snapshot_id"]).agg(
        pl.col("Buerger_Ges").sum().alias("total_citizens"),
        pl.col("Holz_verbaut").sum().alias("total_holz_verbaut"),
        pl.col("Baumeister_Highscore").sum().alias("total_baumeister"),
        pl.col("cities_on_island").sum().alias("calc_city_count"),
        pl.col("owner_id").n_unique().alias("unique_players"),
        pl.col("Buerger_Ges").mean().alias("avg_citizens_per_player"),
        pl.col("Baumeister_Highscore").mean().alias("avg_baumeister_per_player"),
    )
    df = df.join(
        city_agg,
        left_on=["id", "snapshot_id"],
        right_on=["island_id", "snapshot_id"],
        how="left",
    )

    don_agg = donation_enriched.group_by(["island_id", "snapshot_id"]).agg(
        pl.col("Don_Ges").sum().alias("total_donations"),
        pl.col("Don_Wonder_Ges").sum().alias("total_wonder_donations"),
        pl.col("Don_Saegewerk_Ges").sum().alias("total_sawmill_donations"),
        pl.col("Don_Luxusminen_Ges").sum().alias("total_luxury_donations"),
        (pl.col("Don_Ges") > 0).sum().alias("donating_players"),
        pl.col("Don_Ges").mean().alias("avg_donation_per_player"),
    )
    df = df.join(
        don_agg,
        left_on=["id", "snapshot_id"],
        right_on=["island_id", "snapshot_id"],
        how="left",
    )

    df = df.with_columns(
        safe_percent(pl.col("donating_players"), pl.col("unique_players")).alias(
            "donation_participation_rate"
        ),
        safe_divide(pl.col("total_donations"), pl.col("calc_city_count")).alias(
            "avg_donation_per_city"
        ),
    )

    return df
