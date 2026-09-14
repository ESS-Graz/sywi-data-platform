from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl
import pytest

from ikariam.processing.transforms.building_costs import (
    REDUCTION_LEVEL_COLUMNS,
    add_building_base_costs,
)
from ikariam.processing.transforms.city_metrics import compute_city_metrics


BASE_COSTS = {"wood": 100.0, "crystal": 20.0, "marble": 30.0, "sulfur": 40.0, "wine": 10.0}
STORED = {"wood": 5.0, "wine": 1.0, "marble": 2.0, "crystal": 3.0, "sulfur": 4.0}
RESOURCES = tuple(BASE_COSTS)


def _cities(*overrides: dict[str, object]) -> pl.DataFrame:
    rows = []
    for index, override in enumerate(overrides or ({},), start=1):
        row: dict[str, object] = {
            "id": f"c{index}",
            "owner_id": "p1",
            "island_id": "i1",
            "snapshot_id": "s1",
            "snapshot_date": date(2020, 6, 1),
            "country": "DE",
            "capital": 1,
            "citizens": 10,
            "resource_workers": 2,
            "tradegood_workers": 3,
            "scientists": 4,
            "priests": 1,
            "resource": 5,
            "tradegood1": 1,
            "tradegood2": 2,
            "tradegood3": 3,
            "tradegood4": 4,
            "level": 7,
            **{f"p{position}l": 1 if position == 1 else 0 for position in range(1, 18)},
            **{f"building_base_cost_{resource}": cost for resource, cost in BASE_COSTS.items()},
            **{column: 0 for column in REDUCTION_LEVEL_COLUMNS.values()},
        }
        row.update(override)
        rows.append(row)
    return pl.DataFrame(rows)


def _player(*snapshot_ids: str, factor: float = 0.86) -> pl.DataFrame:
    snapshot_ids = snapshot_ids or ("s1",)
    count = len(snapshot_ids)
    return pl.DataFrame(
        {
            "id": ["p1"] * count,
            "snapshot_id": list(snapshot_ids),
            "account_age_days": [200] * count,
            "registered_at": [datetime(2020, 1, 1, tzinfo=UTC)] * count,
            "estimated_research_cost_factor": [factor] * count,
            "estimated_research_cost_factor_source": ["age_heuristic"] * count,
            "research_evidence_tier": ["geometry_or_later"] * count,
        }
    )


def _factors(row: dict[str, object]) -> dict[str, object]:
    return {resource: row[f"estimated_{resource}_cost_factor"] for resource in RESOURCES}


def test_city_metrics_keep_base_costs_and_estimates_reconcilable() -> None:
    row = compute_city_metrics(_cities(), _player()).row(0, named=True)

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


@pytest.mark.parametrize("research_factor", [1.0, 0.98, 0.94, 0.86])
def test_without_reducers_factors_equal_research_factor(research_factor: float) -> None:
    row = compute_city_metrics(_cities(), _player(factor=research_factor)).row(0, named=True)

    assert _factors(row) == dict.fromkeys(RESOURCES, research_factor)
    for resource, cost in BASE_COSTS.items():
        assert row[f"estimated_building_cost_{resource}"] == pytest.approx(cost * research_factor)


def test_carpenter_discounts_only_wood() -> None:
    row = compute_city_metrics(
        _cities({"wood_reduction_building_level": 20}), _player()
    ).row(0, named=True)

    assert _factors(row) == {
        "wood": 0.66,
        "crystal": 0.86,
        "marble": 0.86,
        "sulfur": 0.86,
        "wine": 0.86,
    }
    assert row["estimated_building_cost_wood"] == pytest.approx(66.0)
    assert row["estimated_building_cost_marble"] == pytest.approx(25.8)


def test_each_resource_uses_its_own_reducer_level() -> None:
    levels = {"wood": 20, "marble": 10, "crystal": 5, "wine": 1, "sulfur": 32}
    row = compute_city_metrics(
        _cities({REDUCTION_LEVEL_COLUMNS[resource]: level for resource, level in levels.items()}),
        _player(),
    ).row(0, named=True)

    assert _factors(row) == {
        "wood": 0.66,
        "crystal": 0.81,
        "marble": 0.76,
        "sulfur": 0.54,
        "wine": 0.85,
    }
    for resource, cost in BASE_COSTS.items():
        assert row[f"building_base_cost_{resource}"] == cost
        assert row[f"{resource}_stored"] == STORED[resource]
        assert row[f"estimated_building_cost_{resource}"] == pytest.approx(
            cost * row[f"estimated_{resource}_cost_factor"]
        )
        assert row[f"estimated_{resource}_resource_value"] == pytest.approx(
            row[f"estimated_building_cost_{resource}"] + STORED[resource]
        )
    assert row["building_base_cost_total"] == 200.0
    assert row["resources_stored_total"] == 15.0
    assert row["estimated_building_cost_total"] == pytest.approx(
        sum(row[f"estimated_building_cost_{resource}"] for resource in RESOURCES)
    )


def test_reducer_affects_only_its_own_city() -> None:
    result = compute_city_metrics(
        _cities({"wood_reduction_building_level": 20}, {}), _player()
    ).sort("id")

    assert result.get_column("estimated_wood_cost_factor").to_list() == [0.66, 0.86]


def test_reducer_is_not_carried_across_snapshots() -> None:
    result = compute_city_metrics(
        _cities(
            {"id": "c1", "snapshot_id": "s1"},
            {"id": "c1", "snapshot_id": "s2", "wood_reduction_building_level": 20},
            {"id": "c1", "snapshot_id": "s3"},
        ),
        _player("s1", "s2", "s3"),
    ).sort("snapshot_id")

    assert result.get_column("estimated_wood_cost_factor").to_list() == [0.86, 0.66, 0.86]


def test_missing_research_factor_leaves_estimates_null() -> None:
    row = compute_city_metrics(
        _cities({"wood_reduction_building_level": 20}), _player("other")
    ).row(0, named=True)

    assert row["estimated_wood_cost_factor"] is None
    assert row["estimated_building_cost_wood"] is None
    assert row["building_base_cost_wood"] == 100.0


def test_factor_outside_historical_range_raises() -> None:
    with pytest.raises(ValueError, match=r"outside \[0.54, 1.0\]: rows=1"):
        compute_city_metrics(_cities(), _player(factor=0.5))


def test_missing_reducer_level_column_raises() -> None:
    with pytest.raises(
        ValueError, match="Missing reduction building level columns:.*wine_reduction_building_level"
    ):
        compute_city_metrics(_cities().drop("wine_reduction_building_level"), _player())


def test_building_cost_and_city_metric_steps_share_reducer_columns() -> None:
    raw_city = (
        _cities()
        .drop(
            *(f"building_base_cost_{resource}" for resource in RESOURCES),
            *REDUCTION_LEVEL_COLUMNS.values(),
        )
        .with_columns(pl.lit(0).alias(f"p{position}t") for position in range(1, 18))
        .with_columns(
            pl.lit(3).alias("p1t"),
            pl.lit(2).alias("p1l"),
            pl.lit(23).alias("p2t"),
            pl.lit(2).alias("p2l"),
        )
    )
    costs = pl.DataFrame(
        {
            "building_type": [3, 23],
            "building_level": [2, 2],
            "cost_holz": [100.0, 10.0],
            "cost_kristall": [20.0, 0.0],
            "cost_quartz": [30.0, 0.0],
            "cost_schwefel": [40.0, 0.0],
            "cost_wein": [10.0, 0.0],
        }
    )

    row = compute_city_metrics(add_building_base_costs(raw_city, costs), _player()).row(
        0, named=True
    )

    assert row["wood_reduction_building_level"] == 2
    assert row["building_base_cost_total"] == 210.0
    assert row["estimated_wood_cost_factor"] == 0.84
    assert row["estimated_building_cost_wood"] == pytest.approx(92.4)
    assert row["estimated_building_cost_total"] == pytest.approx(178.4)
