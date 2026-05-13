"""Step 07: process donations with wonder splits and synthetic zero rows.

**Audited logic** (from pipeline_v1/R/07_donation_processing.R lines 53 and 64):
donation aggregation groups on (avatar_id, island_id, snapshot_id) only —
NOT with extra snapshot_date/country columns. The commented-out versions
in the R source are pre-audit and must not be used.

Donation types: 1=Wonder, 2=Sawmill (Saegewerk), 3=Luxury mine (Luxusminen).
Wonder donations split by island's tradegood (matching ~33.3%, non-matching
each ~22.2%; null tradegood → uniform 25% per resource).
Cities with no donations get synthetic zero rows inserted.
"""

from __future__ import annotations

import polars as pl

from ..config import Config
from ..utils import safe_percent


def process_donations(
    donation_raw: pl.DataFrame,
    city_player_island: pl.DataFrame,
    island_raw: pl.DataFrame,
    cfg: Config,
) -> pl.DataFrame:
    work = donation_raw.with_columns(
        pl.col("type").cast(pl.Int64, strict=False),
        pl.col("gold").cast(pl.Float64, strict=False).fill_null(0.0),
    ).with_columns(
        pl.when(pl.col("type") == 1).then(pl.col("gold")).otherwise(0.0).alias("Don_Wonder"),
        pl.when(pl.col("type") == 2).then(pl.col("gold")).otherwise(0.0).alias("Don_Saegewerk"),
        pl.when(pl.col("type") == 3).then(pl.col("gold")).otherwise(0.0).alias("Don_Luxusminen"),
        pl.col("gold").alias("Don_Ges_raw"),
    )

    # AUDITED grouping: (avatar_id, island_id, snapshot_id) only.
    agg = work.group_by(["avatar_id", "island_id", "snapshot_id"]).agg(
        pl.col("Don_Wonder").sum().alias("Don_Wonder_Ges"),
        pl.col("Don_Saegewerk").sum().alias("Don_Saegewerk_Ges"),
        pl.col("Don_Luxusminen").sum().alias("Don_Luxusminen_Ges"),
        pl.col("Don_Ges_raw").sum().alias("Don_Ges"),
        pl.len().alias("donation_records"),
    )

    # city_keys = every (avatar, island, snapshot) where the avatar has a city.
    # AUDITED: keyed on (owner_id, island_id, snapshot_id) only.
    city_keys = (
        city_player_island.select(
            pl.col("owner_id").alias("avatar_id"),
            pl.col("island_id"),
            pl.col("snapshot_id"),
        )
        .unique()
    )

    # Filter donations without a matching city. Legacy SQL name:
    # Q29_Delete_Donations_without_city. This is why donations targeting
    # islands the avatar doesn't occupy (e.g. wonder gifts to foreign islands)
    # don't contribute to A_DS aggregates.
    agg = agg.join(
        city_keys, on=["avatar_id", "island_id", "snapshot_id"], how="semi"
    )

    # Add synthetic zero-donation rows. Legacy SQL name: Q19_Create_NoDons.
    # This keeps the A_DS/I_DS denominators correct for avatar-island-snapshot
    # triples with cities but no donations.
    missing = city_keys.join(
        agg.select(["avatar_id", "island_id", "snapshot_id"]),
        on=["avatar_id", "island_id", "snapshot_id"],
        how="anti",
    )
    if missing.height > 0:
        zeros = missing.with_columns(
            pl.lit(0.0).alias("Don_Wonder_Ges"),
            pl.lit(0.0).alias("Don_Saegewerk_Ges"),
            pl.lit(0.0).alias("Don_Luxusminen_Ges"),
            pl.lit(0.0).alias("Don_Ges"),
            pl.lit(0, dtype=pl.UInt32).alias("donation_records"),
        )
        agg = pl.concat([agg, zeros], how="diagonal_relaxed")

    # Attach island tradegood for wonder split.
    island_tradegood = island_raw.select(
        pl.col("id").alias("island_id"),
        pl.col("tradegood").cast(pl.Int64, strict=False).alias("island_tradegood"),
        pl.col("snapshot_id"),
    ).unique(subset=["island_id", "snapshot_id"])
    agg = agg.join(island_tradegood, on=["island_id", "snapshot_id"], how="left")

    # Split wonder donations by resource. Legacy SQL name: Q22. For each
    # resource R, SQL sets
    # `Don_Wonder_Anteil_R = Don_Wonder_Ges * (1 - 0.666667) ≈ 0.333`
    # ONLY when `island.tradegood != R`; the matching-tradegood resource and
    # any null-tradegood row stay at 0. Total = 3 × 0.333 = 1.0 across the
    # three non-matching resources. (V1 R inverted this — matching got
    # 0.333, non-matching got 0.222 each. Neither of the individual share
    # columns is in our final outputs, so the per-resource totals are
    # internal-only, but this matches SQL for alignment.)
    f = cfg.wonder_split_factor
    non_match_share = 1.0 - f  # ≈ 0.333

    def wonder_share(res_code: int) -> pl.Expr:
        return (
            pl.when(pl.col("island_tradegood").is_null())
            .then(pl.lit(0.0))
            .when(pl.col("island_tradegood") == res_code)
            .then(pl.lit(0.0))
            .otherwise(pl.col("Don_Wonder_Ges") * non_match_share)
        )

    agg = agg.with_columns(
        wonder_share(1).alias("Don_Wonder_Wein"),
        wonder_share(2).alias("Don_Wonder_Stein"),
        wonder_share(3).alias("Don_Wonder_Kristall"),
        wonder_share(4).alias("Don_Wonder_Schwefel"),
    )

    # Luxury mine donation goes entirely to the island's tradegood resource.
    def luxus_share(res_code: int) -> pl.Expr:
        return (
            pl.when(pl.col("island_tradegood") == res_code)
            .then(pl.col("Don_Luxusminen_Ges"))
            .otherwise(0.0)
        )

    agg = agg.with_columns(
        luxus_share(1).alias("Don_Luxus_Wein"),
        luxus_share(2).alias("Don_Luxus_Stein"),
        luxus_share(3).alias("Don_Luxus_Kristall"),
        luxus_share(4).alias("Don_Luxus_Schwefel"),
    )

    agg = agg.with_columns(
        (pl.col("Don_Wonder_Wein") + pl.col("Don_Luxus_Wein")).alias("Don_Wein_Ges"),
        (pl.col("Don_Wonder_Stein") + pl.col("Don_Luxus_Stein")).alias("Don_Stein_Ges"),
        (pl.col("Don_Wonder_Kristall") + pl.col("Don_Luxus_Kristall")).alias("Don_Kristall_Ges"),
        (pl.col("Don_Wonder_Schwefel") + pl.col("Don_Luxus_Schwefel")).alias("Don_Schwefel_Ges"),
    )
    # Algebraically Don_Wein + Don_Stein + Don_Kristall + Don_Schwefel
    # == Don_Wonder_Ges + Don_Luxusminen_Ges exactly (wonder split sums to 1).
    # Computing the shortcut avoids O(1e-16) float error that V1 R's sum happened
    # to dodge. The difference matters because the A_DS output column is Int64.
    agg = agg.with_columns(
        (pl.col("Don_Wonder_Ges") + pl.col("Don_Luxusminen_Ges")).alias("Don_Luxus_Ges")
    )

    agg = agg.with_columns(
        safe_percent(pl.col("Don_Wonder_Ges"), pl.col("Don_Ges")).alias("Don_Wonder_Proz"),
        safe_percent(pl.col("Don_Saegewerk_Ges"), pl.col("Don_Ges")).alias("Don_Saegewerk_Proz"),
        safe_percent(pl.col("Don_Luxusminen_Ges"), pl.col("Don_Ges")).alias("Don_Luxusminen_Proz"),
    )

    # Attach snapshot_date and country back for downstream aggregations.
    snap_meta = (
        city_player_island.select(["snapshot_id", "snapshot_date", "country"])
        .unique(subset=["snapshot_id"])
    )
    agg = agg.join(snap_meta, on="snapshot_id", how="left")

    return agg
