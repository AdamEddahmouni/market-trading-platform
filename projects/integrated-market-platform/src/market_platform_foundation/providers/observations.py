"""Typed, source-attributed observations and provenance envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from collections.abc import Mapping
from typing import Any

from ..contracts.envelope import validate_envelope
from ..canonical import canonical_bytes
from .identity import InstrumentIdentity


class _FrozenDict(dict[str, Any]):
    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("immutable observation value")

    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = _immutable


_EXTENSION_MAX_BYTES = 8_192
_EXTENSION_MAX_DEPTH = 5
_SECRET_KEY_PARTS = ("key", "secret", "token", "password", "authorization", "cookie")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _FrozenDict({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return deepcopy(value)


def _freeze_extensions(value: Mapping[str, Any]) -> Mapping[str, Any]:
    def visit(item: Any, depth: int) -> Any:
        if depth > _EXTENSION_MAX_DEPTH:
            raise ValueError("OBSERVATION_EXTENSIONS_DEPTH_EXCEEDED")
        if isinstance(item, Mapping):
            result: dict[str, Any] = {}
            for key, nested in item.items():
                text = str(key)
                if not text.strip() or len(text) > 64:
                    raise ValueError("OBSERVATION_EXTENSIONS_KEY_INVALID")
                if any(part in text.lower() for part in _SECRET_KEY_PARTS):
                    raise ValueError("OBSERVATION_EXTENSIONS_SECRET")
                result[text] = visit(nested, depth + 1)
            return _FrozenDict(result)
        if isinstance(item, (list, tuple)):
            return tuple(visit(nested, depth + 1) for nested in item)
        if isinstance(item, set):
            return frozenset(visit(nested, depth + 1) for nested in item)
        return deepcopy(item)

    frozen = visit(value, 0)
    try:
        if len(canonical_bytes(frozen)) > _EXTENSION_MAX_BYTES:
            raise ValueError("OBSERVATION_EXTENSIONS_BOUNDED")
    except TypeError as exc:
        raise ValueError("OBSERVATION_EXTENSIONS_STRUCTURED") from exc
    return frozen


@dataclass(frozen=True, slots=True)
class ObservationClocks:
    event_time_ns: int
    source_publish_time_ns: int | None
    effective_time_ns: int
    available_time_ns: int
    received_time_ns: int
    ingested_time_ns: int
    normalized_time_ns: int
    published_time_ns: int | None
    validity_start_ns: int
    validity_end_ns: int | None

    def __post_init__(self) -> None:
        for name in (
            "event_time_ns",
            "effective_time_ns",
            "available_time_ns",
            "received_time_ns",
            "ingested_time_ns",
            "normalized_time_ns",
            "validity_start_ns",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name.upper()}_INVALID")
        for name in ("source_publish_time_ns", "published_time_ns"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name.upper()}_INVALID")
        if self.validity_end_ns is not None and self.validity_end_ns < self.validity_start_ns:
            raise ValueError("VALIDITY_RANGE_INVALID")
        if self.available_time_ns < self.event_time_ns:
            raise ValueError("AVAILABLE_TIME_BEFORE_EVENT")

    def to_dict(self) -> dict[str, int | None]:
        return {
            "available_time_ns": self.available_time_ns,
            "effective_time_ns": self.effective_time_ns,
            "event_time_ns": self.event_time_ns,
            "ingested_time_ns": self.ingested_time_ns,
            "normalized_time_ns": self.normalized_time_ns,
            "published_time_ns": self.published_time_ns,
            "received_time_ns": self.received_time_ns,
            "source_publish_time_ns": self.source_publish_time_ns,
            "validity_end_ns": self.validity_end_ns,
            "validity_start_ns": self.validity_start_ns,
        }


@dataclass(frozen=True, slots=True)
class Observation:
    observation_id: str
    instrument: InstrumentIdentity
    capability_id: str
    provider_id: str
    source_instance_id: str
    clocks: ObservationClocks
    value: Any
    raw_record_id: str
    quality: tuple[str, ...]
    confidence: float
    revision_id: str
    adjustment_state: str
    license_class: str
    normalizer_version: str
    acquisition_mode: str = "historical"
    supersedes_observation_id: str | None = None
    extensions: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _freeze(self.value))
        object.__setattr__(self, "quality", tuple(self.quality))
        if self.extensions is not None:
            object.__setattr__(self, "extensions", _freeze_extensions(self.extensions))
        if not self.observation_id.strip() or not self.raw_record_id.strip():
            raise ValueError("OBSERVATION_ID_REQUIRED")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("OBSERVATION_CONFIDENCE_INVALID")
        if self.acquisition_mode not in {"historical", "live", "replay"}:
            raise ValueError("OBSERVATION_ACQUISITION_MODE_INVALID")

    def to_envelope(self) -> dict[str, Any]:
        return build_observation_envelope(self)


def build_observation_envelope(observation: Observation) -> dict[str, Any]:
    """Convert an observation while preserving clock and revision lineage."""
    clocks = observation.clocks
    historical = observation.acquisition_mode in {"historical", "replay"}
    envelope = {
        "acquisition_mode": observation.acquisition_mode,
        "available_time": clocks.available_time_ns,
        "channel_id": observation.instrument.qualified_id(),
        "effective_time": clocks.effective_time_ns,
        "event_time": clocks.event_time_ns,
        "event_type": "MARKET_OBSERVATION",
        "historical_ingested_time": clocks.ingested_time_ns if historical else None,
        "ingest_run_id": f"observation:{observation.observation_id}",
        "instrument_id": observation.instrument.qualified_id(),
        "live_received_time": clocks.received_time_ns if not historical else None,
        "normalization_version": observation.normalizer_version,
        "normalized_time": clocks.normalized_time_ns,
        "normalized_event_id": observation.observation_id,
        "observation": observation.value,
        "operation": "UPSERT",
        "provider_metadata": {
            "adjustment_state": observation.adjustment_state,
            "confidence": observation.confidence,
            "license_class": observation.license_class,
            "quality": list(observation.quality),
            "provider_id": observation.provider_id,
            "source_instance_id": observation.source_instance_id,
        },
        "published_time": clocks.published_time_ns,
        "publisher_id": observation.provider_id,
        "quality_observation_refs": list(observation.quality),
        "raw_reference": observation.raw_record_id,
        "received_time": clocks.received_time_ns,
        "schema_version": "providers/observation/1.0",
        "source_instance_id": observation.source_instance_id,
        "source_publish_time": clocks.source_publish_time_ns,
        "source_record_id": observation.raw_record_id,
        "source_revision_id": observation.revision_id,
        "source_sequence": None,
        "supersedes_event_id": observation.supersedes_observation_id,
        "validity_end": clocks.validity_end_ns,
        "validity_start": clocks.validity_start_ns,
        "venue_id": observation.instrument.venue_id,
    }
    reasons = validate_envelope(
        envelope,
        timestamp_states={
            "event_time": "REQUIRED",
            "source_publish_time": "UNAVAILABLE"
            if clocks.source_publish_time_ns is None
            else "REQUIRED",
            "live_received_time": "FORBIDDEN" if historical else "REQUIRED",
            "historical_ingested_time": "REQUIRED" if historical else "FORBIDDEN",
            "available_time": "REQUIRED",
        },
        acquisition_mode="historical" if historical else "live",
    )
    if reasons:
        raise ValueError(f"OBSERVATION_ENVELOPE_INVALID:{','.join(reasons)}")
    envelope["clock_lineage"] = clocks.to_dict()
    if observation.extensions is not None:
        envelope["extensions"] = observation.extensions
    return envelope


__all__ = ["Observation", "ObservationClocks", "build_observation_envelope"]
