from __future__ import annotations

import pytest
import polars as pl

from ikariam.pipeline.io_lance import partition_raw_tables_by_country


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
