from __future__ import annotations

import math

import polars as pl

from ikariam_pipeline.config import DurationBand
from ikariam_pipeline.utils import duration_adjustment_expr

BANDS = (
    DurationBand(180000, 1.00),
    DurationBand(1440000, 0.98),
    DurationBand(13149000, 0.94),
    DurationBand(math.inf, 0.86),
)


def _apply(seconds: list[int]) -> list[float]:
    df = pl.DataFrame({"s": seconds}).with_columns(pl.col("s").cast(pl.Float64))
    return df.with_columns(
        duration_adjustment_expr(pl.col("s"), BANDS).alias("f")
    )["f"].to_list()


def test_sql_q15_semantics_first_match_wins_with_gaps():
    # SQL Q15 uses CASE with strict < / > + 1 bounds — first-match wins,
    # boundary-adjacent values (exactly `band.max` or `band.max + 1`) fall
    # into a gap and keep factor 1.0 (unadjusted).
    cases: dict[int, float] = {
        0: 1.00,                  # new band (< 180000)
        179_999: 1.00,            # just under 180000
        180_000: 1.00,            # GAP → unadjusted
        180_001: 1.00,            # GAP → unadjusted
        180_002: 0.98,            # inside early band
        1_439_999: 0.98,          # just under 1440000
        1_440_000: 1.00,          # GAP
        1_440_001: 1.00,          # GAP
        1_440_002: 0.94,          # inside established band
        13_148_999: 0.94,         # just under 13149000
        13_149_000: 1.00,         # GAP
        13_149_001: 1.00,         # GAP
        13_149_002: 0.86,         # veteran band
        10**9: 0.86,              # deep veteran
    }
    result = _apply(list(cases.keys()))
    assert result == list(cases.values())
