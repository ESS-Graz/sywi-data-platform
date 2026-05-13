from __future__ import annotations

import math
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
class DBConfig:
    host: str
    port: int
    user: str
    password: str


@dataclass(frozen=True, slots=True)
class Config:
    db: DBConfig
    reference_timestamp: int
    min_play_duration_days: int
    min_registration_time: int
    wonder_split_factor: float
    duration_adjustments: tuple[DurationBand, ...]
    countries: tuple[str, ...]
    snapshots: tuple[Snapshot, ...]
    building_costs_path: Path
    output_dir: Path
    output_delimiter: str


def _coerce_max_seconds(raw: Any) -> float:
    if isinstance(raw, str) and raw.strip().lower() in {".inf", "inf", "+inf"}:
        return math.inf
    if isinstance(raw, float) and math.isinf(raw):
        return raw
    return float(raw)


def load_config(path: Path) -> Config:
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    db = DBConfig(
        host=raw["database"]["host"],
        port=int(raw["database"]["port"]),
        user=raw["database"]["user"],
        password=raw["database"]["password"],
    )

    bands = tuple(
        DurationBand(max_seconds=_coerce_max_seconds(b["max_seconds"]), factor=float(b["factor"]))
        for b in raw["duration_adjustments"]
    )

    country_code = raw["countries"][0]
    snapshot_key = f"snapshots_{country_code.lower()}"
    snapshot_pairs = [
        Snapshot(
            snapshot_id=sid,
            snapshot_date=date.fromisoformat(str(sdate)),
            country=country_code,
        )
        for sid, sdate in raw[snapshot_key].items()
    ]
    snapshots = tuple(sorted(snapshot_pairs, key=lambda s: s.snapshot_date))

    pipeline_root = path.parent.parent
    building_costs_path = (pipeline_root / raw["paths"]["building_costs"]).resolve()
    output_dir = (pipeline_root / raw["paths"]["output_dir"]).resolve()

    return Config(
        db=db,
        reference_timestamp=int(raw["reference_timestamp"]),
        min_play_duration_days=int(raw["min_play_duration_days"]),
        min_registration_time=int(raw.get("min_registration_time", 0)),
        wonder_split_factor=float(raw["wonder_split_factor"]),
        duration_adjustments=bands,
        countries=tuple(raw["countries"]),
        snapshots=snapshots,
        building_costs_path=building_costs_path,
        output_dir=output_dir,
        output_delimiter=raw["output"]["delimiter"],
    )
