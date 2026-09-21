"""Live order lifecycle safety state machine (cannot submit).

Models acknowledgement, partial fill, cancel, rejection, disconnect, and
restart-restore transitions for Live readiness. Never opens a broker session
or transmits an order. Production remains BUILD28_LIVE_SUBMIT_FORBIDDEN.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .dry_run import LiveSubmitForbiddenError
from .types import BrokerOrderStateKind

# Terminal broker-order states — no further transitions (except identity no-op).
LIVE_ORDER_TERMINAL_STATES: frozenset[BrokerOrderStateKind] = frozenset(
    {
        BrokerOrderStateKind.FILLED,
        BrokerOrderStateKind.CANCELLED,
        BrokerOrderStateKind.REJECTED,
        BrokerOrderStateKind.EXPIRED,
    }
)

# States that may only advance after explicit reconciliation / operator resume.
LIVE_ORDER_RECONCILE_REQUIRED_STATES: frozenset[BrokerOrderStateKind] = frozenset(
    {
        BrokerOrderStateKind.SUBMISSION_STATUS_UNKNOWN,
        BrokerOrderStateKind.UNKNOWN,
    }
)

# Allowed transitions for Live readiness modeling. Replace is intentionally
# absent (BUILD 28: replace/order-modification not certified).
VALID_LIVE_ORDER_TRANSITIONS: dict[BrokerOrderStateKind, frozenset[BrokerOrderStateKind]] = {
    BrokerOrderStateKind.CREATED: frozenset(
        {
            BrokerOrderStateKind.DRY_RUN_VALIDATED,
            BrokerOrderStateKind.REJECTED,
        }
    ),
    BrokerOrderStateKind.DRY_RUN_VALIDATED: frozenset(
        {
            BrokerOrderStateKind.SUBMISSION_PENDING,
            BrokerOrderStateKind.REJECTED,
            BrokerOrderStateKind.EXPIRED,
        }
    ),
    # SUBMISSION_PENDING is a modeled local intent only. Real network submit is
    # refused by LiveOrderSafetyMachine.attempt_network_submit.
    BrokerOrderStateKind.SUBMISSION_PENDING: frozenset(
        {
            BrokerOrderStateKind.ACKNOWLEDGED,
            BrokerOrderStateKind.SUBMISSION_STATUS_UNKNOWN,
            BrokerOrderStateKind.REJECTED,
            BrokerOrderStateKind.CANCEL_PENDING,
        }
    ),
    BrokerOrderStateKind.SUBMISSION_STATUS_UNKNOWN: frozenset(
        {
            BrokerOrderStateKind.ACKNOWLEDGED,
            BrokerOrderStateKind.REJECTED,
            BrokerOrderStateKind.CANCELLED,
            BrokerOrderStateKind.UNKNOWN,
        }
    ),
    BrokerOrderStateKind.ACKNOWLEDGED: frozenset(
        {
            BrokerOrderStateKind.OPEN,
            BrokerOrderStateKind.PARTIALLY_FILLED,
            BrokerOrderStateKind.FILLED,
            BrokerOrderStateKind.CANCEL_PENDING,
            BrokerOrderStateKind.REJECTED,
            BrokerOrderStateKind.EXPIRED,
            BrokerOrderStateKind.UNKNOWN,
        }
    ),
    BrokerOrderStateKind.OPEN: frozenset(
        {
            BrokerOrderStateKind.PARTIALLY_FILLED,
            BrokerOrderStateKind.FILLED,
            BrokerOrderStateKind.CANCEL_PENDING,
            BrokerOrderStateKind.REJECTED,
            BrokerOrderStateKind.EXPIRED,
            BrokerOrderStateKind.UNKNOWN,
        }
    ),
    BrokerOrderStateKind.PARTIALLY_FILLED: frozenset(
        {
            BrokerOrderStateKind.FILLED,
            BrokerOrderStateKind.CANCEL_PENDING,
            BrokerOrderStateKind.EXPIRED,
            BrokerOrderStateKind.UNKNOWN,
        }
    ),
    BrokerOrderStateKind.CANCEL_PENDING: frozenset(
        {
            BrokerOrderStateKind.CANCELLED,
            BrokerOrderStateKind.PARTIALLY_FILLED,
            BrokerOrderStateKind.FILLED,
            BrokerOrderStateKind.REJECTED,
            BrokerOrderStateKind.UNKNOWN,
        }
    ),
    BrokerOrderStateKind.UNKNOWN: frozenset(
        {
            BrokerOrderStateKind.ACKNOWLEDGED,
            BrokerOrderStateKind.OPEN,
            BrokerOrderStateKind.PARTIALLY_FILLED,
            BrokerOrderStateKind.FILLED,
            BrokerOrderStateKind.CANCELLED,
            BrokerOrderStateKind.REJECTED,
            BrokerOrderStateKind.EXPIRED,
        }
    ),
}


def validate_live_order_transition(
    *,
    prior_state: BrokerOrderStateKind,
    next_state: BrokerOrderStateKind,
) -> None:
    """Fail closed on illegal Live order lifecycle transitions."""
    if prior_state == next_state:
        return
    if prior_state in LIVE_ORDER_TERMINAL_STATES:
        raise ValueError(f"LIVE_ORDER_TRANSITION_FROM_TERMINAL: {prior_state.value}")
    allowed = VALID_LIVE_ORDER_TRANSITIONS.get(prior_state, frozenset())
    if next_state not in allowed:
        raise ValueError(
            f"LIVE_ORDER_TRANSITION_INVALID: {prior_state.value} -> {next_state.value}"
        )


@dataclass
class LiveOrderSafetyMachine:
    """In-process Live order lifecycle that cannot transmit to a broker.

    Advancement models acknowledgement / fill / cancel / reject / disconnect
    evidence only. ``attempt_network_submit`` always raises
    ``LiveSubmitForbiddenError``.
    """

    client_order_id: str
    state: BrokerOrderStateKind = BrokerOrderStateKind.CREATED
    filled_quantity: int = 0
    order_quantity: int = 0
    reconcile_required: bool = False
    restart_blocked: bool = False
    audit_trail: list[tuple[str, BrokerOrderStateKind, BrokerOrderStateKind]] = field(
        default_factory=list
    )

    def advance(
        self,
        next_state: BrokerOrderStateKind,
        *,
        event: str,
        filled_delta: int = 0,
    ) -> BrokerOrderStateKind:
        if self.restart_blocked:
            raise ValueError("LIVE_ORDER_RESTART_BLOCKED_UNTIL_OPERATOR_RESUME")
        if self.reconcile_required and next_state not in {
            BrokerOrderStateKind.ACKNOWLEDGED,
            BrokerOrderStateKind.OPEN,
            BrokerOrderStateKind.PARTIALLY_FILLED,
            BrokerOrderStateKind.FILLED,
            BrokerOrderStateKind.CANCELLED,
            BrokerOrderStateKind.REJECTED,
            BrokerOrderStateKind.EXPIRED,
            BrokerOrderStateKind.UNKNOWN,
        }:
            raise ValueError("LIVE_ORDER_RECONCILE_REQUIRED")
        validate_live_order_transition(prior_state=self.state, next_state=next_state)
        if filled_delta < 0:
            raise ValueError("LIVE_ORDER_FILL_DELTA_INVALID")
        # Claimed fill/partial transitions must enforce quantity consistency even
        # when filled_delta is 0 (truthy-only guards previously skipped that edge).
        claimed_fill_or_partial = next_state in {
            BrokerOrderStateKind.PARTIALLY_FILLED,
            BrokerOrderStateKind.FILLED,
        }
        if filled_delta or claimed_fill_or_partial:
            if self.order_quantity <= 0:
                raise ValueError("LIVE_ORDER_QUANTITY_UNKNOWN")
            prospective_filled = self.filled_quantity + filled_delta
            if prospective_filled > self.order_quantity:
                raise ValueError("LIVE_ORDER_OVERFILL")
            if (
                next_state == BrokerOrderStateKind.PARTIALLY_FILLED
                and prospective_filled >= self.order_quantity
            ):
                raise ValueError("LIVE_ORDER_PARTIAL_MUST_BE_STRICT")
            if (
                next_state == BrokerOrderStateKind.FILLED
                and prospective_filled != self.order_quantity
            ):
                raise ValueError("LIVE_ORDER_FILL_QUANTITY_MISMATCH")
            self.filled_quantity = prospective_filled
        prior = self.state
        self.state = next_state
        if next_state in LIVE_ORDER_RECONCILE_REQUIRED_STATES:
            self.reconcile_required = True
        elif next_state in {
            BrokerOrderStateKind.ACKNOWLEDGED,
            BrokerOrderStateKind.OPEN,
            BrokerOrderStateKind.PARTIALLY_FILLED,
            BrokerOrderStateKind.FILLED,
            BrokerOrderStateKind.CANCELLED,
            BrokerOrderStateKind.REJECTED,
            BrokerOrderStateKind.EXPIRED,
        }:
            self.reconcile_required = False
        self.audit_trail.append((event, prior, next_state))
        return self.state

    def record_disconnect(self, *, event: str = "disconnect") -> BrokerOrderStateKind:
        """Disconnect: open-ish states become UNKNOWN and block blind resubmit."""
        if self.state in LIVE_ORDER_TERMINAL_STATES:
            return self.state
        if self.state in {
            BrokerOrderStateKind.CREATED,
            BrokerOrderStateKind.DRY_RUN_VALIDATED,
        }:
            # Never submitted — stay local; mark reconcile so resume is explicit.
            self.reconcile_required = True
            self.audit_trail.append((event, self.state, self.state))
            return self.state
        return self.advance(BrokerOrderStateKind.UNKNOWN, event=event)

    def restore_after_restart(
        self,
        *,
        state: BrokerOrderStateKind,
        filled_quantity: int = 0,
        order_quantity: int = 0,
    ) -> None:
        """Restart restore: rebuild local view and refuse auto-submit."""
        self.state = state
        self.filled_quantity = filled_quantity
        self.order_quantity = order_quantity
        self.reconcile_required = state in LIVE_ORDER_RECONCILE_REQUIRED_STATES or state not in {
            BrokerOrderStateKind.CREATED,
            BrokerOrderStateKind.DRY_RUN_VALIDATED,
        }
        self.restart_blocked = True
        self.audit_trail.append(("restart_restore", state, state))

    def operator_resume_after_restart(self) -> None:
        """Clear restart block only; does not authorize Live submit."""
        self.restart_blocked = False
        self.audit_trail.append(("operator_resume", self.state, self.state))

    def attempt_network_submit(self) -> None:
        """Always refuse — Live remains OFF / BUILD 28 zero-submit."""
        raise LiveSubmitForbiddenError(
            f"BUILD28_ZERO_SUBMIT_VIOLATION:place_order:{self.client_order_id}:{self.state.value}"
        )
