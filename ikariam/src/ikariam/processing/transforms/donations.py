"""Step 07: process donations with wonder splits and synthetic zero rows.

**Audited logic** (from pipeline_v1/R/07_donation_processing.R lines 53 and 64):
donation aggregation groups on (avatar_id, island_id, snapshot_id) only —
NOT with extra snapshot_date/country columns. The commented-out versions
in the R source are pre-audit and must not be used.

Donation types: 1=Wonder, 2=Sawmill (Saegewerk), 3=Luxury mine (Luxusminen).
Wonder donations are allocated evenly across the three luxury goods not
produced on the island (matching island tradegood gets 0).
Cities with no donations get synthetic zero rows inserted.
"""

from __future__ import annotations

import polars as pl

from ..config import Config


def split_donation_types(donation_raw: pl.DataFrame) -> pl.DataFrame:
    """Add one amount column per donation type (wonder, sawmill, luxury mine)."""
    return donation_raw.with_columns(
        pl.col("type").cast(pl.Int64, strict=False),
        pl.col("gold").cast(pl.Float64, strict=False).fill_null(0.0),
    ).with_columns(
        pl.when(pl.col("type") == 1).then(pl.col("gold")).otherwise(0.0).alias("Don_Wonder"),
        pl.when(pl.col("type") == 2).then(pl.col("gold")).otherwise(0.0).alias("Don_Saegewerk"),
        pl.when(pl.col("type") == 3).then(pl.col("gold")).otherwise(0.0).alias("Don_Luxusminen"),
        pl.col("gold").alias("Don_Ges_raw"),
    )


def process_donations(
    donation_raw: pl.DataFrame,
    city_player_island: pl.DataFrame,
    island_raw: pl.DataFrame,
    cfg: Config,
) -> pl.DataFrame:
    work = split_donation_types(donation_raw)

    # AUDITED grouping: (avatar_id, island_id, snapshot_id) only.
    agg = work.group_by(["avatar_id", "island_id", "snapshot_id"]).agg(
        pl.col("Don_Wonder").sum().alias("Don_Wonder_Ges"),
        pl.col("Don_Saegewerk").sum().alias("Don_Saegewerk_Ges"),
        pl.col("Don_Luxusminen").sum().alias("Don_Luxusminen_Ges"),
        pl.col("Don_Ges_raw").sum().alias("Don_Ges"),
    )

    # city_keys = every (player, island, snapshot) where the player has a city.
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
    # Q29_Delete_Donations_without_city. The raw amounts are running totals, so
    # an island the player has left (mostly a relocated city) keeps its old
    # amount; these rows have no city to attach to at player-island grain.
    # Player totals (higher_agg.donations_by_player) read the raw rows and keep them.
    agg = agg.join(
        city_keys, on=["avatar_id", "island_id", "snapshot_id"], how="semi"
    )

    # Add synthetic zero-donation rows. Legacy SQL name: Q19_Create_NoDons.
    # This keeps the A_DS/I_DS denominators correct for player-island-snapshot
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
        )

        agg = pl.concat([agg, zeros], how="diagonal_relaxed")

    # Attach island tradegood for wonder split.
    island_tradegood = island_raw.select(
        pl.col("id").alias("island_id"),
        pl.col("tradegood").cast(pl.Int64, strict=False).alias("island_tradegood"),
        pl.col("snapshot_id"),
    ).unique(subset=["island_id", "snapshot_id"])

    agg = agg.join(island_tradegood, on=["island_id", "snapshot_id"], how="left")

    # Split wonder donations by resource. Ikariam allows miracle/wonder
    # donations using resources that are not produced on the island. Since the
    # raw data has only a type=Wonder total, not the exact luxury good paid,
    # these fields are an equal allocation across eligible luxury goods.
    #
    # Legacy SQL name: Q22. For each resource R, SQL sets
    # `Don_Wonder_Anteil_R = Don_Wonder_Ges * (1 - 0.666667) ≈ 0.333`
    # ONLY when `island.tradegood != R`; the matching-tradegood resource and
    # any null-tradegood row stay at 0. Total = 3 × 0.333 = 1.0 across the
    # three non-matching resources.
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

    # Wonder plus luxury-mine donations, taken from the two totals directly
    # rather than by summing the eight per-resource allocations above.
    agg = agg.with_columns(
        (pl.col("Don_Wonder_Ges") + pl.col("Don_Luxusminen_Ges")).alias("Don_Luxus_Ges")
    )

    # Attach snapshot_date, country and server back for downstream aggregations.
    snap_meta = (
        city_player_island.select(["snapshot_id", "snapshot_date", "country", "server"])
        .unique(subset=["snapshot_id"])
    )

    agg = agg.join(snap_meta, on="snapshot_id", how="left")

    return agg
