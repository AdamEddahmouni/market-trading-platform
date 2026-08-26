"""Zero-submit dry-run execution transport (BUILD 28)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from .broker_inventory import LIVE_SUBMIT_OPERATIONS
from .identity import derive_payload_hash
from .translation import translate_broker_payload
from .types import (
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    BrokerOrderIntentV1,
    BrokerOrderStateKind,
    DryRunTransportResultV1,
)


class LiveSubmitForbiddenError(AssertionError):
    """Raised when any real broker submit operation is attempted in BUILD 28."""


@dataclass
class ZeroSubmitGuard:
    """Global counter and interceptor for real broker submit operations."""

    real_submit_count: int = 0
    real_cancel_count: int = 0
    real_replace_count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_submit(self, operation: str) -> None:
        with self._lock:
            if operation in ("place_order", "submit_order"):
                self.real_submit_count += 1
                raise LiveSubmitForbiddenError(f"BUILD28_ZERO_SUBMIT_VIOLATION:{operation}")
            if operation == "cancel_order":
                self.real_cancel_count += 1
                raise LiveSubmitForbiddenError(f"BUILD28_ZERO_SUBMIT_VIOLATION:{operation}")
            if operation in ("modify_order", "replace_order"):
                self.real_replace_count += 1
                raise LiveSubmitForbiddenError(f"BUILD28_ZERO_SUBMIT_VIOLATION:{operation}")

    def assert_zero(self) -> None:
        with self._lock:
            total = self.real_submit_count + self.real_cancel_count + self.real_replace_count
            if total != 0:
                raise AssertionError(
                    f"BUILD28_ZERO_SUBMIT_VIOLATION: submits={self.real_submit_count} "
                    f"cancels={self.real_cancel_count} replaces={self.real_replace_count}"
                )


GLOBAL_ZERO_SUBMIT_GUARD = ZeroSubmitGuard()


class DryRunExecutionAdapter:
    """Accepts broker payload, validates schema, records hash, never transmits."""

    def __init__(self, *, guard: ZeroSubmitGuard | None = None) -> None:
        self._guard = guard or GLOBAL_ZERO_SUBMIT_GUARD
        self._recorded_payloads: list[dict[str, Any]] = []

    @property
    def recorded_payloads(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._recorded_payloads)

    def validate_and_record(
        self,
        intent: BrokerOrderIntentV1,
        *,
        broker_symbol: str,
        decision_time_ns: int,
    ) -> DryRunTransportResultV1:
        payload, payload_hash = translate_broker_payload(
            intent,
            broker_symbol=broker_symbol,
            decision_time_ns=decision_time_ns,
        )
        self._validate_payload(payload, intent=intent)
        self._recorded_payloads.append(payload)
        return DryRunTransportResultV1(
            result_id=derive_payload_hash({"client_order_id": intent.client_order_id, "hash": payload_hash}),
            schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
            broker=intent.broker_target,
            client_order_id=intent.client_order_id,
            payload_hash=payload_hash,
            provider_payload=payload,
            network_submit_performed=False,
            real_submit_count=0,
            broker_order_state=BrokerOrderStateKind.DRY_RUN_VALIDATED,
            reason_codes=("DRY_RUN_VALIDATED",),
        )

    def simulate_ambiguous_submission(
        self,
        intent: BrokerOrderIntentV1,
        *,
        broker_symbol: str,
        decision_time_ns: int,
    ) -> DryRunTransportResultV1:
        """Model timeout-after-possible-send without resubmitting."""
        payload, payload_hash = translate_broker_payload(
            intent,
            broker_symbol=broker_symbol,
            decision_time_ns=decision_time_ns,
        )
        return DryRunTransportResultV1(
            result_id=derive_payload_hash({"ambiguous": intent.client_order_id}),
            schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
            broker=intent.broker_target,
            client_order_id=intent.client_order_id,
            payload_hash=payload_hash,
            provider_payload=payload,
            network_submit_performed=False,
            real_submit_count=0,
            broker_order_state=BrokerOrderStateKind.SUBMISSION_STATUS_UNKNOWN,
            reason_codes=("RECONCILE_REQUIRED", "NO_BLIND_RESUBMIT"),
        )

    def _validate_payload(self, payload: dict[str, Any], *, intent: BrokerOrderIntentV1) -> None:
        if "client_order_id" not in payload and "client_order_id" not in str(payload):
            raise ValueError("PAYLOAD_MISSING_CLIENT_ORDER_ID")
        qty = payload.get("quantity") or payload.get("qty")
        if qty is not None and int(qty) != intent.quantity:
            raise ValueError("PAYLOAD_QUANTITY_MUTATION")
        side = payload.get("side") or payload.get("trd_side")
        if side is not None:
            normalized = str(side).upper()
            if normalized in {"BUY", "SELL"} and normalized != intent.side:
                raise ValueError("PAYLOAD_SIDE_MUTATION")
