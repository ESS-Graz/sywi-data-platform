"""Step 05: derive city-level columns (resources built/stored, population, levels).

Mirrors these legacy SQL operations:

  calculate_city_building_cost_totals
    Sum g{i}{res} into `{res}_verbaut`; set `Baumeister_Highscore` to the
    UNADJUSTED sum of the five _verbaut cols. Legacy SQL name: Q14.

  apply_account_age_resource_adjustment
    Apply duration-band factor (1.00 / 0.98 / 0.94 / 0.86, with "gap"
    boundary values keeping 1.0) to each `{res}_verbaut` in place.
    Legacy SQL name: Q15.

  calculate_city_resource_and_population_totals
    Compute `Res_Ges_verbaut` as sum of ADJUSTED verbaut, plus
    `{res}_Ges_verb_lag = {res}_verbaut + {res}_lagernd`, etc.
    Legacy SQL name: Q16.

Input: city_with_costs, avatar_enriched.
Output: city_enriched — per-city detail. Aggregated to player-island grain
in step 06.
"""

from __future__ import annotations

import polars as pl

from ..utils import safe_percent


def _cost_cols(suffix: str) -> list[pl.Expr]:
    return [pl.col(f"g{i}{suffix}") for i in range(1, 18)]


def _level_cols() -> list[pl.Expr]:
    return [pl.col(f"p{i}l") for i in range(1, 18)]


def compute_city_metrics(
    city_with_costs: pl.DataFrame, avatar_enriched: pl.DataFrame
) -> pl.DataFrame:
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

    # --- Building cost totals: sum unadjusted cost cols; set Baumeister_Highscore. ---
    df = df.with_columns(
        pl.sum_horizontal(_cost_cols("h")).alias("Holz_verbaut"),
        pl.sum_horizontal(_cost_cols("k")).alias("Kristall_verbaut"),
        pl.sum_horizontal(_cost_cols("q")).alias("Stein_verbaut"),
        pl.sum_horizontal(_cost_cols("s")).alias("Schwefel_verbaut"),
        pl.sum_horizontal(_cost_cols("w")).alias("Wein_verbaut"),
    )
    df = df.with_columns(
        (
            pl.col("Holz_verbaut")
            + pl.col("Kristall_verbaut")
            + pl.col("Stein_verbaut")
            + pl.col("Schwefel_verbaut")
            + pl.col("Wein_verbaut")
        ).alias("Baumeister_Highscore")
    )

    # --- Stored resource totals (depend only on raw tradegood cols). ---
    df = df.with_columns(
        pl.col("resource").alias("Holz_lagernd"),
        pl.col("tradegood1").alias("Wein_lagernd"),
        pl.col("tradegood2").alias("Stein_lagernd"),
        pl.col("tradegood3").alias("Kristall_lagernd"),
        pl.col("tradegood4").alias("Schwefel_lagernd"),
    )
    df = df.with_columns(
        (
            pl.col("Wein_lagernd")
            + pl.col("Stein_lagernd")
            + pl.col("Kristall_lagernd")
            + pl.col("Schwefel_lagernd")
        ).alias("QKWS_lagernd")
    )
    df = df.with_columns(
        (pl.col("Holz_lagernd") + pl.col("QKWS_lagernd")).alias("Res_Ges_lagernd")
    )

    # --- Join avatar data (needed for account-age resource adjustment). ---
    avatar_slice = avatar_enriched.select(
        pl.col("id").alias("owner_id"),
        pl.col("snapshot_id"),
        pl.col("duration_adjustment").alias("avatar_duration_adjustment"),
        pl.col("Spieldauer").alias("avatar_Spieldauer"),
    )
    df = df.join(avatar_slice, on=["owner_id", "snapshot_id"], how="left")

    # --- Account-age resource adjustment: apply band factor to each *_verbaut. ---
    # Cities with no matching avatar (shouldn't normally happen) keep factor 1.0.
    adj = pl.col("avatar_duration_adjustment").fill_null(1.0)
    df = df.with_columns(
        (pl.col("Holz_verbaut") * adj).alias("Holz_verbaut"),
        (pl.col("Kristall_verbaut") * adj).alias("Kristall_verbaut"),
        (pl.col("Stein_verbaut") * adj).alias("Stein_verbaut"),
        (pl.col("Schwefel_verbaut") * adj).alias("Schwefel_verbaut"),
        (pl.col("Wein_verbaut") * adj).alias("Wein_verbaut"),
    )

    # --- City resource totals using adjusted verbaut. ---
    df = df.with_columns(
        (
            pl.col("Holz_verbaut")
            + pl.col("Kristall_verbaut")
            + pl.col("Stein_verbaut")
            + pl.col("Schwefel_verbaut")
            + pl.col("Wein_verbaut")
        ).alias("Res_Ges_verbaut")
    )
    df = df.with_columns(
        (pl.col("Holz_verbaut") + pl.col("Holz_lagernd")).alias("Holz_Ges_verb_lag"),
        (pl.col("Kristall_verbaut") + pl.col("Kristall_lagernd")).alias("Kristall_Ges_verb_lag"),
        (pl.col("Stein_verbaut") + pl.col("Stein_lagernd")).alias("Stein_Ges_verb_lag"),
        (pl.col("Schwefel_verbaut") + pl.col("Schwefel_lagernd")).alias("Schwefel_Ges_verb_lag"),
        (pl.col("Wein_verbaut") + pl.col("Wein_lagernd")).alias("Wein_Ges_verb_lag"),
    )
    df = df.with_columns(
        (pl.col("Res_Ges_verbaut") + pl.col("Res_Ges_lagernd")).alias("Res_Ges_verb_lag")
    )

    # --- Population, worker totals, building levels. ---
    df = df.with_columns(
        (
            pl.col("citizens")
            + pl.col("resource_workers")
            + pl.col("tradegood_workers")
            + pl.col("scientists")
            + pl.col("priests")
        ).alias("Buerger_Ges"),
        (pl.col("resource_workers") + pl.col("tradegood_workers")).alias("Resworkers_Holz_Lux"),
    )
    df = df.with_columns(
        pl.sum_horizontal(_level_cols()).alias("Geblev"),
        pl.col("level").alias("Rathauslev"),
        pl.lit(0, dtype=pl.Int64).alias("GovReslev"),
    )
    df = df.with_columns(
        safe_percent(pl.col("resource_workers"), pl.col("Buerger_Ges")).alias(
            "Proz_resource_workers_pro_Buerger_Ges"
        ),
        safe_percent(pl.col("tradegood_workers"), pl.col("Buerger_Ges")).alias(
            "Proz_tradegood_workers_pro_Buerger_Ges"
        ),
    )

    # --- Per-avatar / per-snapshot counts and broadcast averages. ---
    df = df.with_columns(
        pl.len().over(["owner_id", "snapshot_id"]).alias("Anz_Cities_per_Av"),
        pl.col("island_id").n_unique().over(["owner_id", "snapshot_id"]).alias("Anz_Ins_per_Av"),
        pl.len().over("snapshot_id").alias("Anz_Cities_per_DB"),
    )
    avg_cols = {
        "Avg_Buerger_Ges": "Buerger_Ges",
        "Avg_Holz_Ges_verb_lag": "Holz_Ges_verb_lag",
        "Avg_Kristall_Ges_verb_lag": "Kristall_Ges_verb_lag",
        "Avg_Stein_Ges_verb_lag": "Stein_Ges_verb_lag",
        "Avg_Schwefel_Ges_verb_lag": "Schwefel_Ges_verb_lag",
        "Avg_Wein_Ges_verb_lag": "Wein_Ges_verb_lag",
        "Avg_Rathauslev": "Rathauslev",
        "Avg_Res_Ges_verb_lag": "Res_Ges_verb_lag",
        "Avg_Resource_workers": "resource_workers",
        "Avg_Tradegood_workers": "tradegood_workers",
        "Avg_Anz_cities_per_Av": "Anz_Cities_per_Av",
    }
    df = df.with_columns(
        [
            pl.col(src).mean().over(["owner_id", "snapshot_id"]).alias(dst)
            for dst, src in avg_cols.items()
        ]
    )

    return df
