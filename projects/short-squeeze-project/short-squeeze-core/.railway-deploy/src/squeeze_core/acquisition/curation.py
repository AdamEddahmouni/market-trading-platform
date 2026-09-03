from .models import AcquisitionLedger, CaseAttempt, CuratedCaseBundle, CurationStatus


_ORDERED_LIFECYCLE = (
    CurationStatus.DISCOVERED, CurationStatus.ARTIFACTS_CAPTURED, CurationStatus.NORMALIZED,
    CurationStatus.IDENTITY_REVIEWED, CurationStatus.ELIGIBILITY_REVIEWED,
    CurationStatus.BOUNDARY_FROZEN, CurationStatus.EVALUATION_FROZEN,
    CurationStatus.OUTCOME_CAPTURED, CurationStatus.RESEARCH_EVALUATED,
    CurationStatus.REVIEWED, CurationStatus.PUBLISHED,
)
_TERMINAL_REVIEW_STATES = {
    CurationStatus.PARTIAL, CurationStatus.BLOCKED, CurationStatus.EXCLUDED,
    CurationStatus.REJECTED, CurationStatus.SUPERSEDED,
}


def transition_bundle(bundle: CuratedCaseBundle, target: CurationStatus) -> CuratedCaseBundle:
    current = bundle.curation_status
    allowed = set(_TERMINAL_REVIEW_STATES)
    if current in _ORDERED_LIFECYCLE:
        index = _ORDERED_LIFECYCLE.index(current)
        if index + 1 < len(_ORDERED_LIFECYCLE):
            allowed.add(_ORDERED_LIFECYCLE[index + 1])
    if target not in allowed:
        raise ValueError(f"invalid curation transition: {current} -> {target}")
    values = bundle.model_dump(mode="python", exclude={"deterministic_id"})
    values["curation_status"] = target
    return CuratedCaseBundle(**values)


def append_attempt(ledger: AcquisitionLedger, attempt: CaseAttempt) -> AcquisitionLedger:
    existing = {item.case_attempt_id: item for item in ledger.attempts}
    if attempt.case_attempt_id in existing:
        if existing[attempt.case_attempt_id] == attempt:
            return ledger
        raise ValueError(f"case attempt ID conflict: {attempt.case_attempt_id}")
    return AcquisitionLedger(
        ledger_id=ledger.ledger_id, attempts=ledger.attempts + (attempt,)
    )


__all__ = ["append_attempt", "transition_bundle"]
