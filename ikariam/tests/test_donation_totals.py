"""Which islands count towards a donation total.

The player has a city on island i1 and an old running total on island i2,
where the city is gone. The player total keeps both; the player-island rows
only keep i1, because i2 has no city to attach to.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import polars as pl

from ikariam.processing.transforms.donations import process_donations
from ikariam.processing.transforms.higher_agg import donations_by_avatar

SNAPSHOT = {"snapshot_id": "de23_0101_14", "snapshot_date": date(2014, 1, 1), "country": "DE", "server": 23}


def _donations() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "avatar_id": ["p1", "p1", "p1"],
            "island_id": ["i1", "i1", "i2"],
            "type": [1, 2, 3],
            "gold": [100, 50, 30],
        }
    ).with_columns(**{key: pl.lit(value) for key, value in SNAPSHOT.items()})


def _city_player_island() -> pl.DataFrame:
    return pl.DataFrame({"owner_id": ["p1"], "island_id": ["i1"]}).with_columns(
        **{key: pl.lit(value) for key, value in SNAPSHOT.items()}
    )


def _islands() -> pl.DataFrame:
    return pl.DataFrame(
        {"id": ["i1", "i2"], "tradegood": [1, 2], "snapshot_id": [SNAPSHOT["snapshot_id"]] * 2}
    )


def test_player_total_includes_islands_without_a_city() -> None:
    totals = donations_by_avatar(_donations()).row(0, named=True)

    assert totals["Don_Ges"] == 180.0
    assert totals["Don_Wonder_Ges"] == 100.0
    assert totals["Don_Saegewerk_Ges"] == 50.0
    assert totals["Don_Luxusminen_Ges"] == 30.0
    assert totals["Don_Luxus_Ges"] == 130.0


def test_player_island_rows_drop_islands_without_a_city() -> None:
    cfg = SimpleNamespace(wonder_split_factor=0.666667)
    enriched = process_donations(_donations(), _city_player_island(), _islands(), cfg)

    assert enriched.get_column("island_id").to_list() == ["i1"]
    assert enriched.get_column("Don_Ges").to_list() == [150.0]
