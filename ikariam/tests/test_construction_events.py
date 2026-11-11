from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from ikariam.processing.transforms.construction_events import (
    RESOURCE_NAMES,
    build_construction_events,
    build_demolition_events,
    build_level_cost_deltas,
    build_slot_panel,
    publish_preexisting_share,
    summarize_city_construction,
)

_DATES = {"s1": date(2020, 1, 1), "s2": date(2020, 2, 1), "s3": date(2020, 3, 1)}


def _costs() -> pl.DataFrame:
    """Type 3 costs 100/200/300 per level; type 9 a flat 10; town hall free."""
    rows: list[tuple[int, int, float, float, float, float, float]] = []

    for level, cumulative in ((1, 100.0), (2, 300.0), (3, 600.0)):
        rows.append((3, level, cumulative, 0.0, 0.0, 0.0, 0.0))

    for level in range(1, 6):
        rows.append((9, level, 10.0 * level, 0.0, 0.0, 0.0, 0.0))

    for level in range(1, 4):
        rows.append((1, level, 0.0, 0.0, 0.0, 0.0, 0.0))

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


def _city(*snapshots: dict[str, object], city_id: str = "c1") -> pl.DataFrame:
    """Build a one-city panel; each snapshot gives slot (type, level) pairs."""
    rows = []

    for snapshot in snapshots:
        slots: dict[int, tuple[int, int]] = snapshot.get("slots", {})  # type: ignore[assignment]
        snapshot_id = str(snapshot["snapshot_id"])

        row: dict[str, object] = {
            "country": "DE",
            "server": 1,
            "id": city_id,
            "owner_id": snapshot.get("owner", "p1"),
            "estimated_research_cost_factor": snapshot.get("research", 1.0),
            "snapshot_id": snapshot_id,
            "snapshot_date": _DATES[snapshot_id],
            "level": snapshot.get("town_hall", 0),
        }

        for position in range(1, 18):
            building_type, building_level = slots.get(position, (0, 0))
            row[f"p{position}t"] = building_type
            row[f"p{position}l"] = building_level

        for resource in RESOURCE_NAMES:
            row[f"cost_factor_today_{resource}"] = snapshot.get("factor", 1.0)

        rows.append(row)

    return pl.DataFrame(rows)


def _events(city: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    panel = build_slot_panel(city)
    built = build_construction_events(panel, city, _costs())
    removed = build_demolition_events(panel, built)

    return built, removed, panel


def test_levels_are_priced_at_the_interval_midpoint_factor() -> None:
    city = _city(
        {"snapshot_id": "s1", "slots": {1: (3, 1)}, "factor": 1.0},
        {"snapshot_id": "s2", "slots": {1: (3, 3)}, "factor": 0.8},
    )

    events, _, _ = _events(city)

    assert events.sort("building_level").select(
        "building_level", "is_preexisting", "cost_factor_at_build_wood", "cost_at_build_wood"
    ).to_dicts() == [
        # Level 1 was already there: dated to first sighting, factor 1.0.
        {"building_level": 1, "is_preexisting": True, "cost_factor_at_build_wood": 1.0, "cost_at_build_wood": 100.0},
        # Levels 2 and 3 appeared between s1 and s2: midpoint of 1.0 and 0.8.
        {"building_level": 2, "is_preexisting": False, "cost_factor_at_build_wood": 0.9, "cost_at_build_wood": 180.0},
        {"building_level": 3, "is_preexisting": False, "cost_factor_at_build_wood": 0.9, "cost_at_build_wood": 270.0},
    ]


def test_city_founded_after_the_first_snapshot_is_dated_not_preexisting() -> None:
    # c0 exists from the start; its owner has research factor 0.9 at s1.
    old = _city(
        {"snapshot_id": "s1", "slots": {1: (3, 1)}, "factor": 0.9, "research": 0.9},
        {"snapshot_id": "s2", "slots": {1: (3, 1)}, "factor": 0.8, "research": 0.8},
        city_id="c0",
    )
    # The same player founds c1 between s1 and s2.
    new = _city({"snapshot_id": "s2", "slots": {1: (3, 2)}, "factor": 0.8, "research": 0.8})

    events, _, _ = _events(pl.concat([old, new]))
    c1 = events.filter(pl.col("city_id") == "c1").sort("building_level")

    assert not any(c1["is_preexisting"].to_list())
    assert c1["built_after_snapshot_date"].to_list() == [_DATES["s1"], _DATES["s1"]]
    # Midpoint of the owner's research factor at s1 (no reduction buildings
    # yet) and the city's own factor at s2.
    assert c1["cost_factor_at_build_wood"].to_list() == [pytest.approx(0.85)] * 2
    assert c1["cost_at_build_wood"].to_list() == [pytest.approx(85.0), pytest.approx(170.0)]
    # c0 was already standing at the server's first snapshot.
    assert events.filter(pl.col("city_id") == "c0")["is_preexisting"].to_list() == [True]


def test_new_player_starts_without_research_discount() -> None:
    old = _city(
        {"snapshot_id": "s1", "slots": {1: (3, 1)}, "factor": 0.9, "research": 0.9},
        {"snapshot_id": "s2", "slots": {1: (3, 1)}, "factor": 0.9, "research": 0.9},
        city_id="c0",
    )
    # p2 has no city at s1, so it had not started and had no research yet.
    new = _city({"snapshot_id": "s2", "slots": {1: (3, 1)}, "factor": 0.8, "owner": "p2"})

    events, _, _ = _events(pl.concat([old, new]))
    c1 = events.filter(pl.col("city_id") == "c1")

    assert c1["cost_factor_at_build_wood"].to_list() == [pytest.approx(0.9)]


def test_standing_value_and_lifetime_spend_track_construction() -> None:
    city = _city(
        {"snapshot_id": "s1", "slots": {1: (3, 1)}, "factor": 1.0},
        {"snapshot_id": "s2", "slots": {1: (3, 3)}, "factor": 0.8},
        {"snapshot_id": "s3", "slots": {1: (3, 3)}, "factor": 0.8},
    )

    built, removed, panel = _events(city)
    summary = summarize_city_construction(panel, built, removed).sort("snapshot_date")

    assert summary["standing_cost_at_build_wood"].to_list() == [100.0, 550.0, 550.0]
    assert summary["ever_built_cost_at_build_wood"].to_list() == [100.0, 550.0, 550.0]


def test_demolition_lowers_standing_value_but_not_lifetime_spend() -> None:
    city = _city(
        {"snapshot_id": "s1", "slots": {1: (9, 5)}, "factor": 1.0},
        {"snapshot_id": "s2", "slots": {1: (9, 2)}, "factor": 1.0},
    )

    built, removed, panel = _events(city)
    summary = summarize_city_construction(panel, built, removed).sort("snapshot_date")

    # Five levels at 10 each were paid for; only two still stand at s2.
    assert summary["standing_cost_at_build_wood"].to_list() == [50.0, 20.0]
    assert summary["ever_built_cost_at_build_wood"].to_list() == [50.0, 50.0]


def test_rebuilt_level_is_valued_at_its_latest_vintage() -> None:
    city = _city(
        {"snapshot_id": "s1", "slots": {1: (9, 2)}, "factor": 1.0},
        {"snapshot_id": "s2", "slots": {1: (9, 1)}, "factor": 0.5},
        {"snapshot_id": "s3", "slots": {1: (9, 2)}, "factor": 0.5},
    )

    built, removed, panel = _events(city)
    summary = summarize_city_construction(panel, built, removed).sort("snapshot_date")

    # Level 2 is rebuilt between s2 and s3 at a midpoint factor of 0.5,
    # so it is worth 5 rather than the 10 it cost the first time.
    assert summary["standing_cost_at_build_wood"].to_list() == [20.0, 10.0, 15.0]
    assert summary["ever_built_cost_at_build_wood"].to_list() == [20.0, 20.0, 25.0]


def test_replacing_a_building_restarts_its_levels() -> None:
    city = _city(
        {"snapshot_id": "s1", "slots": {1: (3, 2)}, "factor": 1.0},
        {"snapshot_id": "s2", "slots": {1: (9, 3)}, "factor": 1.0},
    )

    built, removed, panel = _events(city)

    replacement = built.filter(pl.col("building_type") == 9).sort("building_level")
    assert replacement["building_level"].to_list() == [1, 2, 3]
    assert not any(replacement["is_preexisting"].to_list())

    summary = summarize_city_construction(panel, built, removed).sort("snapshot_date")
    # Only the new building stands at s2; the replaced one is gone.
    assert summary["standing_cost_at_build_wood"].to_list() == [300.0, 30.0]
    assert summary["ever_built_cost_at_build_wood"].to_list() == [300.0, 330.0]


def test_town_hall_levels_are_dated_like_any_other_building() -> None:
    city = _city(
        {"snapshot_id": "s1", "slots": {1: (3, 1)}, "town_hall": 1, "factor": 1.0},
        {"snapshot_id": "s2", "slots": {1: (3, 1)}, "town_hall": 3, "factor": 1.0},
    )

    events, _, _ = _events(city)

    town_hall = events.filter(pl.col("building_type") == 1).sort("building_level")
    assert town_hall["building_level"].to_list() == [1, 2, 3]
    assert town_hall["position"].unique().to_list() == [0]


def test_preexisting_share_reports_the_undatable_share() -> None:
    city = _city(
        {"snapshot_id": "s1", "slots": {1: (3, 1)}, "factor": 1.0},
        {"snapshot_id": "s2", "slots": {1: (3, 3)}, "factor": 1.0},
    )

    built, removed, panel = _events(city)
    summary = summarize_city_construction(panel, built, removed).sort("snapshot_date")

    # At s1 everything is preexisting; at s2 only 100 of 600 undiscounted cost is.
    assert summary["preexisting_share"].to_list() == [1.0, pytest.approx(100 / 600)]
    assert summary["preexisting_cost_undiscounted_total"].to_list() == [100.0, 100.0]


def test_published_preexisting_share_is_null_without_buildings_and_drops_its_total() -> None:
    frame = pl.DataFrame(
        {
            "standing_cost_undiscounted_total": [600.0, 0.0],
            "preexisting_cost_undiscounted_total": [150.0, 0.0],
        }
    )

    published = publish_preexisting_share(frame)

    # A city without buildings has no share; it must not read as 0 or 1.
    assert published["preexisting_share"].to_list() == [0.25, None]
    assert "preexisting_cost_undiscounted_total" not in published.columns


def test_non_contiguous_cost_levels_raise() -> None:
    gapped = _costs().filter(
        ~((pl.col("building_type") == 3) & (pl.col("building_level") == 2))
    )

    with pytest.raises(ValueError, match="must run 1..max without gaps"):
        build_level_cost_deltas(gapped)


def test_missing_cost_factor_columns_raise() -> None:
    city = _city({"snapshot_id": "s1", "slots": {1: (3, 1)}})
    panel = build_slot_panel(city)

    with pytest.raises(ValueError, match="missing cost factor columns"):
        build_construction_events(
            panel, city.drop("cost_factor_today_wine"), _costs()
        )
