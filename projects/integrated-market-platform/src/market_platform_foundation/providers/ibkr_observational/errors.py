"""IBKR provider error normalization (G6).

Only error codes with an authoritative mapping (official IBKR message-codes
reference, pinned in :mod:`.constants`) are categorized. Everything else is
``UNKNOWN_PROVIDER_ERROR`` carrying only the raw safe code and message — no
secrets, no account numbers, no invented mappings.
"""

from __future__ import annotations

from .constants import (
    CONNECTION_ERROR_CODES,
    CONTRACT_ERROR_CODES,
    ENTITLEMENT_ERROR_CODES,
    INFORMATIONAL_ERROR_CODES,
    PACING_ERROR_CODES,
    SUBSCRIPTION_ERROR_CODES,
)
from .contracts import IbkrErrorCategory, IbkrProviderError


def normalize_provider_error(
    *,
    code: int | None,
    message: str,
    req_id: int | None = None,
) -> IbkrProviderError:
    """Map a provider error (code, message) to a documented category."""
    safe_code = _valid_code(code)
    safe_message = str(message or "")[:512]
    category = _category_for(safe_code, safe_message)
    return IbkrProviderError(
        code=safe_code,
        message=safe_message,
        category=category,
        req_id=_valid_req_id(req_id),
    )


def _valid_code(code: int | None) -> int | None:
    if code is None or isinstance(code, bool):
        return None
    try:
        parsed = int(code)
    except (TypeError, ValueError):
        return None
    return parsed if -2_147_483_648 <= parsed <= 2_147_483_647 else None


def _valid_req_id(req_id: int | None) -> int | None:
    if req_id is None or isinstance(req_id, bool):
        return None
    try:
        parsed = int(req_id)
    except (TypeError, ValueError):
        return None
    return parsed if 0 <= parsed <= 2_147_483_647 else None


def _category_for(code: int | None, message: str) -> IbkrErrorCategory:
    if code is None:
        return IbkrErrorCategory.UNKNOWN_PROVIDER_ERROR
    if code in ENTITLEMENT_ERROR_CODES:
        return IbkrErrorCategory.ENTITLEMENT
    if code in PACING_ERROR_CODES:
        return IbkrErrorCategory.PACING
    if code in CONTRACT_ERROR_CODES:
        return IbkrErrorCategory.CONTRACT
    if code in SUBSCRIPTION_ERROR_CODES:
        return IbkrErrorCategory.SUBSCRIPTION
    if code in CONNECTION_ERROR_CODES:
        return IbkrErrorCategory.CONNECTION
    if code in INFORMATIONAL_ERROR_CODES:
        return IbkrErrorCategory.INTERNAL_PROVIDER
    # Delayed-data errors arrive as entitlement failures with a message
    # mentioning delayed/frozen delivery; the code mapping stays explicit.
    if _mentions_delayed(message):
        return IbkrErrorCategory.DELAYED_DATA
    return IbkrErrorCategory.UNKNOWN_PROVIDER_ERROR


def _mentions_delayed(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in ("delayed", "frozen", "is not subscribed"))


__all__ = ["normalize_provider_error"]