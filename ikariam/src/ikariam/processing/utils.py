from __future__ import annotations

import polars as pl


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
