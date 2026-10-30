"""OpenD readiness using the existing check_live_environment implementation."""

from __future__ import annotations

import copy
import importlib.util
import os
import threading
import time
from pathlib import Path
from typing import Any

from .paths import REPO_ROOT

# AUD-048 (2026-10-29): every GET /state/startup ran this check, which starts PowerShell (8 s timeout) and opens a
# fresh Moomoo quote context; at 23:02Z it timed out while the API was already stalling. A read-only diagnosis is
# now shared for a short time and computed by one caller at a time; ``start=True`` always runs a fresh check.
_DEFAULT_CACHE_SECONDS = 60.0
_lock = threading.Lock()
_cached: tuple[float, dict[str, Any]] | None = None


def _cache_seconds() -> float:
    try:
        return max(0.0, float(os.environ.get("IMP_OPEND_DIAGNOSIS_CACHE_SECONDS", _DEFAULT_CACHE_SECONDS)))
    except (TypeError, ValueError):
        return _DEFAULT_CACHE_SECONDS


def _run_check(*, start: bool) -> dict[str, Any]:
    module_path = REPO_ROOT / "tools" / "moomoo" / "check_live_environment.py"
    spec = importlib.util.spec_from_file_location("imp_check_live_environment", module_path)
    if spec is None or spec.loader is None:
        return {"ready_for_live_observational": False, "status": "CHECK_MODULE_UNAVAILABLE"}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_check(start=start)


def diagnose_opend(*, start: bool = False, clock: Any = time.monotonic) -> dict[str, Any]:
    global _cached
    if start:
        return _run_check(start=True)
    ttl = _cache_seconds()
    with _lock:  # one check at a time; a caller that waited usually finds the answer it waited for
        if _cached is not None and ttl > 0 and clock() - _cached[0] < ttl:
            return copy.deepcopy(_cached[1])
        result = _run_check(start=False)
        _cached = (clock(), result)
        return copy.deepcopy(result)


def reset_opend_diagnosis_cache() -> None:
    global _cached
    with _lock:
        _cached = None
