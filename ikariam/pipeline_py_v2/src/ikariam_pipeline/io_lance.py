"""Write canonical output DataFrames to LanceDB at `output/ikariam.lancedb/`.

Column-level metadata (description, unit) from `schema.py` is attached via
Arrow field metadata, so reads can introspect via `table.schema.field(c).metadata`.
Table-level descriptions are attached to the schema's metadata dict.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import lancedb
import polars as pl
import pyarrow as pa

from .schema import TABLE_DESCRIPTIONS, TABLE_DOCS


def _attach_metadata(df: pl.DataFrame, table_name: str) -> pa.Table:
    """Convert a polars DataFrame to an Arrow table with field-level and
    schema-level metadata applied from schema.TABLE_DOCS."""
    arrow = df.to_arrow()
    col_docs = TABLE_DOCS.get(table_name, {})
    new_fields = []
    for field in arrow.schema:
        doc = col_docs.get(field.name, {})
        meta = {k.encode(): str(v).encode() for k, v in doc.items()}
        new_fields.append(field.with_metadata(meta) if meta else field)

    schema_meta = {b"description": TABLE_DESCRIPTIONS.get(table_name, "").encode()}
    new_schema = pa.schema(new_fields, metadata=schema_meta)
    return arrow.replace_schema_metadata(schema_meta).cast(new_schema)


def write_lancedb(
    tables: dict[str, pl.DataFrame], output_dir: Path
) -> Path:
    """Create a fresh LanceDB with one table per output frame."""
    db_path = output_dir / "ikariam.lancedb"
    output_dir.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        shutil.rmtree(db_path)
    db = lancedb.connect(db_path)

    for name, df in tables.items():
        tbl = _attach_metadata(df, name)
        # mode="overwrite" drops any existing table of this name.
        db.create_table(name, data=tbl, mode="overwrite")

    return db_path
