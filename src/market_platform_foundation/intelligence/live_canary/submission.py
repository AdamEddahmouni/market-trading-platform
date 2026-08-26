"""Mock/sandbox broker submission with exactly-once semantics (BUILD 29)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..live_execution_safety.identity import derive_payload_hash
from ..live_execution_safety.translation import translate_broker_payload
from ..live_execution_safety.types import BrokerOrderIntentV1, BrokerOrderStateKind
from .identity import derive_fill_receipt_id, derive_submission_receipt_id
from .types import (
    LIVE_CANARY_SCHEMA_VERSION,
    BrokerSubmissionReceiptV1,
    LiveFillReceiptV1,
    SubmissionState,
)


@dataclass
class MockBrokerAck:
    broker_order_id: str
    client_order_id: str
    symbol: str
    side: str
    quantity: int
    order_type: str
    ack_time_ns: int


@dataclass
class MockBrokerFill:
    broker_fill_id: str
    broker_order_id: str
    client_order_id: str
    quantity: int
    price_minor: int
    fill_time_ns: int
    fees_minor: int = 0


@dataclass
class MockBrokerTransport:
    """In-memory mock transport — no real network."""

    submitted: dict[str, BrokerSubmissionReceiptV1] = field(default_factory=dict)
    ambiguous: set[str] = field(default_factory=set)
    acks: dict[str, MockBrokerAck] = field(default_factory=dict)
    fills: list[MockBrokerFill] = field(default_factory=list)
    simulate_ambiguous: bool = False
    simulate_disconnect: bool = False

    def submit(
        self,
        *,
        order_intent: BrokerOrderIntentV1,
        authorization_ref: str,
        confirmation_ref: str,
        submit_time_ns: int,
    ) -> BrokerSubmissionReceiptV1:
        if self.simulate_disconnect:
            raise ConnectionError("BROKER_DISCONNECTED")

        payload, payload_hash = translate_broker_payload(
            order_intent,
            broker_symbol=order_intent.instrument_id.replace("inst-", "").upper(),
            decision_time_ns=submit_time_ns,
        )

        if order_intent.client_order_id in self.submitted:
            existing = self.submitted[order_intent.client_order_id]
            return existing

        if order_intent.client_order_id in self.ambiguous:
            receipt = BrokerSubmissionReceiptV1(
                submission_receipt_id="",
                schema_version=LIVE_CANARY_SCHEMA_VERSION,
                order_intent_ref=order_intent.broker_order_intent_id,
                authorization_ref=authorization_ref,
                confirmation_ref=confirmation_ref,
                client_order_id=order_intent.client_order_id,
                broker=order_intent.broker_target,
                account_ref="mock-account",
                submit_attempt_time_ns=submit_time_ns,
                payload_hash=payload_hash,
                transport_result="UNKNOWN",
                broker_order_id=None,
                ack_time_ns=None,
                raw_response_hash=None,
                submission_state=SubmissionState.SUBMISSION_STATUS_UNKNOWN,
            )
            object.__setattr__(receipt, "submission_receipt_id", derive_submission_receipt_id(receipt))
            self.submitted[order_intent.client_order_id] = receipt
            return receipt

        if self.simulate_ambiguous:
            self.ambiguous.add(order_intent.client_order_id)
            receipt = BrokerSubmissionReceiptV1(
                submission_receipt_id="",
                schema_version=LIVE_CANARY_SCHEMA_VERSION,
                order_intent_ref=order_intent.broker_order_intent_id,
                authorization_ref=authorization_ref,
                confirmation_ref=confirmation_ref,
                client_order_id=order_intent.client_order_id,
                broker=order_intent.broker_target,
                account_ref="mock-account",
                submit_attempt_time_ns=submit_time_ns,
                payload_hash=payload_hash,
                transport_result="TIMEOUT",
                broker_order_id=None,
                ack_time_ns=None,
                raw_response_hash=derive_payload_hash({"timeout": True}),
                submission_state=SubmissionState.SUBMISSION_STATUS_UNKNOWN,
            )
            object.__setattr__(receipt, "submission_receipt_id", derive_submission_receipt_id(receipt))
            self.submitted[order_intent.client_order_id] = receipt
            return receipt

        broker_order_id = f"BRK-{order_intent.client_order_id[-12:]}"
        ack = MockBrokerAck(
            broker_order_id=broker_order_id,
            client_order_id=order_intent.client_order_id,
            symbol=order_intent.instrument_id,
            side=order_intent.side,
            quantity=order_intent.quantity,
            order_type=order_intent.order_type,
            ack_time_ns=submit_time_ns + 1_000_000,
        )
        self.acks[broker_order_id] = ack

        receipt = BrokerSubmissionReceiptV1(
            submission_receipt_id="",
            schema_version=LIVE_CANARY_SCHEMA_VERSION,
            order_intent_ref=order_intent.broker_order_intent_id,
            authorization_ref=authorization_ref,
            confirmation_ref=confirmation_ref,
            client_order_id=order_intent.client_order_id,
            broker=order_intent.broker_target,
            account_ref="mock-account",
            submit_attempt_time_ns=submit_time_ns,
            payload_hash=payload_hash,
            transport_result="ACK",
            broker_order_id=broker_order_id,
            ack_time_ns=ack.ack_time_ns,
            raw_response_hash=derive_payload_hash({"broker_order_id": broker_order_id}),
            submission_state=SubmissionState.ACKNOWLEDGED,
        )
        object.__setattr__(receipt, "submission_receipt_id", derive_submission_receipt_id(receipt))
        self.submitted[order_intent.client_order_id] = receipt
        return receipt

    def resubmit_blocked(self, client_order_id: str) -> bool:
        """Blind resubmit must be blocked for ambiguous or existing submissions."""
        if client_order_id in self.ambiguous:
            return True
        return client_order_id in self.submitted

    def apply_fill(
        self,
        *,
        broker_order_id: str,
        quantity: int,
        price_minor: int,
        fill_time_ns: int,
    ) -> LiveFillReceiptV1 | None:
        ack = self.acks.get(broker_order_id)
        if ack is None:
            return None
        fill = MockBrokerFill(
            broker_fill_id=f"FILL-{broker_order_id}",
            broker_order_id=broker_order_id,
            client_order_id=ack.client_order_id,
            quantity=quantity,
            price_minor=price_minor,
            fill_time_ns=fill_time_ns,
        )
        self.fills.append(fill)
        receipt = LiveFillReceiptV1(
            fill_receipt_id="",
            schema_version=LIVE_CANARY_SCHEMA_VERSION,
            broker_order_id=broker_order_id,
            client_order_id=ack.client_order_id,
            broker_fill_id=fill.broker_fill_id,
            fill_time_ns=fill_time_ns,
            quantity=quantity,
            price_minor=price_minor,
            fees_minor=0,
            liquidity_metadata={},
            source="MOCK_BROKER",
        )
        object.__setattr__(receipt, "fill_receipt_id", derive_fill_receipt_id(receipt))
        return receipt

    def reconcile_ack(self, receipt: BrokerSubmissionReceiptV1) -> tuple[bool, tuple[str, ...]]:
        if receipt.submission_state == SubmissionState.SUBMISSION_STATUS_UNKNOWN:
            return False, ("AMBIGUOUS_SUBMISSION",)
        if receipt.broker_order_id is None:
            return False, ("NO_BROKER_ORDER_ID",)
        ack = self.acks.get(receipt.broker_order_id)
        if ack is None:
            return False, ("UNKNOWN_BROKER_ORDER",)
        mismatches: list[str] = []
        if ack.client_order_id != receipt.client_order_id:
            mismatches.append("CLIENT_ORDER_ID_MISMATCH")
        return len(mismatches) == 0, tuple(mismatches)
