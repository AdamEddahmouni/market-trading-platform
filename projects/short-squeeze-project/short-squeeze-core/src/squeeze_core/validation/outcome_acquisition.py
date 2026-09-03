"""Deterministic contracts for historical acquisition attempts.

This module performs no provider or network access. It records an acquisition event
that already happened, including explicit failures, and hashes exact raw bytes supplied
by the controlled scripts under ``scripts/acquisition``.
"""

import hashlib
import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from squeeze_core.contracts.validation import require_aware_utc
from squeeze_core.metrics.identifiers import deterministic_metric_id
from squeeze_core.serialization.canonical_json import canonical_hash, canonical_json_bytes


_ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/)")
_SENSITIVE_PARAMETER = re.compile(
    r"(?:api.?key|token|authorization|auth|cookie|password|secret|account.?id|client.?secret)",
    re.IGNORECASE,
)


class AcquisitionDataType(StrEnum):
    INTRADAY_MARKET_BARS = "INTRADAY_MARKET_BARS"
    DAILY_MARKET_BARS = "DAILY_MARKET_BARS"
    NEWS = "NEWS"
    TRADING_HALTS = "TRADING_HALTS"
    PUBLISHED_SHORT_INTEREST = "PUBLISHED_SHORT_INTEREST"
    FINRA_SHORT_SALE_VOLUME = "FINRA_SHORT_SALE_VOLUME"
    BORROW_FEE = "BORROW_FEE"
    BORROW_AVAILABILITY = "BORROW_AVAILABILITY"
    CORPORATE_ACTIONS = "CORPORATE_ACTIONS"


class AcquisitionResultState(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"
    UNAVAILABLE = "UNAVAILABLE"
    ENTITLEMENT_REQUIRED = "ENTITLEMENT_REQUIRED"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    RATE_LIMITED = "RATE_LIMITED"
    UNSUPPORTED = "UNSUPPORTED"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    UNKNOWN = "UNKNOWN"


class AcquisitionEntitlementState(StrEnum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    DELAYED_FROZEN = "DELAYED_FROZEN"
    FROZEN = "FROZEN"
    NOT_REQUIRED = "NOT_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class AcquisitionNormalizationState(StrEnum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"


def _relative_path(value: str | None) -> str | None:
    if value is not None and _ABSOLUTE_PATH.match(value):
        raise ValueError("acquisition paths must be workspace-relative")
    return value


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            _SENSITIVE_PARAMETER.search(str(key)) is not None
            or _contains_sensitive_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive_key(item) for item in value)
    return False


class AcquisitionManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    acquisition_id: str
    symbol: str
    provider: str
    data_type: AcquisitionDataType
    requested_start: datetime
    requested_end: datetime
    retrieved_at: datetime
    request_timezone: str
    response_timezone: str | None = None
    bar_size: str | None = None
    session_scope: str | None = None
    adjustment_policy: str | None = None
    request_parameters: dict[str, Any] = Field(default_factory=dict)
    result_state: AcquisitionResultState
    raw_relative_path: str | None = None
    raw_sha256: str | None = None
    record_count: int = Field(default=0, ge=0)
    earliest_record_time: datetime | None = None
    latest_record_time: datetime | None = None
    entitlement_state: AcquisitionEntitlementState = AcquisitionEntitlementState.UNKNOWN
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    normalization_status: AcquisitionNormalizationState = (
        AcquisitionNormalizationState.NOT_ATTEMPTED
    )
    normalized_relative_path: str | None = None
    normalized_sha256: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        return normalized

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("provider is required")
        return normalized

    @field_validator(
        "requested_start",
        "requested_end",
        "retrieved_at",
        "earliest_record_time",
        "latest_record_time",
    )
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)

    @field_validator("raw_relative_path", "normalized_relative_path")
    @classmethod
    def reject_absolute_paths(cls, value: str | None) -> str | None:
        return _relative_path(value)

    @field_validator("warnings", "errors", "limitations")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @field_validator("request_parameters")
    @classmethod
    def sanitize_request_parameters(cls, value: dict[str, Any]) -> dict[str, Any]:
        if _contains_sensitive_key(value):
            raise ValueError("sensitive request parameter names are prohibited in manifests")
        return {key: value[key] for key in sorted(value)}

    @model_validator(mode="after")
    def validate_attempt(self) -> "AcquisitionManifest":
        if self.requested_start > self.requested_end:
            raise ValueError("requested_start must not follow requested_end")
        if self.earliest_record_time and self.latest_record_time:
            if self.earliest_record_time > self.latest_record_time:
                raise ValueError("earliest_record_time must not follow latest_record_time")
        if self.result_state in {
            AcquisitionResultState.SUCCESS,
            AcquisitionResultState.PARTIAL,
        } and (self.raw_relative_path is None or self.raw_sha256 is None):
            raise ValueError("successful acquisition requires preserved raw response bytes")
        if self.result_state is AcquisitionResultState.EMPTY and self.record_count:
            raise ValueError("an empty acquisition cannot carry records")
        if self.record_count == 0 and (
            self.earliest_record_time is not None or self.latest_record_time is not None
        ):
            raise ValueError("a zero-record acquisition cannot carry a record range")
        return self


def acquisition_manifest_identity(result: AcquisitionManifest) -> dict[str, Any]:
    return {
        "result_type": "PHASE_2V_ACQUISITION_MANIFEST",
        "schema_version": result.schema_version,
        "symbol": result.symbol,
        "provider": result.provider,
        "data_type": result.data_type,
        "requested_start": result.requested_start,
        "requested_end": result.requested_end,
        "retrieved_at": result.retrieved_at,
        "request_timezone": result.request_timezone,
        "bar_size": result.bar_size,
        "session_scope": result.session_scope,
        "adjustment_policy": result.adjustment_policy,
        "request_parameters": result.request_parameters,
        "result_state": result.result_state,
        "raw_sha256": result.raw_sha256,
        "record_count": result.record_count,
        "earliest_record_time": result.earliest_record_time,
        "latest_record_time": result.latest_record_time,
        "entitlement_state": result.entitlement_state,
    }


def build_acquisition_manifest(
    *,
    symbol: str,
    provider: str,
    data_type: AcquisitionDataType,
    requested_start: datetime,
    requested_end: datetime,
    retrieved_at: datetime,
    request_timezone: str,
    result_state: AcquisitionResultState,
    raw_bytes: bytes | None = None,
    response_timezone: str | None = None,
    bar_size: str | None = None,
    session_scope: str | None = None,
    adjustment_policy: str | None = None,
    request_parameters: dict[str, Any] | None = None,
    raw_relative_path: str | None = None,
    record_count: int = 0,
    earliest_record_time: datetime | None = None,
    latest_record_time: datetime | None = None,
    entitlement_state: AcquisitionEntitlementState = AcquisitionEntitlementState.UNKNOWN,
    warnings: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
    normalization_status: AcquisitionNormalizationState = AcquisitionNormalizationState.NOT_ATTEMPTED,
    normalized_relative_path: str | None = None,
    normalized_sha256: str | None = None,
) -> AcquisitionManifest:
    raw_sha256 = (
        None
        if raw_bytes is None
        else f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
    )
    draft = AcquisitionManifest(
        acquisition_id="",
        symbol=symbol,
        provider=provider,
        data_type=data_type,
        requested_start=requested_start,
        requested_end=requested_end,
        retrieved_at=retrieved_at,
        request_timezone=request_timezone,
        response_timezone=response_timezone,
        bar_size=bar_size,
        session_scope=session_scope,
        adjustment_policy=adjustment_policy,
        request_parameters=request_parameters or {},
        result_state=result_state,
        raw_relative_path=raw_relative_path,
        raw_sha256=raw_sha256,
        record_count=record_count,
        earliest_record_time=earliest_record_time,
        latest_record_time=latest_record_time,
        entitlement_state=entitlement_state,
        warnings=warnings,
        errors=errors,
        limitations=limitations,
        normalization_status=normalization_status,
        normalized_relative_path=normalized_relative_path,
        normalized_sha256=normalized_sha256,
    )
    return draft.model_copy(
        update={"acquisition_id": deterministic_metric_id(acquisition_manifest_identity(draft))}
    )


def serialize_acquisition_manifest(result: AcquisitionManifest) -> bytes:
    return canonical_json_bytes(result)


def deserialize_acquisition_manifest(serialized: bytes | str) -> AcquisitionManifest:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return AcquisitionManifest.model_validate(json.loads(raw))


def acquisition_manifest_hash(result: AcquisitionManifest) -> str:
    return canonical_hash(result)


__all__ = [
    "AcquisitionDataType",
    "AcquisitionEntitlementState",
    "AcquisitionManifest",
    "AcquisitionNormalizationState",
    "AcquisitionResultState",
    "acquisition_manifest_hash",
    "acquisition_manifest_identity",
    "build_acquisition_manifest",
    "deserialize_acquisition_manifest",
    "serialize_acquisition_manifest",
]
