from __future__ import annotations

import polars as pl

from .config import DurationBand


def safe_divide(num: pl.Expr, den: pl.Expr, default: float = 0.0) -> pl.Expr:
    """R safe_divide: num/den, but 0 when den is 0/NaN/Inf or result is non-finite."""
    raw = num / den
    return (
        pl.when(den.is_null() | (den == 0) | raw.is_nan() | raw.is_infinite() | raw.is_null())
        .then(pl.lit(default))
        .otherwise(raw)
    )


def safe_percent(part: pl.Expr, whole: pl.Expr, default: float = 0.0) -> pl.Expr:
    """R safe_percent: 100 * part / whole with safe-divide semantics."""
    return safe_divide(part * 100, whole, default)


def duration_adjustment_expr(
    seconds: pl.Expr, bands: tuple[DurationBand, ...]
) -> pl.Expr:
    """Reproduce the account-age resource adjustment CASE step function literally.

    Legacy SQL name: Q15_Update_City. For each resource it writes:
        CASE WHEN Spieldauer < band1.max             THEN 1.00
             WHEN Spieldauer > band1.max+1 AND < band2.max THEN 0.98
             WHEN Spieldauer > band2.max+1 AND < band3.max THEN 0.94
             WHEN Spieldauer > band3.max+1            THEN 0.86
             ELSE Holz_verbaut END
    i.e. strict `<` on upper edge, strict `>` + 1 on lower edge, and values
    that fall in the gap (e.g. exactly `band1.max` or `band1.max+1`) retain
    the unadjusted value (factor 1.0). The first matching branch wins.

    Replicating this: iterate bands in ascending `max_seconds` order; emit
    `when (prev_max+1) < seconds < band.max then factor` for each; final
    band above the highest cutoff gets its factor; else (gaps) → 1.0.
    """
    ordered = sorted(bands, key=lambda b: b.max_seconds)
    if not ordered:
        raise ValueError("duration_adjustments must be non-empty")

    # Build the CASE chain in reverse so that earlier bands (checked first
    # in the final expression) become the outer `when/then`.
    import math

    gap_default = pl.lit(1.0, dtype=pl.Float64)  # values in band-boundary gaps
    expr: pl.Expr = gap_default
    prev_max: float = -1.0  # so that "> prev_max + 1" becomes "> 0" for band 1
    # Walk ascending, appending via nested otherwise(). Build the inner-most
    # branch first, then wrap.
    branches: list[tuple[pl.Expr, float]] = []
    for i, band in enumerate(ordered):
        if i == 0:
            cond = seconds < band.max_seconds
        elif math.isinf(band.max_seconds):
            cond = seconds > (prev_max + 1)
        else:
            cond = (seconds > (prev_max + 1)) & (seconds < band.max_seconds)
        branches.append((cond, band.factor))
        prev_max = band.max_seconds

    # Assemble as pl.when(...).then(...).when(...).then(...).otherwise(1.0)
    # First branch becomes the outermost when, so iterate in order.
    chain = pl.when(branches[0][0]).then(pl.lit(branches[0][1]))
    for cond, factor in branches[1:]:
        chain = chain.when(cond).then(pl.lit(factor))
    expr = chain.otherwise(gap_default)
    return expr
