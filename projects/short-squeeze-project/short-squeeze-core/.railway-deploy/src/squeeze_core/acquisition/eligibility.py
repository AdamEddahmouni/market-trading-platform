from .models import (
    AcquisitionPlanStatus, EligibilityContext, EligibilityDecision, ExclusionCode,
    IdentityState,
)


def decide_eligibility(context: EligibilityContext) -> EligibilityDecision:
    exclusions: list[ExclusionCode] = []
    satisfied: list[str] = []
    missing: list[str] = []

    checks = (
        (context.within_date_range, "WITHIN_DATE_RANGE", ExclusionCode.OUTSIDE_PREREGISTERED_DATE_RANGE),
        (context.within_population, "WITHIN_POPULATION", ExclusionCode.OUTSIDE_PREREGISTERED_POPULATION),
        (context.discovery_provenance_available, "DISCOVERY_PROVENANCE", ExclusionCode.DISCOVERY_PROVENANCE_MISSING),
        (context.artifact_validation_passed, "ARTIFACTS_VALID", ExclusionCode.SOURCE_ARTIFACT_HASH_MISMATCH),
        (context.deterministic_boundary_available, "BOUNDARY_AVAILABLE", ExclusionCode.DETECTION_BOUNDARY_UNRESOLVED),
        (context.objective_market_evidence_available, "MARKET_EVIDENCE", ExclusionCode.MARKET_DATA_UNAVAILABLE),
        (context.phase_3a_request_constructible, "PHASE_3A_REQUEST_CONSTRUCTIBLE", ExclusionCode.CASE_REQUIRES_FABRICATED_EVIDENCE),
    )
    for passed, label, code in checks:
        (satisfied if passed else missing).append(label)
        if not passed:
            exclusions.append(code)
    if context.acquisition_plan_status not in {
        AcquisitionPlanStatus.PREREGISTERED, AcquisitionPlanStatus.ACTIVE,
    }:
        exclusions.append(ExclusionCode.ACQUISITION_PLAN_NOT_PREREGISTERED)
    if context.identity_resolution.state is IdentityState.UNRESOLVED:
        exclusions.append(ExclusionCode.IDENTITY_UNRESOLVED)
    elif context.identity_resolution.state is IdentityState.CONFLICTED:
        exclusions.append(ExclusionCode.IDENTITY_CONFLICT)
    if context.duplicate_symbol:
        exclusions.append(ExclusionCode.DUPLICATE_SYMBOL)
    if context.duplicate_discovery:
        exclusions.append(ExclusionCode.DUPLICATE_DISCOVERY)
    if context.synthetic:
        exclusions.append(ExclusionCode.CASE_REQUIRES_FABRICATED_EVIDENCE)
    return EligibilityDecision(
        included=not exclusions,
        context=context,
        satisfied_conditions=tuple(satisfied),
        missing_conditions=tuple(missing),
        exclusion_codes=tuple(exclusions),
    )


__all__ = ["decide_eligibility"]
