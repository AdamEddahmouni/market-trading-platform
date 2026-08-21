"""Live observation is not an admitted research dataset."""

from __future__ import annotations

from enum import StrEnum


class ObservationLifecycle(StrEnum):
    OBSERVED = "OBSERVED"
    CAPTURED = "CAPTURED"
    VALIDATED = "VALIDATED"
    QUALITY_CHARACTERIZED = "QUALITY_CHARACTERIZED"
    ADMITTED = "ADMITTED"


_ALLOWED = {
    ObservationLifecycle.OBSERVED: (ObservationLifecycle.CAPTURED,),
    ObservationLifecycle.CAPTURED: (ObservationLifecycle.VALIDATED,),
    ObservationLifecycle.VALIDATED: (ObservationLifecycle.QUALITY_CHARACTERIZED,),
    ObservationLifecycle.QUALITY_CHARACTERIZED: (ObservationLifecycle.ADMITTED,),
    ObservationLifecycle.ADMITTED: (),
}


def next_lifecycle_state(
    current: ObservationLifecycle,
    nxt: ObservationLifecycle,
    *,
    admission_authorized: bool = False,
) -> ObservationLifecycle:
    if nxt not in _ALLOWED[current]:
        raise ValueError(f"INVALID_LIFECYCLE_TRANSITION:{current.value}->{nxt.value}")
    if nxt == ObservationLifecycle.ADMITTED and not admission_authorized:
        raise ValueError("ADMISSION_REQUIRES_SEPARATE_ADR")
    return nxt
