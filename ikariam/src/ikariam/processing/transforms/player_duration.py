"""Derive snapshot-relative player age and research-cost evidence.

The raw account registration timestamp is validated as a player invariant and
converted to a UTC datetime. Research evidence is inferred from non-zero city
building slots and carried forward within a player trajectory without using
future observations.
"""

from __future__ import annotations

import polars as pl


_PLAYER_KEYS = ["country", "id"]
_SNAPSHOT_KEYS = ["country", "id", "snapshot_id"]
_MIN_PLAUSIBLE_REGISTRATION_UNIX = 1_199_145_600  # 2008-01-01 UTC
_MAX_PLAUSIBLE_REGISTRATION_UNIX = 4_102_444_800  # 2100-01-01 UTC

_EVIDENCE_BY_BUILDING_TYPE: dict[int, tuple[int, float, str]] = {
    9: (1, 0.98, "pulley_or_later"),
    24: (2, 0.94, "geometry_or_later"),
    26: (3, 0.86, "spirit_level_or_later"),
    29: (3, 0.86, "spirit_level_or_later"),
}
_INTERNAL_COLUMNS = {
    "_registration_numeric",
    "_registration_time_int",
    "_snapshot_date",
    "_registration_date",
    "_row_order",
    "_current_evidence_rank",
    "_research_evidence_rank",
    "_age_factor",
    "_evidence_factor",
}


def _sample_keys(frame: pl.DataFrame, keys: list[str]) -> list[dict[str, object]]:
    present = [key for key in keys if key in frame.columns]
    if not present:
        return []
    return frame.select(present).unique(maintain_order=True).head(5).to_dicts()


def _validation_error(
    problem: str,
    frame: pl.DataFrame,
    *,
    keys: list[str] = _SNAPSHOT_KEYS,
    count_name: str = "rows",
) -> ValueError:
    return ValueError(
        f"{problem}: {count_name}={frame.height}; sample_keys={_sample_keys(frame, keys)}"
    )


def _require_columns(frame: pl.DataFrame, required: set[str], frame_name: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{frame_name} missing required columns: {missing}")


def prepare_validated_avatars(avatar_raw: pl.DataFrame) -> pl.DataFrame:
    """Validate registration/snapshot invariants and derive UTC age fields.

    The pipeline calls this before cohort filtering so malformed rows cannot
    disappear merely because their registration value fails the filter cast.
    ``enrich_avatars`` calls it again at its public transform boundary, keeping
    the transform safe when it is used independently of Dagster.
    """
    _require_columns(
        avatar_raw,
        {"country", "id", "snapshot_id", "snapshot_date", "registration_time"},
        "avatar_raw",
    )

    duplicate_keys = (
        avatar_raw.group_by(_SNAPSHOT_KEYS)
        .len()
        .filter(pl.col("len") > 1)
        .drop("len")
    )
    if duplicate_keys.height:
        raise _validation_error(
            "duplicate player-snapshot keys",
            duplicate_keys,
            count_name="duplicate_groups",
        )

    null_registration = avatar_raw.filter(pl.col("registration_time").is_null())
    if null_registration.height:
        raise _validation_error("null registration_time", null_registration)

    prepared = avatar_raw.with_columns(
        pl.col("registration_time").cast(pl.Float64, strict=False).alias("_registration_numeric"),
        pl.col("snapshot_date").cast(pl.Date, strict=False).alias("_snapshot_date"),
    )

    invalid_snapshot_date = prepared.filter(pl.col("_snapshot_date").is_null())
    if invalid_snapshot_date.height:
        raise _validation_error("invalid snapshot_date", invalid_snapshot_date)

    invalid_integer = prepared.filter(
        pl.col("_registration_numeric").is_null()
        | pl.col("_registration_numeric").is_nan()
        | pl.col("_registration_numeric").is_infinite()
        | (pl.col("_registration_numeric") != pl.col("_registration_numeric").floor())
    )
    if invalid_integer.height:
        raise _validation_error("non-integer registration_time", invalid_integer)

    prepared = prepared.with_columns(
        pl.col("_registration_numeric")
        .cast(pl.Int64, strict=False)
        .alias("_registration_time_int")
    )
    implausible = prepared.filter(
        pl.col("_registration_time_int").is_null()
        | (pl.col("_registration_time_int") < _MIN_PLAUSIBLE_REGISTRATION_UNIX)
        | (pl.col("_registration_time_int") > _MAX_PLAUSIBLE_REGISTRATION_UNIX)
    )
    if implausible.height:
        raise _validation_error("implausible registration_time", implausible)

    inconsistent_players = (
        prepared.group_by(_PLAYER_KEYS)
        .agg(pl.col("_registration_time_int").n_unique().alias("registration_time_count"))
        .filter(pl.col("registration_time_count") > 1)
        .drop("registration_time_count")
    )
    if inconsistent_players.height:
        raise _validation_error(
            "registration_time is not invariant per player",
            inconsistent_players,
            keys=_PLAYER_KEYS,
            count_name="players",
        )

    prepared = prepared.with_columns(
        pl.from_epoch(pl.col("_registration_time_int"), time_unit="s")
        .dt.replace_time_zone("UTC")
        .alias("registered_at")
    ).with_columns(pl.col("registered_at").dt.date().alias("_registration_date"))

    future_registration = prepared.filter(
        pl.col("_registration_date") > pl.col("_snapshot_date")
    )
    if future_registration.height:
        raise _validation_error("registration_time is after snapshot_date", future_registration)

    return prepared.with_columns(
        (pl.col("_snapshot_date") - pl.col("_registration_date"))
        .dt.total_days()
        .cast(pl.Int64)
        .alias("account_age_days")
    )


def _current_research_evidence(city_raw: pl.DataFrame) -> pl.DataFrame:
    _require_columns(city_raw, {"country", "owner_id", "snapshot_id"}, "city_raw")

    slot_columns = [
        f"p{position}{suffix}"
        for position in range(1, 18)
        for suffix in ("t", "l")
    ]
    if city_raw.height:
        _require_columns(city_raw, set(slot_columns), "city_raw")

    present_slot_columns = [
        column for column in slot_columns if column in city_raw.columns
    ]
    if present_slot_columns:
        invalid_slot_values = city_raw.filter(
            pl.any_horizontal(
                [
                    pl.col(column).is_not_null()
                    & (
                        pl.col(column).cast(pl.Float64, strict=False).is_null()
                        | pl.col(column).cast(pl.Float64, strict=False).is_nan()
                        | pl.col(column)
                        .cast(pl.Float64, strict=False)
                        .is_infinite()
                        | (
                            pl.col(column).cast(pl.Float64, strict=False)
                            != pl.col(column)
                            .cast(pl.Float64, strict=False)
                            .floor()
                        )
                    )
                    for column in present_slot_columns
                ]
            )
        )
        if invalid_slot_values.height:
            raise _validation_error(
                "non-integer city building slot value",
                invalid_slot_values,
                keys=["country", "owner_id", "snapshot_id"],
            )

    normalized_city = city_raw.with_columns(
        pl.col(column).cast(pl.Int64, strict=False)
        for column in present_slot_columns
    )

    observations: list[pl.DataFrame] = []
    for position in range(1, 18):
        type_column = f"p{position}t"
        level_column = f"p{position}l"
        if (
            type_column not in normalized_city.columns
            or level_column not in normalized_city.columns
        ):
            continue

        slot = (
            normalized_city.select(
                "country",
                pl.col("owner_id").alias("id"),
                "snapshot_id",
                pl.col(type_column).alias("_building_type"),
                pl.col(level_column).alias("_building_level"),
            )
            .filter(
                (pl.col("_building_level") > 0)
                & pl.col("_building_type").is_in(list(_EVIDENCE_BY_BUILDING_TYPE))
            )
            .with_columns(
                pl.col("_building_type")
                .replace_strict(
                    {
                        building_type: evidence[0]
                        for building_type, evidence in _EVIDENCE_BY_BUILDING_TYPE.items()
                    },
                    return_dtype=pl.Int8,
                )
                .alias("_current_evidence_rank")
            )
            .select(*_SNAPSHOT_KEYS, "_current_evidence_rank")
        )
        if slot.height:
            observations.append(slot)

    if not observations:
        return pl.DataFrame(
            schema={
                "country": pl.String,
                "id": pl.String,
                "snapshot_id": pl.String,
                "_current_evidence_rank": pl.Int8,
            }
        )

    return (
        pl.concat(observations, how="vertical_relaxed")
        .group_by(_SNAPSHOT_KEYS)
        .agg(pl.col("_current_evidence_rank").max())
    )


def _age_factor() -> pl.Expr:
    return (
        pl.when(pl.col("account_age_days") <= 2)
        .then(pl.lit(1.0))
        .when(pl.col("account_age_days") <= 16)
        .then(pl.lit(0.98))
        .when(pl.col("account_age_days") <= 152)
        .then(pl.lit(0.94))
        .otherwise(pl.lit(0.86))
        .cast(pl.Float64)
    )


def enrich_avatars(avatar_raw: pl.DataFrame, city_raw: pl.DataFrame) -> pl.DataFrame:
    """Add validated snapshot age and cumulative research-building evidence.

    Evidence is aggregated across all current cities for a player-snapshot and
    then carried only into later observations of the same country/player. The
    final factor is the stronger (numerically smaller) of age and evidence;
    evidence is the source only when it strictly improves on the age heuristic.
    """
    prepared = prepare_validated_avatars(avatar_raw).with_row_index("_row_order")
    current_evidence = _current_research_evidence(city_raw)

    result = prepared.join(current_evidence, on=_SNAPSHOT_KEYS, how="left").with_columns(
        pl.col("_current_evidence_rank").fill_null(0).cast(pl.Int8)
    )
    result = result.sort(["country", "id", "_snapshot_date", "snapshot_id"]).with_columns(
        pl.col("_current_evidence_rank")
        .cum_max()
        .over(_PLAYER_KEYS)
        .alias("_research_evidence_rank")
    )

    result = result.with_columns(
        _age_factor().alias("_age_factor"),
        pl.col("_research_evidence_rank")
        .replace_strict(
            {0: 1.0, 1: 0.98, 2: 0.94, 3: 0.86},
            return_dtype=pl.Float64,
        )
        .alias("_evidence_factor"),
        pl.col("_research_evidence_rank")
        .replace_strict(
            {
                0: "none",
                1: "pulley_or_later",
                2: "geometry_or_later",
                3: "spirit_level_or_later",
            },
            return_dtype=pl.String,
        )
        .alias("research_evidence_tier"),
    ).with_columns(
        pl.min_horizontal("_age_factor", "_evidence_factor")
        .cast(pl.Float64)
        .alias("estimated_research_cost_factor"),
        pl.when(pl.col("_evidence_factor") < pl.col("_age_factor"))
        .then(pl.lit("building_evidence"))
        .otherwise(pl.lit("age_heuristic"))
        .alias("estimated_research_cost_factor_source"),
    )

    internal_columns = [column for column in result.columns if column in _INTERNAL_COLUMNS]
    return result.sort("_row_order").drop(internal_columns)


def build_teilnahme_av(avatar_enriched: pl.DataFrame) -> pl.DataFrame:
    grouped = (
        avatar_enriched.group_by("id")
        .agg(
            pl.col("snapshot_id").n_unique().alias("Anzahl_vorhanden"),
            pl.col("snapshot_date").min().alias("first_seen"),
            pl.col("snapshot_date").max().alias("last_seen"),
        )
        .rename({"id": "avatar_id"})
    )
    return grouped.with_columns(
        (pl.col("last_seen") - pl.col("first_seen")).dt.total_days().alias("days_observed")
    ).sort("avatar_id")


def build_master_avi(
    city_with_costs: pl.DataFrame, teilnahme_av: pl.DataFrame
) -> pl.DataFrame:
    grouped = city_with_costs.group_by(["owner_id", "island_id"]).agg(
        pl.len().alias("Cities_Vorhanden"),
        pl.col("snapshot_date").min().alias("first_seen"),
        pl.col("snapshot_date").max().alias("last_seen"),
        pl.col("snapshot_id").n_unique().alias("snapshots_present"),
    )

    joined = grouped.join(
        teilnahme_av.select(
            pl.col("avatar_id").alias("owner_id"),
            pl.col("Anzahl_vorhanden").alias("Anzahl_Teilnahme"),
        ),
        on="owner_id",
        how="left",
    ).with_columns(pl.col("Anzahl_Teilnahme").fill_null(0))

    return joined.sort(["owner_id", "island_id"])
