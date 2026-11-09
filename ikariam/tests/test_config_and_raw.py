from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from ikariam.processing import config as config_module
from ikariam.processing.config import Config, load_config
from ikariam.processing.io_files import read_building_costs, read_server_starts
from ikariam.processing.io_raw import load_raw_table


def _cfg(raw_data_dir: Path) -> Config:
    return Config(
        wonder_split_factor=0.666667,
        raw_data_dir=raw_data_dir,
        building_costs_path=raw_data_dir / "building_costs.csv",
        server_starts_path=raw_data_dir / "server_starts.csv",
        output_dir=raw_data_dir / "output",
        lancedb_path=raw_data_dir / "output" / "ikariam.lancedb",
    )


def _snapshot_dir(root: Path, country: str, server: int, snapshot_date: str) -> Path:
    return root / f"country={country}" / f"server={server}" / f"snapshot_date={snapshot_date}"


def _write_snapshot(
    root: Path, country: str, snapshot_date: str, server: int = 1, dtype=pl.Int64
) -> None:
    snap_dir = _snapshot_dir(root, country, server, snapshot_date)
    snap_dir.mkdir(parents=True)
    pl.DataFrame(
        {"id": [f"{country}-player"], "registration_time": pl.Series([1366797600], dtype=dtype)}
    ).write_parquet(snap_dir / "avatar_0.parquet")
    pl.DataFrame({"ignored": [1]}).write_parquet(snap_dir / "logGovernmentChanges.parquet")


def test_raw_loader_reads_all_countries_and_adds_snapshot_columns(tmp_path: Path):
    raw_root = tmp_path / "ikariam"
    _write_snapshot(raw_root, "de", "2013-04-25", server=23)
    _write_snapshot(raw_root, "en", "2013-05-02", server=22)

    df = load_raw_table(_cfg(raw_root), "avatar").sort("country")
    assert df.select("country", "snapshot_id", "snapshot_date").to_dicts() == [
        {"country": "DE", "snapshot_id": "de23_2504_13", "snapshot_date": date(2013, 4, 25)},
        {"country": "EN", "snapshot_id": "en22_0205_13", "snapshot_date": date(2013, 5, 2)},
    ]
    assert df.sort("country")["server"].to_list() == [23, 22]


def test_raw_loader_separates_servers_and_widens_integer_types(tmp_path: Path):
    raw_root = tmp_path / "ikariam"
    _write_snapshot(raw_root, "de", "2013-04-25", server=23, dtype=pl.UInt32)
    _write_snapshot(raw_root, "de", "2013-04-25", server=24, dtype=pl.Int64)

    df = load_raw_table(_cfg(raw_root), "avatar").sort("server")

    assert df["snapshot_id"].to_list() == ["de23_2504_13", "de24_2504_13"]
    assert df["registration_time"].dtype == pl.Int64


def test_config_uses_workspace_raw_convention(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    project = workspace / "ikariam"
    raw_root = workspace / "data" / "raw" / "ikariam"
    _snapshot_dir(raw_root, "de", 1, "2013-04-25").mkdir(parents=True)
    project.mkdir()
    (workspace / "dg.toml").write_text('directory_type = "workspace"\n', encoding="utf-8")

    monkeypatch.setattr(config_module, "project_root", lambda: project)

    cfg = load_config()

    assert config_module.platform_root() == workspace
    assert cfg.raw_data_dir == raw_root
    assert cfg.building_costs_path == raw_root / "building_costs.csv"


def test_config_uses_project_root_without_workspace(monkeypatch, tmp_path: Path):
    project = tmp_path / "ikariam"
    raw_root = project / "data" / "raw" / "ikariam"
    _snapshot_dir(raw_root, "de", 1, "2013-04-25").mkdir(parents=True)

    monkeypatch.setattr(config_module, "project_root", lambda: project)

    cfg = load_config()

    assert config_module.platform_root() == project
    assert cfg.raw_data_dir == raw_root
    assert cfg.building_costs_path == raw_root / "building_costs.csv"


def test_raw_loader_rejects_snapshots_with_different_columns(tmp_path: Path):
    raw_root = tmp_path / "ikariam"
    _write_snapshot(raw_root, "de", "2013-04-25")
    later = _snapshot_dir(raw_root, "de", 1, "2013-05-02")
    later.mkdir(parents=True)
    pl.DataFrame({"id": ["de-player"]}).write_parquet(later / "avatar_0.parquet")

    cfg = _cfg(raw_root)
    with pytest.raises(pl.exceptions.PolarsError, match="same schema"):
        load_raw_table(cfg, "avatar")


def test_building_costs_rejects_empty_cells(tmp_path: Path):
    path = tmp_path / "building_costs.csv"
    path.write_text(
        "building_type;building_level;cost_holz;cost_quartz;cost_kristall;cost_wein;cost_schwefel\n1;2;158;;0;0;0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"empty cells in: \['cost_quartz'\]"):
        read_building_costs(path)


def test_server_starts_reads_utc_start_per_server(tmp_path: Path):
    path = tmp_path / "server_starts.csv"
    path.write_text("country;server;start_utc\nde;23;2013-04-24 10:00:00\n", encoding="utf-8")

    assert read_server_starts(path).to_dicts() == [{"country": "DE", "server": 23, "start_unix": 1366797600}]


def test_server_starts_rejects_duplicate_servers(tmp_path: Path):
    path = tmp_path / "server_starts.csv"
    path.write_text("country;server;start_utc\nDE;23;2013-04-24 10:00:00\nDE;23;2013-04-25 10:00:00\n", encoding="utf-8")

    with pytest.raises(ValueError, match="lists a server twice"):
        read_server_starts(path)
