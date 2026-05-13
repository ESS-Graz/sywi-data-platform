from __future__ import annotations

import math
from pathlib import Path

from ikariam_pipeline.config import load_config

PIPELINE_ROOT = Path(__file__).resolve().parent.parent


def test_load_config_has_inf_and_sorted_snapshots():
    cfg = load_config(PIPELINE_ROOT / "config" / "parameters.yaml")

    assert cfg.reference_timestamp == 1415923200
    assert cfg.min_play_duration_days == 2
    assert abs(cfg.wonder_split_factor - 0.666667) < 1e-9

    # Last duration band must be +inf (the ".inf" YAML sentinel).
    assert math.isinf(cfg.duration_adjustments[-1].max_seconds)
    assert cfg.duration_adjustments[-1].factor == 0.86

    # Snapshots sorted ascending by date.
    dates = [s.snapshot_date for s in cfg.snapshots]
    assert dates == sorted(dates)

    # All DE snapshots, YAML lists 36 for DE.
    assert len(cfg.snapshots) == 36
    assert cfg.snapshots[0].snapshot_id == "de_2504_13"
    assert cfg.snapshots[-1].snapshot_id == "de_1311_14"
