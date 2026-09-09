"""IBKR subscription registry and lifecycle (G6).

Owns the reqId ↔ canonical subscription mapping, idempotent subscribe/cancel,
generation identity, and disconnect/reconnect bookkeeping. All mutations are
performed under the owning adapter's lock.

Generation semantics: every (re)subscribe to the same canonical subscription
identity creates a NEW generation and a NEW subscription id. Callbacks carry
the subscription id in the canonical events, so the G5 engine's generation
gate rejects late old-generation callbacks (GENERATION_MISMATCH).
"""

from __future__ import annotations

import threading
from typing import Any, Iterable

from .contracts import (
    CapabilityKind,
    EntitlementState,
    IbkrConnectionState,
    IbkrErrorCategory,
    IbkrProviderError,
    IbkrSubscriptionRecord,
    IbkrSubscriptionState,
    PacingReport,
)


class UnknownReqIdError(ValueError):
    """Raised when a callback references a reqId with no subscription."""


class SubscriptionAlreadyActive(ValueError):
    """Raised when an idempotent subscribe returns the existing record."""


class SubscriptionCapExceeded(ValueError):
    """Raised when a local subscription cap rejects the request."""


class SubscriptionRegistry:
    """reqId / subscription-id / instrument-key → record registry."""

    def __init__(self) -> None:
        self._by_req_id: dict[int, IbkrSubscriptionRecord] = {}
        self._by_subscription_id: dict[str, IbkrSubscriptionRecord] = {}
        self._by_instrument_key: dict[str, IbkrSubscriptionRecord] = {}
        self._lock = threading.RLock()

    def _instrument_key(self, instrument_id: str, capability: CapabilityKind) -> str:
        return f"{instrument_id.upper()}:{capability.value}"

    def put(self, record: IbkrSubscriptionRecord) -> None:
        with self._lock:
            self._by_req_id[record.req_id] = record
            self._by_subscription_id[record.subscription_id] = record
            self._by_instrument_key[self._instrument_key(record.instrument_id, record.capability)] = record

    def get_by_req_id(self, req_id: int) -> IbkrSubscriptionRecord | None:
        with self._lock:
            return self._by_req_id.get(req_id)

    def require_by_req_id(self, req_id: int) -> IbkrSubscriptionRecord:
        record = self.get_by_req_id(req_id)
        if record is None:
            raise UnknownReqIdError(f"callback references unknown req_id {req_id}")
        return record

    def get_by_subscription_id(self, subscription_id: str) -> IbkrSubscriptionRecord | None:
        with self._lock:
            return self._by_subscription_id.get(subscription_id)

    def get_by_instrument(
        self, instrument_id: str, capability: CapabilityKind
    ) -> IbkrSubscriptionRecord | None:
        with self._lock:
            return self._by_instrument_key.get(
                self._instrument_key(instrument_id, capability)
            )

    def remove(self, record: IbkrSubscriptionRecord) -> None:
        with self._lock:
            self._by_req_id.pop(record.req_id, None)
            self._by_subscription_id.pop(record.subscription_id, None)
            key = self._instrument_key(record.instrument_id, record.capability)
            if self._by_instrument_key.get(key) is record:
                self._by_instrument_key.pop(key, None)

    def active_records(self) -> tuple[IbkrSubscriptionRecord, ...]:
        with self._lock:
            return tuple(self._by_subscription_id.values())

    def records_for_generation(self, generation: int) -> tuple[IbkrSubscriptionRecord, ...]:
        with self._lock:
            return tuple(
                record
                for record in self._by_subscription_id.values()
                if record.generation == generation
            )

    def counts(self) -> PacingReport:
        """Active subscription counts by capability (CANCELLED/FAILED excluded)."""
        active = [
            record
            for record in self._by_subscription_id.values()
            if record.state
            not in (IbkrSubscriptionState.CANCELLED, IbkrSubscriptionState.FAILED)
        ]
        l1 = sum(1 for record in active if record.capability is CapabilityKind.L1)
        l2 = sum(1 for record in active if record.capability is CapabilityKind.L2)
        trades = sum(1 for record in active if record.capability is CapabilityKind.TRADES)
        return PacingReport(active_l1=l1, active_l2=l2, active_trades=trades)


class IbkrLifecycle:
    """Lifecycle policy over a :class:`SubscriptionRegistry`."""

    def __init__(
        self,
        registry: SubscriptionRegistry,
        *,
        connection_state: IbkrConnectionState = IbkrConnectionState.DISCONNECTED,
        connection_identity: str = "tws",
    ) -> None:
        self.registry = registry
        self.connection_state = connection_state
        self.connection_identity = connection_identity
        self.connection_generation: int = 0
        self.reconnect_count: int = 0
        self.reset_count: int = 0
        self.last_error: IbkrProviderError | None = None
        self.last_received_ns: int | None = None
        self._lock = threading.RLock()

    def mark_connecting(self) -> None:
        with self._lock:
            self.connection_state = IbkrConnectionState.CONNECTING

    def mark_connected(self, *, advance_generation: bool = False) -> None:
        with self._lock:
            if advance_generation:
                self.connection_generation += 1
                self.reconnect_count += 1
            self.connection_state = IbkrConnectionState.CONNECTED
            self.last_error = None

    def mark_degraded(self, reason: str) -> None:
        with self._lock:
            self.connection_state = IbkrConnectionState.DEGRADED
            self.last_error = IbkrProviderError(
                code=None,
                message=reason,
                category=IbkrErrorCategory.INTERNAL_PROVIDER,
            )

    def mark_disconnected(self, *, reason: str | None = None) -> None:
        with self._lock:
            self.connection_state = IbkrConnectionState.DISCONNECTED
            if reason:
                from .errors import normalize_provider_error

                self.last_error = normalize_provider_error(code=None, message=reason)

    def mark_failed(self, error: IbkrProviderError) -> None:
        with self._lock:
            self.connection_state = IbkrConnectionState.FAILED
            self.last_error = error

    def record_received(self, received_ns: int) -> None:
        with self._lock:
            self.last_received_ns = received_ns

    def diagnostics_subscriptions(self) -> dict[str, dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for record in self.registry.active_records():
            rows[record.subscription_id] = record.as_dict()
        return rows


__all__ = [
    "IbkrLifecycle",
    "SubscriptionAlreadyActive",
    "SubscriptionCapExceeded",
    "SubscriptionRegistry",
    "UnknownReqIdError",
]