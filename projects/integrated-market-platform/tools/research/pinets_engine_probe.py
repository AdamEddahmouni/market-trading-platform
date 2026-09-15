"""Node/PineTS research bridge probe (outside foundation — subprocess allowed)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

from market_platform_foundation.strategy.source_runtime.pinets_engine_probe import (
    pinets_license_audit,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
_BRIDGE_DIR = (
    REPO_ROOT
    / "src"
    / "market_platform_foundation"
    / "strategy"
    / "source_runtime"
    / "pinets_research_bridge"
)
_PROBE_SCRIPT = _BRIDGE_DIR / "probe.mjs"


def _resolve_node_modules() -> Path | None:
    env_path = os.environ.get("IMP_PINETS_NODE_MODULES")
    if env_path:
        candidate = Path(env_path)
        if (candidate / "pinets").exists():
            return candidate
    local = _BRIDGE_DIR / "node_modules"
    if (local / "pinets").exists():
        return local
    return None


def probe_pinets_engine() -> dict[str, Any]:
    audit = pinets_license_audit()
    if shutil.which("node") is None:
        return {
            "status": "UNAVAILABLE",
            "reason": "NODE_RUNTIME_MISSING",
            **audit,
        }
    node_modules = _resolve_node_modules()
    if node_modules is None:
        return {
            "status": "UNAVAILABLE",
            "reason": "PINETS_AGPL_LICENSE_BOUNDARY",
            "detail": (
                "npm pinets (AGPL-3.0-only) is not installed in the isolated research bridge. "
                "Install only under research/pinets_research_bridge after license review."
            ),
            **audit,
        }
    if not _PROBE_SCRIPT.is_file():
        return {
            "status": "UNAVAILABLE",
            "reason": "BRIDGE_SCRIPT_MISSING",
            **audit,
        }
    try:
        completed = subprocess.run(
            ["node", str(_PROBE_SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(_BRIDGE_DIR),
            env={**os.environ, "NODE_PATH": str(node_modules)},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "UNAVAILABLE",
            "reason": "RUNTIME_ERROR",
            "detail": type(exc).__name__,
            **audit,
        }
    if completed.returncode != 0:
        return {
            "status": "UNAVAILABLE",
            "reason": "PINETS_PROBE_FAILED",
            "detail": (completed.stderr or completed.stdout or "").strip()[:500],
            **audit,
        }
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {
            "status": "UNAVAILABLE",
            "reason": "PINETS_PROBE_INVALID_JSON",
            **audit,
        }
    return {
        "status": "AVAILABLE",
        "pinets_version": str(payload.get("version", "unknown")),
        "node_modules": str(node_modules),
        **audit,
    }


def run_pinets_fixture_via_bridge(
    *,
    script_id: str,
    pine_source: str,
    bars: list[Mapping[str, Any]],
    parameters: Mapping[str, Any],
) -> dict[str, Any]:
    probe = probe_pinets_engine()
    if probe.get("status") != "AVAILABLE":
        return {"status": "UNAVAILABLE", "probe": probe}

    runner = _BRIDGE_DIR / "run_reference.mjs"
    if not runner.is_file():
        return {"status": "UNAVAILABLE", "probe": probe, "reason": "RUNNER_MISSING"}

    node_modules = Path(str(probe["node_modules"]))
    request = {
        "script_id": script_id,
        "pine_source": pine_source,
        "bars": bars,
        "parameters": dict(parameters),
    }
    try:
        completed = subprocess.run(
            ["node", str(runner)],
            input=json.dumps(request),
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(_BRIDGE_DIR),
            env={**os.environ, "NODE_PATH": str(node_modules)},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "ERROR", "reason": "RUNTIME_ERROR", "detail": type(exc).__name__}

    if completed.returncode != 0:
        return {
            "status": "ERROR",
            "reason": "RUNTIME_ERROR",
            "detail": (completed.stderr or completed.stdout or "").strip()[:1000],
        }
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {"status": "ERROR", "reason": "RUNTIME_ERROR", "detail": "INVALID_JSON"}
    payload["status"] = payload.get("status", "OK")
    payload["probe"] = probe
    return payload


__all__ = [
    "probe_pinets_engine",
    "run_pinets_fixture_via_bridge",
]
