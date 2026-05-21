from __future__ import annotations


def test_definitions_load_without_ducklake_env(monkeypatch):
    for name in ("DUCKLAKE_CATALOG_DSN", "DUCKLAKE_DATA_PATH", "DUCKLAKE_SCHEMA"):
        monkeypatch.delenv(name, raising=False)

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
