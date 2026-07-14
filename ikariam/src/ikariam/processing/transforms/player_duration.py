"""Step 04: avatar enrichment, Teilnahme_AV participation, Master_Avi backbone.

Three outputs:
- avatar_enriched: avatar_raw + Spieldauer_seconds, Spieldauer, Registration_time_normal,
  duration_adjustment, Anz_Av_per_DB, Avg_Spieldauer
- Teilnahme_AV: one row per avatar (across snapshots) with Anzahl_vorhanden,
  first_seen, last_seen, days_observed
- Master_Avi: one row per (owner_id, island_id) with Cities_Vorhanden,
  first_seen, last_seen, snapshots_present, Anzahl_Teilnahme
"""

from __future__ import annotations

import polars as pl

from ..config import Config
from ..utils import duration_adjustment_expr


def enrich_avatars(avatar_raw: pl.DataFrame, cfg: Config) -> pl.DataFrame:
    df = avatar_raw.with_columns(
        pl.col("registration_time").cast(pl.Int64, strict=False)
    )

    spieldauer_seconds = (pl.lit(cfg.reference_timestamp) - pl.col("registration_time")).cast(
        pl.Float64
    )

    df = df.with_columns(
        spieldauer_seconds.alias("Spieldauer_seconds"),
        (spieldauer_seconds / 86400.0).alias("Spieldauer"),
        # Match SQL's `FROM_UNIXTIME(registration_time)` output as it arrives
        # through connectorx → CSV: `YYYY-MM-DDTHH:MM:SS.000000` (T-separator,
        # 6-digit microseconds, server is UTC, NO `Z` suffix).
        pl.from_epoch(pl.col("registration_time"), time_unit="s")
        .dt.strftime("%Y-%m-%dT%H:%M:%S.000000")
        .alias("Registration_time_normal"),
    )

    df = df.with_columns(
        duration_adjustment_expr(pl.col("Spieldauer_seconds"), cfg.duration_adjustments).alias(
            "duration_adjustment"
        )
    )

    df = df.with_columns(
        pl.len().over("snapshot_id").alias("Anz_Av_per_DB"),
        pl.col("Spieldauer").mean().over("snapshot_id").alias("Avg_Spieldauer"),
    )

    return df


def build_teilnahme_av(avatar_enriched: pl.DataFrame) -> pl.DataFrame:
    grouped = (
        avatar_enriched.group_by("id")
        .agg(
            pl.col("snapshot_id").n_unique().alias("Anzahl_vorhanden"),
            pl.col("snapshot_date").min().alias("first_seen"),
            pl.col("snapshot_date").max().alias("last_seen"),
        )
        .rename({"id": "avatar_id"})
    )
    return grouped.with_columns(
        (pl.col("last_seen") - pl.col("first_seen")).dt.total_days().alias("days_observed")
    ).sort("avatar_id")


def build_master_avi(
    city_with_costs: pl.DataFrame, teilnahme_av: pl.DataFrame
) -> pl.DataFrame:
    grouped = city_with_costs.group_by(["owner_id", "island_id"]).agg(
        pl.len().alias("Cities_Vorhanden"),
        pl.col("snapshot_date").min().alias("first_seen"),
        pl.col("snapshot_date").max().alias("last_seen"),
        pl.col("snapshot_id").n_unique().alias("snapshots_present"),
    )

    joined = grouped.join(
        teilnahme_av.select(
            pl.col("avatar_id").alias("owner_id"),
            pl.col("Anzahl_vorhanden").alias("Anzahl_Teilnahme"),
        ),
        on="owner_id",
        how="left",
    ).with_columns(pl.col("Anzahl_Teilnahme").fill_null(0))

    return joined.sort(["owner_id", "island_id"])
