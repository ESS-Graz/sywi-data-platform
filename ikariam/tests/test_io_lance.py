from __future__ import annotations

import pytest
import polars as pl

from ikariam.processing.io_lance import _attach_metadata, partition_raw_tables_by_country


def test_partition_raw_tables_by_country_splits_rows_deterministically():
    raw_avatar = pl.DataFrame(
        {
            "country": ["EN", "DE", "DE"],
            "snapshot_id": ["en_0205_13", "de_2504_13", "de_0205_13"],
            "id": ["en-player", "de-player-1", "de-player-2"],
        }
    )

    tables = partition_raw_tables_by_country({"raw_avatar": raw_avatar})

    assert list(tables) == ["raw_avatar_de", "raw_avatar_en"]
    assert tables["raw_avatar_de"].select("country", "id").to_dicts() == [
        {"country": "DE", "id": "de-player-1"},
        {"country": "DE", "id": "de-player-2"},
    ]
    assert tables["raw_avatar_en"].select("country", "id").to_dicts() == [
        {"country": "EN", "id": "en-player"},
    ]


def test_partition_raw_tables_by_country_requires_country_column():
    with pytest.raises(ValueError, match="country or country_code"):
        partition_raw_tables_by_country({"raw_avatar": pl.DataFrame({"id": ["player"]})})


@pytest.mark.parametrize(
    ("table_name", "description_start"),
    [
        ("building_construction_event", "One row per building level ever constructed"),
        ("building_demolition_event", "One row per building level that stopped standing"),
    ],
)
def test_construction_ledgers_carry_their_documentation(
    table_name: str, description_start: str
) -> None:
    frame = pl.DataFrame({"city_id": ["c1"], "paid_cost_wood": [1.0]})

    table = _attach_metadata(frame, table_name)

    assert table.schema.metadata[b"description"].decode().startswith(description_start)
    assert table.schema.field("city_id").metadata[b"description"] == b"SHA1 of the city"
    assert table.schema.field("paid_cost_wood").metadata[b"unit"] == b"wood"
