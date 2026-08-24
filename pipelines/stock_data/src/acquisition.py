from enum import Enum


class AcquisitionOutcome(str, Enum):
    COMPLETE = "complete"
    TRANSIENT = "transient"
    THROTTLED = "throttled"
    INVALID_SYMBOL = "invalid_symbol"
    NO_DATA = "no_data"
    PARTIAL_RESPONSE = "partial_response"
    SCHEMA_DRIFT = "schema_drift"


def classify_failure(
    exc: BaseException | None,
    *,
    empty: bool = False,
    partial: bool = False,
) -> AcquisitionOutcome:
    if partial:
        return AcquisitionOutcome.PARTIAL_RESPONSE
    if empty:
        return AcquisitionOutcome.NO_DATA
    if exc is None:
        return AcquisitionOutcome.COMPLETE
    message = f"{type(exc).__name__}: {exc}".lower()
    if "429" in message or "too many requests" in message or "rate limit" in message:
        return AcquisitionOutcome.THROTTLED
    if "delisted" in message or "no timezone found" in message or "invalid symbol" in message:
        return AcquisitionOutcome.INVALID_SYMBOL
    if isinstance(exc, KeyError) or "schema" in message or "column" in message:
        return AcquisitionOutcome.SCHEMA_DRIFT
    return AcquisitionOutcome.TRANSIENT
