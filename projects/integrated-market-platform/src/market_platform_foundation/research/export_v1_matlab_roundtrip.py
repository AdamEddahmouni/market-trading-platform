"""Governed Research Export v1 ↔ MATLAB round-trip orchestration (research-only)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..canonical import write_canonical_json
from .export_v1 import (
    PROFILE_MARKET_TECHNICAL,
    ResearchExportV1Package,
    build_research_export_v1,
    load_research_export_v1_package,
    write_research_export_v1_package,
)
from .export_v1_matlab_result import (
    CONTRACT_READY,
    MATLAB_GOVERNED_RESEARCH_ROUNDTRIP_READY,
    MATLAB_RUNTIME_NOT_AVAILABLE,
    build_parity_matlab_research_result,
    matlab_research_result_content_sha256,
    project_matlab_research_evidence_artifact,
    roundtrip_readiness,
    validate_matlab_research_result_v1,
    verify_matlab_result_export_lineage,
)
from .matlab_environment import validate_toolbox_manifest

MATLAB_RESULT_FILENAME = "matlab_research_result_v1.json"
MATLAB_SMOKE_SCRIPT = "imp_matlab_parity_smoke.m"


def matlab_research_tree_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "research" / "matlab"


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


def load_matlab_research_result_v1(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MATLAB_RESULT_FILE_INVALID")
    validate_matlab_research_result_v1(payload)
    return payload


def write_matlab_research_result_v1(path: Path, payload: dict[str, Any]) -> Path:
    validate_matlab_research_result_v1(payload)
    write_canonical_json(path, payload)
    return path


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
    script_arg = str(script.resolve()).replace("\\", "/")
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
    result = raw
    return {
        "status": "PASS",
        "probe": probe,
        "result_path": str(result_path),
        "result": result,
    }


@dataclass(frozen=True, slots=True)
class GovernedMatlabRoundtripReport:
    readiness: str
    matlab_runtime_available: bool
    lineage_verified: bool
    export_id: str
    manifest_hash: str
    result_content_sha256: str
    evidence_artifact_content_sha256: str
    analysis_source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "readiness": self.readiness,
            "matlab_runtime_available": self.matlab_runtime_available,
            "lineage_verified": self.lineage_verified,
            "export_id": self.export_id,
            "manifest_hash": self.manifest_hash,
            "result_content_sha256": self.result_content_sha256,
            "evidence_artifact_content_sha256": self.evidence_artifact_content_sha256,
            "analysis_source": self.analysis_source,
        }


def execute_governed_roundtrip(
    package: ResearchExportV1Package,
    *,
    work_dir: Path,
    prefer_matlab: bool = True,
    toolbox_manifest: dict[str, Any] | None = None,
) -> GovernedMatlabRoundtripReport:
    if toolbox_manifest is not None:
        validate_toolbox_manifest(toolbox_manifest)

    package_dir = work_dir / "export_package"
    write_research_export_v1_package(package_dir, package)
    loaded = load_research_export_v1_package(package_dir)

    probe = probe_matlab_runtime()
    matlab_available = probe["status"] == "AVAILABLE"
    analysis_source = "python_reference"
    result: dict[str, Any]

    if prefer_matlab and matlab_available:
        smoke = run_matlab_parity_smoke(package_dir, work_dir / "matlab_out")
        if smoke.get("status") == "PASS":
            result = smoke["result"]
            analysis_source = "matlab_smoke"
        else:
            result = build_parity_matlab_research_result(
                loaded,
                analysis_source="python_reference",
                code_identity="export_v1_matlab_roundtrip/python_fallback",
            )
    else:
        result = build_parity_matlab_research_result(
            loaded,
            analysis_source="python_reference",
            code_identity="export_v1_matlab_roundtrip/python_reference",
            matlab_release=str(probe.get("matlab_release") or "UNAVAILABLE"),
        )

    verify_matlab_result_export_lineage(result, loaded)
    evidence = project_matlab_research_evidence_artifact(result)
    write_matlab_research_result_v1(work_dir / MATLAB_RESULT_FILENAME, result)
    write_canonical_json(work_dir / "matlab_research_evidence_artifact.json", evidence)

    lineage_verified = True
    readiness = roundtrip_readiness(
        matlab_runtime_available=matlab_available and analysis_source == "matlab_smoke",
        lineage_verified=lineage_verified,
    )
    if matlab_available and analysis_source == "matlab_smoke":
        readiness = MATLAB_GOVERNED_RESEARCH_ROUNDTRIP_READY
    elif lineage_verified:
        readiness = CONTRACT_READY

    lineage = loaded.manifest
    return GovernedMatlabRoundtripReport(
        readiness=readiness,
        matlab_runtime_available=matlab_available,
        lineage_verified=lineage_verified,
        export_id=str(lineage.get("export_id") or ""),
        manifest_hash=str(lineage.get("manifest_hash") or ""),
        result_content_sha256=str(result.get("content_sha256") or ""),
        evidence_artifact_content_sha256=str(evidence.get("content_sha256") or ""),
        analysis_source=analysis_source,
    )


def build_fixture_roundtrip_package() -> ResearchExportV1Package:
    return build_research_export_v1(profile=PROFILE_MARKET_TECHNICAL)


__all__ = [
    "GovernedMatlabRoundtripReport",
    "MATLAB_RESULT_FILENAME",
    "build_fixture_roundtrip_package",
    "execute_governed_roundtrip",
    "load_matlab_research_result_v1",
    "matlab_research_tree_dir",
    "matlab_smoke_script_path",
    "probe_matlab_runtime",
    "resolve_matlab_executable",
    "run_matlab_parity_smoke",
    "write_matlab_research_result_v1",
]
