"""Step 06: aggregate city_enriched to player-island grain.

Group by (owner_id, island_id, snapshot_id) with rules:
- SUM: population, resources built/stored/combined, building levels, capital count
- FIRST: snapshot_date, country, the pre-broadcast per-avatar/DB counts
- MEAN: worker percentages (then recalculated from summed values)
Adds cities_on_island = count of cities in group, then per-avatar means.
"""

from __future__ import annotations

import polars as pl

from ..utils import safe_percent

SUM_COLUMNS: tuple[str, ...] = (
    "citizens", "scientists", "priests", "resource_workers", "tradegood_workers",
    "Buerger_Ges", "Resworkers_Holz_Lux",
    "Holz_verbaut", "Kristall_verbaut", "Stein_verbaut", "Schwefel_verbaut", "Wein_verbaut",
    "Holz_verbaut_adj", "Kristall_verbaut_adj", "Stein_verbaut_adj",
    "Schwefel_verbaut_adj", "Wein_verbaut_adj",
    "Res_Ges_verbaut", "Baumeister_Highscore", "Baumeister_Highscore_adj",
    "Holz_lagernd", "Kristall_lagernd", "Stein_lagernd", "Schwefel_lagernd", "Wein_lagernd",
    "QKWS_lagernd", "Res_Ges_lagernd",
    "Holz_Ges_verb_lag", "Kristall_Ges_verb_lag", "Stein_Ges_verb_lag",
    "Schwefel_Ges_verb_lag", "Wein_Ges_verb_lag", "Res_Ges_verb_lag",
    "Geblev", "Rathauslev", "GovReslev",
    "capital",
)

FIRST_COLUMNS: tuple[str, ...] = (
    "snapshot_date", "country",
    "Anz_Cities_per_Av", "Anz_Ins_per_Av", "Anz_Cities_per_DB",
    "avatar_duration_adjustment", "avatar_Spieldauer",
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
        "Avg_Holz_Ges_verb_lag": "Holz_Ges_verb_lag",
        "Avg_Kristall_Ges_verb_lag": "Kristall_Ges_verb_lag",
        "Avg_Stein_Ges_verb_lag": "Stein_Ges_verb_lag",
        "Avg_Schwefel_Ges_verb_lag": "Schwefel_Ges_verb_lag",
        "Avg_Wein_Ges_verb_lag": "Wein_Ges_verb_lag",
        "Avg_Rathauslev": "Rathauslev",
        "Avg_Res_Ges_verb_lag": "Res_Ges_verb_lag",
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
