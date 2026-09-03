"""Forward qualification run manifest builder (BUILD 26)."""

from __future__ import annotations

from dataclasses import replace

from .identity import derive_qualification_run_id
from .provider_capabilities import probe_all_provider_capabilities
from .types import (
    FORWARD_QUALIFICATION_IMPLEMENTATION_VERSION,
    FORWARD_QUALIFICATION_SCHEMA_VERSION,
    ForwardQualificationRunV1,
    ForwardQualificationSpecV1,
    ProviderCapabilityEntryV1,
)


def build_forward_qualification_run(
    *,
    spec: ForwardQualificationSpecV1,
    source_head: str,
    run_start_ns: int,
    run_end_ns: int | None = None,
    data_mode: str = "LIVE_OBSERVATIONAL",
    execution_mode: str = "NONE",
    execution_authority: str = "BLOCKED",
    runtime_activation_ref: str | None = None,
    champion_assignment_ref: str | None = None,
    provider_snapshot: tuple[ProviderCapabilityEntryV1, ...] | None = None,
    policy_stack_refs: tuple[str, ...] = (),
) -> ForwardQualificationRunV1:
    if execution_mode != "NONE":
        raise ValueError("BUILD_26_REQUIRES_EXECUTION_MODE_NONE")
    if execution_authority not in {"BLOCKED", "NONE"}:
        raise ValueError("BUILD_26_REQUIRES_EXECUTION_AUTHORITY_BLOCKED")

    snapshot = provider_snapshot or probe_all_provider_capabilities()
    run = ForwardQualificationRunV1(
        qualification_run_id="pending",
        schema_version=FORWARD_QUALIFICATION_SCHEMA_VERSION,
        qualification_spec_ref=spec.qualification_spec_id,
        release_candidate_ref=spec.release_candidate_ref,
        source_head=source_head,
        runtime_activation_ref=runtime_activation_ref,
        champion_assignment_ref=champion_assignment_ref,
        provider_capability_snapshot=snapshot,
        instrument_universe=spec.instrument_universe,
        run_start_ns=run_start_ns,
        run_end_ns=run_end_ns,
        data_mode=data_mode,
        execution_mode=execution_mode,
        execution_authority=execution_authority,
        policy_stack_refs=policy_stack_refs,
        implementation_version=FORWARD_QUALIFICATION_IMPLEMENTATION_VERSION,
        lineage={
            "qualification_spec_id": spec.qualification_spec_id,
            "release_candidate_ref": spec.release_candidate_ref,
        },
        metadata={"qualification_kind": spec.qualification_kind.value},
    )
    return replace(run, qualification_run_id=derive_qualification_run_id(run))
