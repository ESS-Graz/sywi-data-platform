from __future__ import annotations

import pytest
import polars as pl

from ikariam.pipeline.transforms.donation_analytics import (
    build_donation_analytics_player_island_snapshot,
)


def test_donation_analytics_player_island_snapshot_uses_clean_denominators():
    donation_enriched = pl.DataFrame(
        {
            "avatar_id": ["p1", "p2"],
            "island_id": ["i1", "i1"],
            "snapshot_id": ["s1", "s1"],
            "snapshot_date": ["2026-01-01", "2026-01-01"],
            "country": ["DE", "DE"],
            "Don_Ges": [100.0, 50.0],
            "Don_Saegewerk_Ges": [40.0, 10.0],
            "Don_Luxusminen_Ges": [30.0, 15.0],
            "Don_Wonder_Ges": [30.0, 25.0],
            "Don_Luxus_Ges": [60.0, 40.0],
            "Don_Wonder_Wein": [3.0, 0.0],
            "Don_Wonder_Stein": [7.0, 5.0],
            "Don_Wonder_Kristall": [9.0, 10.0],
            "Don_Wonder_Schwefel": [11.0, 10.0],
            "Don_Luxus_Wein": [0.0, 15.0],
            "Don_Luxus_Stein": [30.0, 0.0],
            "Don_Luxus_Kristall": [0.0, 0.0],
            "Don_Luxus_Schwefel": [0.0, 0.0],
        }
    )
    city_player_island = pl.DataFrame(
        {
            "owner_id": ["p1", "p2"],
            "island_id": ["i1", "i1"],
            "snapshot_id": ["s1", "s1"],
            "cities_on_island": [2, 1],
            "Buerger_Ges": [10.0, 5.0],
            "Rathauslev": [5.0, 4.0],
            "Geblev": [20.0, 8.0],
            "resource_workers": [4.0, 2.0],
            "tradegood_workers": [3.0, 5.0],
            "priests": [2.0, 0.0],
            "Holz_Ges_verb_lag": [100.0, 20.0],
            "Wein_Ges_verb_lag": [20.0, 5.0],
            "Stein_Ges_verb_lag": [30.0, 5.0],
            "Kristall_Ges_verb_lag": [40.0, 5.0],
            "Schwefel_Ges_verb_lag": [50.0, 5.0],
            "Res_Ges_verb_lag": [240.0, 40.0],
        }
    )
    player_enriched = pl.DataFrame(
        {
            "id": ["p1", "p2"],
            "snapshot_id": ["s1", "s1"],
            "Spieldauer": [10.0, 20.0],
        }
    )

    result = build_donation_analytics_player_island_snapshot(
        donation_enriched,
        city_player_island,
        player_enriched,
    )
    row = result.filter(pl.col("player_id") == "p1").row(0, named=True)

    assert row["country_code"] == "DE"
    assert row["player_island_city_count"] == 2
    assert row["player_total_city_count"] == 2
    assert row["island_player_count"] == 2
    assert row["island_city_count"] == 3
    assert row["island_donations_total"] == 150.0
    assert row["island_avg_donations_per_player"] == 75.0
    assert row["island_peer_donations_avg"] == 50.0
    assert row["donations_minus_island_peer_avg"] == 50.0
    assert row["sawmill_donation_share_pct"] == 40.0
    assert row["luxury_mine_donation_share_pct"] == 30.0
    assert row["wonder_donation_share_pct"] == 30.0
    assert row["donations_per_city"] == 50.0
    assert row["donations_per_citizen"] == 10.0
    assert row["sawmill_donations_per_resource_worker"] == 10.0
    assert row["luxury_mine_donations_per_tradegood_worker"] == 10.0
    assert row["wonder_donations_per_priest"] == 15.0
    assert row["donations_per_account_age_day"] == 10.0
    assert row["wood_donation_resource_share_pct"] == pytest.approx(70.0 / 170.0 * 100.0)
