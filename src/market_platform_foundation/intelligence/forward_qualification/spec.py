"""Forward qualification spec builder (BUILD 26)."""

from __future__ import annotations

from market_platform_foundation.intelligence.system_acceptance import contract_inventory_hash

from .identity import derive_qualification_spec_id
from .types import (
    DEFAULT_HORIZON_NS,
    DEFAULT_INSTRUMENT_UNIVERSE,
    DEFAULT_MINIMUM_DURATION_NS,
    DEFAULT_MINIMUM_LABELABLE_COUNT,
    DEFAULT_MINIMUM_PREDICTION_COUNT,
    DEFAULT_TARGET_KIND,
    FORWARD_QUALIFICATION_IMPLEMENTATION_VERSION,
    FORWARD_QUALIFICATION_SCHEMA_VERSION,
    ForwardQualificationSpecV1,
    QualificationKind,
)

BUILD25_RC_BRANCH = "build-25-system-acceptance-freeze"
DEFAULT_ALLOWED_PROVIDERS: tuple[str, ...] = ("MOOMOO",)
DEFAULT_CONTROL_SET: tuple[str, ...] = ("ALWAYS_UP", "PRIOR")
DEFAULT_REQUIRED_QUALITY_STATES: tuple[str, ...] = ("GOOD", "DEGRADED")


def build_forward_qualification_spec(
    *,
    release_candidate_ref: str,
    source_head: str,
    qualification_start_ns: int,
    qualification_end_ns: int | None = None,
    allowed_providers: tuple[str, ...] = DEFAULT_ALLOWED_PROVIDERS,
    instrument_universe: tuple[str, ...] = DEFAULT_INSTRUMENT_UNIVERSE,
    target_kind: str = DEFAULT_TARGET_KIND,
    horizon_ns: int = DEFAULT_HORIZON_NS,
    minimum_prediction_count: int = DEFAULT_MINIMUM_PREDICTION_COUNT,
    minimum_labelable_count: int = DEFAULT_MINIMUM_LABELABLE_COUNT,
    minimum_duration_ns: int = DEFAULT_MINIMUM_DURATION_NS,
) -> ForwardQualificationSpecV1:
    spec = ForwardQualificationSpecV1(
        qualification_spec_id="pending",
        schema_version=FORWARD_QUALIFICATION_SCHEMA_VERSION,
        release_candidate_ref=release_candidate_ref,
        source_head=source_head,
        contract_inventory_hash=contract_inventory_hash(),
        qualification_kind=QualificationKind.FORWARD_SHADOW,
        allowed_providers=allowed_providers,
        instrument_universe=instrument_universe,
        target_kind=target_kind,
        horizon_ns=horizon_ns,
        champion_scope="QUALIFICATION_SHADOW",
        qualification_start_ns=qualification_start_ns,
        qualification_end_ns=qualification_end_ns,
        minimum_prediction_count=minimum_prediction_count,
        minimum_labelable_count=minimum_labelable_count,
        minimum_duration_ns=minimum_duration_ns,
        required_quality_states=DEFAULT_REQUIRED_QUALITY_STATES,
        control_set=DEFAULT_CONTROL_SET,
        execution_mode_requirement="NONE",
        execution_authority_requirement="BLOCKED",
        implementation_version=FORWARD_QUALIFICATION_IMPLEMENTATION_VERSION,
        metadata={"build": "BUILD_26_FORWARD_SHADOW_QUALIFICATION"},
    )
    spec_id = derive_qualification_spec_id(spec)
    return ForwardQualificationSpecV1(
        qualification_spec_id=spec_id,
        schema_version=spec.schema_version,
        release_candidate_ref=spec.release_candidate_ref,
        source_head=spec.source_head,
        contract_inventory_hash=spec.contract_inventory_hash,
        qualification_kind=spec.qualification_kind,
        allowed_providers=spec.allowed_providers,
        instrument_universe=spec.instrument_universe,
        target_kind=spec.target_kind,
        horizon_ns=spec.horizon_ns,
        champion_scope=spec.champion_scope,
        qualification_start_ns=spec.qualification_start_ns,
        qualification_end_ns=spec.qualification_end_ns,
        minimum_prediction_count=spec.minimum_prediction_count,
        minimum_labelable_count=spec.minimum_labelable_count,
        minimum_duration_ns=spec.minimum_duration_ns,
        required_quality_states=spec.required_quality_states,
        control_set=spec.control_set,
        execution_mode_requirement=spec.execution_mode_requirement,
        execution_authority_requirement=spec.execution_authority_requirement,
        implementation_version=spec.implementation_version,
        metadata=spec.metadata,
    )
