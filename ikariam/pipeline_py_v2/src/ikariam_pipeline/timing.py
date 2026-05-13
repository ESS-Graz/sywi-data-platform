"""Per-stage timing helper.

Usage:
    from .timing import timed

    with timed("load_raw"):
        raw = load_all_raw(cfg)

Emits one structlog event per stage: `stage_done name=load_raw seconds=2.134`.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

import structlog

_log = structlog.get_logger()


@contextmanager
def timed(name: str) -> Iterator[None]:
    t0 = time.perf_counter()
    try:
        yield
    finally:
        _log.info("stage_done", name=name, seconds=round(time.perf_counter() - t0, 3))
