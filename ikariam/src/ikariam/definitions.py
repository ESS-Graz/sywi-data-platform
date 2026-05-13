"""IKARIAM project definitions."""

from dagster import Definitions, with_source_code_references

from ikariam.assets import ALL_ASSETS


defs = Definitions(
    assets=with_source_code_references(ALL_ASSETS),
)
