from __future__ import annotations

import polars as pl

from ikariam.processing.transforms.islands import enrich_islands


def test_island_upgrade_costs_match_sql_q23_tables():
    island_raw = pl.DataFrame(
        {
            "id": ["i1"],
            "snapshot_id": ["s1"],
            "wonder_level": [4],
            "resource_level": [26],
            "tradegood_level": [21],
            "wonder_donated": [0.0],
            "resource_donated": [0.0],
            "tradegood_donated": [0.0],
            "tradegood": [2],
        }
    )

    result = enrich_islands(island_raw)

    assert result.select(
        "cost_Nextlev_resource",
        "cost_Nextlev_tradegood",
        "cost_Nextlev_wonder",
        "Sub_Noetig_nextlev_resource",
        "Sub_Noetig_nextlev_tradegood",
        "Sub_Noetig_nextlev_wonder",
    ).to_dicts() == [
        {
            "cost_Nextlev_resource": 767723,
            "cost_Nextlev_tradegood": 925396,
            "cost_Nextlev_wonder": 135500,
            "Sub_Noetig_nextlev_resource": 767723.0,
            "Sub_Noetig_nextlev_tradegood": 925396.0,
            "Sub_Noetig_nextlev_wonder": 135500.0,
        }
    ]
