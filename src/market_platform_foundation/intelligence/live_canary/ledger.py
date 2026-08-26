"""Immutable live execution ledger (BUILD 29)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..live_execution_safety.types import BrokerOrderStateKind
from .types import BrokerSubmissionReceiptV1, LiveFillReceiptV1


@dataclass
class LiveExecutionLedger:
    """Append-only live execution evidence — separate from PAPER ledger."""

    submission_receipts: list[BrokerSubmissionReceiptV1] = field(default_factory=list)
    fill_receipts: list[LiveFillReceiptV1] = field(default_factory=list)
    order_states: list[tuple[str, BrokerOrderStateKind, int]] = field(default_factory=list)
    ambiguous_client_order_ids: set[str] = field(default_factory=set)
    orders_submitted: int = 0
    total_notional_minor: int = 0

    def record_submission(self, receipt: BrokerSubmissionReceiptV1) -> None:
        if any(r.client_order_id == receipt.client_order_id for r in self.submission_receipts):
            return
        self.submission_receipts.append(receipt)
        self.orders_submitted += 1
        if receipt.submission_state.value == "SUBMISSION_STATUS_UNKNOWN":
            self.ambiguous_client_order_ids.add(receipt.client_order_id)
            self.order_states.append(
                (receipt.client_order_id, BrokerOrderStateKind.SUBMISSION_STATUS_UNKNOWN, receipt.submit_attempt_time_ns)
            )
        elif receipt.broker_order_id:
            self.order_states.append(
                (receipt.client_order_id, BrokerOrderStateKind.ACKNOWLEDGED, receipt.ack_time_ns or receipt.submit_attempt_time_ns)
            )

    def record_fill(self, fill: LiveFillReceiptV1) -> None:
        known_orders = {r.broker_order_id for r in self.submission_receipts if r.broker_order_id}
        if fill.broker_order_id not in known_orders:
            raise ValueError("UNEXPECTED_FILL")
        if any(f.broker_fill_id == fill.broker_fill_id for f in self.fill_receipts):
            return
        self.fill_receipts.append(fill)
        self.total_notional_minor += fill.quantity * fill.price_minor
        self.order_states.append(
            (fill.client_order_id, BrokerOrderStateKind.FILLED, fill.fill_time_ns)
        )

    def has_ambiguous_submission(self, client_order_id: str) -> bool:
        return client_order_id in self.ambiguous_client_order_ids

    def restore_from_persistence(
        self,
        *,
        receipts: list[BrokerSubmissionReceiptV1],
        fills: list[LiveFillReceiptV1],
    ) -> None:
        """Restart safety — restore state without auto-submit."""
        self.submission_receipts = list(receipts)
        self.fill_receipts = list(fills)
        self.orders_submitted = len(receipts)
        self.ambiguous_client_order_ids = {
            r.client_order_id
            for r in receipts
            if r.submission_state.value == "SUBMISSION_STATUS_UNKNOWN"
        }
        self.total_notional_minor = sum(f.quantity * f.price_minor for f in fills)
