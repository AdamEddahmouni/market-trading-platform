"""Outages are not zeros. Auth failure is not empty short interest."""

from __future__ import annotations

from .contracts import AvailabilityState


def quality_from_failure(exc: BaseException) -> tuple[str, ...]:
    text = str(exc)
    if "AUTH_UNAVAILABLE" in text or "FINRA_CREDENTIALS_MISSING" in text:
        return (AvailabilityState.AUTH_UNAVAILABLE.value,)
    if "AUTH_FAILED" in text or "FINRA_HTTP_401" in text or "FINRA_HTTP_403" in text:
        return (AvailabilityState.AUTH_FAILED.value, "SOURCE_UNAVAILABLE")
    if "IDENTITY_UNRESOLVED" in text:
        return ("IDENTITY_UNRESOLVED",)
    if "OUTSIDE_DATASET_HISTORY" in text:
        return (AvailabilityState.OUTSIDE_DATASET_HISTORY.value,)
    return ("SOURCE_UNAVAILABLE", "TEMPORARILY_UNAVAILABLE")


def empty_is_not_zero(state: str) -> bool:
    return state in {
        AvailabilityState.NO_RECORD.value,
        AvailabilityState.EMPTY_RESULT.value,
        AvailabilityState.NOT_YET_PUBLISHED.value,
        AvailabilityState.SOURCE_UNAVAILABLE.value,
        AvailabilityState.AUTH_UNAVAILABLE.value,
        AvailabilityState.AUTH_FAILED.value,
        AvailabilityState.OUTSIDE_DATASET_HISTORY.value,
        AvailabilityState.COVERAGE_UNAVAILABLE.value,
    }
