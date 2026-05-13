"""Export the SQL pipeline's final tables to CSVs in sql_gold_standard/.

Prereq: `ikariam_sql_gold` database must hold `A_DS`, `AVI_DS`, `I_DS`,
`Teilnahme_AV`, `Master_Avi` after running `Alle_Queries_DE_hintereinander.sql`.
See `pipeline_py/sql_gold_standard/README.md`.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

URI = "mysql://root:root@127.0.0.1:3306/ikariam_sql_gold"
TARGET = Path(__file__).resolve().parent.parent / "sql_gold_standard"

# (canonical output filename, sql table name in ikariam_sql_gold).
# The patched SQL lowercases the auxiliary table names; A_DS / AVI_DS / I_DS
# keep their original case.
TABLES: tuple[tuple[str, str], ...] = (
    ("A_DS",         "A_DS"),
    ("AVI_DS",       "AVI_DS"),
    ("I_DS",         "I_DS"),
    ("Teilnahme_AV", "teilnahme_av"),
    ("Master_Avi",   "master_avi"),
)

# Columns that MariaDB's TINYINT(1) returns as Boolean under connectorx;
# re-fetch as CAST(col AS SIGNED) to preserve integer semantics for values > 1.
TINYINT_PREFIXES = ("a_formOfGovernment", "a_gender", "a_Anz_Av_per_DB")


def _build_select(sql_tbl: str, uri: str) -> str:
    """SELECT * plus CAST AS SIGNED for every TINYINT column. connectorx treats
    any MySQL TINYINT — regardless of display width — as Boolean, which silently
    truncates values like formOfGovernment=6 or tradegood=4 to true/false.
    """
    info = pl.read_database_uri(
        query=(
            "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
            f"WHERE TABLE_SCHEMA='ikariam_sql_gold' AND TABLE_NAME='{sql_tbl}'"
        ),
        uri=uri,
        engine="connectorx",
    )
    tinyint_cols = [
        r["COLUMN_NAME"]
        for r in info.iter_rows(named=True)
        if str(r["DATA_TYPE"]).lower() == "tinyint"
    ]
    if not tinyint_cols:
        return f"SELECT * FROM `{sql_tbl}`"
    extras = ", ".join(f"CAST(`{c}` AS SIGNED) AS `{c}__int`" for c in tinyint_cols)
    return f"SELECT *, {extras} FROM `{sql_tbl}`"


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    for out_name, sql_tbl in TABLES:
        query = _build_select(sql_tbl, URI)
        df = pl.read_database_uri(query=query, uri=URI, engine="connectorx")

        # Replace each boolean-coerced TINYINT(1) column with its integer copy.
        for col in list(df.columns):
            int_col = f"{col}__int"
            if int_col in df.columns:
                df = df.drop(col).rename({int_col: col})

        out = TARGET / f"{out_name}.csv"
        df.write_csv(out, separator=";", null_value="")
        print(f"  {out_name:15s}  {df.height:>7} rows × {df.width:>4} cols  -> {out.name}")


if __name__ == "__main__":
    main()
