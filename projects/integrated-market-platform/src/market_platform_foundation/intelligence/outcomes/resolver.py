"""Future target observation resolution under frozen cutoff (BUILD 15)."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.event import EventV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..persistence.repository import IntelligenceRepository
from ..quality.conflicts import detect_provider_conflicts
from ..quality.policy import DEFAULT_QUALITY_POLICY
from ..temporal.models import TemporalViolationCode
from ..temporal.validation import inspect_event_temporal_integrity
from .errors import OutcomeObservationError
from .observations import (
    event_observation_kind,
    is_valid_settlement_observation,
    observation_from_event,
    terminal_sort_key,
)
from .p6_compat import p6_terminal_candidate
from .policy import OutcomeSettlementPolicy
from .types import PriceObservationReceipt, TerminalResolutionReceipt, UnlabelableReason


@dataclass(frozen=True, slots=True)
class OutcomeObservationResolver:
    repository: IntelligenceRepository

    def resolve_terminal(
        self,
        entry: PredictionLedgerEntryV1,
        *,
        settlement_policy: OutcomeSettlementPolicy,
        settlement_clock_ns: int,
    ) -> TerminalResolutionReceipt:
        if settlement_clock_ns < entry.availability_cutoff_ns:
            raise OutcomeObservationError(
                "SETTLEMENT_BEFORE_CUTOFF",
                details={"settlement_clock_ns": settlement_clock_ns, "cutoff": entry.availability_cutoff_ns},
            )
        events = self._load_candidate_events(entry, settlement_clock_ns=settlement_clock_ns)
        allowed_kinds = self._allowed_terminal_kinds(entry, settlement_policy)
        in_window = [
            event
            for event in events
            if event.instrument_id == entry.instrument_id
            and event_observation_kind(event) in allowed_kinds
            and entry.target_window_start_ns <= event.event_time_ns <= entry.target_window_end_ns
            and event.available_time_ns <= entry.availability_cutoff_ns
            and is_valid_settlement_observation(event)
        ]
        in_window.sort(key=terminal_sort_key)
        if not in_window:
            return TerminalResolutionReceipt(
                observation=None,
                target_time_ns=entry.target_time_ns,
                target_window_start_ns=entry.target_window_start_ns,
                target_window_end_ns=entry.target_window_end_ns,
                availability_cutoff_ns=entry.availability_cutoff_ns,
            )
        conflicts = detect_provider_conflicts(in_window, policy=DEFAULT_QUALITY_POLICY)
        conflict_errors = [
            finding
            for finding in conflicts
            if finding.code == TemporalViolationCode.CONFLICTING_DUPLICATE.value
            or finding.code == "CONFLICTING_DUPLICATE"
        ]
        if conflict_errors:
            raise OutcomeObservationError(
                UnlabelableReason.TARGET_DATA_CONFLICT.value,
                details={"ledger_entry_id": entry.ledger_entry_id},
            )
        selected = in_window[0]
        receipt = observation_from_event(selected)
        if receipt is None:
            return TerminalResolutionReceipt(
                observation=None,
                target_time_ns=entry.target_time_ns,
                target_window_start_ns=entry.target_window_start_ns,
                target_window_end_ns=entry.target_window_end_ns,
                availability_cutoff_ns=entry.availability_cutoff_ns,
            )
        return TerminalResolutionReceipt(
            observation=receipt,
            target_time_ns=entry.target_time_ns,
            target_window_start_ns=entry.target_window_start_ns,
            target_window_end_ns=entry.target_window_end_ns,
            availability_cutoff_ns=entry.availability_cutoff_ns,
        )

    def _allowed_terminal_kinds(
        self,
        entry: PredictionLedgerEntryV1,
        policy: OutcomeSettlementPolicy,
    ) -> set[str]:
        anchor_kind = str(entry.anchor_observation.get("observation_kind") or "").upper()
        allowed = {kind.upper() for kind in policy.observation_kinds}
        for kind in policy.fallback_observation_kinds:
            allowed.add(kind.upper())
        if policy.require_same_observation_kind and anchor_kind:
            if anchor_kind not in allowed:
                raise OutcomeObservationError(
                    UnlabelableReason.SOURCE_POLICY_MISMATCH.value,
                    details={"anchor_kind": anchor_kind},
                )
            return {anchor_kind}
        return allowed

    def _load_candidate_events(
        self,
        entry: PredictionLedgerEntryV1,
        *,
        settlement_clock_ns: int,
    ) -> tuple[EventV1, ...]:
        _ = settlement_clock_ns
        return self.repository.iter_events_by_availability(
            start_time_ns=0,
            end_time_ns=entry.availability_cutoff_ns,
            instrument_id=entry.instrument_id,
            limit=50_000,
        )


def p6_compatible_terminal_from_events(
    events: tuple[EventV1, ...],
    *,
    instrument_id: str,
    target_ns: int,
    tolerance_ns: int,
    cutoff_ns: int,
) -> PriceObservationReceipt | None:
    ticks: list[tuple[int, float, int]] = []
    event_by_time: dict[int, EventV1] = {}
    for event in events:
        if event.instrument_id != instrument_id:
            continue
        if event.available_time_ns > cutoff_ns:
            continue
        receipt = observation_from_event(event)
        if receipt is None:
            continue
        ticks.append((receipt.event_time_ns, receipt.price, receipt.available_time_ns))
        event_by_time[receipt.event_time_ns] = event
    candidate = p6_terminal_candidate(ticks, target_ns=target_ns, tolerance_ns=tolerance_ns)
    if candidate is None:
        return None
    event = event_by_time.get(candidate[0])
    if event is None:
        return None
    return observation_from_event(event)


__all__ = ["OutcomeObservationResolver", "p6_compatible_terminal_from_events"]
