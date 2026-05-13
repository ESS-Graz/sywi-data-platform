"""Orchestrator: wire transforms top-to-bottom, write LanceDB + views.duckdb.

In a follow-up, this module gets replaced by a Dagster Definitions object
where each transform is an @asset. Keeping this thin so conversion is
mechanical.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from .config import Config
from .derived import build_derived
from .io_db import load_all_raw
from .io_files import read_building_costs
from .io_lance import write_lancedb
from .manifest import write_manifest
from .timing import timed
from .transforms.building_costs import join_building_costs
from .transforms.city_agg import aggregate_to_player_island
from .transforms.city_metrics import compute_city_metrics
from .transforms.donations import process_donations
from .transforms.final_datasets import PanelTables, build_panels
from .transforms.higher_agg import (
    aggregate_by_avatar,
    aggregate_by_island,
    donations_by_avatar,
    donations_by_island,
)
from .transforms.islands import enrich_islands
from .transforms.player_duration import enrich_avatars

logger = structlog.get_logger()


def _filter_prelaunch_players(raw, cfg: Config):
    """Drop players registered before the earliest server start.

    Legacy SQL name: Q28_Delete_Players. The filter also drops the affected
    cities and donations. It is applied at the raw level so every downstream
    aggregate sees the same valid-player set.

    The raw MariaDB entity is named `avatar`; public outputs call the same
    entity `player`.
    """
    import polars as pl

    from .io_db import RawTables

    threshold = cfg.min_registration_time
    valid = (
        raw.avatar.filter(pl.col("registration_time").cast(pl.Int64) >= threshold)
        .select("id")
        .unique()
    )
    avatar_f = raw.avatar.join(valid, on="id", how="semi")
    city_f = raw.city.join(valid.rename({"id": "owner_id"}), on="owner_id", how="semi")
    donation_f = raw.donation.join(valid.rename({"id": "avatar_id"}), on="avatar_id", how="semi")
    logger.info(
        "prelaunch_player_filter_applied",
        min_registration_time=threshold,
        avatar_rows_before=raw.avatar.height,
        avatar_rows_after=avatar_f.height,
        city_rows_before=raw.city.height,
        city_rows_after=city_f.height,
        donation_rows_before=raw.donation.height,
        donation_rows_after=donation_f.height,
    )
    return RawTables(avatar=avatar_f, city=city_f, donation=donation_f, island=raw.island)


def run_pipeline(cfg: Config, cache_dir: Path | None = None) -> PanelTables:
    with timed("load_raw"):
        logger.info("load_raw_start", snapshots=len(cfg.snapshots))
        raw = load_all_raw(cfg, cache_dir=cache_dir)
        raw_row_counts = {
            "avatar": raw.avatar.height,
            "city": raw.city.height,
            "donation": raw.donation.height,
            "island": raw.island.height,
        }

    with timed("filter_prelaunch_players"):
        raw = _filter_prelaunch_players(raw, cfg)

    with timed("read_building_costs"):
        building_costs = read_building_costs(cfg.building_costs_path)

    with timed("join_building_costs"):
        city_with_costs = join_building_costs(raw.city, building_costs)

    with timed("enrich_players"):
        player_enriched = enrich_avatars(raw.avatar, cfg)

    with timed("compute_city_metrics"):
        city_enriched = compute_city_metrics(city_with_costs, player_enriched)

    with timed("aggregate_to_player_island"):
        city_player_island = aggregate_to_player_island(city_enriched)

    with timed("process_donations"):
        donation_enriched = process_donations(raw.donation, city_player_island, raw.island, cfg)

    with timed("enrich_islands"):
        island_enriched = enrich_islands(raw.island, city_player_island, donation_enriched)

    with timed("higher_aggregations"):
        city3_av = aggregate_by_avatar(city_player_island)
        city4_i = aggregate_by_island(city_player_island)
        donation3_av = donations_by_avatar(donation_enriched)
        donation4_i = donations_by_island(donation_enriched)

    with timed("build_panels"):
        panels = build_panels(
            player_enriched=player_enriched,
            city_player_island=city_player_island,
            city3_av=city3_av,
            city4_i=city4_i,
            donation_enriched=donation_enriched,
            donation3_av=donation3_av,
            donation4_i=donation4_i,
            island_enriched=island_enriched,
        )

    with timed("build_derived"):
        derived = build_derived(
            player_snapshot=panels.player_snapshot,
            player_island_snapshot=panels.player_island_snapshot,
            island_snapshot=panels.island_snapshot,
        )

    all_tables = {
        "player_snapshot": panels.player_snapshot,
        "player_island_snapshot": panels.player_island_snapshot,
        "island_snapshot": panels.island_snapshot,
        "player_latest": derived.player_latest,
        "player_island_latest": derived.player_island_latest,
        "island_latest": derived.island_latest,
        "player_summary": derived.player_summary,
        "player_island_summary": derived.player_island_summary,
        "island_summary": derived.island_summary,
    }

    with timed("write_lancedb"):
        lancedb_path = write_lancedb(all_tables, cfg.output_dir)

    with timed("write_manifest"):
        row_counts = {name: df.height for name, df in all_tables.items()}
        write_manifest(cfg.output_dir, cfg, raw_row_counts, row_counts)

    logger.info(
        "pipeline_complete",
        player_snapshot_rows=panels.player_snapshot.height,
        player_island_snapshot_rows=panels.player_island_snapshot.height,
        island_snapshot_rows=panels.island_snapshot.height,
        lancedb=str(lancedb_path),
    )
    return panels
