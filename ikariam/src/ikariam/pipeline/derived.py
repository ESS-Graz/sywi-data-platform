"""Derived latest and summary tables computed from the three snapshot tables.

These used to be materialized in DuckDB via `sql/views.sql`. They now run
natively in polars (~5-10x faster on our data sizes) and land as Lance
tables alongside the snapshot tables: one storage format, one reader API.

Semantics match the old SQL:

  *_latest:   latest row per entity (sort by snapshot_date desc, snapshot_id
              desc as deterministic tie-break; exactly `ROW_NUMBER() = 1`).
  *_summary:  per-entity aggregates: snapshots_observed_count,
              first_snapshot_date, last_snapshot_date, observation_span_days
              (+ registered_at_unix for players, SUM of
              player_city_count_on_island for player_islands).

`player_island_latest` special case: (player, island) measurements come
from the last week the player was active on that island, but the island
metadata (luxury_resource_type, wonder_type_id, levels, city_count) comes from the
island's own latest snapshot. Legacy SQL name: Q45 latest-island join.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True, slots=True)
class DerivedTables:
    player_latest: pl.DataFrame
    player_island_latest: pl.DataFrame
    island_latest: pl.DataFrame
    player_summary: pl.DataFrame
    player_island_summary: pl.DataFrame
    island_summary: pl.DataFrame


def _latest_per(panel: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    """Row with max (snapshot_date, snapshot_id) per `keys`."""
    return (
        panel.sort(["snapshot_date", "snapshot_id"])
        .group_by(keys, maintain_order=True)
        .last()
    )


def _compute_island_latest(island_snapshot: pl.DataFrame) -> pl.DataFrame:
    return _latest_per(island_snapshot, ["country_code", "island_id"])


def _compute_player_latest(player_snapshot: pl.DataFrame) -> pl.DataFrame:
    return _latest_per(player_snapshot, ["country_code", "player_id"])


def _compute_player_island_latest(
    player_island_snapshot: pl.DataFrame, island_latest: pl.DataFrame
) -> pl.DataFrame:
    ai_last = _latest_per(
        player_island_snapshot, ["country_code", "player_id", "island_id"]
    )
    # Replace the per-(player, island) island-metadata columns with the
    # island's own latest snapshot (legacy SQL Q45 latest-island join).
    overlapping = [
        "wonder_type_id", "luxury_resource_type", "luxury_mine_level",
        "sawmill_level", "island_city_count",
    ]
    ai_last = ai_last.drop([c for c in overlapping if c in ai_last.columns])
    isl_meta = island_latest.select(
        "country_code",
        "island_id",
        "wonder_type_id",
        "luxury_resource_type",
        "luxury_mine_level",
        "sawmill_level",
        pl.col("raw_city_count").alias("island_city_count"),
    )
    return ai_last.join(isl_meta, on=["country_code", "island_id"], how="left")


def _compute_player_summary(player_snapshot: pl.DataFrame) -> pl.DataFrame:
    return (
        player_snapshot.group_by(["country_code", "player_id"])
        .agg(
            pl.col("snapshot_id").n_unique().alias("snapshots_observed_count"),
            pl.col("snapshot_date").min().alias("first_snapshot_date"),
            pl.col("snapshot_date").max().alias("last_snapshot_date"),
            pl.col("registered_at_unix").min(),
        )
        .with_columns(
            (pl.col("last_snapshot_date") - pl.col("first_snapshot_date"))
            .dt.total_days()
            .alias("observation_span_days")
        )
    )


def _compute_player_island_summary(player_island_snapshot: pl.DataFrame) -> pl.DataFrame:
    return (
        player_island_snapshot.group_by(["country_code", "player_id", "island_id"])
        .agg(
            pl.col("snapshot_id").n_unique().alias("snapshots_observed_count"),
            pl.col("snapshot_date").min().alias("first_snapshot_date"),
            pl.col("snapshot_date").max().alias("last_snapshot_date"),
            pl.col("player_city_count_on_island")
            .sum()
            .alias("player_city_observation_count"),
        )
    )


def _compute_island_summary(island_snapshot: pl.DataFrame) -> pl.DataFrame:
    return (
        island_snapshot.group_by(["country_code", "island_id"])
        .agg(
            pl.col("snapshot_id").n_unique().alias("snapshots_observed_count"),
            pl.col("snapshot_date").min().alias("first_snapshot_date"),
            pl.col("snapshot_date").max().alias("last_snapshot_date"),
        )
    )


def build_derived(
    player_snapshot: pl.DataFrame,
    player_island_snapshot: pl.DataFrame,
    island_snapshot: pl.DataFrame,
) -> DerivedTables:
    island_latest = _compute_island_latest(island_snapshot)
    return DerivedTables(
        player_latest=_compute_player_latest(player_snapshot),
        player_island_latest=_compute_player_island_latest(
            player_island_snapshot, island_latest
        ),
        island_latest=island_latest,
        player_summary=_compute_player_summary(player_snapshot),
        player_island_summary=_compute_player_island_summary(player_island_snapshot),
        island_summary=_compute_island_summary(island_snapshot),
    )
