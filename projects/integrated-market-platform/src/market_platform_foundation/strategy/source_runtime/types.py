"""Typed inputs and result contract for governed strategy source execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ...canonical import canonical_bytes, sha256_bytes

FOUNDATION_SCHEMA_VERSION = "1.0.0"
STRATEGY_RUNTIME_FOUNDATION_READY = "STRATEGY_RUNTIME_FOUNDATION_READY"
STRATEGY_RUNTIME_STUB_UNAVAILABLE = "STRATEGY_RUNTIME_STUB_UNAVAILABLE"
MATLAB_STRATEGY_RUNTIME_READY = "MATLAB_STRATEGY_RUNTIME_READY"
MATLAB_RUNTIME_UNAVAILABLE = "MATLAB_RUNTIME_UNAVAILABLE"

# Hold labels — simulator is not CALIBRATED; Live remains off for this lane.
HOLD_LABEL_SIMULATOR = "SIMULATOR"
HOLD_LABEL_LIVE_OFF = "LIVE_OFF"


class StrategyExecutionMode(StrEnum):
    """Research/replay/parity only — not Paper/Live execution authority."""

    RESEARCH = "RESEARCH"
    REPLAY = "REPLAY"
    PARITY = "PARITY"


class PineRuntimeCompatibilityStatus(StrEnum):
    """Planning enum for external strategy runtimes (PineTS parity track)."""

    UNTESTED = "UNTESTED"
    RUNNABLE = "RUNNABLE"
    PARTIAL_PARITY = "PARTIAL_PARITY"
    VALIDATED = "VALIDATED"
    RESEARCH_APPROVED = "RESEARCH_APPROVED"
    FTEP_ELIGIBLE = "FTEP_ELIGIBLE"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class StrategySourceRef:
    """Opaque strategy/source descriptor (spec body or adapter reference)."""

    kind: str
    body: Mapping[str, Any]

    def content_hash(self) -> str:
        return sha256_bytes(canonical_bytes({"kind": self.kind, "body": dict(self.body)}))


@dataclass(frozen=True, slots=True)
class StrategyDatasetRef:
    """Event-backed research dataset (admitted bar events)."""

    events: tuple[Mapping[str, Any], ...]

    def content_hash(self) -> str:
        return sha256_bytes(
            canonical_bytes([dict(row) for row in self.events]),
        )


@dataclass(frozen=True, slots=True)
class StrategyParameterRef:
    """Execution parameters (preregistration overrides, registered_at, etc.)."""

    body: Mapping[str, Any]

    def content_hash(self) -> str:
        return sha256_bytes(canonical_bytes(dict(self.body)))


@dataclass(frozen=True, slots=True)
class StrategyExecutionContext:
    """Bounded execution context — must not imply Paper/Live mutation authority."""

    mode: StrategyExecutionMode
    generated_at: str
    hold_labels: tuple[str, ...] = (HOLD_LABEL_SIMULATOR, HOLD_LABEL_LIVE_OFF)
    labels: Mapping[str, str] = field(default_factory=dict)
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "hold_labels",
            tuple(sorted({str(value) for value in self.hold_labels})),
        )
        object.__setattr__(
            self,
            "labels",
            {str(key): str(value) for key, value in sorted(self.labels.items())},
        )

    def content_hash(self) -> str:
        return sha256_bytes(
            canonical_bytes(
                {
                    "correlation_id": self.correlation_id,
                    "generated_at": self.generated_at,
                    "hold_labels": list(self.hold_labels),
                    "labels": self.labels,
                    "mode": str(self.mode),
                }
            )
        )


@dataclass(frozen=True, slots=True)
class StrategySourceRuntimeResult:
    """Deterministic research/replay receipt — not Paper order authority."""

    runtime_id: str
    runtime_version: str
    source_hash: str
    dataset_hash: str
    parameter_hash: str
    context_hash: str
    result_identity: str
    execution_context: StrategyExecutionContext
    events: tuple[Mapping[str, Any], ...] = ()
    signals: tuple[Mapping[str, Any], ...] = ()
    trades: tuple[Mapping[str, Any], ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    generated_at: str = ""
    pine_compatibility_status: PineRuntimeCompatibilityStatus = PineRuntimeCompatibilityStatus.UNTESTED
    foundation_gate: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", tuple(dict(row) for row in self.events))
        object.__setattr__(self, "signals", tuple(dict(row) for row in self.signals))
        object.__setattr__(self, "trades", tuple(dict(row) for row in self.trades))
        object.__setattr__(
            self,
            "metrics",
            {str(key): value for key, value in sorted(self.metrics.items(), key=lambda item: item[0])},
        )
        object.__setattr__(self, "warnings", tuple(sorted({str(value) for value in self.warnings})))
        object.__setattr__(self, "errors", tuple(sorted({str(value) for value in self.errors})))

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_hash": self.context_hash,
            "dataset_hash": self.dataset_hash,
            "errors": list(self.errors),
            "events": [dict(row) for row in self.events],
            "execution_context": {
                "generated_at": self.execution_context.generated_at,
                "hold_labels": list(self.execution_context.hold_labels),
                "labels": dict(self.execution_context.labels),
                "mode": str(self.execution_context.mode),
            },
            "foundation_gate": self.foundation_gate,
            "generated_at": self.generated_at,
            "metrics": dict(self.metrics),
            "parameter_hash": self.parameter_hash,
            "pine_compatibility_status": str(self.pine_compatibility_status),
            "result_identity": self.result_identity,
            "runtime_id": self.runtime_id,
            "runtime_version": self.runtime_version,
            "signals": [dict(row) for row in self.signals],
            "source_hash": self.source_hash,
            "trades": [dict(row) for row in self.trades],
            "warnings": list(self.warnings),
        }


def compute_result_identity(
    *,
    runtime_id: str,
    runtime_version: str,
    source_hash: str,
    dataset_hash: str,
    parameter_hash: str,
    context_hash: str,
    payload_root_hash: str,
) -> str:
    body = {
        "context_hash": context_hash,
        "dataset_hash": dataset_hash,
        "parameter_hash": parameter_hash,
        "payload_root_hash": payload_root_hash,
        "runtime_id": runtime_id,
        "runtime_version": runtime_version,
        "source_hash": source_hash,
    }
    return sha256_bytes(canonical_bytes(body))
