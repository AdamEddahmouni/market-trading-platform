from datetime import UTC, date, datetime

from squeeze_core.acquisition.models import AcquisitionPlan, AcquisitionPlanStatus


def sample_plan(**changes) -> AcquisitionPlan:
    values = {
        "acquisition_plan_id": "phase-3d-pilot",
        "plan_version": "phase_3d_pilot.v1",
        "created_from_policy_version": "phase_3d_acquisition_plan_policy.v1",
        "research_question": "Can source-defined cases be reconstructed point in time?",
        "target_population": "US listed common stocks in explicit source manifests",
        "date_range": (date(2024, 1, 1), date(2024, 12, 31)),
        "market_session_scope": ("PRE", "REGULAR", "POST"),
        "symbol_universe_definition": "Explicit source-manifest symbols",
        "discovery_source_definitions": ("PUBLIC_MARKET_EVENT_FEED:pilot",),
        "maximum_case_count": 20,
        "minimum_case_count": 0,
        "sampling_method": "SOURCE_ORDER_THEN_IDENTITY_DEDUPLICATION",
        "deduplication_policy": "phase_3d_unique_security_deduplication_policy.v1",
        "boundary_policy": "phase_3d_detection_boundary_policy.v1",
        "inclusion_policy_version": "phase_3d_historical_inclusion_policy.v1",
        "exclusion_policy_version": "phase_3d_historical_exclusion_policy.v1",
        "provider_priority_policy_version": "phase_3d_provider_priority_policy.v1",
        "artifact_requirements": ("DISCOVERY", "MARKET"),
        "allowed_substitutions": (),
        "forbidden_substitutions": ("CURRENT_FOR_HISTORICAL",),
        "outcome_blinding_state": "OUTCOME_BLINDED",
        "plan_status": AcquisitionPlanStatus.PREREGISTERED,
        "informational_created_at": datetime(2026, 7, 22, tzinfo=UTC),
    }
    values.update(changes)
    return AcquisitionPlan(**values)
