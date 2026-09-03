import re
from enum import Enum


_SENSITIVE_DETAIL = re.compile(
    r"(?i)\b(authorization|cookie|set-cookie|api[-_]?key|token|secret|password|client[-_]?secret)"
    r"\b\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"
)


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


def safe_error_detail(exc: BaseException, *, limit: int = 500) -> str:
    """Serialize an exception for evidence without retaining common credentials."""
    message = f"{type(exc).__name__}: {exc}".replace("\r", " ").replace("\n", " ")
    sanitized = _SENSITIVE_DETAIL.sub(
        lambda match: f"{match.group(1)}=[REDACTED]",
        message,
    )
    return sanitized[:limit]
