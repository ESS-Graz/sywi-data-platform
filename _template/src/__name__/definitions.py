"""__NAME__ project definitions - self-contained Dagster definitions."""

from dagster import Definitions, with_source_code_references

from sywi_core import lance_config_from_env, lance_io_manager
from __name__.assets import example_asset


defs = Definitions(
    assets=with_source_code_references(
        [
            example_asset,
        ]
    ),
    resources={"io_manager": lance_io_manager.configured(lance_config_from_env())},
)
