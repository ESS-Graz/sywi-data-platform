from __future__ import annotations

from datetime import date

import polars as pl

from ikariam_pipeline.derived import build_derived
from ikariam_pipeline.transforms.final_datasets import build_panels


def test_public_outputs_use_canonical_names():
    snap_date = date(2014, 11, 13)

    player_enriched = pl.DataFrame(
        {
            "id": ["A"],
            "snapshot_id": ["de_1311_14"],
            "snapshot_date": [snap_date],
            "country": ["DE"],
            "registration_time": [1_394_397_896],
            "Registration_time_normal": ["2014-03-09T20:44:56.000000"],
            "gold": [100.0],
            "research_points": [10.0],
            "formOfGovernment": [2],
            "gender": [1],
            "Spieldauer": [249.1],
            "duration_adjustment": [0.86],
        }
    )
    city_player_island = pl.DataFrame(
        {
            "owner_id": ["A"],
            "island_id": ["I"],
            "snapshot_id": ["de_1311_14"],
            "snapshot_date": [snap_date],
            "country": ["DE"],
            "cities_on_island": [1],
            "Buerger_Ges": [50.0],
            "Holz_verbaut": [100.0],
            "Res_Ges_verbaut": [200.0],
            "Baumeister_Highscore": [220.0],
            "Res_Ges_lagernd": [30.0],
            "Res_Ges_verb_lag": [230.0],
            "Geblev": [12],
        }
    )
    city3_av = pl.DataFrame(
        {
            "owner_id": ["A"],
            "snapshot_id": ["de_1311_14"],
            "total_islands": [1],
            "total_cities": [1],
            "Buerger_Ges": [50.0],
            "Holz_verbaut": [100.0],
            "Kristall_verbaut": [20.0],
            "Stein_verbaut": [30.0],
            "Schwefel_verbaut": [40.0],
            "Wein_verbaut": [10.0],
            "Res_Ges_verbaut": [200.0],
            "Baumeister_Highscore": [220.0],
            "Res_Ges_lagernd": [30.0],
            "Res_Ges_verb_lag": [230.0],
            "Geblev": [12],
        }
    )
    city4_i = pl.DataFrame(
        {
            "island_id": ["I"],
            "snapshot_id": ["de_1311_14"],
            "total_players": [1],
            "total_cities": [1],
            "Buerger_Ges": [50.0],
            "Holz_verbaut": [100.0],
            "Res_Ges_verbaut": [200.0],
            "Baumeister_Highscore": [220.0],
            "Res_Ges_lagernd": [30.0],
            "Res_Ges_verb_lag": [230.0],
            "Geblev": [12],
            "Avg_Buerger_per_player": [50.0],
            "Avg_Baumeister_per_player": [220.0],
        }
    )
    donation_enriched = pl.DataFrame(
        {
            "avatar_id": ["A"],
            "island_id": ["I"],
            "snapshot_id": ["de_1311_14"],
            "Don_Wonder_Ges": [5.0],
            "Don_Saegewerk_Ges": [7.0],
            "Don_Luxusminen_Ges": [11.0],
            "Don_Ges": [23.0],
        }
    )
    donation3_av = pl.DataFrame(
        {
            "avatar_id": ["A"],
            "snapshot_id": ["de_1311_14"],
            "Don_Wonder_Ges": [5.0],
            "Don_Saegewerk_Ges": [7.0],
            "Don_Luxusminen_Ges": [11.0],
            "Don_Ges": [23.0],
            "Don_Luxus_Ges": [16.0],
        }
    )
    donation4_i = pl.DataFrame(
        {
            "island_id": ["I"],
            "snapshot_id": ["de_1311_14"],
            "donating_players": [1],
            "Don_Wonder_Ges": [5.0],
            "Don_Saegewerk_Ges": [7.0],
            "Don_Luxusminen_Ges": [11.0],
            "Don_Ges": [23.0],
            "Avg_Don_per_player": [23.0],
            "donation_participation_rate": [100.0],
        }
    )
    island_enriched = pl.DataFrame(
        {
            "id": ["I"],
            "snapshot_id": ["de_1311_14"],
            "snapshot_date": [snap_date],
            "country": ["DE"],
            "island_snapshot_key": ["I_de_1311_14"],
            "wonder_type_id": [3],
            "wonder_level": [2],
            "wonder_belief": [100],
            "tradegood": [2],
            "tradegood_level": [20],
            "resource_level": [25],
            "city_count": [16],
            "resource_donated": [1_000.0],
            "tradegood_donated": [2_000.0],
            "wonder_donated": [3_000.0],
            "cost_Nextlev_resource": [4_000.0],
            "cost_Nextlev_tradegood": [5_000.0],
            "cost_Nextlev_wonder": [6_000.0],
            "Sub_Noetig_nextlev_resource": [3_000.0],
            "Sub_Noetig_nextlev_tradegood": [3_000.0],
            "Sub_Noetig_nextlev_wonder": [3_000.0],
        }
    )

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
    derived = build_derived(
        player_snapshot=panels.player_snapshot,
        player_island_snapshot=panels.player_island_snapshot,
        island_snapshot=panels.island_snapshot,
    )

    legacy_names = {
        "Buerger_Ges",
        "Spieldauer",
        "Don_Ges",
        "Baumeister_Highscore",
        "Res_Ges_verbaut",
        "Geblev",
        "country",
        "registration_time",
        "formOfGovernment",
    }
    for df in (
        panels.player_snapshot,
        panels.player_island_snapshot,
        panels.island_snapshot,
        derived.player_latest,
        derived.player_island_latest,
        derived.island_latest,
        derived.player_summary,
        derived.player_island_summary,
        derived.island_summary,
    ):
        assert legacy_names.isdisjoint(df.columns)

    assert "account_age_days" in panels.player_snapshot.columns
    assert "population_total" in panels.player_island_snapshot.columns
    assert "sawmill_next_level_cost" in panels.island_snapshot.columns
    assert "snapshots_observed_count" in derived.player_summary.columns
