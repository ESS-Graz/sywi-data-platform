from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DurationBand:
    max_seconds: float
    factor: float


@dataclass(frozen=True, slots=True)
class Snapshot:
    snapshot_id: str
    snapshot_date: date
    country: str


@dataclass(frozen=True, slots=True)
class Config:
    reference_timestamp: int
    min_play_duration_days: int
    min_registration_time: int
    wonder_split_factor: float
    duration_adjustments: tuple[DurationBand, ...]
    countries: tuple[str, ...]
    snapshots: tuple[Snapshot, ...]
    raw_data_dir: Path
    building_costs_path: Path
    output_dir: Path
    lancedb_path: Path
    output_delimiter: str


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


def _default_duration_bands() -> tuple[DurationBand, ...]:
    return (
        DurationBand(max_seconds=180000, factor=1.00),
        DurationBand(max_seconds=1440000, factor=0.98),
        DurationBand(max_seconds=13149000, factor=0.94),
        DurationBand(max_seconds=math.inf, factor=0.86),
    )


def _discover_countries(raw_data_dir: Path) -> tuple[str, ...]:
    if not raw_data_dir.exists():
        return ()

    country_dirs = sorted(p.name for p in raw_data_dir.iterdir() if p.is_dir())
    invalid = [name for name in country_dirs if name != name.lower()]
    if invalid:
        raise ValueError(
            "Country directories must be lowercase: " + ", ".join(invalid)
        )
    return tuple(name.upper() for name in country_dirs)


def load_config() -> Config:
    """Load configuration from environment variables and built-in defaults."""
    raw_data_dir = platform_root() / "data" / "raw" / "ikariam"
    output_dir = _resolve_path(os.environ.get("IKARIAM_OUTPUT_DIR", "output"))
    if lancedb_path := os.environ.get("IKARIAM_LANCEDB_PATH"):
        resolved_lancedb_path = _resolve_path(lancedb_path)
    else:
        resolved_lancedb_path = output_dir / "ikariam.lancedb"

    return Config(
        reference_timestamp=1415923200,
        min_play_duration_days=2,
        min_registration_time=1366797600,
        wonder_split_factor=0.666667,
        duration_adjustments=_default_duration_bands(),
        countries=_discover_countries(raw_data_dir),
        snapshots=(),
        raw_data_dir=raw_data_dir,
        building_costs_path=raw_data_dir / "building_costs.csv",
        output_dir=output_dir,
        lancedb_path=resolved_lancedb_path,
        output_delimiter=";",
    )


def get_config() -> Config:
    return load_config()
