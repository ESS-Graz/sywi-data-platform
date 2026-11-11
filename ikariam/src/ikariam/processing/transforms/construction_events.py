"""Price individual building levels at the discount state active when built.

The cumulative ``standing_cost_today_*`` family applies one current factor
to a player's whole building stock, which misattributes today's research and
reduction-building discounts to levels built long before either existed.  This
module reconstructs the individual building levels from consecutive snapshots
and prices each level at the discount state observed around the interval in
which it appeared.

The exact moment inside an interval is unknowable, so the applied factor is the
midpoint of the city's factor at the two bracketing observations.  The residual
error is therefore bounded by one interval's change in discount state rather
than by the player's whole history.

Accounting is done as a flow, never by revaluing a level after the fact::

    standing value = everything paid for  -  everything torn down

so a level demolished and later rebuilt more cheaply changes the value from the
rebuild onwards and leaves earlier snapshots untouched.  Revaluing the past
with a later vintage would repeat the very error this module exists to remove.

Two measures come out of it:

``standing_cost_at_build_*``
    What the player paid for the levels still standing at that snapshot.
``ever_built_cost_at_build_*``
    What the player paid for every level ever built, including levels later
    demolished.  It never decreases.

Levels already present the first time a building is observed cannot be dated.
They are priced at the factor seen at that first observation and flagged as
preexisting, so ``preexisting_share`` exposes how much of a row rests on that
weaker assumption.
"""

from __future__ import annotations

import polars as pl

from .building_costs import (
    COST_COLUMNS,
    POSITION_COUNT,
    TOWN_HALL_BUILDING_TYPE,
    TOWN_HALL_LEVEL_COLUMN,
)

RESOURCE_NAMES: tuple[str, ...] = ("wood", "crystal", "marble", "sulfur", "wine")

# Shares the base-cost transform's convention that the town hall is position 0.
TOWN_HALL_POSITION = 0

# Helper total behind preexisting_share; summed at every grain, never published.
PREEXISTING_TOTAL = "preexisting_cost_undiscounted_total"

# Columns that aggregate by plain summation at every coarser grain.
CONSTRUCTION_SUM_COLUMNS: tuple[str, ...] = (
    tuple(f"standing_cost_at_build_{resource}" for resource in RESOURCE_NAMES)
    + ("standing_cost_at_build_total",)
    + tuple(f"ever_built_cost_at_build_{resource}" for resource in RESOURCE_NAMES)
    + ("ever_built_cost_at_build_total",)
    + (PREEXISTING_TOTAL,)
)

_SERIES_KEYS: list[str] = ["country_code", "server", "city_id", "position"]
_LEVEL_KEYS: list[str] = [*_SERIES_KEYS, "building_type", "building_level"]
_CITY_KEYS: list[str] = ["country_code", "server", "city_id"]
_CITY_SNAPSHOT_KEYS: list[str] = [
    "country_code",
    "server",
    "city_id",
    "snapshot_id",
    "snapshot_date",
]


def _cost_source_by_resource() -> dict[str, str]:
    """Resource name -> raw lookup column, derived from the base-cost mapping."""
    return {
        target.removeprefix("standing_cost_undiscounted_"): source
        for source, target in COST_COLUMNS
    }


def _midpoint(start: pl.Expr, end: pl.Expr) -> pl.Expr:
    """Midpoint of two factors, tolerating a missing one at a series start."""
    return (
        pl.when(start.is_null())
        .then(end)
        .when(end.is_null())
        .then(start)
        .otherwise((start + end) / 2)
    )


def build_level_cost_deltas(building_costs: pl.DataFrame) -> pl.DataFrame:
    """Cost of each single level: cumulative(level) - cumulative(level - 1).

    The lookup stores cumulative costs, so each type's levels must form an
    unbroken run from 1 for the difference to be the real upgrade price.
    """
    sources = _cost_source_by_resource()
    costs = building_costs.sort("building_type", "building_level")

    shape = costs.group_by("building_type").agg(
        pl.col("building_level").min().alias("min_level"),
        pl.col("building_level").max().alias("max_level"),
        pl.len().alias("rows"),
    )

    broken = shape.filter(
        (pl.col("min_level") != 1) | (pl.col("rows") != pl.col("max_level"))
    )
    if not broken.is_empty():
        raise ValueError(
            f"Building cost levels must run 1..max without gaps; offending types: {sorted(broken.get_column('building_type').to_list())}"
        )

    return costs.select(
        "building_type",
        "building_level",
        *(
            (
                pl.col(source).cast(pl.Float64)
                - pl.col(source)
                .cast(pl.Float64)
                .shift(1)
                .over("building_type")
                .fill_null(0.0)
            ).alias(f"cost_undiscounted_{resource}")
            for resource, source in sources.items()
        ),
    )


def build_slot_panel(city_enriched: pl.DataFrame) -> pl.DataFrame:
    """Every building position of every city-snapshot, including empty ones.

    Empty positions are normalised to type 0 / level 0 and deliberately kept:
    a building that vanishes between two snapshots is only visible as a
    transition *to* an empty position.
    """
    frames = [
        city_enriched.select(
            pl.col("country").alias("country_code"),
            "server",
            pl.col("id").alias("city_id"),
            "snapshot_id",
            "snapshot_date",
            pl.lit(TOWN_HALL_POSITION, dtype=pl.Int64).alias("position"),
            pl.lit(TOWN_HALL_BUILDING_TYPE, dtype=pl.Int64).alias("_type"),
            pl.col(TOWN_HALL_LEVEL_COLUMN).cast(pl.Int64).alias("_level"),
        )
    ]

    frames.extend(
        city_enriched.select(
            pl.col("country").alias("country_code"),
            "server",
            pl.col("id").alias("city_id"),
            "snapshot_id",
            "snapshot_date",
            pl.lit(position, dtype=pl.Int64).alias("position"),
            pl.col(f"p{position}t").cast(pl.Int64).alias("_type"),
            pl.col(f"p{position}l").cast(pl.Int64).alias("_level"),
        )
        for position in range(1, POSITION_COUNT + 1)
    )

    occupied = (pl.col("_type") > 0) & (pl.col("_level") > 0)

    return (
        pl.concat(frames)
        .with_columns(
            pl.when(occupied)
            .then(pl.col("_type"))
            .otherwise(pl.lit(0, dtype=pl.Int64))
            .alias("building_type"),
            pl.when(occupied)
            .then(pl.col("_level"))
            .otherwise(pl.lit(0, dtype=pl.Int64))
            .alias("building_level"),
        )
        .drop("_type", "_level")
        .sort(*_SERIES_KEYS, "snapshot_date")
    )


def _with_transitions(slot_panel: pl.DataFrame) -> pl.DataFrame:
    return slot_panel.with_columns(
        pl.col("building_type").shift(1).over(_SERIES_KEYS).alias("_prev_type"),
        pl.col("building_level").shift(1).over(_SERIES_KEYS).alias("_prev_level"),
        pl.col("snapshot_date").shift(1).over(_SERIES_KEYS).alias("_prev_date"),
    )


def build_construction_events(
    slot_panel: pl.DataFrame,
    city_enriched: pl.DataFrame,
    building_costs: pl.DataFrame,
) -> pl.DataFrame:
    """One row per building level ever constructed, priced at its own vintage.

    A level is attributed to the interval between the observation that lacked
    it and the observation that first shows it.  Replacing a building at a
    position restarts its levels from 1, because the new building was paid for
    from scratch.
    """
    missing = sorted(
        {f"cost_factor_today_{resource}" for resource in RESOURCE_NAMES}
        - set(city_enriched.columns)
    )
    if missing:
        raise ValueError(f"city_enriched missing cost factor columns: {missing}")

    factors = city_enriched.select(
        pl.col("country").alias("country_code"),
        "server",
        pl.col("id").alias("city_id"),
        "snapshot_date",
        *(f"cost_factor_today_{resource}" for resource in RESOURCE_NAMES),
    )

    start_factors = factors.rename(
        {
            "snapshot_date": "_prev_date",
            **{
                f"cost_factor_today_{resource}": f"_start_factor_{resource}"
                for resource in RESOURCE_NAMES
            },
        }
    )

    same_building = pl.col("_prev_type") == pl.col("building_type")

    # Levels at or below this were already paid for before this observation.
    already_built = (
        pl.when(same_building)
        .then(pl.col("_prev_level"))
        .otherwise(pl.lit(0, dtype=pl.Int64))
    )

    events = (
        _with_transitions(slot_panel)
        .with_columns(already_built.alias("_already_built"))
        .filter(
            (pl.col("building_type") > 0)
            & (pl.col("building_level") > pl.col("_already_built"))
        )
        .with_columns(
            pl.int_ranges(
                pl.col("_already_built") + 1, pl.col("building_level") + 1
            ).alias("_levels"),
            pl.col("_prev_type").is_null().alias("is_preexisting"),
        )
        .drop("building_level")
        .explode("_levels")
        .rename({"_levels": "building_level"})
        .join(factors, on=["country_code", "server", "city_id", "snapshot_date"], how="left")
        .join(start_factors, on=["country_code", "server", "city_id", "_prev_date"], how="left")
        .join(
            build_level_cost_deltas(building_costs),
            on=["building_type", "building_level"],
            how="left",
        )
    )

    unpriced = events.filter(pl.col("cost_undiscounted_wood").is_null())
    if not unpriced.is_empty():
        sample = unpriced.select("building_type", "building_level").unique().head(5)
        raise ValueError(
            f"Building levels without a cost lookup: {sample.to_dicts()}"
        )

    events = events.with_columns(
        *(
            _midpoint(
                pl.col(f"_start_factor_{resource}"),
                pl.col(f"cost_factor_today_{resource}"),
            ).alias(f"cost_factor_at_build_{resource}")
            for resource in RESOURCE_NAMES
        )
    )

    return events.select(
        *_LEVEL_KEYS,
        pl.col("snapshot_id").alias("built_by_snapshot_id"),
        pl.col("snapshot_date").alias("built_by_snapshot_date"),
        pl.col("_prev_date").alias("built_after_snapshot_date"),
        "is_preexisting",
        *(f"cost_factor_at_build_{resource}" for resource in RESOURCE_NAMES),
        *(f"cost_undiscounted_{resource}" for resource in RESOURCE_NAMES),
        *(
            (pl.col(f"cost_undiscounted_{resource}") * pl.col(f"cost_factor_at_build_{resource}")).alias(
                f"cost_at_build_{resource}"
            )
            for resource in RESOURCE_NAMES
        ),
    ).sort(*_LEVEL_KEYS, "built_by_snapshot_date")


def build_demolition_events(
    slot_panel: pl.DataFrame, construction_events: pl.DataFrame
) -> pl.DataFrame:
    """One row per building level that stopped standing.

    Each removed level is valued at the vintage it carried at that moment, so
    the standing total loses exactly what it previously gained.
    """
    same_building = pl.col("_prev_type") == pl.col("building_type")

    # Levels at or below this survived the transition.
    kept = (
        pl.when(same_building)
        .then(pl.col("building_level"))
        .otherwise(pl.lit(0, dtype=pl.Int64))
    )

    removals = (
        _with_transitions(slot_panel)
        .with_columns(kept.alias("_kept"))
        .filter((pl.col("_prev_type") > 0) & (pl.col("_prev_level") > pl.col("_kept")))
        .with_columns(
            pl.int_ranges(pl.col("_kept") + 1, pl.col("_prev_level") + 1).alias("_levels")
        )
        .select(
            *_SERIES_KEYS,
            pl.col("_prev_type").alias("building_type"),
            "_levels",
            pl.col("snapshot_id").alias("removed_by_snapshot_id"),
            pl.col("snapshot_date").alias("removed_at_snapshot_date"),
        )
        .explode("_levels")
        .rename({"_levels": "building_level"})
    )

    priced = (
        removals.join(
            construction_events.select(
                *_LEVEL_KEYS,
                "built_by_snapshot_date",
                "is_preexisting",
                *(f"cost_undiscounted_{resource}" for resource in RESOURCE_NAMES),
                *(f"cost_at_build_{resource}" for resource in RESOURCE_NAMES),
            ),
            on=_LEVEL_KEYS,
            how="left",
        )
        # Value it at the most recent build that preceded the removal.
        .filter(pl.col("built_by_snapshot_date") < pl.col("removed_at_snapshot_date"))
        .filter(
            pl.col("built_by_snapshot_date")
            == pl.col("built_by_snapshot_date")
            .max()
            .over([*_LEVEL_KEYS, "removed_at_snapshot_date"])
        )
    )
    if priced.height != removals.height:
        raise ValueError(
            f"Demolished levels without a matching prior construction event: removals={removals.height}, priced={priced.height}"
        )

    return priced.sort(*_LEVEL_KEYS, "removed_at_snapshot_date")


def summarize_city_construction(
    slot_panel: pl.DataFrame,
    construction_events: pl.DataFrame,
    demolition_events: pl.DataFrame,
) -> pl.DataFrame:
    """Per city-snapshot standing cost, ever-built cost and preexisting share."""
    paid = [f"cost_at_build_{resource}" for resource in RESOURCE_NAMES]

    def _flows(frame: pl.DataFrame, date_column: str, prefix: str) -> pl.LazyFrame:
        return (
            frame.lazy()
            .with_columns(
                pl.sum_horizontal(
                    [f"cost_undiscounted_{resource}" for resource in RESOURCE_NAMES]
                ).alias("_base_total")
            )
            .with_columns(
                pl.when(pl.col("is_preexisting"))
                .then(pl.col("_base_total"))
                .otherwise(pl.lit(0.0))
                .alias("_preexisting_total")
            )
            .group_by(*_CITY_KEYS, date_column)
            .agg(
                *(pl.col(column).sum().alias(f"{prefix}{column}") for column in paid),
                pl.col("_base_total").sum().alias(f"{prefix}base_total"),
                pl.col("_preexisting_total").sum().alias(f"{prefix}preexisting_total"),
            )
            .rename({date_column: "snapshot_date"})
        )

    built = _flows(construction_events, "built_by_snapshot_date", "built_")
    removed = _flows(demolition_events, "removed_at_snapshot_date", "removed_")

    flow_columns = [
        *(f"built_{column}" for column in paid),
        "built_base_total",
        "built_preexisting_total",
        *(f"removed_{column}" for column in paid),
        "removed_base_total",
        "removed_preexisting_total",
    ]

    running = (
        slot_panel.lazy()
        .select(*_CITY_SNAPSHOT_KEYS)
        .unique()
        .join(built, on=[*_CITY_KEYS, "snapshot_date"], how="left")
        .join(removed, on=[*_CITY_KEYS, "snapshot_date"], how="left")
        .with_columns(*(pl.col(column).fill_null(0.0) for column in flow_columns))
        .sort(*_CITY_KEYS, "snapshot_date")
        .with_columns(
            *(
                pl.col(column).cum_sum().over(_CITY_KEYS).alias(f"cum_{column}")
                for column in flow_columns
            )
        )
    )

    summary = running.with_columns(
        *(
            (
                pl.col(f"cum_built_cost_at_build_{resource}")
                - pl.col(f"cum_removed_cost_at_build_{resource}")
            ).alias(f"standing_cost_at_build_{resource}")
            for resource in RESOURCE_NAMES
        ),
        *(
            pl.col(f"cum_built_cost_at_build_{resource}").alias(
                f"ever_built_cost_at_build_{resource}"
            )
            for resource in RESOURCE_NAMES
        ),
        (pl.col("cum_built_base_total") - pl.col("cum_removed_base_total")).alias(
            "_standing_base_total"
        ),
        (pl.col("cum_built_preexisting_total") - pl.col("cum_removed_preexisting_total")).alias(
            "preexisting_cost_undiscounted_total"
        ),
    ).with_columns(
        pl.sum_horizontal(
            [f"standing_cost_at_build_{resource}" for resource in RESOURCE_NAMES]
        ).alias("standing_cost_at_build_total"),
        pl.sum_horizontal(
            [f"ever_built_cost_at_build_{resource}" for resource in RESOURCE_NAMES]
        ).alias("ever_built_cost_at_build_total"),
        _preexisting_share(
            pl.col("preexisting_cost_undiscounted_total"),
            pl.col("_standing_base_total"),
        ),
    )

    return (
        summary.select(
            *_CITY_SNAPSHOT_KEYS,
            *(f"standing_cost_at_build_{resource}" for resource in RESOURCE_NAMES),
            "standing_cost_at_build_total",
            *(
                f"ever_built_cost_at_build_{resource}"
                for resource in RESOURCE_NAMES
            ),
            "ever_built_cost_at_build_total",
            "preexisting_cost_undiscounted_total",
            "preexisting_share",
        )
        .sort(*_CITY_KEYS, "snapshot_date")
        .collect(engine="streaming")
    )


def _preexisting_share(preexisting: pl.Expr, standing: pl.Expr) -> pl.Expr:
    """Share of the standing undiscounted cost that was already there at first sighting.

    Null when nothing stands, so averages skip rows without buildings instead
    of counting them as fully reliable or fully guessed.
    """
    return (
        pl.when(standing > 0)
        .then(preexisting / standing)
        .otherwise(None)
        .alias("preexisting_share")
    )


def preexisting_share_expr() -> pl.Expr:
    """``preexisting_share`` at any grain: city, player, island or player-island.

    Standing undiscounted cost equals ``standing_cost_undiscounted_total``
    exactly, and both it and the preexisting total sum cleanly, so the share
    is recomputed from the summed totals of each published table.
    """
    return _preexisting_share(
        pl.col(PREEXISTING_TOTAL),
        pl.col("standing_cost_undiscounted_total"),
    )


def publish_preexisting_share(frame: pl.DataFrame) -> pl.DataFrame:
    """Add ``preexisting_share`` and drop the helper total it was computed from.

    The share times ``standing_cost_undiscounted_total`` gives the total back,
    so publishing it would only add a column without information.
    """
    return frame.with_columns(preexisting_share_expr()).drop(PREEXISTING_TOTAL)


def attach_city_construction(
    city_enriched: pl.DataFrame, city_construction: pl.DataFrame
) -> pl.DataFrame:
    """Join the summable construction measures onto the city panel.

    ``preexisting_share`` is deliberately not carried through: it
    is a ratio, so every published table recomputes it with
    :func:`preexisting_share_expr` from its own summed totals.
    """
    measures = city_construction.select(
        pl.col("country_code").alias("country"),
        "server",
        pl.col("city_id").alias("id"),
        "snapshot_id",
        *CONSTRUCTION_SUM_COLUMNS,
    )

    return city_enriched.join(
        measures, on=["country", "server", "id", "snapshot_id"], how="left"
    ).with_columns(
        pl.col(column).fill_null(0.0) for column in CONSTRUCTION_SUM_COLUMNS
    )
