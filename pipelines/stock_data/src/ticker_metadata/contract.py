from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass

from src.acquisition import AcquisitionOutcome
from src.ticker_metadata.models import ClassifiedResult


REQUEST_CONTRACT_VERSION = "ticker-metadata-v1"
ALLOWLIST = (
    "symbol",
    "shortName",
    "longName",
    "exchange",
    "fullExchangeName",
    "quoteType",
    "currency",
    "sector",
    "industry",
    "country",
    "marketCap",
)


@dataclass(frozen=True)
class _FieldSpec:
    column: str
    maximum_length: int | None


_FIELDS = {
    "symbol": _FieldSpec("provider_symbol", 64),
    "shortName": _FieldSpec("short_name", 512),
    "longName": _FieldSpec("long_name", 512),
    "exchange": _FieldSpec("exchange_code", 128),
    "fullExchangeName": _FieldSpec("exchange_name", 128),
    "quoteType": _FieldSpec("quote_type", 64),
    "currency": _FieldSpec("currency", 64),
    "sector": _FieldSpec("sector", 256),
    "industry": _FieldSpec("industry", 256),
    "country": _FieldSpec("country", 256),
    "marketCap": _FieldSpec("market_cap", None),
}
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f-\x9f]")

_CONTRACT = {
    "version": REQUEST_CONTRACT_VERSION,
    "adapter_schema_version": "1",
    "provider": "yfinance",
    "method": "get_info",
    "allowlisted_provider_keys": list(ALLOWLIST),
    "validators": {
        key: (
            {"type": "integer", "minimum": 0, "boolean_allowed": False, "nullable": True}
            if key == "marketCap"
            else {
                "type": "string",
                "trim": True,
                "unicode": True,
                "control_characters": "reject",
                "minimum_length": 1,
                "maximum_length": _FIELDS[key].maximum_length,
                "nullable": True,
            }
        )
        for key in ALLOWLIST
    },
    "symbol_normalization": {
        "version": "1",
        "operations": ["trim", "uppercase", "period_to_hyphen"],
    },
    "identity_envelope": {
        "version": "1",
        "required": ["provider_symbol", "quote_type"],
        "at_least_one_name": ["short_name", "long_name"],
        "at_least_one_exchange": ["exchange_code", "exchange_name"],
    },
    "outcome_classification_version": "1",
}
REQUEST_CONTRACT_JSON = json.dumps(
    _CONTRACT,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
)
REQUEST_CONTRACT_SHA256 = hashlib.sha256(
    REQUEST_CONTRACT_JSON.encode("utf-8")
).hexdigest()


def normalize_symbol(value: str) -> str:
    return value.strip().upper().replace(".", "-")


def _invalid(
    reason_code: str, observed_provider_fields: tuple[str, ...] = ()
) -> ClassifiedResult:
    return ClassifiedResult(
        AcquisitionOutcome.SCHEMA_DRIFT,
        reason_code,
        observed_provider_fields=observed_provider_fields,
    )


def classify_response(requested_symbol: str, payload: object) -> ClassifiedResult:
    if not isinstance(payload, Mapping):
        return _invalid("top_level_not_mapping")

    observed_provider_fields = tuple(sorted(key for key in ALLOWLIST if key in payload))
    projected: dict[str, str | int] = {}
    for provider_key in ALLOWLIST:
        if provider_key not in payload or payload[provider_key] is None:
            continue
        value = payload[provider_key]
        spec = _FIELDS[provider_key]
        if provider_key == "marketCap":
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return _invalid("invalid_marketCap", observed_provider_fields)
            projected[spec.column] = value
            continue
        if not isinstance(value, str):
            return _invalid(f"invalid_{provider_key}", observed_provider_fields)
        clean = value.strip()
        if (
            not clean
            or _CONTROL_CHARACTER.search(clean)
            or len(clean) > int(spec.maximum_length or 0)
        ):
            return _invalid(f"invalid_{provider_key}", observed_provider_fields)
        projected[spec.column] = clean

    provider_symbol = projected.get("provider_symbol")
    if provider_symbol is not None and normalize_symbol(str(provider_symbol)) != normalize_symbol(
        requested_symbol
    ):
        return _invalid("provider_symbol_mismatch", observed_provider_fields)

    observed_fields = tuple(sorted(projected))
    if not projected:
        reason = "empty_mapping" if not payload else "no_useful_allowlisted_values"
        return ClassifiedResult(
            AcquisitionOutcome.NO_DATA,
            reason,
            observed_provider_fields=observed_provider_fields,
        )

    complete = (
        "provider_symbol" in projected
        and "quote_type" in projected
        and bool({"short_name", "long_name"}.intersection(projected))
        and bool({"exchange_code", "exchange_name"}.intersection(projected))
    )
    return ClassifiedResult(
        AcquisitionOutcome.COMPLETE if complete else AcquisitionOutcome.PARTIAL_RESPONSE,
        "identity_envelope_complete" if complete else "identity_envelope_incomplete",
        projected=projected,
        observed_fields=observed_fields,
        observed_provider_fields=observed_provider_fields,
    )


def classify_exception(exc: BaseException) -> ClassifiedResult:
    message = str(exc).lower()
    exception_type = type(exc).__name__
    if "429" in message or "too many requests" in message or "rate limit" in message:
        outcome = AcquisitionOutcome.THROTTLED
        reason = "provider_rate_limited"
    elif (
        "delisted" in message
        or "no timezone found" in message
        or "invalid symbol" in message
        or "unknown symbol" in message
    ):
        outcome = AcquisitionOutcome.INVALID_SYMBOL
        reason = "provider_invalid_symbol"
    elif isinstance(exc, TimeoutError):
        outcome = AcquisitionOutcome.TRANSIENT
        reason = "provider_timeout"
    elif isinstance(exc, ConnectionError):
        outcome = AcquisitionOutcome.TRANSIENT
        reason = "provider_connection_error"
    else:
        outcome = AcquisitionOutcome.TRANSIENT
        reason = "unknown_exception"
    return ClassifiedResult(outcome, reason, detail=exception_type)
