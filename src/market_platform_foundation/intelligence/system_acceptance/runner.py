"""System acceptance runner and report builder (BUILD 25)."""

from __future__ import annotations

from typing import Any

from market_platform_foundation.git_ref import read_git_head, read_remote_ref

from .identity import derive_acceptance_report_id
from .invariants import invariant_failures, run_invariant_checks
from .scenarios import run_scenarios
from .spec import build_acceptance_spec
from .types import (
    SYSTEM_ACCEPTANCE_IMPLEMENTATION_VERSION,
    SYSTEM_ACCEPTANCE_SCHEMA_VERSION,
    AcceptanceDisposition,
    ScenarioStatus,
    SystemAcceptanceReportV1,
)


def _git_head() -> str:
    return read_git_head() or ""


def _build24_head() -> str:
    return read_remote_ref("origin", "cloud/build-24-controlled-adaptation") or _git_head()


def run_acceptance(
    *,
    source_head: str | None = None,
    candidate_head: str | None = None,
) -> SystemAcceptanceReportV1:
    source = source_head or _build24_head()
    candidate = candidate_head or _git_head()
    spec = build_acceptance_spec(source_build_head=source)

    scenario_results = run_scenarios(spec.required_adversarial_scenarios)
    invariant_results = run_invariant_checks(spec.required_invariants)

    blocking: list[str] = []
    for row in scenario_results:
        if row.status == ScenarioStatus.FAIL:
            blocking.append(f"scenario:{row.scenario_id}:{row.observed}")
    for row in invariant_failures(invariant_results):
        blocking.append(f"invariant:{row.invariant_id}:{row.evidence}")

    nonblocking = list(spec.allowed_known_limitations)
    if any(row.status == ScenarioStatus.SKIP for row in scenario_results):
        nonblocking.append("KL-003")

    if blocking:
        disposition = AcceptanceDisposition.REJECTED
    elif nonblocking:
        disposition = AcceptanceDisposition.ACCEPTED_WITH_LIMITATIONS
    else:
        disposition = AcceptanceDisposition.ACCEPTED

    report_id = derive_acceptance_report_id(
        acceptance_spec_id=spec.acceptance_spec_id,
        source_head=source,
        candidate_head=candidate,
        fixture_identities=("golden-lifecycle-v1", "adversarial-fixtures-v1"),
        implementation_version=SYSTEM_ACCEPTANCE_IMPLEMENTATION_VERSION,
    )

    return SystemAcceptanceReportV1(
        acceptance_report_id=report_id,
        schema_version=SYSTEM_ACCEPTANCE_SCHEMA_VERSION,
        acceptance_spec_ref=spec.acceptance_spec_id,
        source_head=source,
        candidate_head=candidate,
        scenario_results=scenario_results,
        invariant_results=invariant_results,
        test_suite_results={},
        determinism_results={
            "golden_lifecycle_twice": next(
                (r.status.value for r in scenario_results if r.scenario_id == "A25"),
                "NOT_RUN",
            ),
        },
        replay_parity_results={},
        persistence_results={
            "same_id_conflict": next(
                (r.status.value for r in scenario_results if r.scenario_id == "A45"),
                "NOT_RUN",
            ),
        },
        security_results={
            "no_live_execution": next(
                (r.status.value for r in scenario_results if r.scenario_id == "A16"),
                "NOT_RUN",
            ),
        },
        blocking_failures=tuple(blocking),
        nonblocking_limitations=tuple(nonblocking),
        overall_disposition=disposition,
        implementation_version=SYSTEM_ACCEPTANCE_IMPLEMENTATION_VERSION,
        metadata={"spec_id": spec.acceptance_spec_id},
    )
