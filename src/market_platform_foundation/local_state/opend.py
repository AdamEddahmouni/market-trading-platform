"""OpenD readiness using the existing check_live_environment implementation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from .paths import REPO_ROOT


def diagnose_opend(*, start: bool = False) -> dict[str, Any]:
    module_path = REPO_ROOT / "tools" / "moomoo" / "check_live_environment.py"
    spec = importlib.util.spec_from_file_location("imp_check_live_environment", module_path)
    if spec is None or spec.loader is None:
        return {"ready_for_live_observational": False, "status": "CHECK_MODULE_UNAVAILABLE"}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_check(start=start)
