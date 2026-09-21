"""Live position reconciliation contract (fail closed, never submit).

Compares a broker position observation to IMP position truth without wiring a
live broker or inventing a second position database. Missing / stale / unknown
external observations stay explicit and never become a silent match.

Live remains OFF: ``allows_network_submit`` is always False. Operator
acknowledgement records an audit fact only and never authorizes network submit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .dry_run import LiveSubmitForbiddenError


class PositionReconciliationState(StrEnum):
    MATCH = "MATCH"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    PARTIAL_FILL_OPEN = "PARTIAL_FILL_OPEN"
    STALE = "STALE"
    MISSING_BROKER_SNAPSHOT = "MISSING_BROKER_SNAPSHOT"
    UNKNOWN_EXTERNAL_POSITION = "UNKNOWN_EXTERNAL_POSITION"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class ImpPositionTruthV1:
    """IMP-side position truth input (explicit snapshot; not a live DB)."""

    instrument_id: str
    quantity: int
    as_of_ns: int = 0
    # Residual working quantity after a partial fill; non-zero means position
    # is not yet equal to a fully settled book even when filled qty matches.
    open_quantity: int = 0


@dataclass(frozen=True)
class BrokerPositionObservationV1:
    """Broker-side position observation for Live reconciliation (no network I/O)."""

    instrument_id: str
    quantity: int
    as_of_ns: int
    snapshot_id: str
    # Explicit freshness token. STALE / UNAVAILABLE are never treated as truth.
    freshness: str = "FRESH"


@dataclass(frozen=True)
class PositionReconciliationResultV1:
    state: PositionReconciliationState
    instrument_id: str | None
    imp_quantity: int | None
    broker_quantity: int | None
    open_quantity: int | None
    reason_codes: tuple[str, ...]
    snapshot_id: str | None
    allows_network_submit: bool = False


@dataclass(frozen=True)
class PositionReconciliationOperatorAckV1:
    note: str
    decision_time_ns: int
    recorded: bool
    allows_network_submit: bool = False
    last_result_state: PositionReconciliationState | None = None


@dataclass
class LivePositionReconciliationGate:
    """Startup fail-closed gate for Live position reconciliation.

    Does not open broker sessions, does not mutate IMP position truth from
    broker observations, and never authorizes network submit.
    """

    max_broker_age_ns: int
    reconciliation_required: bool = True
    operator_acknowledged: bool = False
    _applied_results: dict[str, PositionReconciliationResultV1] = field(
        default_factory=dict, repr=False
    )
    _last_result: PositionReconciliationResultV1 | None = field(default=None, repr=False)
    _audit: list[tuple[str, str]] = field(default_factory=list, repr=False)
    # Explicit IMP truth instruments seen on the last reconcile call only —
    # never auto-populated from unknown broker positions.
    _last_imp_instruments: tuple[str, ...] = field(default=(), repr=False)

    @property
    def allows_network_submit(self) -> bool:
        return False

    @property
    def allows_subsequent_live_action(self) -> bool:
        """Modeled live-action gate after match + operator ack; submit stays OFF."""
        if self.allows_network_submit:
            return False
        if self.reconciliation_required:
            return False
        if not self.operator_acknowledged:
            return False
        if self._last_result is None:
            return False
        return self._last_result.state == PositionReconciliationState.MATCH

    @property
    def applied_snapshot_ids(self) -> tuple[str, ...]:
        return tuple(self._applied_results.keys())

    def apply_count_for(self, snapshot_id: str) -> int:
        return 1 if snapshot_id in self._applied_results else 0

    def imp_truth_instruments(self) -> tuple[str, ...]:
        return self._last_imp_instruments

    def reconcile(
        self,
        *,
        imp_positions: tuple[ImpPositionTruthV1, ...] | list[ImpPositionTruthV1],
        broker_snapshot: BrokerPositionObservationV1 | None,
        decision_time_ns: int,
    ) -> PositionReconciliationResultV1:
        imp_list = tuple(imp_positions)
        self._last_imp_instruments = tuple(sorted({p.instrument_id for p in imp_list}))

        if broker_snapshot is not None and broker_snapshot.snapshot_id in self._applied_results:
            # Idempotent: return the exact prior result; do not re-apply side effects.
            cached = self._applied_results[broker_snapshot.snapshot_id]
            self._last_result = cached
            self._audit.append(("reconcile_replay", broker_snapshot.snapshot_id))
            return cached

        result = _evaluate_position_reconciliation(
            imp_positions=imp_list,
            broker_snapshot=broker_snapshot,
            decision_time_ns=decision_time_ns,
            max_broker_age_ns=self.max_broker_age_ns,
        )
        if broker_snapshot is not None:
            self._applied_results[broker_snapshot.snapshot_id] = result
            self._audit.append(("reconcile_apply", broker_snapshot.snapshot_id))
        else:
            self._audit.append(("reconcile_apply", "MISSING"))

        self._last_result = result
        # Fresh apply after match clears recon requirement; mismatch keeps it.
        # Operator acknowledgement is always required again after a new apply
        # so startup / post-mismatch live action stays fail-closed.
        self.operator_acknowledged = False
        if result.state == PositionReconciliationState.MATCH:
            self.reconciliation_required = False
        else:
            self.reconciliation_required = True
        return result

    def acknowledge_operator(
        self,
        *,
        note: str,
        decision_time_ns: int,
    ) -> PositionReconciliationOperatorAckV1:
        last_state = self._last_result.state if self._last_result is not None else None
        self._audit.append(("operator_ack", note))
        # Ack records the audit fact. It never authorizes network submit.
        # Subsequent live action is only modeled as allowed after MATCH.
        if last_state == PositionReconciliationState.MATCH and not self.reconciliation_required:
            self.operator_acknowledged = True
        else:
            self.operator_acknowledged = False
        return PositionReconciliationOperatorAckV1(
            note=note,
            decision_time_ns=decision_time_ns,
            recorded=True,
            allows_network_submit=False,
            last_result_state=last_state,
        )

    def attempt_network_submit(self) -> None:
        """Always refuse — Live remains OFF / BUILD 28 zero-submit."""
        raise LiveSubmitForbiddenError(
            "BUILD28_ZERO_SUBMIT_VIOLATION:place_order:position_reconciliation"
        )


def _evaluate_position_reconciliation(
    *,
    imp_positions: tuple[ImpPositionTruthV1, ...],
    broker_snapshot: BrokerPositionObservationV1 | None,
    decision_time_ns: int,
    max_broker_age_ns: int,
) -> PositionReconciliationResultV1:
    if broker_snapshot is None:
        instrument_id = imp_positions[0].instrument_id if imp_positions else None
        imp_qty = imp_positions[0].quantity if imp_positions else None
        open_qty = imp_positions[0].open_quantity if imp_positions else None
        return PositionReconciliationResultV1(
            state=PositionReconciliationState.MISSING_BROKER_SNAPSHOT,
            instrument_id=instrument_id,
            imp_quantity=imp_qty,
            broker_quantity=None,
            open_quantity=open_qty,
            reason_codes=("BROKER_SNAPSHOT_MISSING",),
            snapshot_id=None,
            allows_network_submit=False,
        )

    freshness = str(broker_snapshot.freshness or "").upper()
    if freshness in {"STALE", "UNAVAILABLE", "UNKNOWN", "NOT_OBSERVED"}:
        return PositionReconciliationResultV1(
            state=PositionReconciliationState.STALE
            if freshness == "STALE"
            else PositionReconciliationState.UNAVAILABLE,
            instrument_id=broker_snapshot.instrument_id,
            imp_quantity=None,
            broker_quantity=broker_snapshot.quantity,
            open_quantity=None,
            reason_codes=("BROKER_SNAPSHOT_STALE",)
            if freshness == "STALE"
            else ("BROKER_SNAPSHOT_UNAVAILABLE",),
            snapshot_id=broker_snapshot.snapshot_id,
            allows_network_submit=False,
        )

    if decision_time_ns < broker_snapshot.as_of_ns:
        return PositionReconciliationResultV1(
            state=PositionReconciliationState.STALE,
            instrument_id=broker_snapshot.instrument_id,
            imp_quantity=None,
            broker_quantity=broker_snapshot.quantity,
            open_quantity=None,
            reason_codes=("BROKER_SNAPSHOT_TIMESTAMP_IN_FUTURE",),
            snapshot_id=broker_snapshot.snapshot_id,
            allows_network_submit=False,
        )

    if decision_time_ns - broker_snapshot.as_of_ns > max_broker_age_ns:
        return PositionReconciliationResultV1(
            state=PositionReconciliationState.STALE,
            instrument_id=broker_snapshot.instrument_id,
            imp_quantity=None,
            broker_quantity=broker_snapshot.quantity,
            open_quantity=None,
            reason_codes=("BROKER_SNAPSHOT_STALE",),
            snapshot_id=broker_snapshot.snapshot_id,
            allows_network_submit=False,
        )

    by_instrument = {p.instrument_id: p for p in imp_positions}
    imp = by_instrument.get(broker_snapshot.instrument_id)
    if imp is None:
        return PositionReconciliationResultV1(
            state=PositionReconciliationState.UNKNOWN_EXTERNAL_POSITION,
            instrument_id=broker_snapshot.instrument_id,
            imp_quantity=None,
            broker_quantity=broker_snapshot.quantity,
            open_quantity=None,
            reason_codes=("UNKNOWN_EXTERNAL_POSITION",),
            snapshot_id=broker_snapshot.snapshot_id,
            allows_network_submit=False,
        )

    if imp.quantity != broker_snapshot.quantity:
        return PositionReconciliationResultV1(
            state=PositionReconciliationState.QUANTITY_MISMATCH,
            instrument_id=imp.instrument_id,
            imp_quantity=imp.quantity,
            broker_quantity=broker_snapshot.quantity,
            open_quantity=imp.open_quantity,
            reason_codes=("POSITION_QUANTITY_MISMATCH",),
            snapshot_id=broker_snapshot.snapshot_id,
            allows_network_submit=False,
        )

    if imp.open_quantity > 0:
        return PositionReconciliationResultV1(
            state=PositionReconciliationState.PARTIAL_FILL_OPEN,
            instrument_id=imp.instrument_id,
            imp_quantity=imp.quantity,
            broker_quantity=broker_snapshot.quantity,
            open_quantity=imp.open_quantity,
            reason_codes=("PARTIAL_FILL_QUANTITY_STILL_OPEN",),
            snapshot_id=broker_snapshot.snapshot_id,
            allows_network_submit=False,
        )

    return PositionReconciliationResultV1(
        state=PositionReconciliationState.MATCH,
        instrument_id=imp.instrument_id,
        imp_quantity=imp.quantity,
        broker_quantity=broker_snapshot.quantity,
        open_quantity=imp.open_quantity,
        reason_codes=("POSITION_QUANTITY_MATCH",),
        snapshot_id=broker_snapshot.snapshot_id,
        allows_network_submit=False,
    )


__all__ = [
    "BrokerPositionObservationV1",
    "ImpPositionTruthV1",
    "LivePositionReconciliationGate",
    "PositionReconciliationOperatorAckV1",
    "PositionReconciliationResultV1",
    "PositionReconciliationState",
]
