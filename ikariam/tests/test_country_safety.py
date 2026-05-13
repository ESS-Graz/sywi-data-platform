from __future__ import annotations

from datetime import date

import polars as pl

from ikariam.pipeline.derived import build_derived


def test_derived_tables_do_not_merge_same_ids_across_countries():
    player_snapshot = pl.DataFrame(
        {
            "country_code": ["DE", "EN"],
            "player_id": ["same-player", "same-player"],
            "snapshot_id": ["de_2504_13", "en_2504_13"],
            "snapshot_date": [date(2013, 4, 25), date(2013, 4, 25)],
            "registered_at_unix": [1366797600, 1366797601],
        }
    )
    player_island_snapshot = pl.DataFrame(
        {
            "country_code": ["DE", "EN"],
            "player_id": ["same-player", "same-player"],
            "island_id": ["same-island", "same-island"],
            "snapshot_id": ["de_2504_13", "en_2504_13"],
            "snapshot_date": [date(2013, 4, 25), date(2013, 4, 25)],
            "player_city_count_on_island": [1, 2],
            "wonder_type_id": [1, 2],
            "luxury_resource_type": [1, 2],
            "luxury_mine_level": [10, 20],
            "sawmill_level": [11, 21],
            "island_city_count": [3, 4],
        }
    )
    island_snapshot = pl.DataFrame(
        {
            "country_code": ["DE", "EN"],
            "island_id": ["same-island", "same-island"],
            "snapshot_id": ["de_2504_13", "en_2504_13"],
            "snapshot_date": [date(2013, 4, 25), date(2013, 4, 25)],
            "raw_city_count": [3, 4],
            "wonder_type_id": [1, 2],
            "luxury_resource_type": [1, 2],
            "luxury_mine_level": [10, 20],
            "sawmill_level": [11, 21],
        }
    )

    derived = build_derived(player_snapshot, player_island_snapshot, island_snapshot)

    assert derived.player_latest.height == 2
    assert derived.player_summary.height == 2
    assert derived.player_island_latest.height == 2
    assert derived.island_summary.height == 2
    assert set(derived.player_summary["country_code"].to_list()) == {"DE", "EN"}
