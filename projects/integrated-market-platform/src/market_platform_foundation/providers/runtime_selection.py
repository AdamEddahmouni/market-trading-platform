"""G7 — deterministic observational provider selection (fail-closed).

Answers: which provider can satisfy capability X for instrument Y at runtime
state Z, with what provenance and entitlement/delayed status. Never silently
falls back to stale, delayed, unauthorized, or ambiguous providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .registry import ProviderRegistry
from .runtime_capability import (
    RuntimeCapabilityRegistry,
    RuntimeCapabilityState,
    RuntimeCapabilityView,
)


class SelectionOutcome(StrEnum):
    SELECTED = "SELECTED"
    NO_PROVIDER = "NO_PROVIDER"
    NOT_ENTITLED = "NOT_ENTITLED"
    DELAYED_REJECTED = "DELAYED_REJECTED"
    STALE_REJECTED = "STALE_REJECTED"
    PROVIDER_DOWN = "PROVIDER_DOWN"
    UNSUPPORTED_INSTRUMENT = "UNSUPPORTED_INSTRUMENT"
    AMBIGUOUS = "AMBIGUOUS"
    REPLAY_ONLY = "REPLAY_ONLY"


@dataclass(frozen=True, slots=True)
class ObservationalSelectionRequest:
    capability_id: str
    instrument_id: str
    require_real_time: bool = False
    allow_replay: bool = True
    provider_id: str | None = None
    asset_class: str | None = None
    instrument_kind: str | None = None


@dataclass(frozen=True, slots=True)
class ObservationalSelectionResult:
    outcome: SelectionOutcome
    provider_id: str | None
    capability_view: RuntimeCapabilityView | None
    diagnostics: tuple[str, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_view": (
                None if self.capability_view is None else self.capability_view.to_dict()
            ),
            "diagnostics": list(self.diagnostics),
            "outcome": self.outcome.value,
            "provider_id": self.provider_id,
            "provenance": dict(self.provenance),
        }


_ACCEPTABLE_STATES = frozenset(
    {
        RuntimeCapabilityState.READY,
        RuntimeCapabilityState.DEGRADED,
        RuntimeCapabilityState.LIVE_PROVIDER_UNVERIFIED,
    }
)


class ObservationalProviderSelector:
    """Deterministic fail-closed observational provider selection."""

    def __init__(
        self,
        capability_registry: RuntimeCapabilityRegistry | None = None,
        provider_registry: ProviderRegistry | None = None,
    ) -> None:
        self._capability_registry = capability_registry or RuntimeCapabilityRegistry(
            provider_registry
        )

    def select(self, request: ObservationalSelectionRequest) -> ObservationalSelectionResult:
        instrument_id = str(request.instrument_id or "").strip().upper()
        if not instrument_id:
            return ObservationalSelectionResult(
                outcome=SelectionOutcome.UNSUPPORTED_INSTRUMENT,
                provider_id=None,
                capability_view=None,
                diagnostics=("INSTRUMENT_ID_REQUIRED",),
            )

        kind_error = _validate_instrument_kind(
            request.capability_id,
            request.instrument_kind,
            instrument_id,
        )
        if kind_error is not None:
            return ObservationalSelectionResult(
                outcome=SelectionOutcome.UNSUPPORTED_INSTRUMENT,
                provider_id=None,
                capability_view=None,
                diagnostics=(kind_error,),
            )

        provider_ids = self._capability_registry.providers_for_lane_capability(
            request.capability_id
        )
        if request.provider_id is not None:
            if request.provider_id not in provider_ids:
                return ObservationalSelectionResult(
                    outcome=SelectionOutcome.NO_PROVIDER,
                    provider_id=None,
                    capability_view=None,
                    diagnostics=(f"UNKNOWN_PROVIDER:{request.provider_id}",),
                )
            provider_ids = [request.provider_id]

        if not provider_ids:
            return ObservationalSelectionResult(
                outcome=SelectionOutcome.NO_PROVIDER,
                provider_id=None,
                capability_view=None,
                diagnostics=("NO_IMPLEMENTED_PROVIDER",),
            )

        candidates: list[tuple[str, RuntimeCapabilityView]] = []
        diagnostics: list[str] = []

        for pid in sorted(provider_ids):
            registry_cap = self._capability_registry.resolve_registry_capability(
                pid, request.capability_id
            )
            view = self._capability_registry.view_capability(
                pid,
                registry_cap,
                instrument_id=instrument_id,
                require_real_time=request.require_real_time,
            )
            if not view.implemented:
                diagnostics.append(f"NOT_IMPLEMENTED:{pid}")
                continue
            if view.runtime_state == RuntimeCapabilityState.PROVIDER_UNAVAILABLE:
                diagnostics.append(f"PROVIDER_DOWN:{pid}")
                continue
            if view.runtime_state == RuntimeCapabilityState.NOT_ENTITLED:
                diagnostics.append(f"NOT_ENTITLED:{pid}")
                continue
            if view.runtime_state == RuntimeCapabilityState.STALE:
                diagnostics.append(f"STALE:{pid}")
                continue
            if view.runtime_state == RuntimeCapabilityState.DELAYED:
                diagnostics.append(f"DELAYED:{pid}")
                continue
            if view.runtime_state in _ACCEPTABLE_STATES:
                candidates.append((pid, view))

        if not candidates:
            outcome = _failure_outcome(diagnostics)
            return ObservationalSelectionResult(
                outcome=outcome,
                provider_id=None,
                capability_view=None,
                diagnostics=tuple(sorted(diagnostics)),
            )

        if len(candidates) > 1 and request.provider_id is None:
            # Deterministic: lowest provider_id wins; never merge facts.
            candidates.sort(key=lambda item: item[0])
            diagnostics.append(
                f"MULTIPLE_ELIGIBLE:{','.join(pid for pid, _ in candidates)}"
            )

        selected_id, selected_view = candidates[0]
        outcome = SelectionOutcome.SELECTED
        if selected_view.runtime_state == RuntimeCapabilityState.LIVE_PROVIDER_UNVERIFIED:
            outcome = (
                SelectionOutcome.REPLAY_ONLY
                if request.allow_replay
                else SelectionOutcome.NO_PROVIDER
            )
            if outcome == SelectionOutcome.NO_PROVIDER:
                diagnostics.append("LIVE_UNVERIFIED_REPLAY_DISALLOWED")

        return ObservationalSelectionResult(
            outcome=outcome,
            provider_id=selected_id if outcome != SelectionOutcome.NO_PROVIDER else None,
            capability_view=selected_view if outcome != SelectionOutcome.NO_PROVIDER else None,
            diagnostics=tuple(sorted(diagnostics)),
            provenance={
                "instrument_id": instrument_id,
                "capability_id": request.capability_id,
                "provider_id": selected_id,
                "selection_policy": "deterministic_priority",
            } if outcome != SelectionOutcome.NO_PROVIDER else {},
        )


def _validate_instrument_kind(
    capability_id: str,
    instrument_kind: str | None,
    instrument_id: str,
) -> str | None:
    from .runtime_capability import CAP_FUTURE_CONTRACT, CAP_OPTION_CONTRACT
    from ..xa01.enums import InstrumentKind

    if instrument_kind is None:
        return None
    kind = instrument_kind
    if capability_id == CAP_OPTION_CONTRACT and kind != InstrumentKind.OPTION_CONTRACT.value:
        return "OPTION_CONTRACT_REQUIRED"
    if capability_id == CAP_FUTURE_CONTRACT:
        if kind in {
            InstrumentKind.FUTURE_FAMILY.value,
            InstrumentKind.CONTINUOUS_SERIES.value,
        }:
            return "SPECIFIC_FUTURE_CONTRACT_REQUIRED"
        if kind != InstrumentKind.FUTURE_CONTRACT.value:
            return "FUTURE_CONTRACT_REQUIRED"
    return None


def _failure_outcome(diagnostics: list[str]) -> SelectionOutcome:
    joined = " ".join(diagnostics)
    if "NOT_ENTITLED" in joined:
        return SelectionOutcome.NOT_ENTITLED
    if "DELAYED" in joined:
        return SelectionOutcome.DELAYED_REJECTED
    if "STALE" in joined:
        return SelectionOutcome.STALE_REJECTED
    if "PROVIDER_DOWN" in joined:
        return SelectionOutcome.PROVIDER_DOWN
    return SelectionOutcome.NO_PROVIDER


__all__ = [
    "ObservationalProviderSelector",
    "ObservationalSelectionRequest",
    "ObservationalSelectionResult",
    "SelectionOutcome",
]
