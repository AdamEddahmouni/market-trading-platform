"""Governed Research Export v1 round-trip finalize (foundation — no subprocess)."""

from __future__ import annotations

import json
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
    build_parity_matlab_research_result,
    project_matlab_research_evidence_artifact,
    roundtrip_readiness,
    validate_matlab_research_result_v1,
    verify_matlab_result_export_lineage,
)
from .matlab_environment import validate_toolbox_manifest

MATLAB_RESULT_FILENAME = "matlab_research_result_v1.json"


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
    matlab_smoke_result: dict[str, Any] | None = None,
    matlab_runtime_available: bool = False,
    toolbox_manifest: dict[str, Any] | None = None,
) -> GovernedMatlabRoundtripReport:
    """Verify lineage and write evidence artifacts. MATLAB spawn lives under tools/research/."""
    if toolbox_manifest is not None:
        validate_toolbox_manifest(toolbox_manifest)

    package_dir = work_dir / "export_package"
    write_research_export_v1_package(package_dir, package)
    loaded = load_research_export_v1_package(package_dir)

    analysis_source = "python_reference"
    if matlab_smoke_result is not None:
        result = matlab_smoke_result
        analysis_source = "matlab_smoke"
    else:
        result = build_parity_matlab_research_result(
            loaded,
            analysis_source="python_reference",
            code_identity="export_v1_matlab_roundtrip/python_reference",
            matlab_release="UNAVAILABLE",
        )

    verify_matlab_result_export_lineage(result, loaded)
    evidence = project_matlab_research_evidence_artifact(result)
    write_matlab_research_result_v1(work_dir / MATLAB_RESULT_FILENAME, result)
    write_canonical_json(work_dir / "matlab_research_evidence_artifact.json", evidence)

    lineage_verified = True
    smoke_used = matlab_smoke_result is not None and matlab_runtime_available
    readiness = roundtrip_readiness(
        matlab_runtime_available=smoke_used,
        lineage_verified=lineage_verified,
    )
    if smoke_used:
        readiness = MATLAB_GOVERNED_RESEARCH_ROUNDTRIP_READY
    elif lineage_verified:
        readiness = CONTRACT_READY

    lineage = loaded.manifest
    return GovernedMatlabRoundtripReport(
        readiness=readiness,
        matlab_runtime_available=matlab_runtime_available and matlab_smoke_result is not None,
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
    "write_matlab_research_result_v1",
]
