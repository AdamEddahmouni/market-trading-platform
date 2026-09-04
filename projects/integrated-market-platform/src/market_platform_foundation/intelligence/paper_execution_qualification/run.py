"""Paper execution qualification run manifest builder (BUILD 27)."""

from __future__ import annotations

from dataclasses import replace

from market_platform_foundation.intelligence.forward_qualification.provider_capabilities import probe_all_provider_capabilities

from .identity import derive_qualification_run_id
from .types import (
    PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION,
    PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION,
    PaperExecutionQualificationRunV1,
    PaperExecutionQualificationSpecV1,
)


def build_paper_execution_qualification_run(
    *,
    spec: PaperExecutionQualificationSpecV1,
    source_head: str,
    run_start_ns: int,
    run_end_ns: int | None = None,
    data_mode: str = "FIXTURE_REPLAY",
    execution_mode: str = "PAPER",
    execution_authority: str = "PAPER_ONLY",
    forward_qualification_run_ref: str | None = None,
    runtime_activation_ref: str | None = None,
    champion_assignment_ref: str | None = None,
    provider_snapshot: tuple[object, ...] | None = None,
) -> PaperExecutionQualificationRunV1:
    if execution_mode != "PAPER":
        raise ValueError("BUILD_27_REQUIRES_EXECUTION_MODE_PAPER")
    if execution_authority not in {"PAPER_ONLY", "AUTHORIZED"}:
        raise ValueError("BUILD_27_REQUIRES_PAPER_EXECUTION_AUTHORITY")

    snapshot = provider_snapshot or probe_all_provider_capabilities()
    run = PaperExecutionQualificationRunV1(
        qualification_run_id="pending",
        schema_version=PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION,
        qualification_spec_ref=spec.qualification_spec_id,
        source_build26_ref=spec.source_build26_ref,
        source_release_candidate_ref=spec.source_release_candidate_ref,
        source_head=source_head,
        forward_qualification_run_ref=forward_qualification_run_ref,
        runtime_activation_ref=runtime_activation_ref,
        champion_assignment_ref=champion_assignment_ref,
        opportunity_policy_ref=spec.opportunity_policy_ref,
        execution_policy_ref=spec.execution_policy_ref,
        fill_policy_ref=spec.fill_policy_ref,
        initial_portfolio_state_ref=spec.initial_portfolio_state_ref,
        provider_capability_snapshot=snapshot,
        instrument_universe=spec.instrument_universe,
        run_start_ns=run_start_ns,
        run_end_ns=run_end_ns,
        data_mode=data_mode,
        execution_mode=execution_mode,
        execution_authority=execution_authority,
        implementation_version=PAPER_EXECUTION_QUALIFICATION_IMPLEMENTATION_VERSION,
        lineage={
            "qualification_spec_id": spec.qualification_spec_id,
            "source_build26_ref": spec.source_build26_ref,
            "source_release_candidate_ref": spec.source_release_candidate_ref,
        },
        metadata={"qualification_kind": spec.qualification_kind.value},
    )
    return replace(run, qualification_run_id=derive_qualification_run_id(run))
