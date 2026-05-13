"""Compare `pipeline_py/output/*.csv` against `pipeline_py/sql_gold_standard/*.csv`
and write a Markdown divergence report to `docs/sql_vs_python_audit.md`.

The SQL outputs have columns prefixed `t_`, `a_`, `c_`, `d_`, `i_` (source table).
Our Python outputs use plain names. We build a prefix→plain mapping by stripping
the known prefixes and looking for the result in the Python frame.

Known pre-fixup divergences (documented so the report is readable):
- `c_*_verbaut` columns are band-adjusted in SQL, unadjusted in Python.
- `a_Registration_time_normal` uses MySQL FROM_UNIXTIME format in SQL;
  Python uses ISO 8601 with 'T' / 'Z'.
- `d_Don_Wonder_*` splits differ (flip direction fix pending).
- Row counts differ by ~7 (player-filter semantics).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import polars as pl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PY_OUT = ROOT / "output"
SQL_OUT = ROOT / "sql_gold_standard"
REPORT = ROOT / "docs" / "sql_vs_python_audit.md"

TOLERANCE = 1e-6

# (sql_filename, py_filename, sql_key_col, py_key_col)
# I_DS note: SQL builds I_DS from city2 LEFT JOIN island, so c_id is NULL for
# orphan islands. i_id (island.id) is the authoritative key.
FILE_PAIRS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("A_DS.csv",         "A_DS.csv",         ("t_id",), ("id",)),
    ("AVI_DS.csv",       "AVI_DS.csv",
        ("m_owner_id", "m_island_id"), ("owner_id", "island_id")),
    ("I_DS.csv",         "I_DS.csv",         ("i_id",), ("id",)),
    ("Teilnahme_AV.csv", "Teilnahme_AV.csv", ("id",),   ("avatar_id",)),
    ("Master_Avi.csv",   "Master_Avi.csv",
        ("owner_id", "island_id"), ("owner_id", "island_id")),
)

# Python column → SQL column (for values that diverge by known transform).
# Maps the Python column name to the SQL equivalent. We strip SQL prefixes
# dynamically where possible; this table is for non-obvious mappings and
# for column aliases that don't survive prefix-stripping.
MANUAL_MAPPINGS: dict[str, str] = {
    # A_DS avatar-level donations — SQL has the H prefix
    "Don_Luxusminen_Ges": "d_DonH_Luxusminen_Ges",
    # AVI_DS renamings (column case differences the strip_prefix logic misses)
    "Cities_Vorhanden":   "m_Cities_vorhanden",
    # Teilnahme_AV: SQL column is `Anzahl_Vorhanden` (capital V)
    "Anzahl_vorhanden":   "Anzahl_Vorhanden",
}


def _strip_prefix(col: str) -> str:
    for p in ("t_", "a_", "c_", "d_", "i_", "m_"):
        if col.startswith(p):
            return col[len(p):]
    return col


def _build_column_map(py_cols: Iterable[str], sql_cols: Iterable[str]) -> dict[str, str]:
    """Return py_col -> sql_col mapping for overlapping columns."""
    sql_set = set(sql_cols)
    mapping: dict[str, str] = {}
    for py_col in py_cols:
        if py_col in MANUAL_MAPPINGS and MANUAL_MAPPINGS[py_col] in sql_set:
            mapping[py_col] = MANUAL_MAPPINGS[py_col]
            continue
        for prefix in ("t_", "a_", "c_", "d_", "i_", "m_"):
            candidate = prefix + py_col
            if candidate in sql_set:
                mapping[py_col] = candidate
                break
        else:
            if py_col in sql_set:
                mapping[py_col] = py_col
    return mapping


def _compare_column(
    py_col: pl.Series, sql_col: pl.Series
) -> dict[str, float | int]:
    """Compare only rows where SQL has a non-null value — SQL's A_DS is built
    with LEFT JOINs against snapshot-36-only tables, so most rows for avatars
    absent from snapshot 36 are NULL shells. Those don't represent a SQL
    statement about what the value should be; they're gaps."""
    sql_non_null = sql_col.is_not_null()
    sql_null_rows = int((~sql_non_null).sum())
    total_rows = py_col.len()

    if py_col.dtype.is_numeric() and sql_col.dtype.is_numeric():
        py_cast = py_col.cast(pl.Float64, strict=False)
        sql_cast = sql_col.cast(pl.Float64, strict=False)
        # Filter to rows where SQL is non-null.
        py_f = py_cast.filter(sql_non_null)
        sql_f = sql_cast.filter(sql_non_null)
        diff = (py_f - sql_f).abs()
        compared = diff.len()
        matching = int((diff < TOLERANCE).fill_null(False).sum())
        max_d = diff.max()
        mean_d = diff.mean()
        return {
            "total": total_rows,
            "sql_null": sql_null_rows,
            "compared": compared,
            "matching": matching,
            "nonmatching": compared - matching,
            "max_abs_diff": float(max_d) if max_d is not None else 0.0,  # type: ignore[arg-type]
            "mean_abs_diff": float(mean_d) if mean_d is not None else 0.0,  # type: ignore[arg-type]
        }
    py_f = py_col.filter(sql_non_null)
    sql_f = sql_col.filter(sql_non_null)
    compared = py_f.len()
    matching = int((py_f == sql_f).sum())
    return {
        "total": total_rows,
        "sql_null": sql_null_rows,
        "compared": compared,
        "matching": matching,
        "nonmatching": compared - matching,
        "max_abs_diff": 0.0,
        "mean_abs_diff": 0.0,
    }


def audit_pair(
    sql_file: str, py_file: str, sql_keys: tuple[str, ...], py_keys: tuple[str, ...]
) -> list[str]:
    lines: list[str] = [f"\n## {py_file}\n"]
    sql_path = SQL_OUT / sql_file
    py_path = PY_OUT / py_file
    if not sql_path.exists():
        return lines + [f"SQL file missing: {sql_path}\n"]
    if not py_path.exists():
        return lines + [f"Python file missing: {py_path}\n"]

    sql_df = pl.read_csv(sql_path, separator=";", infer_schema_length=10000)
    py_df = pl.read_csv(py_path, separator=";", infer_schema_length=10000)

    lines.append(f"- SQL rows: **{sql_df.height}**, cols: {sql_df.width}")
    lines.append(f"- Python rows: **{py_df.height}**, cols: {py_df.width}")

    # Build join frame
    sql_key_renamed = {sk: pk for sk, pk in zip(sql_keys, py_keys, strict=True)}
    sql_for_join = sql_df.rename(sql_key_renamed)
    common = py_df.join(sql_for_join, on=list(py_keys), how="inner", suffix="__sql")
    lines.append(f"- Common keys: **{common.height}**")
    lines.append(
        f"- Python-only keys: {py_df.height - common.height}, "
        f"SQL-only keys: {sql_df.height - common.height}\n"
    )

    col_map = _build_column_map(py_df.columns, sql_for_join.columns)
    lines.append(f"Mapped columns: {len(col_map)} / {py_df.width}\n")

    unmapped = sorted(set(py_df.columns) - set(col_map))
    if unmapped:
        lines.append(f"Unmapped Python columns: {', '.join(unmapped)}\n")

    lines.append(
        "| Py column | SQL column | compared | matching | nonmatching "
        "| SQL nulls | max\\|Δ\\| | mean\\|Δ\\| |"
    )
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for py_col in py_df.columns:
        if py_col in py_keys or py_col not in col_map:
            continue
        sql_col = col_map[py_col]
        sql_name_in_joined = sql_col if sql_col not in py_df.columns else f"{sql_col}__sql"
        if sql_name_in_joined not in common.columns:
            continue
        stats = _compare_column(common[py_col], common[sql_name_in_joined])
        if stats["compared"] == 0:
            flag = "🫥"  # no comparable rows
        elif stats["nonmatching"] == 0:
            flag = "✅"
        else:
            flag = "⚠️"
        lines.append(
            f"| {flag} `{py_col}` | `{sql_col}` | "
            f"{stats['compared']} | {stats['matching']} | {stats['nonmatching']} | "
            f"{stats['sql_null']} | "
            f"{stats['max_abs_diff']:.4f} | {stats['mean_abs_diff']:.4f} |"
        )

    return lines


def main() -> None:
    if not SQL_OUT.exists():
        raise SystemExit(f"SQL gold-standard dir missing: {SQL_OUT}")
    if not PY_OUT.exists():
        raise SystemExit(f"Python output dir missing: {PY_OUT}")

    report: list[str] = [
        "# Python vs SQL gold-standard audit",
        "",
        "Column-by-column diff between `pipeline_py/output/*.csv` and",
        "`pipeline_py/sql_gold_standard/*.csv`. The SQL outputs are the",
        "authoritative reference.",
        "",
        f"Tolerance: `{TOLERANCE}` (absolute). Comparison restricted to rows",
        "where SQL has a non-null value — SQL's A_DS/I_DS have NULL shells for",
        "entities absent from the seeded snapshot (snapshot 36), so only the",
        "subset with real data can be compared.",
    ]
    for sql_f, py_f, sk, pk in FILE_PAIRS:
        report.extend(audit_pair(sql_f, py_f, sk, pk))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(report), encoding="utf-8")
    print(f"Wrote {REPORT} ({len(report)} lines)")


if __name__ == "__main__":
    main()
