from __future__ import annotations

import argparse
from pathlib import Path

from ikariam_pipeline.config import load_config
from ikariam_pipeline.logging_setup import configure_logging
from ikariam_pipeline.run_pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Ikariam Python pipeline.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/parameters.yaml"),
        help="Path to parameters.yaml (default: config/parameters.yaml)",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Use raw_cache/ parquet cache instead of hitting MariaDB (if cache exists).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("raw_cache"),
        help="Directory for raw parquet cache (default: raw_cache/)",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    configure_logging(args.log_level)
    cfg = load_config(args.config.resolve())

    cache_dir = args.cache_dir if args.use_cache else None
    run_pipeline(cfg, cache_dir=cache_dir)


if __name__ == "__main__":
    main()
