from .models import EvidenceSufficiencyReview, EvidenceSufficiencyState


def review_evidence_sufficiency(
    *, present_domains: tuple[str, ...], missing_domains: tuple[str, ...],
    phase_3a_request_constructible: bool, outcome_only_available: bool,
    identity_conflicted: bool, publication_blocked: bool,
) -> EvidenceSufficiencyReview:
    if identity_conflicted:
        state = EvidenceSufficiencyState.CONFLICTED
    elif publication_blocked:
        state = EvidenceSufficiencyState.BLOCKED
    elif phase_3a_request_constructible:
        state = EvidenceSufficiencyState.SUFFICIENT_FOR_PHASE_3A
    elif outcome_only_available:
        state = EvidenceSufficiencyState.SUFFICIENT_FOR_PHASE_3B_OUTCOME_ONLY
    elif present_domains:
        state = EvidenceSufficiencyState.SUFFICIENT_FOR_REGISTRY_ONLY
    else:
        state = EvidenceSufficiencyState.UNUSABLE
    limitations = tuple(f"missing domain: {domain}" for domain in missing_domains)
    return EvidenceSufficiencyReview(
        state=state, present_domains=present_domains, missing_domains=missing_domains,
        phase_3a_request_constructible=phase_3a_request_constructible,
        outcome_only_available=outcome_only_available, limitations=limitations,
    )


__all__ = ["review_evidence_sufficiency"]
