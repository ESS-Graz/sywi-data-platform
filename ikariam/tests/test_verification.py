from __future__ import annotations

from datetime import datetime

import pytest
import polars as pl

from ikariam.pipeline.verification import (
    ComparisonSpec,
    LEGACY_DONATION_AVG_MAP,
    LEGACY_DONATION_SUM_COLUMNS,
    aggregate_donations,
    aggregate_city2,
    build_island_level_per_avatar,
    build_legacy_donation2,
    build_legacy_donation3av,
    build_legacy_donation4isl,
    build_legacy_avatar,
    build_legacy_city2,
    build_master_avi,
    build_teilnahme_av,
    compare_frame,
)


def test_build_teilnahme_and_master_from_raw_lance_tables():
    raw_avatar = pl.DataFrame(
        {
            "id": ["p1", "p1", "p2"],
            "snapshot_id": ["s1", "s2", "s1"],
        }
    )
    raw_city = pl.DataFrame(
        {
            "id": ["c1", "c2", "c3"],
            "owner_id": ["p1", "p1", "p2"],
            "island_id": ["i1", "i1", "i2"],
        }
    )

    teilnahme = build_teilnahme_av(raw_avatar)
    assert teilnahme.select("id", "Anzahl_Vorhanden").to_dicts() == [
        {"id": "p1", "Anzahl_Vorhanden": 2.0},
        {"id": "p2", "Anzahl_Vorhanden": 1.0},
    ]

    master = build_master_avi(raw_city, teilnahme)
    assert master.to_dicts() == [
        {
            "owner_id": "p1",
            "island_id": "i1",
            "Cities_Vorhanden": 2.0,
            "Anzahl_Teilnahme": 2.0,
        },
        {
            "owner_id": "p2",
            "island_id": "i2",
            "Cities_Vorhanden": 1.0,
            "Anzahl_Teilnahme": 1.0,
        },
    ]


def test_build_legacy_avatar_maps_direct_sql_avatar_fields():
    player = pl.DataFrame(
        {
            "player_id": ["p1", "p2"],
            "gold": [10.5, 20.0],
            "registered_at_unix": [1000, 2000],
            "registered_at": [datetime(1970, 1, 1, 0, 16, 40), datetime(1970, 1, 1, 0, 33, 20)],
            "account_age_days": [1.0, 3.0],
            "government_form": [6, 0],
        }
    )

    result = build_legacy_avatar(player)

    assert result.sort("a_id").to_dicts() == [
        {
            "a_id": "p1",
            "a_gold": 10.5,
            "a_registration_time": 1000,
            "a_Registration_time_normal": "1970-01-01T00:16:40.000000",
            "a_Spieldauer": 1.0,
            "a_formOfGovernment": 6,
            "a_Anz_Av_per_DB": 2.0,
            "a_Avg_Spieldauer": 2.0,
        },
        {
            "a_id": "p2",
            "a_gold": 20.0,
            "a_registration_time": 2000,
            "a_Registration_time_normal": "1970-01-01T00:33:20.000000",
            "a_Spieldauer": 3.0,
            "a_formOfGovernment": 0,
            "a_Anz_Av_per_DB": 2.0,
            "a_Avg_Spieldauer": 2.0,
        },
    ]


def test_aggregate_donations_deduplicates_city_level_repetition():
    city = pl.DataFrame(
        {
            "player_id": ["p1", "p1", "p1"],
            "island_id": ["i1", "i1", "i1"],
            "snapshot_id": ["s1", "s1", "s2"],
            "wonder_donations_total": [3.0, 3.0, 1.0],
            "sawmill_donations_total": [5.0, 5.0, 2.0],
            "luxury_mine_donations_total": [7.0, 7.0, 4.0],
            "donations_total": [15.0, 15.0, 7.0],
        }
    )

    result = aggregate_donations(city, ("player_id",))

    assert result.to_dicts() == [
        {
            "player_id": "p1",
            "d_Don_Ges": 22.0,
            "d_Don_Saegewerk_Ges": 7.0,
            "d_Don_Wonder_Ges": 4.0,
            "d_DonH_Luxusminen_Ges": 11.0,
            "d_DonH_Ges": 18.0,
        }
    ]


def test_legacy_city2_sums_q17_fields_but_keeps_lowest_city_representative():
    city = pl.DataFrame(
        {
            "city_id": ["c2", "c1", "c3"],
            "player_id": ["p1", "p1", "p1"],
            "island_id": ["i1", "i1", "i2"],
            "is_capital": [False, True, False],
            "town_hall_level": [20, 10, 30],
            "citizens": [2.0, 1.0, 4.0],
            "resource_workers": [3.0, 1.0, 5.0],
            "tradegood_workers": [4.0, 1.0, 6.0],
            "scientists": [5.0, 1.0, 7.0],
            "priests": [6.0, 1.0, 8.0],
            "population_total": [20.0, 10.0, 30.0],
            "wood_stored": [200.0, 100.0, 300.0],
            "wine_stored": [210.0, 110.0, 310.0],
            "marble_stored": [220.0, 120.0, 320.0],
            "crystal_stored": [230.0, 130.0, 330.0],
            "sulfur_stored": [240.0, 140.0, 340.0],
            "building_resource_score": [2.0, 1.0, 3.0],
            "building_levels_total": [2.0, 1.0, 3.0],
            "wood_total": [2.0, 1.0, 3.0],
            "wood_in_buildings": [2.0, 1.0, 3.0],
            "crystal_total": [2.0, 1.0, 3.0],
            "crystal_in_buildings": [2.0, 1.0, 3.0],
            "resources_stored_total": [2.0, 1.0, 3.0],
            "resources_in_buildings_and_storage_total": [2.0, 1.0, 3.0],
            "resources_in_buildings_total": [2.0, 1.0, 3.0],
            "sulfur_total": [2.0, 1.0, 3.0],
            "sulfur_in_buildings": [2.0, 1.0, 3.0],
            "marble_total": [2.0, 1.0, 3.0],
            "marble_in_buildings": [2.0, 1.0, 3.0],
            "wine_total": [2.0, 1.0, 3.0],
            "wine_in_buildings": [2.0, 1.0, 3.0],
        }
    )

    city2 = build_legacy_city2(city)
    pair = city2.filter((pl.col("player_id") == "p1") & (pl.col("island_id") == "i1"))

    assert pair.select(
        "city_id",
        "c_id",
        "c_owner_id",
        "c_island_id",
        "c_level",
        "c_resource",
        "c_Rathauslev",
        "c_Anz_Cities_per_Av",
        "c_Anz_Ins_per_Av",
        "c_Anz_Cities_per_DB",
        "c_GovReslev",
    ).to_dicts() == [
        {
            "city_id": "c1",
            "c_id": "c1",
            "c_owner_id": "p1",
            "c_island_id": "i1",
            "c_level": 10,
            "c_resource": 100.0,
            "c_Rathauslev": 30,
            "c_Anz_Cities_per_Av": 2.0,
            "c_Anz_Ins_per_Av": 2.0,
            "c_Anz_Cities_per_DB": 2.0,
            "c_GovReslev": 0.0,
        }
    ]

    player_island = aggregate_city2(city2, ("player_id", "island_id")).sort("island_id")
    assert player_island.select("player_id", "island_id", "c_Avg_Buerger_Ges").to_dicts() == [
        {"player_id": "p1", "island_id": "i1", "c_Avg_Buerger_Ges": 0.0},
        {"player_id": "p1", "island_id": "i2", "c_Avg_Buerger_Ges": 0.0},
    ]

    player = aggregate_city2(city2, ("player_id",))
    assert player.select(
        "player_id",
        "c_level",
        "c_resource",
        "c_Rathauslev",
        "c_Avg_Anz_cities_per_Av",
        "c_Avg_Buerger_Ges",
        "c_Avg_Resource_workers",
        "c_Avg_Tradegood_workers",
    ).to_dicts() == [
        {
            "player_id": "p1",
            "c_level": 10,
            "c_resource": 100.0,
            "c_Rathauslev": 60,
            "c_Avg_Anz_cities_per_Av": 2.0,
            "c_Avg_Buerger_Ges": 30.0,
            "c_Avg_Resource_workers": 4.5,
            "c_Avg_Tradegood_workers": 5.5,
        }
    ]


def test_build_island_level_per_avatar_uses_global_sql_denominator():
    island = pl.DataFrame(
        {
            "island_id": ["i1", "i2"],
            "sawmill_level": [2, 4],
            "luxury_mine_level": [3, 5],
            "wonder_level": [1, 3],
        }
    )
    player = pl.DataFrame({"player_id": ["p1", "p2"]})

    result = build_island_level_per_avatar(island, player).sort("i_id")

    assert result.to_dicts() == [
        {
            "i_id": "i1",
            "c_Avg_Resource_lev_per_Av": 3.0,
            "c_Avg_Tradegood_lev_per_Av": 4.0,
            "c_Avg_Wonder_lev_per_Av": 2.0,
        },
        {
            "i_id": "i2",
            "c_Avg_Resource_lev_per_Av": 3.0,
            "c_Avg_Tradegood_lev_per_Av": 4.0,
            "c_Avg_Wonder_lev_per_Av": 2.0,
        },
    ]


def test_build_legacy_donation2_projects_row_level_donation_analytics():
    city = pl.DataFrame(
        {
            "player_id": ["p1", "p1"],
            "island_id": ["i1", "i1"],
            "snapshot_id": ["s1", "s1"],
            "wonder_donations_total": [30.0, 30.0],
            "sawmill_donations_total": [40.0, 40.0],
            "luxury_mine_donations_total": [30.0, 30.0],
            "donations_total": [100.0, 100.0],
        }
    )
    city2 = pl.DataFrame(
        {
            "player_id": ["p1"],
            "island_id": ["i1"],
            "c_Anz_Cities_per_Av": [1.0],
            "c_Buerger_Ges": [10.0],
            "c_Geblev": [20.0],
            "c_Holz_Ges_verb_lag": [100.0],
            "c_Kristall_Ges_verb_lag": [40.0],
            "c_priests": [2.0],
            "c_Rathauslev": [5.0],
            "c_Res_Ges_verb_lag": [240.0],
            "c_resource_workers": [4.0],
            "c_Schwefel_Ges_verb_lag": [50.0],
            "c_Stein_Ges_verb_lag": [30.0],
            "c_tradegood_workers": [3.0],
            "c_Wein_Ges_verb_lag": [20.0],
        }
    )
    player = pl.DataFrame({"player_id": ["p1"], "account_age_days": [10.0]})
    island = pl.DataFrame({"island_id": ["i1"], "luxury_resource_type": [2]})

    result = build_legacy_donation2(city, city2, player, island)
    row = result.row(0, named=True)

    assert row["d_avatar_id"] == "p1"
    assert row["d_island_id"] == "i1"
    assert row["d_gold"] == 100.0
    assert row["d_DonH_Ges"] == 70.0
    assert row["d_DonH_fuer_Steinbruch"] == 30.0
    assert row["d_DonH_fuer_Weinreben"] == 0.0
    assert row["d_Don_Wonder_Anteil_Stein"] == 0.0
    assert row["d_Don_Wonder_Anteil_Kristall"] == pytest.approx(30.0 * 0.333333)
    assert row["d_Holz_Ges_verb_lag_don"] == 170.0
    assert row["d_Don_pro_City"] == 100.0
    assert row["d_Don_pro_Resource_Worker"] == 10.0
    assert row["d_Don_pro_Tradegood_Worker"] == 10.0
    assert row["d_Don_Wonder_Ges_pro_Spieldauer"] == 3.0


def test_build_legacy_donation3av_projects_player_level_sql_rollup():
    donation2 = _legacy_donation2_fixture()
    city2 = _legacy_city2_donation_context_fixture()
    player = pl.DataFrame(
        {
            "player_id": ["p1", "p2"],
            "account_age_days": [10.0, 30.0],
        }
    )

    result = build_legacy_donation3av(donation2, city2, player)
    row = result.filter(pl.col("player_id") == "p1").row(0, named=True)

    assert row["d_avatar_id"] == "p1"
    assert row["d_island_id"] == "i1"
    assert row["d_Don_Ges"] == 150.0
    assert row["d_Don_Saegewerk_Ges"] == 50.0
    assert row["d_DonH_Luxusminen_Ges"] == 65.0
    assert row["d_Don_pro_Rathauslev"] == 7.5
    assert row["d_Don_pro_City"] == 75.0
    assert row["d_Don_pro_Resource_Worker"] == 5.0
    assert row["d_Don_pro_Tradegood_Worker"] == pytest.approx(65.0 / 6.0)
    assert row["d_Don_pro_Priester"] == pytest.approx(35.0 / 3.0)
    assert row["d_Don_pro_Buerger_Ges"] == 3.75
    assert row["d_Buerger_Ges_pro_Spieldauer"] == 4.0
    assert row["d_Don_Ges_pro_Spieldauer"] == 15.0
    assert row["d_Avg_Don_Ges"] == 75.0
    assert row["d_Avg_Proz_Don_von_Res_Ges"] == 25.0
    assert row["d_Proz_Don_Anteil_Holz_von_Holz_Ges_verb_lag"] == pytest.approx(
        115.0 / 415.0 * 100.0
    )


def test_build_legacy_donation4isl_projects_island_level_sql_rollup():
    donation2 = _legacy_donation2_fixture()
    city2 = _legacy_city2_donation_context_fixture()
    player = pl.DataFrame(
        {
            "player_id": ["p1", "p2"],
            "account_age_days": [10.0, 30.0],
        }
    )

    result = build_legacy_donation4isl(donation2, city2, player)
    row = result.filter(pl.col("island_id") == "i1").row(0, named=True)

    assert row["d_avatar_id"] == "p1"
    assert row["d_island_id"] == "i1"
    assert row["d_Don_Ges"] == 120.0
    assert row["d_Don_pro_City"] == 60.0
    assert row["d_Don_pro_Rathauslev"] == 12.0
    assert row["d_Don_pro_Buerger_Ges"] == 4.0
    assert row["d_Buerger_Ges_pro_Spieldauer"] == 0.75
    assert row["d_Don_Ges_pro_Spieldauer"] == 3.0
    assert row["d_Avg_Don_Ges"] == 60.0
    assert row["d_Avg_Holz_Ges_verb_lag_don"] == 130.0
    assert row["d_Avg_Proz_Don_von_Res_Ges"] == 25.0


def test_compare_frame_reports_key_coverage_unmapped_and_tolerated_values(tmp_path):
    gold = pl.DataFrame(
        {
            "id": ["a", "b"],
            "value": [1.0, 2.0],
            "unmapped": [10.0, 20.0],
        }
    )
    actual = pl.DataFrame({"id": ["a", "c"], "value": [1.0 + 5e-7, 3.0]})

    result = compare_frame(gold, actual, ComparisonSpec("sample", ("id",)), tmp_path)

    assert result.mapped_columns == ("value",)
    assert result.unmapped_columns == ("unmapped",)
    assert result.gold_only_keys == 1
    assert result.actual_only_keys == 1
    assert result.mismatch_count == 0
    assert result.failed


def test_compare_frame_reports_value_mismatches(tmp_path):
    gold = pl.DataFrame({"id": ["a"], "value": [1.0]})
    actual = pl.DataFrame({"id": ["a"], "value": [1.1]})

    result = compare_frame(gold, actual, ComparisonSpec("sample", ("id",)), tmp_path)

    assert result.gold_only_keys == 0
    assert result.actual_only_keys == 0
    assert result.mismatch_count == 1
    assert pl.read_csv(result.mismatch_path).select("id", "column").to_dicts() == [
        {"id": "a", "column": "value"}
    ]


def _legacy_donation2_fixture() -> pl.DataFrame:
    def row(player_id: str, island_id: str, **values: float) -> dict[str, float | str]:
        data: dict[str, float | str] = {
            "player_id": player_id,
            "island_id": island_id,
            "d_avatar_id": player_id,
            "d_island_id": island_id,
        }
        for column in LEGACY_DONATION_SUM_COLUMNS:
            data[column] = 0.0
        for source in LEGACY_DONATION_AVG_MAP.values():
            data[source] = data.get(source, 0.0)
        data.update(values)
        return data

    return pl.DataFrame(
        [
            row(
                "p1",
                "i1",
                d_gold=100.0,
                d_Don_Ges=100.0,
                d_Don_Saegewerk_Ges=40.0,
                d_Don_Wonder_Ges=30.0,
                d_DonH_Luxusminen_Ges=30.0,
                d_DonH_Ges=70.0,
                d_Holz_Ges_verb_lag_don=170.0,
                d_Res_Ges_verb_lag_don=340.0,
                d_Proz_Don_von_Res_Ges=25.0,
                d_Proz_Don_Anteil_Holz_von_Holz_Ges_verb_lag=40.0,
            ),
            row(
                "p1",
                "i2",
                d_gold=50.0,
                d_Don_Ges=50.0,
                d_Don_Saegewerk_Ges=10.0,
                d_Don_Wonder_Ges=5.0,
                d_DonH_Luxusminen_Ges=35.0,
                d_DonH_Ges=45.0,
                d_Holz_Ges_verb_lag_don=245.0,
                d_Res_Ges_verb_lag_don=260.0,
                d_Proz_Don_von_Res_Ges=25.0,
                d_Proz_Don_Anteil_Holz_von_Holz_Ges_verb_lag=20.0,
            ),
            row(
                "p2",
                "i1",
                d_gold=20.0,
                d_Don_Ges=20.0,
                d_Don_Saegewerk_Ges=5.0,
                d_Don_Wonder_Ges=5.0,
                d_DonH_Luxusminen_Ges=5.0,
                d_DonH_Ges=10.0,
                d_Holz_Ges_verb_lag_don=90.0,
                d_Res_Ges_verb_lag_don=120.0,
                d_Proz_Don_von_Res_Ges=25.0,
                d_Proz_Don_Anteil_Holz_von_Holz_Ges_verb_lag=10.0,
            ),
        ]
    )


def _legacy_city2_donation_context_fixture() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "player_id": ["p1", "p1", "p2"],
            "island_id": ["i1", "i2", "i1"],
            "c_Anz_Cities_per_Av": [2.0, 2.0, 1.0],
            "c_Buerger_Ges": [10.0, 30.0, 20.0],
            "c_Geblev": [20.0, 10.0, 10.0],
            "c_Holz_Ges_verb_lag": [100.0, 200.0, 80.0],
            "c_Kristall_Ges_verb_lag": [40.0, 50.0, 20.0],
            "c_priests": [2.0, 0.0, 1.0],
            "c_Rathauslev": [5.0, 15.0, 5.0],
            "c_Res_Ges_verb_lag": [240.0, 210.0, 100.0],
            "c_resource_workers": [4.0, 6.0, 1.0],
            "c_Schwefel_Ges_verb_lag": [50.0, 60.0, 30.0],
            "c_Stein_Ges_verb_lag": [30.0, 40.0, 10.0],
            "c_tradegood_workers": [0.0, 5.0, 1.0],
            "c_Wein_Ges_verb_lag": [20.0, 30.0, 10.0],
        }
    )
