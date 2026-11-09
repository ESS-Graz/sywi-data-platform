from __future__ import annotations


def test_definitions_load():
    from ikariam.definitions import defs

    asset_keys = {
        tuple(key.path) for key in defs.resolve_asset_graph().get_all_asset_keys()
    }

    assert ("raw_avatar",) in asset_keys
    assert ("player_snapshot",) in asset_keys
    assert ("city_snapshot",) in asset_keys
    assert ("player_island_snapshot",) not in asset_keys
    assert ("donation_analytics_player_island_snapshot",) in asset_keys
    assert ("player_latest",) not in asset_keys
    assert ("ikariam_lancedb",) in asset_keys


def test_no_asset_depends_on_a_later_group():
    """Groups must run in order, so each one can be materialized after the one before it."""
    from ikariam.assets.pipeline import (
        EXPORT_GROUP,
        PUBLIC_GROUP,
        RAW_GROUP,
        TRANSFORM_GROUP,
    )
    from ikariam.definitions import defs

    order = [RAW_GROUP, TRANSFORM_GROUP, PUBLIC_GROUP, EXPORT_GROUP]
    graph = defs.resolve_asset_graph()

    backward = [
        (parent.path[-1], key.path[-1])
        for key in graph.get_all_asset_keys()
        for parent in graph.get(key).parent_keys
        if order.index(graph.get(parent).group_name) > order.index(graph.get(key).group_name)
    ]

    assert backward == []


def test_full_pipeline_job_runs_every_asset():
    from ikariam.definitions import defs

    job = defs.resolve_job_def("ikariam_full_pipeline")

    assert job.asset_layer.selected_asset_keys == defs.resolve_asset_graph().get_all_asset_keys()
