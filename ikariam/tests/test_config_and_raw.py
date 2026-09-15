from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from ikariam.processing import config as config_module
from ikariam.processing.config import Config, load_config
from ikariam.processing.io_raw import discover_snapshots, load_raw_table


def _cfg(raw_data_dir: Path) -> Config:
    return Config(
        min_registration_time=1366797600,
        wonder_split_factor=0.666667,
        countries=("DE", "EN"),
        raw_data_dir=raw_data_dir,
        building_costs_path=raw_data_dir / "building_costs.csv",
        output_dir=raw_data_dir / "output",
        lancedb_path=raw_data_dir / "output" / "ikariam.lancedb",
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


def test_config_uses_workspace_raw_convention(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = workspace / "ikariam"
    raw_root = workspace / "data" / "raw" / "ikariam"
    (raw_root / "de" / "2013-04-25").mkdir(parents=True)
    project.mkdir()
    (workspace / "dg.toml").write_text('directory_type = "workspace"\n', encoding="utf-8")

    monkeypatch.setattr(config_module, "project_root", lambda: project)

    cfg = load_config()

    assert config_module.platform_root() == workspace
    assert cfg.raw_data_dir == raw_root
    assert cfg.countries == ("DE",)
    assert cfg.building_costs_path == raw_root / "building_costs.csv"


def test_config_uses_project_root_without_workspace(monkeypatch, tmp_path: Path):
    project = tmp_path / "ikariam"
    raw_root = project / "data" / "raw" / "ikariam"
    (raw_root / "de" / "2013-04-25").mkdir(parents=True)

    monkeypatch.setattr(config_module, "project_root", lambda: project)

    cfg = load_config()

    assert config_module.platform_root() == project
    assert cfg.raw_data_dir == raw_root
    assert cfg.countries == ("DE",)
    assert cfg.building_costs_path == raw_root / "building_costs.csv"


def test_config_rejects_uppercase_country_directories(monkeypatch, tmp_path: Path):
    project = tmp_path / "ikariam"
    raw_root = project / "data" / "raw" / "ikariam"
    (raw_root / "DE" / "2013-04-25").mkdir(parents=True)

    monkeypatch.setattr(config_module, "project_root", lambda: project)

    with pytest.raises(ValueError, match="Country directories must be lowercase: DE"):
        load_config()
