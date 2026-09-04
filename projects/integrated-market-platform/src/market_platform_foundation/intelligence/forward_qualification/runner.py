"""Forward qualification orchestration runner (BUILD 26)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from market_platform_foundation.git_ref import read_git_head, read_remote_ref, repo_root

from .fixture_lifecycle import run_prospective_fixture_lifecycle
from .provider_capabilities import provider_capability_matrix
from .rc_integrity import verify_build25_rc_integrity
from .scenarios import REQUIRED_SCENARIOS, ScenarioStatus, run_scenarios
from .spec import BUILD25_RC_BRANCH, build_forward_qualification_spec
from .types import ForwardIntegrityStatus, QualificationDisposition


@dataclass(frozen=True)
class ForwardQualificationRunResult:
    rc_integrity_status: str
    scenario_failures: tuple[str, ...]
    fixture_lifecycle_ok: bool
    provider_matrix: dict[str, Any]
    disposition: QualificationDisposition
    metadata: dict[str, Any]


def _build25_head() -> str:
    return read_remote_ref("origin", BUILD25_RC_BRANCH) or read_git_head() or ""


def _load_build25_manifest() -> dict[str, Any]:
    root = repo_root()
    return json.loads((root / "artifacts/system-acceptance/BUILD25_RC_MANIFEST.json").read_text(encoding="utf-8"))


def run_forward_qualification(
    *,
    release_candidate_ref: str | None = None,
    source_head: str | None = None,
    qualification_start_ns: int = 1_700_000_000_000_000_000,
) -> ForwardQualificationRunResult:
    rc_ref = release_candidate_ref or _build25_head()
    head = source_head or read_git_head() or ""
    rc_result = verify_build25_rc_integrity(expected_head=rc_ref)

    scenario_results = run_scenarios(REQUIRED_SCENARIOS)
    scenario_failures = tuple(
        f"{row.scenario_id}:{row.observed}"
        for row in scenario_results
        if row.status == ScenarioStatus.FAIL
    )

    fixture = run_prospective_fixture_lifecycle(
        release_candidate_ref=rc_ref,
        source_head=head,
        qualification_start_ns=qualification_start_ns,
    )
    fixture_ok = (
        fixture.pending_before_horizon
        and fixture.settled_after_horizon
        and fixture.integrity_status == ForwardIntegrityStatus.VALID
    )

    manifest = _load_build25_manifest()
    acceptance = manifest.get("acceptance_disposition", "UNKNOWN")
    if acceptance == "REJECTED":
        disposition = QualificationDisposition.INVALID_RUNTIME_INTEGRITY
    elif rc_result.status != "PASS":
        disposition = QualificationDisposition.INVALID_RUNTIME_INTEGRITY
    elif scenario_failures:
        disposition = QualificationDisposition.INVALID_FORWARD_INTEGRITY
    elif not fixture_ok:
        disposition = QualificationDisposition.INVALID_FORWARD_INTEGRITY
    else:
        disposition = QualificationDisposition.INSUFFICIENT_FORWARD_EVIDENCE

    return ForwardQualificationRunResult(
        rc_integrity_status=rc_result.status,
        scenario_failures=scenario_failures,
        fixture_lifecycle_ok=fixture_ok,
        provider_matrix=provider_capability_matrix(),
        disposition=disposition,
        metadata={
            "release_candidate_ref": rc_ref,
            "source_head": head,
            "acceptance_disposition": acceptance,
            "fixture_report_id": fixture.report_id,
            "spec_id": build_forward_qualification_spec(
                release_candidate_ref=rc_ref,
                source_head=head,
                qualification_start_ns=qualification_start_ns,
            ).qualification_spec_id,
        },
    )
