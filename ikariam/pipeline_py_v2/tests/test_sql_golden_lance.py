"""SQL gold-standard audit for v2.

All pipeline outputs now live in LanceDB. SQL gold still comes from
`sql_gold_standard/*.csv` (exported once from the SQL run). To compare, we
pull the `*_latest` Lance tables into polars and diff column-by-column
against the SQL CSV (which is itself a latest-snapshot cross-section since
the SQL pipeline was seeded from the last snapshot).

Only rows where SQL has non-null values are compared — SQL's output has
NULL shells for players absent from snapshot 36. We assert that every
column we can map matches within 1e-6.
"""

from __future__ import annotations

from pathlib import Path

import lancedb
import polars as pl
import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SQL_OUT = ROOT / "sql_gold_standard"
LANCEDB_PATH = ROOT / "output" / "ikariam.lancedb"

TOLERANCE = 1e-6

# (sql_csv name, lance table name, sql keys, py keys)
PAIRS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("A_DS.csv",   "player_latest",        ("t_id",),                     ("player_id",)),
    ("AVI_DS.csv", "player_island_latest",
        ("m_owner_id", "m_island_id"), ("player_id", "island_id")),
    ("I_DS.csv",   "island_latest",        ("i_id",),                     ("island_id",)),
)

MANUAL_MAPPINGS: dict[str, str] = {
    "registered_at_unix": "a_registration_time",
    "registered_at": "a_Registration_time_normal",
    "government_form": "a_formOfGovernment",
    "account_age_days": "a_Spieldauer",
    "population_total": "c_Buerger_Ges",
    "wood_in_buildings": "c_Holz_verbaut",
    "crystal_in_buildings": "c_Kristall_verbaut",
    "marble_in_buildings": "c_Stein_verbaut",
    "sulfur_in_buildings": "c_Schwefel_verbaut",
    "wine_in_buildings": "c_Wein_verbaut",
    "resources_in_buildings_total": "c_Res_Ges_verbaut",
    "building_resource_score": "c_Baumeister_Highscore",
    "resources_stored_total": "c_Res_Ges_lagernd",
    "resources_in_buildings_and_storage_total": "c_Res_Ges_verb_lag",
    "building_levels_total": "c_Geblev",
    "wonder_donations_total": "d_Don_Wonder_Ges",
    "sawmill_donations_total": "d_Don_Saegewerk_Ges",
    "luxury_mine_donations_total": "d_DonH_Luxusminen_Ges",
    "donations_total": "d_Don_Ges",
    "luxury_resource_type": "i_tradegood",
    "luxury_mine_level": "i_tradegood_level",
    "sawmill_level": "i_resource_level",
    "sawmill_donated_cumulative": "i_resource_donated",
    "luxury_mine_donated_cumulative": "i_tradegood_donated",
    "wonder_donated_cumulative": "i_wonder_donated",
}


def _map_columns(py_cols: list[str], sql_cols: list[str]) -> dict[str, str]:
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


def _require_outputs():
    if not LANCEDB_PATH.exists():
        pytest.skip(f"{LANCEDB_PATH} missing — run scripts/run.py first")
    if not SQL_OUT.exists() or not any(SQL_OUT.glob("*.csv")):
        pytest.skip(f"{SQL_OUT} empty — run scripts/export_sql_gold.py first")


@pytest.mark.integration
@pytest.mark.parametrize("sql_file,view,sql_keys,py_keys", PAIRS)
def test_view_matches_sql(
    sql_file: str, view: str, sql_keys: tuple[str, ...], py_keys: tuple[str, ...]
):
    _require_outputs()

    db = lancedb.connect(LANCEDB_PATH)
    py_df = pl.from_arrow(db[view].to_arrow())
    assert isinstance(py_df, pl.DataFrame)
    sql_df = pl.read_csv(SQL_OUT / sql_file, separator=";", infer_schema_length=10_000)

    sql_renamed = sql_df.rename(dict(zip(sql_keys, py_keys, strict=True)))
    common = py_df.join(sql_renamed, on=list(py_keys), how="inner", suffix="__sql")
    assert common.height > 0, f"{view}: no common keys with {sql_file}"

    col_map = _map_columns(py_df.columns, sql_renamed.columns)

    failures: list[str] = []
    for py_col, sql_col in col_map.items():
        if py_col in py_keys:
            continue
        sql_in_joined = sql_col if sql_col not in py_df.columns else f"{sql_col}__sql"
        if sql_in_joined not in common.columns:
            continue

        py_s = common[py_col]
        sql_s = common[sql_in_joined]
        sql_non_null = sql_s.is_not_null()
        if int(sql_non_null.sum()) == 0:
            continue

        if py_s.dtype.is_numeric() and sql_s.dtype.is_numeric():
            py_f = py_s.cast(pl.Float64, strict=False).filter(sql_non_null)
            sql_f = sql_s.cast(pl.Float64, strict=False).filter(sql_non_null)
            diff = (py_f - sql_f).abs()
            max_d = diff.max()
            max_d_val = 0.0 if max_d is None else float(max_d)  # type: ignore[arg-type]
            if max_d_val >= TOLERANCE:
                failures.append(f"{py_col} (sql={sql_col}): max|Δ|={max_d_val:.4f}")
        else:
            py_f = py_s.filter(sql_non_null).to_list()
            sql_f = sql_s.filter(sql_non_null).to_list()
            if py_f != sql_f:
                failures.append(f"{py_col} (sql={sql_col}): non-numeric mismatch")

    assert not failures, f"{view} diverges from {sql_file}:\n  " + "\n  ".join(failures)
