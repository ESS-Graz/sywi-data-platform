"""Lance IOManager for Dagster assets: every asset is stored as a LanceDB table."""

from __future__ import annotations

import os
from typing import Any

import lancedb
import pandas as pd
import pyarrow as pa
from dagster import (
    Field,
    InitResourceContext,
    InputContext,
    IOManager,
    OutputContext,
    Permissive,
    io_manager,
)

DEFAULT_LANCE_URI = "./data/lance"


def lance_config_from_env() -> dict:
    """Build the IO manager config from environment variables.

    LANCE_URI is a local directory (default ./data/lance) or an S3 path such as
    s3://bucket/path. For S3 the credentials come from AWS_ACCESS_KEY_ID and
    AWS_SECRET_ACCESS_KEY, plus the optional AWS_ENDPOINT_URL and AWS_REGION.
    """
    uri = os.environ.get("LANCE_URI", DEFAULT_LANCE_URI)
    config: dict = {"uri": uri}

    if uri.startswith("s3://"):
        options = {
            "aws_access_key_id": os.environ["AWS_ACCESS_KEY_ID"],
            "aws_secret_access_key": os.environ["AWS_SECRET_ACCESS_KEY"],
            "aws_region": os.environ.get("AWS_REGION", "us-east-1"),
            "aws_virtual_hosted_style_request": "false",
        }
        if "AWS_ENDPOINT_URL" in os.environ:
            options["aws_endpoint"] = os.environ["AWS_ENDPOINT_URL"]
        config["storage_options"] = options

    return config


class LanceIOManager(IOManager):
    """Stores each asset as a LanceDB table named after the asset.

    Writing replaces the whole table, including its schema, so a changed set of
    columns needs no migration. Assets return and receive pandas DataFrames.
    """

    def __init__(self, uri: str, storage_options: dict | None = None) -> None:
        self._uri = uri
        self._storage_options = storage_options

    def _connect(self):
        return lancedb.connect(self._uri, storage_options=self._storage_options)

    def handle_output(self, context: OutputContext, obj: Any) -> None:
        table_name = context.asset_key.path[-1]
        df = obj if isinstance(obj, pd.DataFrame) else pd.DataFrame(obj)
        data = pa.Table.from_pandas(df, preserve_index=False)

        context.log.info(f"[LanceIOManager] Writing table {table_name} to {self._uri}")
        self._connect().create_table(table_name, data, mode="overwrite")

        context.add_output_metadata(
            {"lance_table": table_name, "row_count": data.num_rows, "uri": self._uri}
        )

    def load_input(self, context: InputContext) -> pd.DataFrame:
        # An asset from another code location has no upstream output here, only its key.
        key = context.upstream_output.asset_key if context.upstream_output else context.asset_key
        table_name = key.path[-1]
        context.log.info(f"[LanceIOManager] Reading table {table_name} from {self._uri}")
        return self._connect().open_table(table_name).to_pandas()


@io_manager(
    config_schema={
        "uri": str,
        "storage_options": Field(Permissive(), is_required=False),
    }
)
def lance_io_manager(init_context: InitResourceContext) -> LanceIOManager:
    cfg = init_context.resource_config
    return LanceIOManager(cfg["uri"], cfg.get("storage_options"))
