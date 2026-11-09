from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Config:
    wonder_split_factor: float
    raw_data_dir: Path
    building_costs_path: Path
    server_starts_path: Path
    output_dir: Path
    # Local directory, or an object-store URI such as s3://ikariam/ikariam.lancedb
    lancedb_path: Path | str


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def platform_root() -> Path:
    project = project_root()
    workspace = project.parent
    return workspace if (workspace / "dg.toml").is_file() else project


def _resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()

    return (project_root() / path).resolve()


def load_config() -> Config:
    """Load configuration from environment variables and built-in defaults."""
    raw_data_dir = platform_root() / "data" / "raw" / "ikariam"
    output_dir = _resolve_path(os.environ.get("IKARIAM_OUTPUT_DIR", "output"))
    resolved_lancedb_path: Path | str

    if lancedb_path := os.environ.get("IKARIAM_LANCEDB_PATH"):
        # URIs (s3://...) go to LanceDB as-is; S3 endpoint and credentials come
        # from the AWS_* environment variables that LanceDB reads natively.
        resolved_lancedb_path = (
            lancedb_path if "://" in lancedb_path else _resolve_path(lancedb_path)
        )
    else:
        resolved_lancedb_path = output_dir / "ikariam.lancedb"

    return Config(
        wonder_split_factor=0.666667,  # 2/3, rounded; see transforms/donations.py
        raw_data_dir=raw_data_dir,
        building_costs_path=raw_data_dir / "building_costs.csv",
        # Documented start of each server's world; accounts registered earlier
        # are admin/test accounts (docs/snapshots_verification.xlsx, sheet Servers).
        server_starts_path=raw_data_dir / "server_starts.csv",
        output_dir=output_dir,
        lancedb_path=resolved_lancedb_path,
    )


def get_config() -> Config:
    return load_config()
