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


def test_zero_row_inserted_for_city_without_donation():
    # One city-island with no donation at all.
    donations = pl.DataFrame(
        schema={
            "avatar_id": pl.Utf8,
            "island_id": pl.Utf8,
            "type": pl.Int64,
            "gold": pl.Float64,
            "snapshot_id": pl.Utf8,
            "snapshot_date": pl.Date,
            "country": pl.Utf8,
        }
    )
    islands = pl.DataFrame(
        {
            "id": ["I1"],
            "tradegood": [1],
            "snapshot_id": ["de_0101_13"],
            "snapshot_date": [date(2013, 1, 1)],
            "country": ["DE"],
        }
    )
    city = pl.DataFrame(
        {
            "owner_id": ["A"],
            "island_id": ["I1"],
            "snapshot_id": ["de_0101_13"],
            "snapshot_date": [date(2013, 1, 1)],
            "country": ["DE"],
        }
    )

    out = process_donations(donations, city, islands, _cfg())

    assert out.height == 1
    row = out.to_dicts()[0]
    assert row["avatar_id"] == "A"
    assert row["island_id"] == "I1"
    assert row["Don_Wonder_Ges"] == 0.0
    assert row["Don_Saegewerk_Ges"] == 0.0
    assert row["Don_Luxusminen_Ges"] == 0.0
    assert row["Don_Ges"] == 0.0
    assert row["donation_records"] == 0
