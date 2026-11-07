"""HackerNews data storage in Lance."""

from datetime import datetime

import pandas as pd
from dagster import AssetExecutionContext, MetadataValue, asset


@asset(
    group_name="hackernews",
    description="Stores HackerNews stories as a LanceDB table",
    metadata={
        "output_format": "Lance",
        "storage": "lancedb",
    },
    kinds={"python", "lance"},
    tags={
        "storage": "lancedb",
    },
    code_version="2.0.1",
)
def hackernews_stories(
    context: AssetExecutionContext,
    hackernews_titles: pd.DataFrame,
) -> pd.DataFrame:
    """Store HackerNews titles in Lance via IOManager."""
    # hackernews_titles is already a DataFrame from the IOManager
    df = hackernews_titles.copy()

    # Add fetched_at timestamp
    df["fetched_at"] = datetime.now()

    context.log.info(f"Prepared {len(df)} stories for storage")

    # Add preview metadata
    context.add_output_metadata(
        metadata={
            "num_records": len(df),
            "preview": MetadataValue.md(
                "**Stories to Store:**\n\n"
                + "\n".join(
                    [
                        f"- **{row['title']}** (ID: {row['id']}) by {row['author']}"
                        for _, row in df.head(3).iterrows()
                    ]
                )
            ),
        }
    )

    # Return DataFrame - IOManager will handle Lance storage
    return df
