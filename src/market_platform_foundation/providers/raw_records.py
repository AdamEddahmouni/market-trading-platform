"""Bounded immutable raw capture and reproducible normalization lineage."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Any, Callable, Mapping

from ..canonical import canonical_bytes, sha256_bytes


_SECRET_TEXT = re.compile(
    r"(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|"
    r"authorization|cookie|username)\b\s*[=:]\s*)([^&\s,;]+)"
)
_AUTH_TEXT = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+")
_LICENSE_CLASSES = frozenset(
    {"PUBLIC", "RESEARCH_ONLY", "COMMERCIAL", "INTERNAL_ONLY", "RESTRICTED", "UNKNOWN"}
)


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                str(key): "***REDACTED***"
                if any(
                    token in str(key).lower()
                    for token in ("key", "secret", "token", "password", "authorization", "cookie", "username")
                )
                else _redact(item)
                for key, item in value.items()
            }
        )
    if isinstance(value, (list, tuple)):
        return tuple(_redact(item) for item in value)
    if isinstance(value, str):
        redacted = _SECRET_TEXT.sub(r"\1***REDACTED***", value)
        return _AUTH_TEXT.sub(r"\1 ***REDACTED***", redacted)
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return deepcopy(value)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class RawRecord:
    raw_record_id: str
    request_identity: Mapping[str, Any]
    provider_id: str
    source_instance_id: str
    received_time_ns: int
    payload_hash: str
    payload: Mapping[str, Any]
    schema_version: str
    ingestion_version: str
    license_class: str
    storage_ref: str
    redacted_request: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.raw_record_id.strip() or not self.provider_id.strip() or not self.source_instance_id.strip():
            raise ValueError("RAW_RECORD_IDENTITY_REQUIRED")
        if self.received_time_ns < 0:
            raise ValueError("RAW_RECORD_RECEIVED_TIME_INVALID")
        license_class = self.license_class.strip().upper()
        if license_class not in _LICENSE_CLASSES:
            raise ValueError("RAW_RECORD_LICENSE_INVALID")
        object.__setattr__(self, "license_class", license_class)
        object.__setattr__(self, "request_identity", _freeze(_redact(self.request_identity)))
        object.__setattr__(self, "payload", _freeze(_redact(self.payload)))
        object.__setattr__(self, "redacted_request", _freeze(_redact(self.redacted_request)))

    @classmethod
    def create(
        cls,
        *,
        request_identity: Mapping[str, Any],
        provider_id: str,
        source_instance_id: str,
        received_time_ns: int,
        payload: Mapping[str, Any],
        schema_version: str,
        ingestion_version: str,
        license_class: str,
        storage_ref: str,
        request_metadata: Mapping[str, Any],
    ) -> "RawRecord":
        safe_request = _redact(request_identity)
        safe_payload = _redact(payload)
        source_payload = {
            "provider_id": provider_id,
            "source_instance_id": source_instance_id,
            "payload": safe_payload,
        }
        payload_hash = sha256_bytes(canonical_bytes(_plain(source_payload)))
        request_identity_hash = sha256_bytes(
            canonical_bytes(
                {
                    "provider_id": provider_id,
                    "source_instance_id": source_instance_id,
                    "request_identity": _plain(safe_request),
                }
            )
        )
        return cls(
            raw_record_id=f"raw-{sha256_bytes((request_identity_hash + payload_hash).encode())[:24]}",
            request_identity=_freeze(safe_request),
            provider_id=provider_id,
            source_instance_id=source_instance_id,
            received_time_ns=received_time_ns,
            payload_hash=payload_hash,
            payload=_freeze(safe_payload),
            schema_version=schema_version,
            ingestion_version=ingestion_version,
            license_class=license_class.strip().upper(),
            storage_ref=storage_ref,
            redacted_request=_freeze(_redact(request_metadata)),
        )


class RawRecordStore:
    def __init__(self, *, max_records: int = 1_000, max_bytes: int = 10_000_000) -> None:
        self._max_records = max_records
        self._max_bytes = max_bytes
        self._records: dict[str, RawRecord] = {}
        self._sizes: dict[str, int] = {}
        self._normalizations: dict[tuple[str, str], NormalizedObservation] = {}
        self._bytes = 0

    def put(self, record: RawRecord) -> RawRecord:
        existing = self._records.get(record.raw_record_id)
        if existing is not None:
            if existing.payload_hash != record.payload_hash:
                raise ValueError("RAW_RECORD_IMMUTABILITY_CONFLICT")
            return existing
        size = len(canonical_bytes(_plain(record.payload)))
        if size > self._max_bytes or len(self._records) >= self._max_records or self._bytes + size > self._max_bytes:
            raise ValueError("RAW_RECORD_STORE_BOUNDED")
        self._records[record.raw_record_id] = record
        self._sizes[record.raw_record_id] = size
        self._bytes += size
        return record

    def get(self, raw_record_id: str) -> RawRecord:
        try:
            return self._records[raw_record_id]
        except KeyError as exc:
            raise KeyError(f"RAW_RECORD_NOT_FOUND:{raw_record_id}") from exc

    def reprocess(
        self,
        raw_record_id: str,
        normalizer_version: str,
        normalizer: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    ) -> NormalizedObservation:
        record = self.get(raw_record_id)
        normalized = deepcopy(dict(normalizer(record.payload)))
        extensions = normalized.get("extensions")
        output = NormalizedObservation(
            observation_id=f"{raw_record_id}:{normalizer_version}",
            raw_record_id=raw_record_id,
            normalizer_version=normalizer_version,
            provider_id=record.provider_id,
            source_instance_id=record.source_instance_id,
            license_class=record.license_class,
            value=_freeze(normalized),
            extensions=_freeze(_redact(extensions)) if isinstance(extensions, Mapping) else None,
        )
        key = (raw_record_id, normalizer_version)
        existing = self._normalizations.get(key)
        if existing is not None:
            if canonical_bytes(_plain(existing.to_dict())) != canonical_bytes(_plain(output.to_dict())):
                raise ValueError("NORMALIZATION_IMMUTABILITY_CONFLICT")
            return existing
        self._normalizations[key] = output
        return output

    def manifest(self) -> dict[str, int]:
        return {
            "record_count": len(self._records),
            "normalization_count": len(self._normalizations),
            "retained_bytes": self._bytes,
        }


@dataclass(frozen=True, slots=True)
class NormalizedObservation:
    observation_id: str
    raw_record_id: str
    normalizer_version: str
    provider_id: str
    source_instance_id: str
    license_class: str
    value: Mapping[str, Any]
    extensions: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _freeze(self.value))
        if self.extensions is not None:
            object.__setattr__(self, "extensions", _freeze(_redact(self.extensions)))

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "raw_record_id": self.raw_record_id,
            "normalizer_version": self.normalizer_version,
            "provider_id": self.provider_id,
            "source_instance_id": self.source_instance_id,
            "license_class": self.license_class,
            "value": self.value,
            "extensions": self.extensions,
        }


__all__ = ["NormalizedObservation", "RawRecord", "RawRecordStore"]
