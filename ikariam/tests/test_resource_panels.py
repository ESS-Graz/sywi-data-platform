from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl
import pytest

from ikariam.processing.transforms.city_metrics import compute_city_metrics


def test_city_metrics_keep_base_costs_and_estimates_reconcilable() -> None:
    city_data: dict[str, list[object]] = {
        "id": ["c1"],
        "owner_id": ["p1"],
        "island_id": ["i1"],
        "snapshot_id": ["s1"],
        "snapshot_date": [date(2020, 6, 1)],
        "country": ["DE"],
        "capital": [1],
        "citizens": [10],
        "resource_workers": [2],
        "tradegood_workers": [3],
        "scientists": [4],
        "priests": [1],
        "resource": [5],
        "tradegood1": [1],
        "tradegood2": [2],
        "tradegood3": [3],
        "tradegood4": [4],
        "level": [7],
    }
    for position in range(1, 18):
        city_data[f"p{position}l"] = [1 if position == 1 else 0]
        for suffix in ("h", "k", "q", "s", "w"):
            city_data[f"g{position}{suffix}"] = [0.0]
    city_data.update(
        {
            "g1h": [100.0],
            "g1k": [20.0],
            "g1q": [30.0],
            "g1s": [40.0],
            "g1w": [10.0],
        }
    )

    player = pl.DataFrame(
        {
            "id": ["p1"],
            "snapshot_id": ["s1"],
            "account_age_days": [200],
            "registered_at": [datetime(2020, 1, 1, tzinfo=UTC)],
            "estimated_research_cost_factor": [0.86],
            "estimated_research_cost_factor_source": ["age_heuristic"],
            "research_evidence_tier": ["geometry_or_later"],
        }
    )

    row = compute_city_metrics(pl.DataFrame(city_data), player).row(0, named=True)

    assert row["building_base_cost_wood"] == 100.0
    assert row["building_base_cost_total"] == 200.0
    assert row["estimated_building_cost_wood"] == 86.0
    assert row["estimated_building_cost_total"] == pytest.approx(172.0)
    assert row["resources_stored_total"] == 15.0
    assert row["estimated_wood_resource_value"] == 91.0
    assert row["estimated_resource_value_total"] == pytest.approx(187.0)
    assert row["estimated_research_cost_factor"] == 0.86
    assert row["estimated_research_cost_factor_source"] == "age_heuristic"
    assert row["research_evidence_tier"] == "geometry_or_later"

    legacy_columns = {
        "Holz_verbaut",
        "Res_Ges_verbaut",
        "Baumeister_Highscore",
        "duration_adjustment",
    }
    assert legacy_columns.isdisjoint(row)
