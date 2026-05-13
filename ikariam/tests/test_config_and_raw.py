from __future__ import annotations

import math
from pathlib import Path

import polars as pl

from ikariam.pipeline.config import Config, DurationBand, load_config, project_root
from ikariam.pipeline.io_raw import discover_snapshots, load_raw_table


def _cfg(raw_data_dir: Path) -> Config:
    return Config(
        reference_timestamp=1415923200,
        min_play_duration_days=2,
        min_registration_time=1366797600,
        wonder_split_factor=0.666667,
        duration_adjustments=(DurationBand(math.inf, 1.0),),
        countries=("DE", "EN"),
        snapshots=(),
        raw_data_dir=raw_data_dir,
        building_costs_path=raw_data_dir / "building_costs.csv",
        output_dir=raw_data_dir / "output",
        lancedb_path=raw_data_dir / "output" / "ikariam.lancedb",
        output_delimiter=";",
    )


def _write_snapshot(root: Path, country: str, snapshot_date: str) -> None:
    snap_dir = root / country / snapshot_date
    snap_dir.mkdir(parents=True)
    pl.DataFrame({"id": [f"{country}-player"], "registration_time": [1366797600]}).write_parquet(
        snap_dir / "avatar.parquet"
    )
    pl.DataFrame({"ignored": [1]}).write_parquet(snap_dir / "logGovernmentChanges.parquet")


def test_raw_loader_discovers_countries_and_adds_snapshot_columns(tmp_path: Path):
    raw_root = tmp_path / "ikariam"
    _write_snapshot(raw_root, "de", "2013-04-25")
    _write_snapshot(raw_root, "en", "2013-05-02")

    snapshots = discover_snapshots(raw_root, ("DE", "EN"))
    assert [s.snapshot_id for s in snapshots] == ["de_2504_13", "en_0205_13"]

    df = load_raw_table(_cfg(raw_root), "avatar").sort("country")
    assert df.select("country", "snapshot_id", "snapshot_date").to_dicts() == [
        {"country": "DE", "snapshot_id": "de_2504_13", "snapshot_date": snapshots[0].snapshot_date},
        {"country": "EN", "snapshot_id": "en_0205_13", "snapshot_date": snapshots[1].snapshot_date},
    ]


def test_default_config_finds_workspace_level_raw_data(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = workspace / "ikariam"
    raw_root = workspace / "data" / "raw" / "ikariam"
    (raw_root / "de" / "2013-04-25").mkdir(parents=True)
    project.mkdir()

    monkeypatch.chdir(project)
    monkeypatch.delenv("IKARIAM_RAW_DATA_DIR", raising=False)
    monkeypatch.delenv("SYWI_RAW_DATA_DIR", raising=False)
    monkeypatch.delenv("IKARIAM_COUNTRIES", raising=False)

    cfg = load_config()

    assert cfg.raw_data_dir == raw_root
    assert cfg.countries == ("DE",)


def test_default_config_resolves_from_dagster_dev_workspace(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = workspace / "ikariam"
    dagster_workspace = workspace / ".dagster" / "dev-workspace"
    raw_root = workspace / "data" / "raw" / "ikariam"
    building_costs = project / "data" / "building_costs.csv"

    (project / "src" / "ikariam").mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname = \"ikariam\"\n", encoding="utf-8")
    building_costs.parent.mkdir(parents=True)
    building_costs.write_text("", encoding="utf-8")
    (raw_root / "de" / "2013-04-25").mkdir(parents=True)
    dagster_workspace.mkdir(parents=True)

    monkeypatch.chdir(dagster_workspace)
    monkeypatch.delenv("IKARIAM_PROJECT_ROOT", raising=False)
    monkeypatch.delenv("IKARIAM_RAW_DATA_DIR", raising=False)
    monkeypatch.delenv("SYWI_RAW_DATA_DIR", raising=False)
    monkeypatch.delenv("IKARIAM_COUNTRIES", raising=False)

    cfg = load_config()

    assert project_root() == project
    assert cfg.raw_data_dir == raw_root
    assert cfg.countries == ("DE",)
    assert cfg.building_costs_path == building_costs
