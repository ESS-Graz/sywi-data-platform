from __future__ import annotations

import math

import polars as pl

from ikariam.pipeline.config import DurationBand
from ikariam.pipeline.utils import duration_adjustment_expr

BANDS = (
    DurationBand(180000, 1.00),
    DurationBand(1440000, 0.98),
    DurationBand(13149000, 0.94),
    DurationBand(math.inf, 0.86),
)


def _apply(seconds: list[int]) -> list[float]:
    df = pl.DataFrame({"s": seconds}).with_columns(pl.col("s").cast(pl.Float64))
    return df.with_columns(duration_adjustment_expr(pl.col("s"), BANDS).alias("f"))[
        "f"
    ].to_list()


def test_sql_q15_semantics_first_match_wins_with_gaps():
    cases: dict[int, float] = {
        0: 1.00,
        179_999: 1.00,
        180_000: 1.00,
        180_001: 1.00,
        180_002: 0.98,
        1_439_999: 0.98,
        1_440_000: 1.00,
        1_440_001: 1.00,
        1_440_002: 0.94,
        13_148_999: 0.94,
        13_149_000: 1.00,
        13_149_001: 1.00,
        13_149_002: 0.86,
        10**9: 0.86,
    }
    assert _apply(list(cases.keys())) == list(cases.values())
