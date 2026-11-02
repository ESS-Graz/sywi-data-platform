"""Step 08: compute island upgrade costs.

- Upgrade costs follow the literal Q23 SQL cost tables.
  Level 0 wonder → cost of level 1.
- Sub_Noetig_nextlev_* = max(0, cost - donated), with null → 0.

Per-island city and donation totals are built in ``higher_agg``.
"""

from __future__ import annotations

import polars as pl

RESOURCE_COSTS: tuple[tuple[int, int], ...] = (
    (1, 394),
    (2, 992),
    (3, 1732),
    (4, 2788),
    (5, 3783),
    (6, 5632),
    (7, 8139),
    (8, 10452),
    (9, 13298),
    (10, 18478),
    (11, 23213),
    (12, 29038),
    (13, 39494),
    (14, 49107),
    (15, 66010),
    (16, 81766),
    (17, 101146),
    (18, 134598),
    (19, 154304),
    (20, 205012),
    (21, 270839),
    (22, 311541),
    (23, 411229),
    (24, 506475),
    (25, 665201),
    (26, 767723),
    (27, 1007959),
    (28, 1240496),
    (29, 1526516),
    (30, 1995717),
    (31, 2311042),
    (32, 3020994),
    (33, 3935195),
    (34, 4572136),
    (35, 5624478),
    (36, 7325850),
    (37, 9011590),
    (38, 11085051),
    (39, 13635408),
    (40, 17704143),
    (41, 20630781),
    (42, 26786470),
    (43, 32948197),
    (44, 40527121),
    (45, 52472840),
    (46, 61315353),
    (47, 79388129),
    (48, 97648282),
    (49, 120108270),
)

TRADEGOOD_COSTS: tuple[tuple[int, int], ...] = (
    (1, 1303),
    (2, 2689),
    (3, 4373),
    (4, 7421),
    (5, 10037),
    (6, 13333),
    (7, 20665),
    (8, 26849),
    (9, 37305),
    (10, 47879),
    (11, 65572),
    (12, 89127),
    (13, 106217),
    (14, 152739),
    (15, 193512),
    (16, 244886),
    (17, 309618),
    (18, 414190),
    (19, 552058),
    (20, 660106),
    (21, 925396),
    (22, 1108885),
    (23, 1471979),
    (24, 1855942),
    (25, 2339735),
    (26, 3096779),
    (27, 3903252),
    (28, 5153666),
    (29, 6199765),
    (30, 8185063),
    (31, 10314552),
    (32, 13588513),
    (33, 17122961),
    (34, 21576366),
    (35, 27187657),
    (36, 35747356),
    (37, 45043166),
    (38, 56755887),
    (39, 71513915),
    (40, 93863574),
    (41, 118269663),
    (42, 149021335),
    (43, 187768443),
    (44, 246053390),
    (45, 298104705),
    (46, 390638028),
    (47, 511136520),
    (48, 620180600),
    (49, 811484147),
)

WONDER_COSTS: tuple[tuple[int, int], ...] = (
    (1, 8800),
    (2, 31800),
    (3, 73200),
    (4, 135500),
)


def _cost_table(costs: tuple[tuple[int, int], ...]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "level": [lvl for lvl, _ in costs],
            "cost": [cost for _, cost in costs],
        }
    ).with_columns(pl.col("level").cast(pl.Int64), pl.col("cost").cast(pl.Int64))


def _resource_cost_table() -> pl.DataFrame:
    return _cost_table(RESOURCE_COSTS)


def _tradegood_cost_table() -> pl.DataFrame:
    return _cost_table(TRADEGOOD_COSTS)


def _wonder_cost_table() -> pl.DataFrame:
    return _cost_table(WONDER_COSTS)


def enrich_islands(island_raw: pl.DataFrame) -> pl.DataFrame:
    df = island_raw.with_columns(
        pl.col("wonder_level").cast(pl.Int64, strict=False),
        pl.col("resource_level").cast(pl.Int64, strict=False),
        pl.col("tradegood_level").cast(pl.Int64, strict=False),
        pl.col("wonder_donated").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("resource_donated").cast(pl.Float64, strict=False).fill_null(0.0),
        pl.col("tradegood_donated").cast(pl.Float64, strict=False).fill_null(0.0),
        (pl.col("id") + pl.lit("_") + pl.col("snapshot_id")).alias("island_snapshot_key"),
    )

    wonder_costs = _wonder_cost_table().rename({"cost": "cost_Nextlev_wonder"})
    df = df.join(wonder_costs, left_on="wonder_level", right_on="level", how="left")
    df = df.with_columns(
        pl.when((pl.col("wonder_level") == 0) & pl.col("cost_Nextlev_wonder").is_null())
        .then(pl.lit(WONDER_COSTS[0][1]))
        .otherwise(pl.col("cost_Nextlev_wonder"))
        .alias("cost_Nextlev_wonder")
    )
    resource_costs = _resource_cost_table().rename({"cost": "cost_Nextlev_resource"})
    df = df.join(resource_costs, left_on="resource_level", right_on="level", how="left")

    tradegood_costs = _tradegood_cost_table().rename({"cost": "cost_Nextlev_tradegood"})
    df = df.join(tradegood_costs, left_on="tradegood_level", right_on="level", how="left")

    def remaining(cost: str, donated: str) -> pl.Expr:
        raw = pl.col(cost) - pl.col(donated)
        return (
            pl.when(pl.col(cost).is_null())
            .then(pl.lit(0.0))
            .otherwise(pl.max_horizontal(pl.lit(0.0), raw))
        )

    return df.with_columns(
        remaining("cost_Nextlev_wonder", "wonder_donated").alias("Sub_Noetig_nextlev_wonder"),
        remaining("cost_Nextlev_resource", "resource_donated").alias("Sub_Noetig_nextlev_resource"),
        remaining("cost_Nextlev_tradegood", "tradegood_donated").alias(
            "Sub_Noetig_nextlev_tradegood"
        ),
    )
