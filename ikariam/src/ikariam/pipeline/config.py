from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


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
    if root := os.environ.get("IKARIAM_PROJECT_ROOT"):
        return Path(root).expanduser().resolve()

    cwd = Path.cwd().resolve()
    for candidate in _project_root_candidates(cwd):
        if _looks_like_project_root(candidate):
            return candidate.resolve()

    if cwd.name == "ikariam":
        return cwd

    return Path(__file__).resolve().parents[3]


def _project_root_candidates(cwd: Path) -> tuple[Path, ...]:
    ancestors = (cwd, *cwd.parents)
    return (*ancestors, *(path / "ikariam" for path in ancestors))


def _looks_like_project_root(path: Path) -> bool:
    return (path / "pyproject.toml").is_file() and (path / "src" / "ikariam").is_dir()


def _resolve_path(value: str | Path, base: Path | None = None) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return ((base or project_root()) / path).resolve()


def _coerce_max_seconds(raw: Any) -> float:
    if isinstance(raw, str) and raw.strip().lower() in {".inf", "inf", "+inf"}:
        return math.inf
    if isinstance(raw, float) and math.isinf(raw):
        return raw
    return float(raw)


def _default_duration_bands() -> tuple[DurationBand, ...]:
    return (
        DurationBand(max_seconds=180000, factor=1.00),
        DurationBand(max_seconds=1440000, factor=0.98),
        DurationBand(max_seconds=13149000, factor=0.94),
        DurationBand(max_seconds=math.inf, factor=0.86),
    )


def _read_yaml(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _raw_data_dir_from_env() -> Path:
    if raw_dir := os.environ.get("IKARIAM_RAW_DATA_DIR"):
        return _resolve_path(raw_dir)
    if raw_root := os.environ.get("SYWI_RAW_DATA_DIR"):
        return _resolve_path(Path(raw_root) / "ikariam")

    root = project_root()
    candidates = (
        root / "data" / "raw" / "ikariam",
        root.parent / "data" / "raw" / "ikariam",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def _configured_countries(raw: dict[str, Any], raw_data_dir: Path) -> tuple[str, ...]:
    if env_countries := os.environ.get("IKARIAM_COUNTRIES"):
        values = [c.strip() for c in env_countries.split(",")]
    else:
        values = raw.get("countries") or []

    if values:
        return tuple(c.upper() for c in values if c)

    if raw_data_dir.exists():
        countries = [p.name.upper() for p in raw_data_dir.iterdir() if p.is_dir()]
        return tuple(sorted(countries))

    return ()


def _duration_bands(raw: dict[str, Any]) -> tuple[DurationBand, ...]:
    bands = raw.get("duration_adjustments")
    if not bands:
        return _default_duration_bands()
    return tuple(
        DurationBand(
            max_seconds=_coerce_max_seconds(b["max_seconds"]),
            factor=float(b["factor"]),
        )
        for b in bands
    )


def _building_costs_path(raw: dict[str, Any], raw_data_dir: Path, base: Path) -> Path:
    if configured := os.environ.get("IKARIAM_BUILDING_COSTS_PATH"):
        return _resolve_path(configured)

    if configured := raw.get("paths", {}).get("building_costs"):
        return _resolve_path(configured, base)

    return (raw_data_dir / "building_costs.csv").resolve()


def load_config(path: Path | None = None) -> Config:
    """Load pipeline config from env plus optional YAML.

    The old v2 YAML still provides numeric transformation parameters, but raw
    snapshots are now discovered from the parquet directory tree.
    """
    raw = _read_yaml(path)
    base = path.parent.parent if path is not None and path.exists() else project_root()

    raw_data_dir = _raw_data_dir_from_env()
    output_dir = _resolve_path(
        os.environ.get("IKARIAM_OUTPUT_DIR", raw.get("paths", {}).get("output_dir", "output")),
        base,
    )
    if lancedb_path := os.environ.get("IKARIAM_LANCEDB_PATH"):
        resolved_lancedb_path = _resolve_path(lancedb_path)
    else:
        resolved_lancedb_path = output_dir / "ikariam.lancedb"

    building_costs_path = _building_costs_path(raw, raw_data_dir, base)

    return Config(
        reference_timestamp=int(raw.get("reference_timestamp", 1415923200)),
        min_play_duration_days=int(raw.get("min_play_duration_days", 2)),
        min_registration_time=int(raw.get("min_registration_time", 1366797600)),
        wonder_split_factor=float(raw.get("wonder_split_factor", 0.666667)),
        duration_adjustments=_duration_bands(raw),
        countries=_configured_countries(raw, raw_data_dir),
        snapshots=(),
        raw_data_dir=raw_data_dir,
        building_costs_path=building_costs_path,
        output_dir=output_dir,
        lancedb_path=resolved_lancedb_path,
        output_delimiter=raw.get("output", {}).get("delimiter", ";"),
    )


def get_config() -> Config:
    config_path = os.environ.get("IKARIAM_CONFIG_PATH")
    return load_config(_resolve_path(config_path) if config_path else None)
