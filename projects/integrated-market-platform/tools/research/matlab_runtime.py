"""MATLAB process probe and smoke (outside foundation — subprocess allowed)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from market_platform_foundation.research.export_v1_matlab_result import (
    MATLAB_RUNTIME_NOT_AVAILABLE,
    matlab_research_result_content_sha256,
    validate_matlab_research_result_v1,
)

MATLAB_RESULT_FILENAME = "matlab_research_result_v1.json"
MATLAB_SMOKE_SCRIPT = "imp_matlab_parity_smoke.m"
REPO_ROOT = Path(__file__).resolve().parents[2]


def matlab_research_tree_dir() -> Path:
    return REPO_ROOT / "research" / "matlab"


def matlab_smoke_script_path() -> Path:
    return matlab_research_tree_dir() / "smoke" / MATLAB_SMOKE_SCRIPT


def resolve_matlab_executable() -> Path | None:
    env = os.environ.get("MATLAB_EXECUTABLE")
    if env:
        path = Path(env)
        if path.is_file():
            return path
    found = shutil.which("matlab")
    if found:
        return Path(found)
    return None


def probe_matlab_runtime() -> dict[str, Any]:
    executable = resolve_matlab_executable()
    if executable is None:
        return {
            "status": MATLAB_RUNTIME_NOT_AVAILABLE,
            "executable": None,
            "matlab_release": "UNAVAILABLE",
        }
    try:
        completed = subprocess.run(
            [str(executable), "-batch", "fprintf('%s', version('-release'));"],
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        release = (completed.stdout or "").strip() or "UNKNOWN"
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return {
            "status": MATLAB_RUNTIME_NOT_AVAILABLE,
            "executable": str(executable),
            "matlab_release": "UNAVAILABLE",
        }
    return {
        "status": "AVAILABLE",
        "executable": str(executable),
        "matlab_release": release,
    }


def run_matlab_parity_smoke(package_dir: Path, output_dir: Path) -> dict[str, Any]:
    probe = probe_matlab_runtime()
    if probe["status"] != "AVAILABLE":
        return {"status": MATLAB_RUNTIME_NOT_AVAILABLE, "probe": probe}
    script = matlab_smoke_script_path()
    if not script.is_file():
        raise ValueError("MATLAB_SMOKE_SCRIPT_MISSING")
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / MATLAB_RESULT_FILENAME
    package_dir_arg = str(package_dir.resolve()).replace("\\", "/")
    result_path_arg = str(result_path.resolve()).replace("\\", "/")
    batch = (
        f"addpath('{script.parent.as_posix()}'); "
        f"imp_matlab_parity_smoke('{package_dir_arg}','{result_path_arg}');"
    )
    executable = Path(str(probe["executable"]))
    subprocess.run(
        [str(executable), "-batch", batch],
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if not result_path.is_file():
        raise ValueError("MATLAB_SMOKE_RESULT_MISSING")
    raw = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("MATLAB_RESULT_FILE_INVALID")
    raw.pop("content_sha256", None)
    raw["content_sha256"] = matlab_research_result_content_sha256(raw)
    validate_matlab_research_result_v1(raw)
    return {
        "status": "PASS",
        "probe": probe,
        "result_path": str(result_path),
        "result": raw,
    }


__all__ = [
    "MATLAB_RESULT_FILENAME",
    "matlab_research_tree_dir",
    "matlab_smoke_script_path",
    "probe_matlab_runtime",
    "resolve_matlab_executable",
    "run_matlab_parity_smoke",
]
