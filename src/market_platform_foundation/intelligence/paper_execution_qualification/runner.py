"""Paper execution qualification orchestration runner (BUILD 27)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from market_platform_foundation.git_ref import read_git_head, read_remote_ref
from market_platform_foundation.intelligence.forward_qualification import BUILD25_RC_BRANCH, verify_build25_rc_integrity

from .build26_integrity import verify_build26_integrity
from .fixture_lifecycle import run_prospective_paper_fixture_lifecycle
from .scenarios import REQUIRED_SCENARIOS, ScenarioStatus, run_scenarios
from .spec import BUILD26_BRANCH, build_paper_execution_qualification_spec
from .types import ExecutionIntegrityStatus, PaperQualificationDisposition


@dataclass(frozen=True)
class PaperExecutionQualificationRunResult:
    build26_integrity_status: str
    build25_rc_integrity_status: str
    scenario_failures: tuple[str, ...]
    fixture_lifecycle_ok: bool
    disposition: PaperQualificationDisposition
    metadata: dict[str, Any]


def _build26_head() -> str:
    return read_remote_ref("origin", BUILD26_BRANCH) or read_git_head() or ""


def _build25_head() -> str:
    return read_remote_ref("origin", BUILD25_RC_BRANCH) or read_git_head() or ""


def run_paper_execution_qualification(
    *,
    source_build26_ref: str | None = None,
    source_release_candidate_ref: str | None = None,
    source_head: str | None = None,
    qualification_start_ns: int = 1_700_000_000_000_000_000,
) -> PaperExecutionQualificationRunResult:
    build26_ref = source_build26_ref or _build26_head()
    rc_ref = source_release_candidate_ref or _build25_head()
    head = source_head or read_git_head() or ""

    build26_result = verify_build26_integrity(expected_head=build26_ref)
    rc_result = verify_build25_rc_integrity(expected_head=rc_ref)

    scenario_results = run_scenarios(REQUIRED_SCENARIOS)
    scenario_failures = tuple(
        f"{row.scenario_id}:{row.observed}"
        for row in scenario_results
        if row.status == ScenarioStatus.FAIL
    )

    fixture = run_prospective_paper_fixture_lifecycle(
        source_build26_ref=build26_ref,
        source_release_candidate_ref=rc_ref,
        source_head=head,
        qualification_start_ns=qualification_start_ns,
    )
    fixture_ok = (
        fixture.integrity_status == ExecutionIntegrityStatus.VALID
        and fixture.forward_receipt_ref is not None
    )

    if build26_result.status != "PASS" or rc_result.status != "PASS":
        disposition = PaperQualificationDisposition.INVALID_EXECUTION_INTEGRITY
    elif scenario_failures:
        disposition = PaperQualificationDisposition.INVALID_EXECUTION_INTEGRITY
    elif not fixture_ok:
        disposition = PaperQualificationDisposition.INVALID_EXECUTION_INTEGRITY
    elif fixture.fill_id and fixture.opportunity_id:
        disposition = PaperQualificationDisposition.PAPER_EXECUTION_QUALIFIED_WITH_LIMITATIONS
    else:
        disposition = PaperQualificationDisposition.INSUFFICIENT_PAPER_EXECUTION_EVIDENCE

    spec = build_paper_execution_qualification_spec(
        source_build26_ref=build26_ref,
        source_release_candidate_ref=rc_ref,
        source_head=head,
        qualification_start_ns=qualification_start_ns,
    )

    return PaperExecutionQualificationRunResult(
        build26_integrity_status=build26_result.status,
        build25_rc_integrity_status=rc_result.status,
        scenario_failures=scenario_failures,
        fixture_lifecycle_ok=fixture_ok,
        disposition=disposition,
        metadata={
            "source_build26_ref": build26_ref,
            "source_release_candidate_ref": rc_ref,
            "source_head": head,
            "fixture_report_id": fixture.report_id,
            "spec_id": spec.qualification_spec_id,
            "fixture_disposition": fixture.metadata.get("disposition"),
        },
    )
