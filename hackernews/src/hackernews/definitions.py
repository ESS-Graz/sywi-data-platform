"""HackerNews project definitions - Dagster assets and resources."""

from dagster import Definitions, with_source_code_references

from sywi_core import lance_config_from_env, lance_io_manager
from hackernews.assets import (
    hackernews_top_stories_ids,
    hackernews_titles,
    hackernews_stories,
    save_to_csv,
    story_analytics,
)


defs = Definitions(
    assets=with_source_code_references(
        [
            hackernews_top_stories_ids,
            hackernews_titles,
            hackernews_stories,
            save_to_csv,
            story_analytics,
        ]
    ),
    resources={"io_manager": lance_io_manager.configured(lance_config_from_env())},
)
