from __future__ import annotations

import math
from datetime import date

import polars as pl

from ikariam_pipeline.config import Config, DBConfig, DurationBand, Snapshot
from ikariam_pipeline.transforms.donations import process_donations


def _cfg() -> Config:
    return Config(
        db=DBConfig("localhost", 3306, "u", "p"),
        reference_timestamp=1415923200,
        min_play_duration_days=2,
        min_registration_time=1366797600,
        wonder_split_factor=0.666667,
        duration_adjustments=(DurationBand(math.inf, 1.0),),
        countries=("DE",),
        snapshots=(Snapshot("de_0101_13", date(2013, 1, 1), "DE"),),
        building_costs_path=None,  # type: ignore[arg-type]
        output_dir=None,  # type: ignore[arg-type]
        output_delimiter=";",
    )


def _donation_row(avatar_id: str, island_id: str, dtype: int, gold: float) -> dict:
    return {
        "avatar_id": avatar_id,
        "island_id": island_id,
        "type": dtype,
        "gold": gold,
        "snapshot_id": "de_0101_13",
        "snapshot_date": date(2013, 1, 1),
        "country": "DE",
    }


def _base_island(island_id: str, tradegood: int | None) -> dict:
    return {
        "id": island_id,
        "tradegood": tradegood,
        "snapshot_id": "de_0101_13",
        "snapshot_date": date(2013, 1, 1),
        "country": "DE",
    }


def _base_city_player(avatar: str, island: str) -> dict:
    return {
        "owner_id": avatar,
        "island_id": island,
        "snapshot_id": "de_0101_13",
        "snapshot_date": date(2013, 1, 1),
        "country": "DE",
    }


def test_wonder_split_sql_q22_semantics():
    # SQL Q22: for each resource R, set `Don_Wonder_Anteil_R = Don_Wonder_Ges
    # * (1 - 0.666667) ≈ 0.333` ONLY when the island's tradegood is NOT R.
    # Matching resource stays at 0. Total conserved across 3 non-matching
    # resources: 3 × 0.333 = 1.0.
    donations = pl.DataFrame([_donation_row("A", "I1", 1, 900.0)])
    islands = pl.DataFrame([_base_island("I1", tradegood=1)])  # 1 = wine
    city = pl.DataFrame([_base_city_player("A", "I1")])
    cfg = _cfg()

    out = process_donations(donations, city, islands, cfg)
    row = out.filter((pl.col("avatar_id") == "A") & (pl.col("island_id") == "I1")).to_dicts()[0]

    # Wine island: wine share = 0, others each get 900 * 0.333 = 300.
    share = 900 * (1 - cfg.wonder_split_factor)
    assert abs(row["Don_Wonder_Wein"] - 0.0) < 1e-6
    assert abs(row["Don_Wonder_Stein"] - share) < 1e-6
    assert abs(row["Don_Wonder_Kristall"] - share) < 1e-6
    assert abs(row["Don_Wonder_Schwefel"] - share) < 1e-6
    total = sum(
        row[k] for k in ("Don_Wonder_Wein", "Don_Wonder_Stein",
                          "Don_Wonder_Kristall", "Don_Wonder_Schwefel")
    )
    # Conservation holds within the float representation of (1 - f): since
    # 0.666667 has a finite base-10 representation but not base-2,
    # 3 × (1 - 0.666667) × 900 differs from 900 by ~1e-3.
    assert abs(total - 900.0) < 1e-2


def test_wonder_split_null_tradegood_all_zero():
    # SQL's Q22 uses `tradegood != 'N'` which is NULL when tradegood IS NULL,
    # so no resource gets a share — all 4 stay at 0. V1 R handled null with
    # uniform 0.25 each; we match SQL here.
    donations = pl.DataFrame([_donation_row("A", "I2", 1, 400.0)])
    islands = pl.DataFrame([_base_island("I2", tradegood=None)])
    city = pl.DataFrame([_base_city_player("A", "I2")])
    cfg = _cfg()

    out = process_donations(donations, city, islands, cfg)
    row = out.filter(pl.col("island_id") == "I2").to_dicts()[0]

    keys = ("Don_Wonder_Wein", "Don_Wonder_Stein", "Don_Wonder_Kristall", "Don_Wonder_Schwefel")
    for key in keys:
        assert abs(row[key] - 0.0) < 1e-6
