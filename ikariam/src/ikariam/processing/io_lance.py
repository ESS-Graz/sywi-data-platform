"""Write canonical output DataFrames to LanceDB at `output/ikariam.lancedb/`.

Column-level metadata (description, unit) from `schema.py` is attached via
Arrow field metadata, so reads can introspect via `table.schema.field(c).metadata`.
Table-level descriptions are attached to the schema's metadata dict.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import lancedb
import polars as pl
import pyarrow as pa

from .schema import TABLE_DESCRIPTIONS, TABLE_DOCS


def _metadata_table_name(table_name: str) -> str:
    """Map dynamic country-partitioned raw tables to their base docs."""
    if table_name.startswith("raw_"):
        base, _, suffix = table_name.rpartition("_")
        if base and len(suffix) == 2:
            return base
    return table_name


def _raw_partition_metadata(table_name: str) -> dict[bytes, bytes]:
    if not table_name.startswith("raw_"):
        return {}

    base, _, suffix = table_name.rpartition("_")
    if not base or len(suffix) != 2:
        return {}

    return {
        b"source_table": base.encode(),
        b"partition_column": b"country",
        b"partition_value": suffix.upper().encode(),
    }


def _attach_metadata(df: pl.DataFrame, table_name: str) -> pa.Table:
    """Convert a polars DataFrame to an Arrow table with field-level and
    schema-level metadata applied from schema.TABLE_DOCS."""
    arrow = df.to_arrow()
    metadata_table_name = _metadata_table_name(table_name)
    col_docs = TABLE_DOCS.get(metadata_table_name, {})
    new_fields = []
    for field in arrow.schema:
        doc = col_docs.get(field.name, {})
        meta = {k.encode(): str(v).encode() for k, v in doc.items()}
        new_fields.append(field.with_metadata(meta) if meta else field)

    schema_meta = {
        b"description": TABLE_DESCRIPTIONS.get(metadata_table_name, "").encode(),
        **_raw_partition_metadata(table_name),
    }
    new_schema = pa.schema(new_fields, metadata=schema_meta)
    return arrow.replace_schema_metadata(schema_meta).cast(new_schema)


def _country_sort_key(country: Any) -> str:
    return str(country).upper()


def partition_raw_tables_by_country(raw_tables: dict[str, pl.DataFrame]) -> dict[str, pl.DataFrame]:
    """Split raw output tables into one Lance table per country.

    LanceDB's Python table creation API does not expose a native partition_by
    option, so raw rows are exported as explicit country partition tables:
    `raw_avatar_de`, `raw_city_de`, etc.
    """
    partitioned: dict[str, pl.DataFrame] = {}
    for name, df in raw_tables.items():
        country_column = "country" if "country" in df.columns else "country_code"
        if country_column not in df.columns:
            raise ValueError(f"Raw table {name!r} must include a country or country_code column")

        countries = sorted(
            df.get_column(country_column).drop_nulls().unique().to_list(),
            key=_country_sort_key,
        )
        for country in countries:
            country_code = str(country).lower()
            partitioned[f"{name}_{country_code}"] = df.filter(pl.col(country_column) == country)

    return partitioned


def write_lancedb(tables: dict[str, pl.DataFrame], db_path: Path) -> Path:
    """Create a fresh LanceDB with one table per output frame."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        shutil.rmtree(db_path)
    db = lancedb.connect(db_path)

    for name, df in tables.items():
        tbl = _attach_metadata(df, name)
        # mode="overwrite" drops any existing table of this name.
        db.create_table(name, data=tbl, mode="overwrite")

    return db_path
