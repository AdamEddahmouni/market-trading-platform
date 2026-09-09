"""Canonical IBKR observational L1/L2 adapter (G6).

Transport-agnostic adapter owning IBKR callback decoding, reqId ↔ canonical
subscription mapping, position/rank translation, L1 accumulation, entitlement
normalization, pacing, and reconnect/generation lifecycle. The canonical book
engine stays the single authoritative book state; this adapter only ever
produces canonical facts (``DepthUpdate`` / ``L1QuoteFacts``) and applies
them to the ``ObservationalStateStore``.

Safety boundary: the adapter exposes NO execution capability. The transport
protocol is observational only (``req_mkt_data`` / ``req_mkt_depth`` /
cancels); no order/account methods exist on any public surface, and the
adapter cannot construct trading authority.

Offline gate: with ``live_enabled=False``, ``connect``/``subscribe_*`` raise
before any transport I/O. Callback *entry points* and replay registration
remain available offline (they perform no network operations) so capture →
replay is provable without a live IBKR session.
"""

from __future__ import annotations

import ipaddress
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol, Sequence

from ...clock import monotonic_wall_ns
from ...order_flow.order_book.contracts import (
    ApplyOutcome,
    ApplyResult,
    DepthOperation,
    DepthSide,
    DepthUpdate,
    build_depth_update,
)
from .contracts import (
    CapabilityKind,
    DepthTranslationOutcome,
    EntitlementState,
    IbkrConnectionState,
    IbkrErrorCategory,
    IbkrProviderError,
    IbkrSubscriptionRecord,
    IbkrSubscriptionState,
    L1QuoteFacts,
)
from .capture import (
    CallbackCapture,
    capture_depth_callback,
    capture_error_record,
    capture_tick_callback,
    capture_trade_callback,
)
from .constants import (
    ERROR_CODE_1100_CONNECTIVITY_LOST,
    ERROR_CODE_1101_RESTORED_DATA_LOST,
    ERROR_CODE_316_DEPTH_HALTED,
    ERROR_CODE_317_DEPTH_RESET,
)
from .diagnostics import (
    CapabilityReadiness,
    ReadinessState,
    book_facts,
    build_diagnostics,
    compute_readiness,
)
from .identity import (
    AdmittedInstrument,
    IdentityAdmissionError,
    InstrumentLookup,
    Xa01Admission,
)
from .l1 import L1Accumulator
from .lifecycle import (
    IbkrLifecycle,
    SubscriptionRegistry,
    UnknownReqIdError,
)
from .pacing import LocalPacingState, SubscriptionCapPolicy
from .rank import (
    SubscriptionRankState,
    translate_depth_callback,
)
from .trades import QuoteContext, classify_trade_print, facts_from_tick_by_tick_all_last


class IbkrOfflineError(RuntimeError):
    """Raised before any transport I/O when live observations are disabled."""


class IbkrTransport(Protocol):
    """Observational-only transport surface (implemented by tools/ibkr or a fake).

    No order/account/execution method exists on this protocol — the adapter
    cannot reach trading authority through it.
    """

    def connect(self, *, host: str, port: int, client_id: int, readonly: bool = True) -> None: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...
    def req_mkt_data(self, req_id: int, contract: Any, *, generic_ticks: str = "", snapshot: bool = False) -> None: ...
    def cancel_mkt_data(self, req_id: int) -> None: ...
    def req_mkt_depth(self, req_id: int, contract: Any, *, num_rows: int, is_smart_depth: bool = False) -> None: ...
    def cancel_mkt_depth(self, req_id: int, *, is_smart_depth: bool = False) -> None: ...
    def req_tick_by_tick_data(
        self, req_id: int, contract: Any, *, tick_type: str = "AllLast", number_of_ticks: int = 0, ignore_size: bool = False
    ) -> None: ...
    def cancel_tick_by_tick_data(self, req_id: int) -> None: ...


@dataclass(frozen=True, slots=True)
class IbkrObservationalConfig:
    live_enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 4001
    client_id: int = 37
    readonly: bool = True
    provider: str = "IBKR"
    connection_identity: str = "tws"
    default_depth_levels: int = 20
    max_l1_subscriptions: int = 50
    max_l2_subscriptions: int = 20
    max_trades_subscriptions: int = 20
    max_reconnect_attempts: int = 3
    capture_path: str | None = None

    def __post_init__(self) -> None:
        host = self.host.strip().lower()
        if host != "localhost":
            try:
                if not ipaddress.ip_address(host).is_loopback:
                    raise ValueError("host must be loopback")
            except ValueError as exc:
                raise ValueError(f"IBKR host must be a loopback address: {self.host!r}") from exc
        if self.port not in {4001, 4002}:
            raise ValueError(f"IBKR TWS port must be 4001 or 4002: {self.port!r}")
        if self.client_id <= 0:
            raise ValueError("IBKR client_id must be positive")
        if self.default_depth_levels < 3 or self.default_depth_levels > 60:
            raise ValueError("default_depth_levels must be within the IBKR floor/ceiling")


@dataclass(frozen=True, slots=True)
class CallbackResult:
    """Explicit result of one adapter callback (never inferred)."""

    accepted: bool
    kind: str
    events: tuple[DepthUpdate, ...] = ()
    apply_results: tuple[ApplyResult, ...] = ()
    quote_facts: L1QuoteFacts | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "events": [event.as_dict() for event in self.events],
            "kind": self.kind,
            "quote_facts": None if self.quote_facts is None else self.quote_facts.as_dict(),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class SubscribeResult:
    accepted: bool
    subscription_id: str
    req_id: int
    instrument_id: str
    capability: CapabilityKind
    reason: str | None = None
    generation: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "capability": self.capability.value,
            "generation": self.generation,
            "instrument_id": self.instrument_id,
            "reason": self.reason,
            "req_id": self.req_id,
            "subscription_id": self.subscription_id,
        }


class IbkrObservationalAdapter:
    """Canonical IBKR observational L1/L2 adapter (G6)."""

    provider = "IBKR"
    #: Capabilities this adapter may ever exercise. Execution is absent by
    #: construction; a static regression test proves the public surface.
    authorized_capabilities = frozenset(
        {"CONTRACT_RESOLUTION", "L1", "L2", "TRADES", "MARKET_DATA", "DEPTH"}
    )

    def __init__(
        self,
        config: IbkrObservationalConfig,
        *,
        transport: IbkrTransport,
        store: Any | None = None,
        admission: Xa01Admission | None = None,
        lookup: InstrumentLookup | None = None,
        capture: CallbackCapture | None = None,
        subscription_id_factory: Callable[[int, CapabilityKind, str], str] | None = None,
        now_ns: Callable[[], int] = monotonic_wall_ns,
        pacing: LocalPacingState | None = None,
    ) -> None:
        self.config = config
        self._transport = transport
        self.store = store
        self._admission = admission or Xa01Admission()
        self._lookup = lookup
        from pathlib import Path

        self._capture = capture or CallbackCapture(Path(config.capture_path) if config.capture_path else None)
        self._now = now_ns
        self._registry = SubscriptionRegistry()
        self._lifecycle = IbkrLifecycle(
            self._registry,
            connection_identity=config.connection_identity,
        )
        self._pacing = pacing or LocalPacingState(
            SubscriptionCapPolicy(
                max_l1=config.max_l1_subscriptions,
                max_l2=config.max_l2_subscriptions,
                max_trades=config.max_trades_subscriptions,
                min_depth_levels=3,
                max_depth_levels=config.default_depth_levels,
            )
        )
        self._subscription_id_factory = subscription_id_factory or self._default_subscription_id
        self._accumulators: dict[str, L1Accumulator] = {}
        self._rank_states: dict[str, SubscriptionRankState] = {}
        self._next_req_id = 1000
        self._subscription_seq = 0
        self._reset_count = 0
        self._prev_trade_prices: dict[str, float] = {}
        self._prev_trade_dirs: dict[str, float] = {}
        self._lock = threading.RLock()
        self._shutdown = False
        self._callbacks_dropped = 0
        self._callbacks_processed = 0

    # ------------------------------------------------------------------ ids

    def _default_subscription_id(self, seq: int, capability: CapabilityKind, instrument_id: str) -> str:
        return f"ibkr:{capability.value}:{seq}"

    def _next_subscription_id(self, capability: CapabilityKind, instrument_id: str) -> str:
        self._subscription_seq += 1
        return self._subscription_id_factory(self._subscription_seq, capability, instrument_id)

    def _allocate_req_id(self) -> int:
        self._next_req_id += 1
        return self._next_req_id - 1

    def _require_live(self) -> None:
        if not self.config.live_enabled:
            raise IbkrOfflineError(
                "IBKR observational live data is not enabled (offline mode)"
            )

    # --------------------------------------------------------------- connect

    def connect(self) -> None:
        """Connect the transport. Raises :class:`IbkrOfflineError` offline."""
        self._require_live()
        with self._lock:
            if self._shutdown:
                raise RuntimeError("adapter shutdown — connect rejected")
            self._lifecycle.mark_connecting()
            self._transport.connect(
                host=self.config.host,
                port=self.config.port,
                client_id=self.config.client_id,
                readonly=self.config.readonly,
            )
            self._lifecycle.mark_connected()

    def disconnect(self) -> None:
        with self._lock:
            self._lifecycle.mark_disconnected(reason="ADAPTER_DISCONNECT")
            for record in self._registry.active_records():
                if record.state not in (IbkrSubscriptionState.CANCELLED, IbkrSubscriptionState.FAILED):
                    record.mark_degraded("CONNECTION_LOST")
            self._transport.disconnect()

    def shutdown(self) -> None:
        """Idempotent graceful shutdown — safe to call repeatedly."""
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            for record in list(self._registry.active_records()):
                if record.state not in (IbkrSubscriptionState.CANCELLED, IbkrSubscriptionState.FAILED):
                    self._transport_cancel(record)
                    self._retire_record(record)
            self._lifecycle.mark_disconnected(reason="ADAPTER_SHUTDOWN")
            if self._transport.is_connected():
                self._transport.disconnect()

    def callback_metrics(self) -> dict[str, int]:
        return {
            "callbacks_dropped": self._callbacks_dropped,
            "callbacks_processed": self._callbacks_processed,
        }

    def handle_disconnect(self, reason: str) -> None:
        """Provider-driven disconnect (e.g. error 1100 / socket drop)."""
        with self._lock:
            self._lifecycle.mark_disconnected(reason=reason)
            for record in self._registry.active_records():
                if record.state not in (IbkrSubscriptionState.CANCELLED, IbkrSubscriptionState.FAILED):
                    record.mark_degraded("CONNECTION_LOST")

    def handle_reconnect(self) -> None:
        """New connection generation + resubscribe of authorized subscriptions.

        Old subscriptions are retired (their callbacks can no longer
        contaminate state: old reqIds are gone and new events carry new
        subscription ids, which the canonical engine's generation gate
        rejects when stale). No automatic retry loop; the operator drives
        reconnects, bounded by ``max_reconnect_attempts``.
        """
        with self._lock:
            if self._shutdown:
                return
            if not self.config.live_enabled:
                raise IbkrOfflineError("cannot reconnect while offline")
            if self._lifecycle.reconnect_count >= self.config.max_reconnect_attempts:
                self._lifecycle.mark_degraded("RECONNECT_ATTEMPTS_EXHAUSTED")
                return
            authorized = [
                record
                for record in self._registry.active_records()
                if record.state not in (IbkrSubscriptionState.CANCELLED, IbkrSubscriptionState.FAILED)
            ]
            for old in authorized:
                self._retire_record(old)
            self._lifecycle.mark_connected(advance_generation=True)
            self._transport.connect(
                host=self.config.host,
                port=self.config.port,
                client_id=self.config.client_id,
                readonly=self.config.readonly,
            )
            for old in authorized:
                self._resubscribe_record(old)

    def _retire_record(self, record: IbkrSubscriptionRecord) -> None:
        self._registry.remove(record)
        record.state = IbkrSubscriptionState.CANCELLED
        self._accumulators.pop(record.subscription_id, None)
        self._rank_states.pop(record.subscription_id, None)
        self._prev_trade_prices.pop(record.instrument_id, None)
        self._prev_trade_dirs.pop(record.instrument_id, None)

    def _resubscribe_record(self, old: IbkrSubscriptionRecord) -> None:
        generation = self._lifecycle.connection_generation
        subscription_id = self._next_subscription_id(old.capability, old.instrument_id)
        req_id = self._allocate_req_id()
        record = IbkrSubscriptionRecord(
            subscription_id=subscription_id,
            capability=old.capability,
            instrument_id=old.instrument_id,
            req_id=req_id,
            generation=generation,
            connection_identity=self.config.connection_identity,
            con_id=old.con_id,
            entitlement=EntitlementState.UNKNOWN,
            state=IbkrSubscriptionState.SUBSCRIBING,
            depth_levels=old.depth_levels,
            created_ns=self._now(),
        )
        self._registry.put(record)
        self._rank_states[subscription_id] = SubscriptionRankState()
        self._emit_subscription_reset(record)
        if old.capability is CapabilityKind.L2:
            self._transport.req_mkt_depth(
                req_id,
                self._contract_for(record),
                num_rows=record.depth_levels,
                is_smart_depth=False,
            )
        elif old.capability is CapabilityKind.TRADES:
            self._transport.req_tick_by_tick_data(req_id, self._contract_for(record))
        else:
            self._accumulators[subscription_id] = L1Accumulator(
                instrument_id=record.instrument_id,
                subscription_id=subscription_id,
                generation=generation,
            )
            self._transport.req_mkt_data(req_id, self._contract_for(record))

    # ------------------------------------------------------------ subscribe

    def subscribe_l1(
        self,
        *,
        instrument_id: str,
        con_id: int | None = None,
        qualification: Any | None = None,
    ) -> SubscribeResult:
        return self._subscribe(
            capability=CapabilityKind.L1,
            instrument_id=instrument_id,
            con_id=con_id,
            qualification=qualification,
        )

    def subscribe_l2(
        self,
        *,
        instrument_id: str,
        con_id: int | None = None,
        qualification: Any | None = None,
        depth_levels: int | None = None,
    ) -> SubscribeResult:
        return self._subscribe(
            capability=CapabilityKind.L2,
            instrument_id=instrument_id,
            con_id=con_id,
            qualification=qualification,
            depth_levels=depth_levels,
        )

    def subscribe_trades(
        self,
        *,
        instrument_id: str,
        con_id: int | None = None,
        qualification: Any | None = None,
    ) -> SubscribeResult:
        return self._subscribe(
            capability=CapabilityKind.TRADES,
            instrument_id=instrument_id,
            con_id=con_id,
            qualification=qualification,
        )

    def _subscribe(
        self,
        *,
        capability: CapabilityKind,
        instrument_id: str,
        con_id: int | None,
        qualification: Any | None,
        depth_levels: int | None = None,
    ) -> SubscribeResult:
        self._require_live()
        if qualification is not None and con_id is None:
            con_id = qualification.con_id
        admitted = self._admit(instrument_id, con_id, qualification)
        canonical_id = admitted.instrument_id
        with self._lock:
            if self._lifecycle.connection_state is not IbkrConnectionState.CONNECTED:
                return SubscribeResult(
                    accepted=False,
                    subscription_id="",
                    req_id=-1,
                    instrument_id=canonical_id,
                    capability=capability,
                    reason="NOT_CONNECTED",
                )
            existing = self._registry.get_by_instrument(canonical_id, capability)
            if existing is not None and existing.state not in (
                IbkrSubscriptionState.CANCELLED,
                IbkrSubscriptionState.FAILED,
            ):
                # Idempotent subscribe: return the existing active subscription.
                return SubscribeResult(
                    accepted=True,
                    subscription_id=existing.subscription_id,
                    req_id=existing.req_id,
                    instrument_id=canonical_id,
                    capability=capability,
                    generation=existing.generation,
                )
            pacing = self._registry.counts()
            allowed, reason = self._pacing.can_subscribe(
                capability=capability,
                active_l1=pacing.active_l1,
                active_l2=pacing.active_l2,
                active_trades=pacing.active_trades,
            )
            if not allowed:
                return SubscribeResult(
                    accepted=False,
                    subscription_id="",
                    req_id=-1,
                    instrument_id=canonical_id,
                    capability=capability,
                    reason=reason,
                )
            levels = depth_levels
            if capability is CapabilityKind.L2:
                if levels is None:
                    levels = self.config.default_depth_levels
                ok, depth_reason = self._pacing.policy.validate_depth_levels(levels)
                if not ok:
                    return SubscribeResult(
                        accepted=False,
                        subscription_id="",
                        req_id=-1,
                        instrument_id=canonical_id,
                        capability=capability,
                        reason=depth_reason,
                    )
            generation = self._lifecycle.connection_generation
            subscription_id = self._next_subscription_id(capability, canonical_id)
            req_id = self._allocate_req_id()
            record = IbkrSubscriptionRecord(
                subscription_id=subscription_id,
                capability=capability,
                instrument_id=canonical_id,
                req_id=req_id,
                generation=generation,
                connection_identity=self.config.connection_identity,
                con_id=None if admitted.qualification is None else admitted.qualification.con_id,
                entitlement=EntitlementState.UNKNOWN,
                state=IbkrSubscriptionState.SUBSCRIBING,
                depth_levels=levels if levels is not None else self.config.default_depth_levels,
                created_ns=self._now(),
            )
            self._registry.put(record)
            self._rank_states[subscription_id] = SubscriptionRankState()
            self._emit_subscription_reset(record)
            if capability is CapabilityKind.L2:
                self._transport.req_mkt_depth(
                    req_id,
                    self._contract_for(record),
                    num_rows=record.depth_levels,
                    is_smart_depth=False,
                )
            elif capability is CapabilityKind.TRADES:
                self._transport.req_tick_by_tick_data(req_id, self._contract_for(record))
            else:
                self._accumulators[subscription_id] = L1Accumulator(
                    instrument_id=canonical_id,
                    subscription_id=subscription_id,
                    generation=generation,
                )
                self._transport.req_mkt_data(req_id, self._contract_for(record))
            return SubscribeResult(
                accepted=True,
                subscription_id=subscription_id,
                req_id=req_id,
                instrument_id=canonical_id,
                capability=capability,
                generation=generation,
            )

    def _admit(self, instrument_id: str, con_id: int | None, qualification: Any | None) -> AdmittedInstrument:
        try:
            if self._lookup is not None:
                return self._admission.admit_with_lookup(
                    instrument_id=instrument_id,
                    con_id=con_id,
                    qualification=qualification,
                    lookup=self._lookup,
                )
            return self._admission.admit(
                instrument_id=instrument_id,
                con_id=con_id,
                qualification=qualification,
            )
        except IdentityAdmissionError:
            raise

    def _contract_for(self, record: IbkrSubscriptionRecord) -> Any:
        """Provider contract descriptor passed to the transport.

        Uses conId when known (provider provenance, not canonical identity).
        """
        if record.con_id is not None:
            return {"conId": record.con_id}
        return {"symbol": record.instrument_id}

    def _emit_subscription_reset(self, record: IbkrSubscriptionRecord) -> None:
        """Issue a canonical RESET for the new subscription generation.

        The engine clears prior levels, advances its generation, and marks
        RESET_PENDING until fresh state arrives. Old-generation levels can
        never mix with the new subscription's callbacks.
        """
        reset = build_depth_update(
            instrument_id=record.instrument_id,
            operation=DepthOperation.RESET,
            side=None,
            received_time_ns=self._now(),
            source="IBKR",
            subscription_id=record.subscription_id,
            provenance={"generation": record.generation, "req_id": record.req_id},
        )
        if self.store is not None:
            self.store.apply_depth_update(reset)

    # ----------------------------------------------------------------- cancel

    def cancel_l1(self, instrument_id: str) -> SubscribeResult:
        return self._cancel(CapabilityKind.L1, instrument_id)

    def cancel_l2(self, instrument_id: str) -> SubscribeResult:
        return self._cancel(CapabilityKind.L2, instrument_id)

    def cancel_trades(self, instrument_id: str) -> SubscribeResult:
        return self._cancel(CapabilityKind.TRADES, instrument_id)

    def _cancel(self, capability: CapabilityKind, instrument_id: str) -> SubscribeResult:
        with self._lock:
            record = self._registry.get_by_instrument(instrument_id, capability)
            if record is None:
                return SubscribeResult(
                    accepted=False,
                    subscription_id="",
                    req_id=-1,
                    instrument_id=instrument_id,
                    capability=capability,
                    reason="NOT_SUBSCRIBED",
                )
            if record.state in (IbkrSubscriptionState.CANCELLED, IbkrSubscriptionState.FAILED):
                # Repeated cancel is safe/idempotent.
                return SubscribeResult(
                    accepted=False,
                    subscription_id=record.subscription_id,
                    req_id=record.req_id,
                    instrument_id=record.instrument_id,
                    capability=capability,
                    reason="ALREADY_CANCELLED",
                    generation=record.generation,
                )
            self._transport_cancel(record)
            self._retire_record(record)
            return SubscribeResult(
                accepted=True,
                subscription_id=record.subscription_id,
                req_id=record.req_id,
                instrument_id=record.instrument_id,
                capability=capability,
                generation=record.generation,
            )

    def _transport_cancel(self, record: IbkrSubscriptionRecord) -> None:
        if record.capability is CapabilityKind.L2:
            self._transport.cancel_mkt_depth(record.req_id, is_smart_depth=False)
        elif record.capability is CapabilityKind.TRADES:
            self._transport.cancel_tick_by_tick_data(record.req_id)
        else:
            self._transport.cancel_mkt_data(record.req_id)

    def reset_subscription(self, subscription_id: str, *, reason: str = "ADAPTER_RESET") -> None:
        """Explicit subscription reset: new rank state + canonical RESET."""
        with self._lock:
            record = self._registry.get_by_subscription_id(subscription_id)
            if record is None:
                return
            record.state = IbkrSubscriptionState.RESETTING
            record.reason = reason
            self._rank_states[subscription_id] = SubscriptionRankState()
            self._emit_subscription_reset(record)
            record.state = IbkrSubscriptionState.SUBSCRIBING
            self._reset_count += 1
            record.reset_count += 1

    # -------------------------------------------------------------- callbacks

    def on_tick_price(
        self,
        req_id: int,
        field: int,
        price: float | None,
        *,
        received_ns: int | None = None,
        source_time_ns: int | None = None,
    ) -> CallbackResult:
        received = received_ns if received_ns is not None else self._now()
        with self._lock:
            try:
                record = self._registry.require_by_req_id(req_id)
            except UnknownReqIdError as exc:
                return self._reject_unknown(req_id, str(exc), received)
            if record.capability is not CapabilityKind.L1:
                return CallbackResult(False, "REJECTED", reason="TICK_FOR_NON_L1_SUBSCRIPTION")
            accumulator = self._accumulators.get(record.subscription_id)
            if accumulator is None:
                accumulator = L1Accumulator(
                    instrument_id=record.instrument_id,
                    subscription_id=record.subscription_id,
                    generation=record.generation,
                )
                self._accumulators[record.subscription_id] = accumulator
            facts = accumulator.on_tick_price(
                field=field,
                price=price,
                source_time_ns=source_time_ns,
                received_time_ns=received,
            )
            self._publish_l1(record, facts)
            self._capture.record(
                capture_tick_callback(
                    callback="tickPrice",
                    req_id=req_id,
                    instrument_id=record.instrument_id,
                    generation=record.generation,
                    field=field,
                    value=price,
                    received_time_ns=received,
                    source_time_ns=source_time_ns,
                )
            )
            return CallbackResult(True, "TICK", quote_facts=facts)

    def on_tick_size(
        self,
        req_id: int,
        field: int,
        size: float | None,
        *,
        received_ns: int | None = None,
        source_time_ns: int | None = None,
    ) -> CallbackResult:
        received = received_ns if received_ns is not None else self._now()
        with self._lock:
            try:
                record = self._registry.require_by_req_id(req_id)
            except UnknownReqIdError as exc:
                return self._reject_unknown(req_id, str(exc), received)
            if record.capability is not CapabilityKind.L1:
                return CallbackResult(False, "REJECTED", reason="TICK_FOR_NON_L1_SUBSCRIPTION")
            accumulator = self._accumulators.get(record.subscription_id)
            if accumulator is None:
                accumulator = L1Accumulator(
                    instrument_id=record.instrument_id,
                    subscription_id=record.subscription_id,
                    generation=record.generation,
                )
                self._accumulators[record.subscription_id] = accumulator
            facts = accumulator.on_tick_size(
                field=field,
                size=size,
                source_time_ns=source_time_ns,
                received_time_ns=received,
            )
            self._publish_l1(record, facts)
            self._capture.record(
                capture_tick_callback(
                    callback="tickSize",
                    req_id=req_id,
                    instrument_id=record.instrument_id,
                    generation=record.generation,
                    field=field,
                    value=size,
                    received_time_ns=received,
                    source_time_ns=source_time_ns,
                )
            )
            return CallbackResult(True, "TICK", quote_facts=facts)

    def on_tick_by_tick_all_last(
        self,
        req_id: int,
        tick_type: int,
        price: float | None,
        size: float | None,
        *,
        source_time_ns: int | None = None,
        received_ns: int | None = None,
        exchange: str | None = None,
        special_conditions: str | None = None,
        past_limit: bool | None = None,
        unreported: bool | None = None,
    ) -> CallbackResult:
        received = received_ns if received_ns is not None else self._now()
        with self._lock:
            try:
                record = self._registry.require_by_req_id(req_id)
            except UnknownReqIdError as exc:
                return self._reject_unknown(req_id, str(exc), received)
            if record.capability is not CapabilityKind.TRADES:
                return CallbackResult(False, "REJECTED", reason="TRADE_FOR_NON_TRADES_SUBSCRIPTION")
            if record.generation != self._lifecycle.connection_generation:
                return CallbackResult(False, "REJECTED", reason="GENERATION_MISMATCH")
            if price is None or size is None or size <= 0:
                return CallbackResult(False, "REJECTED", reason="INCOMPLETE_TRADE_FACTS")
            facts = facts_from_tick_by_tick_all_last(
                instrument_id=record.instrument_id,
                subscription_id=record.subscription_id,
                req_id=req_id,
                generation=record.generation,
                price=float(price),
                size=float(size),
                source_time_ns=source_time_ns,
                received_time_ns=received,
                exchange=exchange,
                special_conditions=special_conditions,
                tick_type=tick_type,
                past_limit=past_limit,
                unreported=unreported,
            )
            classified, _kind, _reason = self._classify_and_publish_trade(record, facts, received)
            self._capture.record(
                capture_trade_callback(
                    callback="tickByTickAllLast",
                    req_id=req_id,
                    instrument_id=record.instrument_id,
                    generation=record.generation,
                    price=facts.price,
                    size=facts.size,
                    exchange=exchange,
                    special_conditions=special_conditions,
                    tick_type=tick_type,
                    past_limit=past_limit,
                    unreported=unreported,
                    received_time_ns=received,
                    source_time_ns=source_time_ns,
                )
            )
            record.last_received_time_ns = received
            if source_time_ns is not None:
                record.last_source_time_ns = source_time_ns
            if record.state in (IbkrSubscriptionState.CREATED, IbkrSubscriptionState.SUBSCRIBING):
                record.mark_active(received_ns=received)
            return CallbackResult(True, "TRADE", reason=classified.classification_method)

    def _quote_context_for(self, instrument_id: str) -> QuoteContext | None:
        if self.store is None:
            return None
        quote = self.store.quote_for(instrument_id)
        if quote is None:
            return None
        entitlement = None
        l1_record = self._registry.get_by_instrument(instrument_id, CapabilityKind.L1)
        if l1_record is not None:
            entitlement = l1_record.entitlement
        return QuoteContext(
            bid=quote.bid_price,
            ask=quote.ask_price,
            provider=str(quote.provider or self.config.provider),
            received_ns=quote.received_ns,
            quality=str(quote.quality or "PASS"),
            entitlement=entitlement,
        )

    def _classify_and_publish_trade(
        self,
        record: IbkrSubscriptionRecord,
        facts: Any,
        received_ns: int,
    ) -> tuple[Any, Any, str | None]:
        instrument_id = record.instrument_id
        prev_price = self._prev_trade_prices.get(instrument_id)
        prev_dir = self._prev_trade_dirs.get(instrument_id, 0.0)
        classified, kind, reason = classify_trade_print(
            facts,
            quote=self._quote_context_for(instrument_id),
            prev_price=prev_price,
            prev_dir=prev_dir,
            provider=self.config.provider,
        )
        if self.store is not None:
            self.store.apply_classified_trade(
                classified,
                instrument_id=instrument_id,
                event_time_ns=facts.source_time_ns,
                available_time_ns=received_ns,
                received_ns=received_ns,
                quality="DELAYED" if record.delayed else "PASS",
                provider=self.config.provider,
            )
        if classified.aggressor_side.value.upper() != "UNKNOWN":
            self._prev_trade_prices[instrument_id] = facts.price
            signed = classified.signed_volume
            self._prev_trade_dirs[instrument_id] = 1.0 if signed > 0 else (-1.0 if signed < 0 else 0.0)
        return classified, kind, reason

    def _publish_l1(self, record: IbkrSubscriptionRecord, facts: L1QuoteFacts) -> None:
        record.last_received_time_ns = facts.received_time_ns
        record.last_source_time_ns = facts.source_time_ns
        record.delayed = facts.delayed
        if facts.delayed and record.entitlement is EntitlementState.UNKNOWN:
            record.entitlement = EntitlementState.DELAYED
        if not facts.has_any_fact:
            return
        if self.store is not None:
            self.store.apply_quote_update(
                instrument_id=record.instrument_id,
                bid_price=facts.bid_price,
                ask_price=facts.ask_price,
                bid_size=facts.bid_size,
                ask_size=facts.ask_size,
                last_price=facts.last_price,
                last_size=facts.last_size,
                event_time_ns=facts.source_time_ns,
                available_time_ns=facts.received_time_ns,
                received_ns=facts.received_time_ns,
                quality="DELAYED" if facts.delayed else "PASS",
                provider=self.config.provider,
            )
        if record.state in (IbkrSubscriptionState.CREATED, IbkrSubscriptionState.SUBSCRIBING):
            record.mark_active(received_ns=facts.received_time_ns)

    def _republish_l1_quote(self, record: IbkrSubscriptionRecord, *, delayed: bool) -> None:
        """Re-publish the accumulated L1 facts with delayed quality.

        Called when a delayed/entitlement error arrives after facts were
        already published: the store must not keep presenting the old quote
        as real-time.
        """
        accumulator = self._accumulators.get(record.subscription_id)
        if accumulator is None or self.store is None:
            return
        facts = accumulator.facts()
        if not facts.has_any_fact:
            return
        self.store.apply_quote_update(
            instrument_id=record.instrument_id,
            bid_price=facts.bid_price,
            ask_price=facts.ask_price,
            bid_size=facts.bid_size,
            ask_size=facts.ask_size,
            last_price=facts.last_price,
            last_size=facts.last_size,
            event_time_ns=facts.source_time_ns,
            available_time_ns=facts.received_time_ns,
            received_ns=record.last_received_time_ns or facts.received_time_ns,
            quality="DELAYED" if delayed else "PASS",
            provider=self.config.provider,
        )

    def on_mkt_depth(
        self,
        req_id: int,
        position: int,
        operation: int,
        side: int,
        price: float | None,
        size: float | None,
        *,
        received_ns: int | None = None,
        source_time_ns: int | None = None,
    ) -> CallbackResult:
        return self._on_depth(
            req_id=req_id,
            position=position,
            operation=operation,
            side=side,
            price=price,
            size=size,
            market_maker=None,
            is_smart_depth=None,
            callback_type="updateMktDepth",
            received_ns=received_ns,
            source_time_ns=source_time_ns,
        )

    def on_mkt_depth_l2(
        self,
        req_id: int,
        position: int,
        market_maker: str,
        operation: int,
        side: int,
        price: float | None,
        size: float | None,
        is_smart_depth: bool,
        *,
        received_ns: int | None = None,
        source_time_ns: int | None = None,
    ) -> CallbackResult:
        return self._on_depth(
            req_id=req_id,
            position=position,
            operation=operation,
            side=side,
            price=price,
            size=size,
            market_maker=market_maker,
            is_smart_depth=is_smart_depth,
            callback_type="updateMktDepthL2",
            received_ns=received_ns,
            source_time_ns=source_time_ns,
        )

    def _on_depth(
        self,
        *,
        req_id: int,
        position: int,
        operation: int,
        side: int,
        price: float | None,
        size: float | None,
        market_maker: str | None,
        is_smart_depth: bool | None,
        callback_type: str,
        received_ns: int | None,
        source_time_ns: int | None,
    ) -> CallbackResult:
        received = received_ns if received_ns is not None else self._now()
        with self._lock:
            try:
                record = self._registry.require_by_req_id(req_id)
            except UnknownReqIdError as exc:
                return self._reject_unknown(req_id, str(exc), received)
            if record.capability is not CapabilityKind.L2:
                return CallbackResult(False, "REJECTED", reason="DEPTH_FOR_NON_L2_SUBSCRIPTION")
            rank_state = self._rank_states.setdefault(
                record.subscription_id, SubscriptionRankState()
            )
            outcome, events, reason = translate_depth_callback(
                rank_state,
                instrument_id=record.instrument_id,
                subscription_id=record.subscription_id,
                generation=record.generation,
                side_value=side,
                operation_value=operation,
                position=position,
                price=price,
                size=size,
                market_maker=market_maker,
                is_smart_depth=is_smart_depth,
                callback_type=callback_type,
                source_time_ns=source_time_ns,
                received_time_ns=received,
                provider_req_id=req_id,
                resolve_snapshot_price=self._snapshot_price_resolver(record.instrument_id),
            )
            if outcome is DepthTranslationOutcome.REJECTED:
                self._record_subscription_error(
                    record,
                    f"DEPTH_TRANSLATION_REJECTED:{reason}",
                    received,
                )
                self._capture.record(
                    capture_error_record(
                        req_id=req_id,
                        code=None,
                        message=reason or "rejected depth callback",
                        category="UNKNOWN_PROVIDER_ERROR",
                        received_time_ns=received,
                    )
                )
                return CallbackResult(False, "REJECTED", reason=reason)
            if outcome is DepthTranslationOutcome.DEGRADED:
                self._degrade_and_reset(record, reason or "RANK_DISAGREEMENT", received)
                self._capture.record(
                    capture_error_record(
                        req_id=req_id,
                        code=None,
                        message=reason or "rank disagreement",
                        category="SUBSCRIPTION",
                        received_time_ns=received,
                    )
                )
                return CallbackResult(False, "DEGRADED", reason=reason)
            if outcome is DepthTranslationOutcome.IGNORED:
                record.last_received_time_ns = received
                return CallbackResult(False, "IGNORED", reason=reason)
            record.last_received_time_ns = received
            if source_time_ns is not None:
                record.last_source_time_ns = source_time_ns
            apply_results = self._apply_depth_events(record, events)
            if record.state in (IbkrSubscriptionState.CREATED, IbkrSubscriptionState.SUBSCRIBING):
                if any(result.outcome in (ApplyOutcome.APPLIED, ApplyOutcome.NOOP) for result in apply_results):
                    record.mark_active(received_ns=received)
            self._capture.record(
                capture_depth_callback(
                    callback=callback_type,
                    req_id=req_id,
                    instrument_id=record.instrument_id,
                    generation=record.generation,
                    position=position,
                    operation=operation,
                    side=side,
                    price=price,
                    size=size,
                    market_maker=market_maker,
                    is_smart_depth=is_smart_depth,
                    received_time_ns=received,
                    source_time_ns=source_time_ns,
                )
            )
            return CallbackResult(
                True,
                "DEPTH",
                events=tuple(events),
                apply_results=tuple(apply_results),
            )

    def _apply_depth_events(
        self,
        record: IbkrSubscriptionRecord,
        events: Sequence[DepthUpdate],
    ) -> list[ApplyResult]:
        results: list[ApplyResult] = []
        for event in events:
            if self.store is not None:
                applied = self.store.apply_depth_update(event)
                if applied is not None:
                    results.append(applied)
        return results

    def _snapshot_price_resolver(self, instrument_id: str) -> Callable[[DepthSide, int], Any]:
        def resolve(side: DepthSide, position: int) -> Any:
            if self.store is None:
                return None
            engine = self.store.book_engine_for(instrument_id)
            if engine is None:
                return None
            rows = engine.bids if side is DepthSide.BID else engine.asks
            if 0 <= position < len(rows):
                return rows[position].price
            return None

        return resolve

    def _degrade_and_reset(
        self,
        record: IbkrSubscriptionRecord,
        reason: str,
        received_ns: int,
    ) -> None:
        """Fail closed on rank disagreement: degrade + RESET + clear rank state.

        The subscription cannot remain ACTIVE and the book cannot remain valid
        after a provider disagreement; a fresh generation is required.
        """
        record.mark_degraded(reason)
        self._rank_states.pop(record.subscription_id, None)
        record.reset_count += 1
        self._reset_count += 1
        self._emit_subscription_reset(record)
        record.last_received_time_ns = received_ns

    def _reject_unknown(self, req_id: int, message: str, received_ns: int) -> CallbackResult:
        """Unknown reqId is logged/rejected explicitly — never guessed."""
        self._capture.record(
            capture_error_record(
                req_id=req_id,
                code=None,
                message=message,
                category="SUBSCRIPTION",
                received_time_ns=received_ns,
            )
        )
        return CallbackResult(False, "REJECTED", reason=message)

    def _record_subscription_error(
        self,
        record: IbkrSubscriptionRecord,
        message: str,
        received_ns: int,
    ) -> None:
        record.last_received_time_ns = received_ns
        record.reason = message
        record.last_error = IbkrProviderError(
            code=None,
            message=message,
            category=IbkrErrorCategory.INTERNAL_PROVIDER,
        )

    # ---------------------------------------------------------------- errors

    def on_error(
        self,
        req_id: int | None,
        code: int | None,
        message: str,
        *,
        received_ns: int | None = None,
    ) -> CallbackResult:
        from .errors import normalize_provider_error

        received = received_ns if received_ns is not None else self._now()
        error = normalize_provider_error(code=code, message=message, req_id=req_id)
        with self._lock:
            self._capture.record(
                capture_error_record(
                    req_id=req_id,
                    code=code,
                    message=message,
                    category=error.category.value,
                    received_time_ns=received,
                )
            )
            if code == ERROR_CODE_1100_CONNECTIVITY_LOST:
                self.handle_disconnect("IBKR_CONNECTIVITY_LOST_1100")
                return CallbackResult(True, "CONNECTION", reason=error.category.value)
            if code == ERROR_CODE_1101_RESTORED_DATA_LOST:
                self.handle_reconnect()
                return CallbackResult(True, "CONNECTION", reason=error.category.value)
            self._lifecycle.record_received(received)
            if req_id is None:
                self._lifecycle.last_error = error
                return CallbackResult(False, "ERROR", reason=error.category.value)
            record = self._registry.get_by_req_id(req_id)
            if record is None:
                self._capture.record(
                    capture_error_record(
                        req_id=req_id,
                        code=code,
                        message=f"error for unknown req_id {req_id}",
                        category=error.category.value,
                        received_time_ns=received,
                    )
                )
                return CallbackResult(False, "ERROR", reason="UNKNOWN_REQ_ID")
            self._apply_error_to_record(record, error, received)
            return CallbackResult(False, "ERROR", reason=error.category.value)

    def _apply_error_to_record(
        self,
        record: IbkrSubscriptionRecord,
        error: IbkrProviderError,
        received_ns: int,
    ) -> None:
        from .contracts import IbkrErrorCategory

        record.last_received_time_ns = received_ns
        record.last_error = error
        category = error.category
        if category is IbkrErrorCategory.ENTITLEMENT:
            if record.capability is CapabilityKind.L2:
                # Missing depth entitlement: subscription cannot remain
                # ACTIVE and the book cannot remain valid — no fake fallback.
                record.entitlement = EntitlementState.NOT_ENTITLED
                record.mark_failed("ENTITLEMENT_MISSING", error=error)
                self._rank_states.pop(record.subscription_id, None)
                self._emit_subscription_reset(record)
            else:
                record.entitlement = EntitlementState.DELAYED
                accumulator = self._accumulators.get(record.subscription_id)
                if accumulator is not None:
                    accumulator.mark_delayed()
                record.delayed = True
                record.mark_degraded("DELAYED_DATA", received_ns=received_ns)
                self._republish_l1_quote(record, delayed=True)
        elif category is IbkrErrorCategory.DELAYED_DATA:
            record.entitlement = EntitlementState.DELAYED
            record.delayed = True
            accumulator = self._accumulators.get(record.subscription_id)
            if accumulator is not None:
                accumulator.mark_delayed()
            record.mark_degraded("DELAYED_DATA", received_ns=received_ns)
            self._republish_l1_quote(record, delayed=True)
        elif category is IbkrErrorCategory.PACING:
            self._pacing.enter_cooldown(seconds=15.0, now_ns=received_ns)
            record.mark_degraded("PACING_LIMIT", received_ns=received_ns)
        elif category is IbkrErrorCategory.SUBSCRIPTION:
            if error.code == ERROR_CODE_317_DEPTH_RESET:
                self.reset_subscription(record.subscription_id, reason="IB_DEPTH_RESET_317")
                record.last_error = error
            elif error.code == ERROR_CODE_316_DEPTH_HALTED:
                record.mark_degraded("DEPTH_HALTED_REQUIRES_RESUBSCRIBE", received_ns=received_ns)
            else:
                record.mark_degraded("SUBSCRIPTION_ERROR", received_ns=received_ns)
        elif category is IbkrErrorCategory.CONNECTION:
            record.mark_degraded("CONNECTION_ERROR", received_ns=received_ns)
        elif category is IbkrErrorCategory.CONTRACT:
            record.mark_failed("CONTRACT_RESOLUTION_FAILED", error=error)
        elif category is IbkrErrorCategory.INTERNAL_PROVIDER:
            pass  # informational notifications only
        else:
            record.mark_degraded("PROVIDER_ERROR", received_ns=received_ns)

    def on_connection_state(
        self,
        state: IbkrConnectionState,
        *,
        reason: str | None = None,
    ) -> None:
        with self._lock:
            if state is IbkrConnectionState.CONNECTED:
                self._lifecycle.mark_connected()
            elif state is IbkrConnectionState.DISCONNECTED:
                self.handle_disconnect(reason or "PROVIDER_DISCONNECTED")
            elif state is IbkrConnectionState.DEGRADED:
                self._lifecycle.mark_degraded(reason or "PROVIDER_DEGRADED")
            elif state is IbkrConnectionState.FAILED:
                self._lifecycle.mark_failed(
                    IbkrProviderError(
                        code=None,
                        message=reason or "PROVIDER_FAILED",
                        category=IbkrErrorCategory.CONNECTION,
                    )
                )

    # ------------------------------------------------------ capture / replay

    def register_replay_subscription(
        self,
        *,
        instrument_id: str,
        capability: CapabilityKind,
        con_id: int | None = None,
        depth_levels: int | None = None,
        req_id: int | None = None,
    ) -> SubscribeResult:
        """Offline subscription registration for capture replay (no transport I/O)."""
        admitted = self._admit(instrument_id, con_id, None)
        canonical_id = admitted.instrument_id
        with self._lock:
            generation = self._lifecycle.connection_generation
            subscription_id = self._next_subscription_id(capability, canonical_id)
            allocated = req_id if req_id is not None else self._allocate_req_id()
            record = IbkrSubscriptionRecord(
                subscription_id=subscription_id,
                capability=capability,
                instrument_id=canonical_id,
                req_id=allocated,
                generation=generation,
                connection_identity=self.config.connection_identity,
                con_id=None if admitted.qualification is None else admitted.qualification.con_id,
                entitlement=EntitlementState.UNKNOWN,
                state=IbkrSubscriptionState.SUBSCRIBING,
                depth_levels=depth_levels or self.config.default_depth_levels,
                created_ns=self._now(),
            )
            self._registry.put(record)
            self._rank_states[subscription_id] = SubscriptionRankState()
            if capability is CapabilityKind.L1:
                self._accumulators[subscription_id] = L1Accumulator(
                    instrument_id=canonical_id,
                    subscription_id=subscription_id,
                    generation=generation,
                )
            self._emit_subscription_reset(record)
            return SubscribeResult(
                accepted=True,
                subscription_id=subscription_id,
                req_id=allocated,
                instrument_id=canonical_id,
                capability=capability,
                generation=generation,
            )

    def on_captured_record(self, record: Mapping[str, Any]) -> CallbackResult | None:
        """Route one captured record through the canonical normalization path."""
        kind = str(record.get("callback_kind") or "")
        req_id = int(record.get("req_id") or -1)
        received = record.get("received_time_ns")
        source = record.get("source_time_ns")
        if kind == "DEPTH":
            operation = record.get("operation")
            side = record.get("side")
            position = record.get("position")
            if not all(isinstance(v, int) and not isinstance(v, bool) for v in (operation, side, position)):
                return None
            return self.on_mkt_depth_l2(
                req_id,
                position,
                str(record.get("market_maker") or ""),
                operation,
                side,
                _as_float(record.get("price")),
                _as_float(record.get("size")),
                bool(record.get("is_smart_depth") or False),
                received_ns=received,
                source_time_ns=source,
            )
        if kind == "TICK":
            callback = str(record.get("callback") or "")
            value = _as_float(record.get("value"))
            field = record.get("field")
            if not isinstance(field, int) or isinstance(field, bool):
                return None
            if callback == "tickPrice":
                return self.on_tick_price(
                    req_id,
                    field,
                    value,
                    received_ns=received,
                    source_time_ns=source,
                )
            return self.on_tick_size(
                req_id,
                field,
                value,
                received_ns=received,
                source_time_ns=source,
            )
        if kind == "TRADE":
            tick_type = record.get("tick_type")
            if not isinstance(tick_type, int) or isinstance(tick_type, bool):
                tick_type = 2
            return self.on_tick_by_tick_all_last(
                req_id,
                tick_type,
                _as_float(record.get("price")),
                _as_float(record.get("size")),
                source_time_ns=source,
                received_ns=received,
                exchange=str(record.get("exchange") or "") or None,
                special_conditions=str(record.get("special_conditions") or "") or None,
                past_limit=record.get("past_limit"),
                unreported=record.get("unreported"),
            )
        if kind == "ERROR":
            self.on_error(
                req_id if req_id >= 0 else None,
                record.get("code"),
                str(record.get("message") or ""),
                received_ns=received,
            )
            return None
        return None

    # ------------------------------------------------------------ diagnostics

    def subscription_status(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return self._lifecycle.diagnostics_subscriptions()

    def pacing_report(self) -> dict[str, Any]:
        with self._lock:
            counts = self._registry.counts()
            return self._pacing.report(
                active_l1=counts.active_l1,
                active_l2=counts.active_l2,
                active_trades=counts.active_trades,
            ).as_dict()

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            counts = self._registry.counts()
            pacing = self._pacing.report(
                active_l1=counts.active_l1,
                active_l2=counts.active_l2,
                active_trades=counts.active_trades,
            )
            diagnostics = build_diagnostics(
                provider=self.config.provider,
                connection_state=self._lifecycle.connection_state,
                connection_generation=self._lifecycle.connection_generation,
                reconnect_count=self._lifecycle.reconnect_count,
                reset_count=self._reset_count,
                l1_count=counts.active_l1,
                l2_count=counts.active_l2,
                trades_count=counts.active_trades,
                subscriptions=self._lifecycle.diagnostics_subscriptions(),
                pacing=pacing,
                entitlement=self._aggregate_entitlement(),
                last_error=(
                    None
                    if self._lifecycle.last_error is None
                    else self._lifecycle.last_error.as_dict()
                ),
                last_received_ns=self._lifecycle.last_received_ns,
            )
            return diagnostics.as_dict()

    def _aggregate_entitlement(self) -> EntitlementState:
        records = [
            record
            for record in self._registry.active_records()
            if record.state not in (IbkrSubscriptionState.CANCELLED, IbkrSubscriptionState.FAILED)
        ]
        if not records:
            return EntitlementState.UNKNOWN
        if any(record.entitlement is EntitlementState.NOT_ENTITLED for record in records):
            return EntitlementState.NOT_ENTITLED
        if any(record.entitlement is EntitlementState.DELAYED for record in records):
            return EntitlementState.DELAYED
        if any(record.entitlement is EntitlementState.ERROR for record in records):
            return EntitlementState.ERROR
        if all(record.entitlement is EntitlementState.ENTITLED for record in records):
            return EntitlementState.ENTITLED
        return EntitlementState.UNKNOWN

    def readiness(self) -> dict[str, Any]:
        with self._lock:
            subscriptions = self._lifecycle.diagnostics_subscriptions()
            states = compute_readiness(
                connection_state=self._lifecycle.connection_state,
                subscriptions=subscriptions,
                entitlement=self._aggregate_entitlement(),
            )
            return {
                "capability_readiness": states,
                "provider": self.config.provider,
                "overall": (
                    ReadinessState.READY
                    if all(value == ReadinessState.READY for value in states.values())
                    else (
                        ReadinessState.UNAVAILABLE
                        if self._lifecycle.connection_state is IbkrConnectionState.DISCONNECTED
                        else ReadinessState.DEGRADED
                    )
                ),
            }

    def book_diagnostics(self, instrument_id: str, *, as_of_time_ns: int | None = None) -> dict[str, Any]:
        if self.store is None:
            return {"book_state": "UNAVAILABLE", "store": "NOT_ATTACHED"}
        return book_facts(
            store=self.store,
            instrument_id=instrument_id,
            as_of_time_ns=as_of_time_ns or self._now(),
        )

    def capture_records(self) -> tuple[dict[str, Any], ...]:
        return self._capture.captured_records()


def _as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "CallbackResult",
    "IbkrObservationalAdapter",
    "IbkrObservationalConfig",
    "IbkrOfflineError",
    "IbkrTransport",
    "SubscribeResult",
]