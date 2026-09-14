from __future__ import annotations

import polars as pl
import pytest

from ikariam.processing.transforms.building_costs import (
    REDUCTION_BUILDING_TYPES,
    REDUCTION_LEVEL_COLUMNS,
    add_building_base_costs,
)


def _city(**positions: list[int | None]) -> pl.DataFrame:
    row_count = len(next(iter(positions.values()), [0]))
    data: dict[str, list[int | None]] = {"id": list(range(1, row_count + 1))}
    for position in range(1, 18):
        data[f"p{position}t"] = positions.get(f"p{position}t", [0] * row_count)
        data[f"p{position}l"] = positions.get(f"p{position}l", [0] * row_count)
    return pl.DataFrame(data)


def _costs() -> pl.DataFrame:
    reducer_rows = [
        (building_type, level, float(level), 0.0, 0.0, 0.0, 0.0)
        for building_type in range(23, 28)
        for level in range(1, 33)
    ]
    rows = [
        (3, 2, 100.0, 20.0, 30.0, 40.0, 50.0),
        (9, 4, 10.0, 2.0, 3.0, 4.0, 5.0),
        *reducer_rows,
    ]
    return pl.DataFrame(
        rows,
        schema=[
            "building_type",
            "building_level",
            "cost_holz",
            "cost_kristall",
            "cost_quartz",
            "cost_schwefel",
            "cost_wein",
        ],
        orient="row",
    )


def _reducer_levels(result: pl.DataFrame) -> list[dict[str, int]]:
    return result.select(
        pl.col(column).alias(resource) for resource, column in REDUCTION_LEVEL_COLUMNS.items()
    ).to_dicts()


def test_add_building_base_costs_aggregates_positions() -> None:
    result = add_building_base_costs(
        _city(p1t=[3], p1l=[2], p2t=[9], p2l=[4]),
        _costs(),
    )

    cost_columns = [column for column in result.columns if column.startswith("building_base_cost_")]
    assert result.select(cost_columns).row(0) == (110.0, 22.0, 33.0, 44.0, 55.0)
    assert not any(column.startswith("g1") for column in result.columns)


def test_zero_type_or_level_is_a_zero_cost_slot() -> None:
    result = add_building_base_costs(
        _city(p1t=[31], p1l=[0], p2t=[0], p2l=[13]),
        _costs(),
    )

    cost_columns = [column for column in result.columns if column.startswith("building_base_cost_")]
    assert result.select(pl.sum_horizontal(cost_columns)).item() == 0


def test_missing_position_column_raises() -> None:
    with pytest.raises(ValueError, match="Missing building position columns:.*p17l"):
        add_building_base_costs(_city().drop("p17l"), _costs())


def test_missing_cost_lookup_raises() -> None:
    with pytest.raises(ValueError, match=r"Missing building cost lookups: \(31, 1\)"):
        add_building_base_costs(_city(p1t=[31], p1l=[1]), _costs())


def test_duplicate_cost_lookup_raises() -> None:
    duplicate = pl.concat([_costs(), _costs().head(1)])

    with pytest.raises(ValueError, match=r"Duplicate building cost lookups: \(3, 2\)"):
        add_building_base_costs(_city(), duplicate)


def test_reduction_building_types_match_documented_mapping() -> None:
    assert REDUCTION_BUILDING_TYPES == {
        "wood": 23,
        "marble": 24,
        "crystal": 25,
        "wine": 26,
        "sulfur": 27,
    }


def test_reducer_levels_are_extracted_per_resource_from_any_position() -> None:
    result = add_building_base_costs(
        _city(p1t=[3], p1l=[2], p2t=[24], p2l=[10], p9t=[23], p9l=[20], p17t=[27], p17l=[32]),
        _costs(),
    )

    assert _reducer_levels(result) == [
        {"wood": 20, "marble": 10, "crystal": 0, "wine": 0, "sulfur": 32}
    ]
    assert all(result.schema[column] == pl.Int64 for column in REDUCTION_LEVEL_COLUMNS.values())


def test_reducers_add_their_own_undiscounted_base_cost_only() -> None:
    result = add_building_base_costs(
        _city(p1t=[3], p1l=[2], p2t=[23], p2l=[20], p3t=[24], p3l=[10]),
        _costs(),
    )

    cost_columns = [column for column in result.columns if column.startswith("building_base_cost_")]
    assert result.select(cost_columns).row(0) == (130.0, 20.0, 30.0, 40.0, 50.0)


def test_empty_null_and_zero_level_slots_give_reducer_level_zero() -> None:
    result = add_building_base_costs(
        _city(p1t=[23, None, 0], p1l=[0, None, 0], p2t=[25, 26, 0], p2l=[None, 0, 5]),
        _costs(),
    )

    assert _reducer_levels(result) == [
        {"wood": 0, "marble": 0, "crystal": 0, "wine": 0, "sulfur": 0}
    ] * 3


def test_reducer_levels_stay_in_their_own_city_row() -> None:
    result = add_building_base_costs(
        _city(p1t=[23, 0], p1l=[20, 0], p2t=[0, 24], p2l=[0, 7]),
        _costs(),
    )

    assert result.get_column("id").to_list() == [1, 2]
    assert [(row["wood"], row["marble"]) for row in _reducer_levels(result)] == [(20, 0), (0, 7)]


def test_duplicate_reducer_in_one_city_raises() -> None:
    with pytest.raises(
        ValueError, match=r"Duplicate reduction buildings in 1 city rows: \[\{'id': 1\}\]"
    ):
        add_building_base_costs(_city(p1t=[23], p1l=[5], p2t=[23], p2l=[6]), _costs())


def test_reducer_level_above_historical_cap_raises_before_lookup_check() -> None:
    with pytest.raises(ValueError, match=r"above historical cap 32: \(23, 33\)"):
        add_building_base_costs(_city(p1t=[23], p1l=[33]), _costs())


def test_negative_building_level_raises() -> None:
    with pytest.raises(ValueError, match=r"Negative building levels: \(3, -1\)"):
        add_building_base_costs(_city(p1t=[3], p1l=[-1]), _costs())
