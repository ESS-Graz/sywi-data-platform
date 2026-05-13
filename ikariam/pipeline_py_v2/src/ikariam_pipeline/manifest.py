"""Write `output/manifest.json` with run metadata so outputs are
self-describing and traceable back to the pipeline version + config."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import Config


def _git_sha() -> str | None:
    """Short HEAD sha of the repo this code runs in, or None if not in git."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return res.stdout.strip() or None
    except Exception:
        return None


def _config_snapshot(cfg: Config) -> dict[str, Any]:
    data = asdict(cfg)
    # Non-JSON-friendly bits: Path → str, date → iso, tuple of dataclasses → list of dicts.
    def _clean(obj: Any) -> Any:
        if isinstance(obj, Path):
            return str(obj)
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_clean(x) for x in obj]
        if isinstance(obj, float):
            # math.inf in duration_adjustments → keep as-is via str
            import math
            return obj if math.isfinite(obj) else str(obj)
        return obj
    return _clean(data)


def write_manifest(
    output_dir: Path,
    cfg: Config,
    raw_row_counts: dict[str, int],
    lancedb_row_counts: dict[str, int],
) -> Path:
    manifest = {
        "pipeline_version": "ikariam-pipeline-v2",
        "git_sha": _git_sha(),
        "run_timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "input": {
            "snapshots": len(cfg.snapshots),
            "date_range": [
                cfg.snapshots[0].snapshot_date.isoformat(),
                cfg.snapshots[-1].snapshot_date.isoformat(),
            ],
            "raw_row_counts": raw_row_counts,
        },
        "output": {
            "lancedb_tables": lancedb_row_counts,
        },
        "sql_alignment": {
            "gold_standard": "Alle_Queries_DE_hintereinander.sql",
            "known_divergences_from_v1r": [
                "duration_adjustment: CASE first-match-wins with gap=1.0 (was always 0.86)",
                "_verbaut columns: multiplied by band factor in place (was unadjusted)",
                "wonder split: matching=0, non-matching=(1-f) each (was flipped)",
                "prelaunch player filter: registration_time >= min_registration_time "
                "(was Spieldauer>=2)",
                "donations without a matching city are dropped (was retained)",
            ],
            "known_divergences_from_sql": [
                "prelaunch player filter applied across all snapshots "
                "(SQL filters only seed snapshot)",
                "Python keeps full panel; SQL keeps cross-section with NULL-shell rows",
            ],
        },
        "config": _config_snapshot(cfg),
    }
    path = output_dir / "manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path
