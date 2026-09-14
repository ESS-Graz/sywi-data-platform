"""Attach cumulative base building costs and local reducer levels to each city.

The raw city export stores 17 building positions as wide ``p{n}t`` (type) and
``p{n}l`` (level) pairs. This transform normalizes those positions, performs
one lookup join, and aggregates the five resource costs back to the city row.
The same normalized positions provide each city's observed level of the five
resource-reduction buildings.
"""

from __future__ import annotations

import polars as pl


POSITION_COUNT = 17
LOOKUP_KEYS = ("building_type", "building_level")
COST_COLUMNS: tuple[tuple[str, str], ...] = (
    ("cost_holz", "building_base_cost_wood"),
    ("cost_kristall", "building_base_cost_crystal"),
    ("cost_quartz", "building_base_cost_marble"),
    ("cost_schwefel", "building_base_cost_sulfur"),
    ("cost_wein", "building_base_cost_wine"),
)

# Raw type IDs of the city-local construction-cost reducers. These are the
# game's own building-type IDs, copied unchanged from the server backup; that
# source carries no building dictionary, so the resource assignment rests on
# each type's cost series, level limit, and first-appearance date
# (docs/building_value_and_discount_findings.md).
REDUCTION_BUILDING_TYPES: dict[str, int] = {
    "wood": 23,  # Carpenter
    "marble": 24,  # Architect's Office
    "crystal": 25,  # Optician
    "wine": 26,  # Wine Press
    "sulfur": 27,  # Firework Test Area
}
# Reducers were capped at level 32 until version 8.8.0 (2022).
HISTORICAL_REDUCTION_BUILDING_MAX_LEVEL = 32
REDUCTION_LEVEL_COLUMNS: dict[str, str] = {
    resource: f"{resource}_reduction_building_level"
    for resource in REDUCTION_BUILDING_TYPES
}


def add_building_base_costs(
    city_raw: pl.DataFrame, building_costs: pl.DataFrame
) -> pl.DataFrame:
    """Add five cumulative base-cost totals and five reducer levels to every city row."""
    position_columns = [
        f"p{position}{kind}"
        for position in range(1, POSITION_COUNT + 1)
        for kind in ("t", "l")
    ]
    missing_position_columns = sorted(set(position_columns) - set(city_raw.columns))
    if missing_position_columns:
        raise ValueError(
            f"Missing building position columns: {missing_position_columns}"
        )

    lookup_columns = [*LOOKUP_KEYS, *(source for source, _ in COST_COLUMNS)]
    missing_lookup_columns = sorted(set(lookup_columns) - set(building_costs.columns))
    if missing_lookup_columns:
        raise ValueError(f"Missing building cost columns: {missing_lookup_columns}")

    costs = building_costs.select(lookup_columns).with_columns(
        pl.col("building_type").cast(pl.Int64),
        pl.col("building_level").cast(pl.Int64),
        *(pl.col(source).cast(pl.Float64) for source, _ in COST_COLUMNS),
    )
    duplicate_costs = costs.group_by(LOOKUP_KEYS).len().filter(pl.col("len") > 1)
    if not duplicate_costs.is_empty():
        duplicate_pairs = _format_pairs(duplicate_costs.select(LOOKUP_KEYS))
        raise ValueError(f"Duplicate building cost lookups: {duplicate_pairs}")

    cities = city_raw.with_columns(
        pl.col(column).cast(pl.Int64) for column in position_columns
    ).with_row_index("_city_row")

    slots = pl.concat(
        [
            cities.select(
                "_city_row",
                pl.lit(position).alias("position"),
                pl.col(f"p{position}t").alias("building_type"),
                pl.col(f"p{position}l").alias("building_level"),
            )
            for position in range(1, POSITION_COUNT + 1)
        ]
    )
    negative_levels = slots.filter(pl.col("building_level") < 0)
    if not negative_levels.is_empty():
        raise ValueError(
            "Negative building levels: "
            f"{_format_pairs(negative_levels.select(LOOKUP_KEYS).unique())}"
        )
    buildings = slots.filter(
        (pl.col("building_type") > 0) & (pl.col("building_level") > 0)
    )

    reducers = buildings.filter(
        pl.col("building_type").is_in(list(REDUCTION_BUILDING_TYPES.values()))
    )
    duplicate_reducers = (
        reducers.group_by("_city_row", "building_type").len().filter(pl.col("len") > 1)
    )
    if not duplicate_reducers.is_empty():
        raise ValueError(
            "Duplicate reduction buildings in "
            f"{duplicate_reducers.select('_city_row').n_unique()} city rows: "
            f"{_sample_city_keys(cities, duplicate_reducers)}"
        )
    over_cap_reducers = reducers.filter(
        pl.col("building_level") > HISTORICAL_REDUCTION_BUILDING_MAX_LEVEL
    )
    if not over_cap_reducers.is_empty():
        raise ValueError(
            "Reduction building levels above historical cap "
            f"{HISTORICAL_REDUCTION_BUILDING_MAX_LEVEL}: "
            f"{_format_pairs(over_cap_reducers.select(LOOKUP_KEYS).unique())}"
        )

    used_buildings = buildings.select(LOOKUP_KEYS).unique()
    missing_costs = used_buildings.join(
        costs.select(LOOKUP_KEYS),
        on=LOOKUP_KEYS,
        how="anti",
    ).sort(LOOKUP_KEYS)
    if not missing_costs.is_empty():
        raise ValueError(f"Missing building cost lookups: {_format_pairs(missing_costs)}")

    city_costs = (
        buildings.join(costs, on=LOOKUP_KEYS, how="left", validate="m:1")
        .group_by("_city_row")
        .agg(
            *(pl.col(source).sum().alias(target) for source, target in COST_COLUMNS),
            *(
                pl.col("building_level")
                .filter(pl.col("building_type") == building_type)
                .max()
                .alias(REDUCTION_LEVEL_COLUMNS[resource])
                for resource, building_type in REDUCTION_BUILDING_TYPES.items()
            ),
        )
    )
    cost_output_columns = [target for _, target in COST_COLUMNS]
    return (
        cities.join(city_costs, on="_city_row", how="left", validate="1:1")
        .with_columns(
            *(pl.col(column).fill_null(0.0) for column in cost_output_columns),
            *(
                pl.col(column).fill_null(0).cast(pl.Int64)
                for column in REDUCTION_LEVEL_COLUMNS.values()
            ),
        )
        .sort("_city_row")
        .drop("_city_row")
    )


def _format_pairs(pairs: pl.DataFrame) -> str:
    return ", ".join(
        f"({building_type}, {building_level})"
        for building_type, building_level in pairs.sort(LOOKUP_KEYS).iter_rows()
    )


def _sample_city_keys(
    cities: pl.DataFrame, rows: pl.DataFrame
) -> list[dict[str, object]]:
    keys = [column for column in ("id", "snapshot_id") if column in cities.columns]
    return (
        cities.join(rows.select("_city_row").unique(), on="_city_row", how="semi")
        .sort("_city_row")
        .select(keys or ["_city_row"])
        .head(5)
        .to_dicts()
    )
