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
        filled_qty = self.filled_quantity_for_order(fill.broker_order_id)
        order_qty = self.order_quantity_for(fill.broker_order_id)
        if order_qty is not None and filled_qty >= order_qty:
            state = BrokerOrderStateKind.FILLED
        else:
            state = BrokerOrderStateKind.PARTIALLY_FILLED
        self.order_states.append(
            (fill.client_order_id, state, fill.fill_time_ns)
        )

    def filled_quantity_for_order(self, broker_order_id: str) -> int:
        return sum(
            f.quantity
            for f in self.fill_receipts
            if f.broker_order_id == broker_order_id
        )

    def order_quantity_for(self, broker_order_id: str) -> int | None:
        for receipt in self.submission_receipts:
            if receipt.broker_order_id == broker_order_id:
                meta = receipt.metadata.get("order_quantity")
                if meta is not None:
                    return int(meta)
        return None

    def remaining_quantity_for(self, broker_order_id: str, total_quantity: int) -> int:
        return max(0, total_quantity - self.filled_quantity_for_order(broker_order_id))

    def get_open_local_orders(self) -> tuple[str, ...]:
        open_ids: list[str] = []
        for receipt in self.submission_receipts:
            if not receipt.broker_order_id:
                open_ids.append(receipt.client_order_id)
                continue
            filled = self.filled_quantity_for_order(receipt.broker_order_id)
            total = int(receipt.metadata.get("order_quantity", 0))
            if total <= 0 or filled < total:
                open_ids.append(receipt.client_order_id)
        return tuple(open_ids)

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
