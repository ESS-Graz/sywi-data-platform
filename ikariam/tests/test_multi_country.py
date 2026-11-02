"""Country isolation across the transform chain.

Snapshot ids are country-prefixed (``de_1311_14``), so most joins are scoped to
one country for free. These tests pin that down with the adversarial case the
real data cannot produce yet: the *same* player, city and island ids present on
two servers. If a join or window key ever loses its country component, the two
servers merge and these assertions fail.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl
import pytest

from ikariam.processing.transforms.building_costs import add_building_base_costs
from ikariam.processing.transforms.city_metrics import compute_city_metrics
from ikariam.processing.transforms.construction_events import (
    attach_city_construction,
    build_construction_events,
    build_demolition_events,
    build_slot_panel,
    summarize_city_construction,
)
from ikariam.processing.io_lance import partition_raw_tables_by_country


# The same ids on both servers: a server-local id space is not assumed.
CITY_ID = "c1"
PLAYER_ID = "p1"
ISLAND_ID = "i1"


def _city(
    country: str,
    snapshot_id: str,
    snapshot_date: date,
    town_hall_level: int,
    slot_level: int,
) -> dict[str, object]:
    row: dict[str, object] = {
        "id": CITY_ID,
        "owner_id": PLAYER_ID,
        "island_id": ISLAND_ID,
        "snapshot_id": snapshot_id,
        "snapshot_date": snapshot_date,
        "country": country,
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
        "level": town_hall_level,
    }
    for position in range(1, 18):
        row[f"p{position}t"] = 3 if position == 1 else 0
        row[f"p{position}l"] = slot_level if position == 1 else 0
    return row


@pytest.fixture
def cities() -> pl.DataFrame:
    """DE builds between the two snapshots; EN stands still."""
    return pl.DataFrame(
        [
            _city("DE", "de_0101_20", date(2020, 1, 1), town_hall_level=5, slot_level=1),
            _city("DE", "de_0801_20", date(2020, 1, 8), town_hall_level=7, slot_level=3),
            _city("EN", "en_0101_20", date(2020, 1, 1), town_hall_level=2, slot_level=1),
            _city("EN", "en_0801_20", date(2020, 1, 8), town_hall_level=2, slot_level=1),
        ]
    )


@pytest.fixture
def costs() -> pl.DataFrame:
    """Town hall (type 1) 1000 wood/level, type 3 100 wood/level, cumulative."""
    return pl.DataFrame(
        [(1, level, 1000.0 * level, 0.0, 500.0 * level, 0.0, 0.0) for level in range(1, 11)]
        + [(3, level, 100.0 * level, 0.0, 50.0 * level, 0.0, 0.0) for level in range(1, 11)],
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


@pytest.fixture
def players() -> pl.DataFrame:
    snapshot_ids = ["de_0101_20", "de_0801_20", "en_0101_20", "en_0801_20"]
    return pl.DataFrame(
        {
            "country": ["DE", "DE", "EN", "EN"],
            "id": [PLAYER_ID] * 4,
            "snapshot_id": snapshot_ids,
            "account_age_days": [200] * 4,
            "registered_at": [datetime(2020, 1, 1, tzinfo=UTC)] * 4,
            "estimated_research_cost_factor": [0.86] * 4,
            "estimated_research_cost_factor_source": ["age_heuristic"] * 4,
            "research_evidence_tier": ["geometry_or_later"] * 4,
        }
    )


@pytest.fixture
def enriched(cities: pl.DataFrame, costs: pl.DataFrame, players: pl.DataFrame) -> pl.DataFrame:
    return compute_city_metrics(add_building_base_costs(cities, costs), players)


def _by_snapshot(df: pl.DataFrame, column: str) -> dict[str, object]:
    return {row["snapshot_id"]: row[column] for row in df.select("snapshot_id", column).to_dicts()}


def test_colliding_city_ids_keep_separate_base_costs(enriched: pl.DataFrame) -> None:
    # DE: town hall 5 (5000) + slot 1 (100); then 7 (7000) + slot 3 (300).
    # EN: town hall 2 (2000) + slot 1 (100), unchanged in both snapshots.
    assert _by_snapshot(enriched, "building_base_cost_wood") == {
        "de_0101_20": 5100.0,
        "de_0801_20": 7300.0,
        "en_0101_20": 2100.0,
        "en_0801_20": 2100.0,
    }


def test_colliding_city_ids_keep_separate_building_levels(enriched: pl.DataFrame) -> None:
    assert _by_snapshot(enriched, "Geblev") == {
        "de_0101_20": 6,
        "de_0801_20": 10,
        "en_0101_20": 3,
        "en_0801_20": 3,
    }


def test_research_factors_join_within_their_own_country(enriched: pl.DataFrame) -> None:
    assert enriched.get_column("estimated_research_cost_factor").to_list() == [0.86] * 4
    assert enriched.height == 4


def test_construction_events_are_attributed_to_their_own_country(
    enriched: pl.DataFrame, costs: pl.DataFrame
) -> None:
    panel = build_slot_panel(enriched)
    events = build_construction_events(panel, enriched, costs)

    counts = dict(events.group_by("country_code").len().iter_rows())
    # DE: 7 town hall levels + 3 slot levels. EN: 2 town hall levels + 1 slot.
    assert counts == {"DE": 10, "EN": 3}

    # Nothing EN is dated by a DE snapshot, or the reverse.
    for country, prefix in (("DE", "de_"), ("EN", "en_")):
        dated = events.filter(pl.col("country_code") == country)
        assert dated.get_column("built_by_snapshot_id").str.starts_with(prefix).all()


def test_de_construction_creates_no_en_events(
    enriched: pl.DataFrame, costs: pl.DataFrame
) -> None:
    panel = build_slot_panel(enriched)
    events = build_construction_events(panel, enriched, costs)
    en_events = events.filter(pl.col("country_code") == "EN")

    # EN never built after its first snapshot, so every EN level is opening stock.
    assert en_events.get_column("is_opening_stock").all()
    # DE's two post-opening levels must not appear anywhere under EN.
    assert en_events.filter(pl.col("building_level") > 2).is_empty()


def test_construction_measures_do_not_accumulate_across_countries(
    enriched: pl.DataFrame, costs: pl.DataFrame
) -> None:
    panel = build_slot_panel(enriched)
    events = build_construction_events(panel, enriched, costs)
    demolitions = build_demolition_events(panel, events)
    result = attach_city_construction(
        enriched, summarize_city_construction(panel, events, demolitions)
    )

    assert demolitions.is_empty()
    # EN stands still, so its lifetime spend is flat across both snapshots and
    # strictly below DE's.
    lifetime = _by_snapshot(result, "lifetime_construction_spend_total")
    assert lifetime["en_0101_20"] == lifetime["en_0801_20"]
    assert lifetime["de_0801_20"] > lifetime["de_0101_20"] > lifetime["en_0801_20"]

    # Opening stock is a per-city constant and must not pick up the other server.
    opening = _by_snapshot(result, "opening_stock_base_cost_total")
    assert opening["de_0101_20"] == opening["de_0801_20"]
    assert opening["en_0101_20"] == opening["en_0801_20"]
    assert opening["de_0101_20"] != opening["en_0101_20"]


def test_raw_tables_partition_into_one_table_per_country(cities: pl.DataFrame) -> None:
    partitions = partition_raw_tables_by_country({"raw_city": cities})

    assert sorted(partitions) == ["raw_city_de", "raw_city_en"]
    for name, country in (("raw_city_de", "DE"), ("raw_city_en", "EN")):
        assert partitions[name].get_column("country").unique().to_list() == [country]
        assert partitions[name].height == 2
