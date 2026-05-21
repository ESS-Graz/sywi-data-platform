"""Dagster assets for the Ikariam LanceDB pipeline."""

import polars as pl
from dagster import AssetExecutionContext, MaterializeResult, MetadataValue, asset

from ikariam.pipeline.config import get_config
from ikariam.pipeline.io_files import read_building_costs
from ikariam.pipeline.io_lance import partition_raw_tables_by_country, write_lancedb
from ikariam.pipeline.io_raw import load_raw_table
from ikariam.pipeline.transforms.building_costs import join_building_costs
from ikariam.pipeline.transforms.city_agg import aggregate_to_player_island
from ikariam.pipeline.transforms.city_metrics import compute_city_metrics
from ikariam.pipeline.transforms.donations import process_donations
from ikariam.pipeline.transforms.final_datasets import (
    build_city_snapshot_table,
    build_island_snapshot_table,
    build_player_snapshot_table,
)
from ikariam.pipeline.transforms.higher_agg import (
    aggregate_by_avatar,
    aggregate_by_island,
    donations_by_avatar,
    donations_by_island,
)
from ikariam.pipeline.transforms.islands import enrich_islands
from ikariam.pipeline.transforms.player_duration import enrich_avatars

RAW_GROUP = "ikariam_raw"
TRANSFORM_GROUP = "ikariam_transforms"
PUBLIC_GROUP = "ikariam_public"
EXPORT_GROUP = "ikariam_export"


def _add_df_metadata(context: AssetExecutionContext, df: pl.DataFrame) -> None:
    context.add_output_metadata(
        {
            "row_count": df.height,
            "column_count": len(df.columns),
        }
    )


@asset(group_name=RAW_GROUP)
def raw_avatar(context: AssetExecutionContext) -> pl.DataFrame:
    df = load_raw_table(get_config(), "avatar")
    _add_df_metadata(context, df)
    return df


@asset(group_name=RAW_GROUP)
def raw_city(context: AssetExecutionContext) -> pl.DataFrame:
    df = load_raw_table(get_config(), "city")
    _add_df_metadata(context, df)
    return df


@asset(group_name=RAW_GROUP)
def raw_donation(context: AssetExecutionContext) -> pl.DataFrame:
    df = load_raw_table(get_config(), "donation")
    _add_df_metadata(context, df)
    return df


@asset(group_name=RAW_GROUP)
def raw_island(context: AssetExecutionContext) -> pl.DataFrame:
    df = load_raw_table(get_config(), "island")
    _add_df_metadata(context, df)
    return df


@asset(group_name=RAW_GROUP)
def building_costs(context: AssetExecutionContext) -> pl.DataFrame:
    df = read_building_costs(get_config().building_costs_path)
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def valid_players(context: AssetExecutionContext, raw_avatar: pl.DataFrame) -> pl.DataFrame:
    cfg = get_config()
    df = (
        raw_avatar.filter(pl.col("registration_time").cast(pl.Int64) >= cfg.min_registration_time)
        .select("country", "id")
        .unique()
    )
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def filtered_avatar(
    context: AssetExecutionContext,
    raw_avatar: pl.DataFrame,
    valid_players: pl.DataFrame,
) -> pl.DataFrame:
    df = raw_avatar.join(valid_players, on=["country", "id"], how="semi")
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def filtered_city(
    context: AssetExecutionContext,
    raw_city: pl.DataFrame,
    valid_players: pl.DataFrame,
) -> pl.DataFrame:
    keys = valid_players.rename({"id": "owner_id"})
    df = raw_city.join(keys, on=["country", "owner_id"], how="semi")
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def filtered_donation(
    context: AssetExecutionContext,
    raw_donation: pl.DataFrame,
    valid_players: pl.DataFrame,
) -> pl.DataFrame:
    keys = valid_players.rename({"id": "avatar_id"})
    df = raw_donation.join(keys, on=["country", "avatar_id"], how="semi")
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def city_with_costs(
    context: AssetExecutionContext,
    filtered_city: pl.DataFrame,
    building_costs: pl.DataFrame,
) -> pl.DataFrame:
    df = join_building_costs(filtered_city, building_costs)
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def player_enriched(
    context: AssetExecutionContext,
    filtered_avatar: pl.DataFrame,
) -> pl.DataFrame:
    df = enrich_avatars(filtered_avatar, get_config())
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def city_enriched(
    context: AssetExecutionContext,
    city_with_costs: pl.DataFrame,
    player_enriched: pl.DataFrame,
) -> pl.DataFrame:
    df = compute_city_metrics(city_with_costs, player_enriched)
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def city_player_island(
    context: AssetExecutionContext,
    city_enriched: pl.DataFrame,
) -> pl.DataFrame:
    df = aggregate_to_player_island(city_enriched)
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def donation_enriched(
    context: AssetExecutionContext,
    filtered_donation: pl.DataFrame,
    city_player_island: pl.DataFrame,
    raw_island: pl.DataFrame,
) -> pl.DataFrame:
    df = process_donations(filtered_donation, city_player_island, raw_island, get_config())
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def island_enriched(
    context: AssetExecutionContext,
    raw_island: pl.DataFrame,
    city_player_island: pl.DataFrame,
    donation_enriched: pl.DataFrame,
) -> pl.DataFrame:
    df = enrich_islands(raw_island, city_player_island, donation_enriched)
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def city_by_player_snapshot(
    context: AssetExecutionContext,
    city_player_island: pl.DataFrame,
) -> pl.DataFrame:
    df = aggregate_by_avatar(city_player_island)
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def city_by_island_snapshot(
    context: AssetExecutionContext,
    city_player_island: pl.DataFrame,
) -> pl.DataFrame:
    df = aggregate_by_island(city_player_island)
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def donations_by_player_snapshot(
    context: AssetExecutionContext,
    donation_enriched: pl.DataFrame,
) -> pl.DataFrame:
    df = donations_by_avatar(donation_enriched)
    _add_df_metadata(context, df)
    return df


@asset(group_name=TRANSFORM_GROUP)
def donations_by_island_snapshot(
    context: AssetExecutionContext,
    donation_enriched: pl.DataFrame,
) -> pl.DataFrame:
    df = donations_by_island(donation_enriched)
    _add_df_metadata(context, df)
    return df


@asset(group_name=PUBLIC_GROUP)
def player_snapshot(
    context: AssetExecutionContext,
    player_enriched: pl.DataFrame,
    city_by_player_snapshot: pl.DataFrame,
    donations_by_player_snapshot: pl.DataFrame,
) -> pl.DataFrame:
    df = build_player_snapshot_table(
        player_enriched,
        city_by_player_snapshot,
        donations_by_player_snapshot,
    )
    _add_df_metadata(context, df)
    return df


@asset(group_name=PUBLIC_GROUP)
def city_snapshot(
    context: AssetExecutionContext,
    city_enriched: pl.DataFrame,
    donation_enriched: pl.DataFrame,
    island_enriched: pl.DataFrame,
) -> pl.DataFrame:
    """One row per (city, snapshot). Contains detailed city-level metrics
    and corresponding player-island donations and island metadata.

    NOTE ON NORMALIZATION:
    This table is intentionally denormalized. Player-island level donations and island metadata
    (e.g. wonder level) are duplicated across multiple cities owned by the same player on the same island.
    This duplication is intentional for the sake of ease of downstream analysis (avoiding complex multi-table joins).
    When aggregating player-island level columns (such as donations), use MAX instead of SUM to avoid double-counting.
    """
    df = build_city_snapshot_table(
        city_enriched,
        donation_enriched,
        island_enriched,
    )
    _add_df_metadata(context, df)
    return df


@asset(group_name=PUBLIC_GROUP)
def island_snapshot(
    context: AssetExecutionContext,
    island_enriched: pl.DataFrame,
    city_by_island_snapshot: pl.DataFrame,
    donations_by_island_snapshot: pl.DataFrame,
) -> pl.DataFrame:
    df = build_island_snapshot_table(
        island_enriched,
        city_by_island_snapshot,
        donations_by_island_snapshot,
    )
    _add_df_metadata(context, df)
    return df





@asset(group_name=EXPORT_GROUP)
def ikariam_lancedb(
    context: AssetExecutionContext,
    raw_avatar: pl.DataFrame,
    raw_city: pl.DataFrame,
    raw_donation: pl.DataFrame,
    raw_island: pl.DataFrame,
    player_snapshot: pl.DataFrame,
    city_snapshot: pl.DataFrame,
    island_snapshot: pl.DataFrame,
) -> MaterializeResult:
    public_tables = {
        "player_snapshot": player_snapshot,
        "city_snapshot": city_snapshot,
        "island_snapshot": island_snapshot,
    }
    raw_tables = partition_raw_tables_by_country(
        {
            "raw_avatar": raw_avatar,
            "raw_city": raw_city,
            "raw_donation": raw_donation,
            "raw_island": raw_island,
        }
    )
    tables = {
        **public_tables,
        **raw_tables,
    }
    db_path = write_lancedb(tables, get_config().lancedb_path)
    return MaterializeResult(
        metadata={
            "lancedb_path": MetadataValue.path(str(db_path)),
            **{f"{name}_row_count": df.height for name, df in tables.items()},
            "raw_country_partition_count": len(raw_tables),
        }
    )


ALL_ASSETS = [
    raw_avatar,
    raw_city,
    raw_donation,
    raw_island,
    building_costs,
    valid_players,
    filtered_avatar,
    filtered_city,
    filtered_donation,
    city_with_costs,
    player_enriched,
    city_enriched,
    city_player_island,
    donation_enriched,
    island_enriched,
    city_by_player_snapshot,
    city_by_island_snapshot,
    donations_by_player_snapshot,
    donations_by_island_snapshot,
    player_snapshot,
    city_snapshot,
    island_snapshot,
    ikariam_lancedb,
]
