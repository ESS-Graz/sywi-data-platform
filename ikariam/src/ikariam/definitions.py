"""IKARIAM project definitions."""

from dagster import (
    AssetSelection,
    Definitions,
    define_asset_job,
    with_source_code_references,
)

from ikariam.assets import ALL_ASSETS

# Runs every asset in dependency order: raw inputs through to the LanceDB export.
full_pipeline_job = define_asset_job("ikariam_full_pipeline", selection=AssetSelection.all())


defs = Definitions(
    assets=with_source_code_references(ALL_ASSETS),
    jobs=[full_pipeline_job],
)
