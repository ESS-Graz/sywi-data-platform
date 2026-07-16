from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import polars as pl
import pytest

from ikariam.processing.transforms.player_duration import enrich_avatars


REGISTRATION = datetime(2020, 1, 1, 12, 30, tzinfo=UTC)
REGISTRATION_UNIX = int(REGISTRATION.timestamp())


def _avatar(
    observations: list[tuple[str, str, int]],
    *,
    country: str = "DE",
    registration_time: object = REGISTRATION_UNIX,
) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "country": [country] * len(observations),
            "id": [player_id for player_id, _, _ in observations],
            "snapshot_id": [snapshot_id for _, snapshot_id, _ in observations],
            "snapshot_date": [
                REGISTRATION.date() + timedelta(days=age_days)
                for _, _, age_days in observations
            ],
            "registration_time": [registration_time] * len(observations),
            "gold": list(range(len(observations))),
        }
    )


def _empty_city() -> pl.DataFrame:
    return pl.DataFrame(
        schema={"country": pl.String, "owner_id": pl.String, "snapshot_id": pl.String}
    )


def _complete_city_slots(frame: pl.DataFrame) -> pl.DataFrame:
    missing = [
        pl.lit(0, dtype=pl.Int64).alias(f"p{position}{suffix}")
        for position in range(1, 18)
        for suffix in ("t", "l")
        if f"p{position}{suffix}" not in frame.columns
    ]
    return frame.with_columns(missing)


def test_snapshot_age_boundaries_and_output_contract() -> None:
    observations = [
        ("p1", "s0", 0),
        ("p1", "s2", 2),
        ("p1", "s3", 3),
        ("p1", "s16", 16),
        ("p1", "s17", 17),
        ("p1", "s152", 152),
        ("p1", "s153", 153),
    ]

    result = enrich_avatars(_avatar(observations), _empty_city())

    assert result.get_column("account_age_days").to_list() == [0, 2, 3, 16, 17, 152, 153]
    assert result.get_column("estimated_research_cost_factor").to_list() == [
        1.0,
        1.0,
        0.98,
        0.98,
        0.94,
        0.94,
        0.86,
    ]
    assert result.get_column("estimated_research_cost_factor_source").to_list() == [
        "age_heuristic"
    ] * len(observations)
    assert result.get_column("research_evidence_tier").to_list() == ["none"] * len(
        observations
    )
    assert result.schema["registered_at"] == pl.Datetime("us", "UTC")
    assert result.schema["account_age_days"] == pl.Int64
    assert result.schema["estimated_research_cost_factor"] == pl.Float64
    assert result.row(0, named=True)["registered_at"] == REGISTRATION
    assert result.get_column("gold").to_list() == list(range(len(observations)))


def test_strongest_nonzero_building_evidence_is_used_per_player_snapshot() -> None:
    avatar = _avatar(
        [
            ("pulley", "s1", 1),
            ("geometry", "s1", 1),
            ("spirit26", "s1", 1),
            ("spirit29", "s1", 1),
            ("zero_level", "s1", 1),
            ("strongest", "s1", 1),
        ]
    )
    city = _complete_city_slots(pl.DataFrame(
        {
            "country": ["DE"] * 7,
            "owner_id": [
                "pulley",
                "geometry",
                "spirit26",
                "spirit29",
                "zero_level",
                "strongest",
                "strongest",
            ],
            "snapshot_id": ["s1"] * 7,
            "p1t": [9, 24, 26, 29, 26, 9, 24],
            "p1l": [1, 1, 1, 1, 0, 1, 1],
        }
    ))

    rows = {
        row["id"]: row for row in enrich_avatars(avatar, city).sort("id").to_dicts()
    }

    assert (rows["pulley"]["estimated_research_cost_factor"], rows["pulley"]["research_evidence_tier"]) == (
        0.98,
        "pulley_or_later",
    )
    assert (
        rows["geometry"]["estimated_research_cost_factor"],
        rows["geometry"]["research_evidence_tier"],
    ) == (0.94, "geometry_or_later")
    assert (
        rows["spirit26"]["estimated_research_cost_factor"],
        rows["spirit26"]["research_evidence_tier"],
    ) == (0.86, "spirit_level_or_later")
    assert rows["spirit29"]["estimated_research_cost_factor"] == 0.86
    assert rows["zero_level"]["research_evidence_tier"] == "none"
    assert rows["strongest"]["research_evidence_tier"] == "geometry_or_later"
    assert rows["strongest"]["estimated_research_cost_factor_source"] == "building_evidence"


def test_building_source_requires_strictly_stronger_evidence() -> None:
    avatar = _avatar([("equal", "s3", 3), ("weaker", "s17", 17)])
    city = _complete_city_slots(pl.DataFrame(
        {
            "country": ["DE", "DE"],
            "owner_id": ["equal", "weaker"],
            "snapshot_id": ["s3", "s17"],
            "p1t": [9, 9],
            "p1l": [1, 1],
        }
    ))

    result = enrich_avatars(avatar, city).sort("id")

    assert result.get_column("estimated_research_cost_factor").to_list() == [0.98, 0.94]
    assert result.get_column("estimated_research_cost_factor_source").to_list() == [
        "age_heuristic",
        "age_heuristic",
    ]
    assert result.get_column("research_evidence_tier").to_list() == [
        "pulley_or_later",
        "pulley_or_later",
    ]


def test_evidence_carries_forward_without_lookahead_or_cross_country_leakage() -> None:
    de_avatar = _avatar(
        [("p1", "de_late", 10), ("p1", "de_early", 1), ("p1", "de_evidence", 5)]
    )
    en_avatar = _avatar([("p1", "en_late", 10)], country="EN")
    avatar = pl.concat([de_avatar, en_avatar])
    city = _complete_city_slots(pl.DataFrame(
        {
            "country": ["DE"],
            "owner_id": ["p1"],
            "snapshot_id": ["de_evidence"],
            "p1t": [24],
            "p1l": [1],
        }
    ))

    rows = {
        (row["country"], row["snapshot_id"]): row
        for row in enrich_avatars(avatar, city).to_dicts()
    }

    assert rows[("DE", "de_early")]["research_evidence_tier"] == "none"
    assert rows[("DE", "de_early")]["estimated_research_cost_factor"] == 1.0
    assert rows[("DE", "de_evidence")]["research_evidence_tier"] == "geometry_or_later"
    assert rows[("DE", "de_late")]["research_evidence_tier"] == "geometry_or_later"
    assert rows[("DE", "de_late")]["estimated_research_cost_factor"] == 0.94
    assert rows[("EN", "en_late")]["research_evidence_tier"] == "none"


@pytest.mark.parametrize(
    ("registration_time", "message"),
    [
        (None, "null registration_time: rows=1"),
        (REGISTRATION_UNIX + 0.5, "non-integer registration_time: rows=1"),
        ("not-a-timestamp", "non-integer registration_time: rows=1"),
        (946_684_800, "implausible registration_time: rows=1"),
        (float("nan"), "non-integer registration_time: rows=1"),
    ],
)
def test_registration_value_validation_reports_count_and_sample_keys(
    registration_time: object, message: str
) -> None:
    avatar = _avatar([("bad-player", "bad-snapshot", 1)], registration_time=registration_time)

    with pytest.raises(ValueError) as exc_info:
        enrich_avatars(avatar, _empty_city())

    assert message in str(exc_info.value)
    assert "bad-player" in str(exc_info.value)
    assert "bad-snapshot" in str(exc_info.value)


def test_registration_must_be_invariant_per_country_player() -> None:
    avatar = _avatar([("p1", "s1", 1), ("p1", "s2", 2)]).with_columns(
        pl.when(pl.col("snapshot_id") == "s2")
        .then(pl.col("registration_time") + 1)
        .otherwise(pl.col("registration_time"))
        .alias("registration_time")
    )

    with pytest.raises(ValueError) as exc_info:
        enrich_avatars(avatar, _empty_city())

    assert "registration_time is not invariant per player: players=1" in str(exc_info.value)
    assert "p1" in str(exc_info.value)


def test_registration_cannot_be_after_snapshot_date() -> None:
    future_registration = int((REGISTRATION + timedelta(days=2)).timestamp())
    avatar = _avatar([("p1", "s1", 1)], registration_time=future_registration)

    with pytest.raises(ValueError) as exc_info:
        enrich_avatars(avatar, _empty_city())

    assert "registration_time is after snapshot_date: rows=1" in str(exc_info.value)
    assert "p1" in str(exc_info.value)


def test_duplicate_player_snapshot_reports_group_count_and_sample_key() -> None:
    row = _avatar([("p1", "s1", 1)])
    avatar = pl.concat([row, row])

    with pytest.raises(ValueError) as exc_info:
        enrich_avatars(avatar, _empty_city())

    assert "duplicate player-snapshot keys: duplicate_groups=1" in str(exc_info.value)
    assert "p1" in str(exc_info.value)
    assert "s1" in str(exc_info.value)


def test_invalid_snapshot_date_is_reported() -> None:
    avatar = _avatar([("p1", "s1", 1)]).with_columns(
        pl.lit(None, dtype=pl.Date).alias("snapshot_date")
    )

    with pytest.raises(ValueError, match="invalid snapshot_date: rows=1"):
        enrich_avatars(avatar, _empty_city())


def test_nonempty_city_requires_the_complete_building_slot_schema() -> None:
    city = pl.DataFrame(
        {
            "country": ["DE"],
            "owner_id": ["p1"],
            "snapshot_id": ["s1"],
            "p1t": [9],
            "p1l": [1],
        }
    )

    with pytest.raises(ValueError, match="city_raw missing required columns"):
        enrich_avatars(_avatar([("p1", "s1", 1)]), city)


def test_malformed_building_slot_value_is_reported() -> None:
    city = _complete_city_slots(
        pl.DataFrame(
            {
                "country": ["DE"],
                "owner_id": ["p1"],
                "snapshot_id": ["s1"],
                "p1t": ["not-a-building-type"],
                "p1l": [1],
            }
        )
    )

    with pytest.raises(ValueError) as exc_info:
        enrich_avatars(_avatar([("p1", "s1", 1)]), city)

    assert "non-integer city building slot value: rows=1" in str(exc_info.value)
    assert "p1" in str(exc_info.value)
