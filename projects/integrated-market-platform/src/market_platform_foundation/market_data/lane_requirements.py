"""G7 — lane requirement graph (capability → lane mapping).

Each research/observational lane declares required capabilities. Lanes explain
READY / DEGRADED / UNAVAILABLE / STALE / NOT_ENTITLED / etc. using existing
vocabularies from runtime_capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..providers.runtime_capability import (
    CAP_FUTURE_CONTRACT,
    CAP_L1,
    CAP_L2,
    CAP_OPTION_CONTRACT,
    CAP_TRADES,
    RuntimeCapabilityState,
)
from ..providers.runtime_selection import (
    ObservationalProviderSelector,
    ObservationalSelectionRequest,
    SelectionOutcome,
)


class ObservationalLane(StrEnum):
    L1 = "L1"
    L2 = "L2"
    CVD = "CVD"
    OFI = "OFI"
    BOOK_FEATURES = "BOOK_FEATURES"
    SQUEEZE = "SQUEEZE"
    FUSION = "FUSION"
    OPTIONS = "OPTIONS"
    FUTURES = "FUTURES"


_LANE_REQUIREMENTS: dict[ObservationalLane, tuple[str, ...]] = {
    ObservationalLane.L1: (CAP_L1,),
    ObservationalLane.L2: (CAP_L2,),
    ObservationalLane.CVD: (CAP_TRADES,),
    ObservationalLane.OFI: (CAP_L2,),
    ObservationalLane.BOOK_FEATURES: (CAP_L2,),
    ObservationalLane.SQUEEZE: (CAP_L1, CAP_L2),
    ObservationalLane.FUSION: (CAP_L1, CAP_L2, CAP_TRADES),
    ObservationalLane.OPTIONS: (CAP_OPTION_CONTRACT, CAP_L1),
    ObservationalLane.FUTURES: (CAP_FUTURE_CONTRACT,),
}


@dataclass(frozen=True, slots=True)
class LaneReadiness:
    lane: ObservationalLane
    state: RuntimeCapabilityState
    satisfied_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    provider_id: str | None
    reason_code: str | None
    diagnostics: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnostics": list(self.diagnostics),
            "lane": self.lane.value,
            "missing_capabilities": list(self.missing_capabilities),
            "provider_id": self.provider_id,
            "reason_code": self.reason_code,
            "satisfied_capabilities": list(self.satisfied_capabilities),
            "state": self.state.value,
        }


def lane_required_capabilities(lane: ObservationalLane) -> tuple[str, ...]:
    return _LANE_REQUIREMENTS.get(lane, ())


def evaluate_lane_readiness(
    lane: ObservationalLane,
    *,
    instrument_id: str,
    selector: ObservationalProviderSelector | None = None,
    instrument_kind: str | None = None,
    require_real_time: bool = False,
) -> LaneReadiness:
    """Evaluate whether required capabilities are satisfiable for a lane."""
    selector = selector or ObservationalProviderSelector()
    required = lane_required_capabilities(lane)
    if not required:
        return LaneReadiness(
            lane=lane,
            state=RuntimeCapabilityState.UNAVAILABLE,
            satisfied_capabilities=(),
            missing_capabilities=(),
            provider_id=None,
            reason_code="LANE_UNKNOWN",
            diagnostics=("LANE_NOT_DEFINED",),
        )

    satisfied: list[str] = []
    missing: list[str] = []
    diagnostics: list[str] = []
    worst_state = RuntimeCapabilityState.READY
    provider_id: str | None = None
    reason: str | None = None

    for cap in required:
        result = selector.select(
            ObservationalSelectionRequest(
                capability_id=cap,
                instrument_id=instrument_id,
                instrument_kind=instrument_kind,
                require_real_time=require_real_time,
            )
        )
        if result.outcome in {SelectionOutcome.SELECTED, SelectionOutcome.REPLAY_ONLY}:
            satisfied.append(cap)
            if provider_id is None:
                provider_id = result.provider_id
            view = result.capability_view
            if view is not None:
                state = view.runtime_state
                if state == RuntimeCapabilityState.LIVE_PROVIDER_UNVERIFIED:
                    worst_state = RuntimeCapabilityState.LIVE_PROVIDER_UNVERIFIED
                elif state == RuntimeCapabilityState.DEGRADED and worst_state == RuntimeCapabilityState.READY:
                    worst_state = RuntimeCapabilityState.DEGRADED
        else:
            missing.append(cap)
            diagnostics.extend(result.diagnostics)
            reason = result.outcome.value

    if missing:
        state = _missing_to_state(reason)
        return LaneReadiness(
            lane=lane,
            state=state,
            satisfied_capabilities=tuple(satisfied),
            missing_capabilities=tuple(missing),
            provider_id=provider_id,
            reason_code=reason,
            diagnostics=tuple(sorted(set(diagnostics))),
        )

    return LaneReadiness(
        lane=lane,
        state=worst_state,
        satisfied_capabilities=tuple(satisfied),
        missing_capabilities=(),
        provider_id=provider_id,
        reason_code=None,
        diagnostics=tuple(sorted(set(diagnostics))),
    )


def _missing_to_state(reason: str | None) -> RuntimeCapabilityState:
    mapping = {
        SelectionOutcome.NOT_ENTITLED.value: RuntimeCapabilityState.NOT_ENTITLED,
        SelectionOutcome.DELAYED_REJECTED.value: RuntimeCapabilityState.DELAYED,
        SelectionOutcome.STALE_REJECTED.value: RuntimeCapabilityState.STALE,
        SelectionOutcome.PROVIDER_DOWN.value: RuntimeCapabilityState.PROVIDER_UNAVAILABLE,
        SelectionOutcome.UNSUPPORTED_INSTRUMENT.value: RuntimeCapabilityState.UNSUPPORTED_INSTRUMENT,
    }
    if reason in mapping:
        return mapping[reason]
    return RuntimeCapabilityState.UNAVAILABLE


__all__ = [
    "LaneReadiness",
    "ObservationalLane",
    "evaluate_lane_readiness",
    "lane_required_capabilities",
]
