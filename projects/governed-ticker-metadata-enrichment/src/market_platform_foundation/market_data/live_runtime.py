"""Live observational runtime — ingest, admission, state, subscriptions."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..clock import monotonic_wall_ns
from .capture import read_envelopes
from .capabilities import CapabilityState, MarketCapability, merge_capability
from .capability_registry import VerifiedCapabilityRegistry
from .execution_event_buffer import LiveExecutionEventBuffer
from .internal_simulation_gate import evaluate_internal_simulation_gates
from .live_admission import LiveAdmissionEngine
from .live_config import (
    fixture_feed_path,
    live_internal_simulation_enabled,
    live_observational_enabled,
    moomoo_host,
    moomoo_live_enabled,
    moomoo_port,
    probe_report_path,
    probe_staleness_seconds,
    shadow_recording_enabled,
    subscription_quota,
)
from .connectivity import opend_reachable
from .observational_state import ObservationalStateStore
from .provider_lifecycle import ProviderConnectionState, ProviderLifecycle
from .recorder import ObservationalRecorder
from .subscription_manager import LiveSubscriptionManager, SubscriptionPriority

_RUNTIME: LiveObservationalRuntime | None = None
_RUNTIME_LOCK = threading.Lock()

KNOWN_INSTRUMENTS: dict[str, dict[str, str]] = {
    "AAPL": {"provider_symbol": "US.AAPL", "venue_id": "US_EQUITY"},
    "NVDA": {"provider_symbol": "US.NVDA", "venue_id": "US_EQUITY"},
    "MSFT": {"provider_symbol": "US.MSFT", "venue_id": "US_EQUITY"},
    "TSLA": {"provider_symbol": "US.TSLA", "venue_id": "US_EQUITY"},
    "SPY": {"provider_symbol": "US.SPY", "venue_id": "US_EQUITY"},
}


def provider_symbol_for(instrument_id: str) -> str:
    key = instrument_id.strip().upper()
    meta = KNOWN_INSTRUMENTS.get(key)
    if meta:
        return meta["provider_symbol"]
    return f"US.{key}"


@dataclass
class LiveObservationalRuntime:
    state: ObservationalStateStore = field(default_factory=ObservationalStateStore)
    admission: LiveAdmissionEngine = field(default_factory=LiveAdmissionEngine)
    subscriptions: LiveSubscriptionManager = field(default_factory=lambda: LiveSubscriptionManager(max_quota=subscription_quota()))
    lifecycle: ProviderLifecycle = field(default_factory=ProviderLifecycle)
    execution_buffer: LiveExecutionEventBuffer = field(default_factory=LiveExecutionEventBuffer)
    capability_registry: VerifiedCapabilityRegistry = field(default_factory=VerifiedCapabilityRegistry)
    recorder: ObservationalRecorder | None = None
    scope_symbols: list[str] = field(default_factory=list)
    capability_probe: dict[str, CapabilityState] = field(default_factory=dict)
    feed: Any | None = field(default=None, repr=False)
    feed_metrics: dict[str, Any] = field(default_factory=dict)
    shadow_recorder: Any | None = field(default=None, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _fresh_event_count: int = 0

    def configure(self) -> None:
        self.lifecycle.quota_available = self.subscriptions.max_quota
        if not live_observational_enabled():
            self.lifecycle.connection_state = ProviderConnectionState.DISABLED
            return
        self.lifecycle.connection_state = ProviderConnectionState.CONNECTING
        self._load_verified_capabilities()
        if moomoo_live_enabled():
            if not opend_reachable(host=moomoo_host(), port=moomoo_port()):
                self.lifecycle.connection_state = ProviderConnectionState.DISCONNECTED
                self.lifecycle.last_error = (
                    f"MOOMOO LIVE DATA UNAVAILABLE: OpenD is not reachable at {moomoo_host()}:{moomoo_port()}. "
                    "Replay mode remains available."
                )
                self.admission.on_disconnect()
                return
            self.lifecycle.sdk_version = self.capability_registry.sdk_version
            self.lifecycle.opend_version = self.capability_registry.opend_version
            self.lifecycle.entitlement_state = "PROBE_VERIFIED" if not self.capability_registry.is_stale else "PROBE_STALE"
            self._start_moomoo_push_feed()
        else:
            fixture = fixture_feed_path()
            if fixture and fixture.is_file():
                self.lifecycle.mark_connected()
                self.admission.on_connect()
                self._replay_fixture(fixture)
            else:
                self.lifecycle.connection_state = ProviderConnectionState.DISABLED
                self.lifecycle.last_error = "IMP_MOOMOO_LIVE or IMP_LIVE_FIXTURE_FEED required"
        if shadow_recording_enabled():
            from ..shadow.recording import attach_default_recorder

            self.shadow_recorder = attach_default_recorder(self)

    def _load_verified_capabilities(self) -> None:
        receiving = self._fresh_event_count > 0
        healthy = self.lifecycle.connection_state in {
            ProviderConnectionState.CONNECTED,
            ProviderConnectionState.CONNECTED_DEGRADED,
        }
        self.capability_registry = VerifiedCapabilityRegistry.from_probe_file(
            probe_report_path(),
            max_staleness_seconds=probe_staleness_seconds(),
            moomoo_configured=moomoo_live_enabled(),
            runtime_connected=healthy or opend_reachable(),
            runtime_receiving=receiving,
            runtime_healthy=healthy and receiving,
        )
        self.capability_probe = dict(self.capability_registry.capabilities)
        from .live_config import subscription_quota_override

        override = subscription_quota_override()
        if override is not None:
            self.subscriptions.max_quota = override
        elif self.capability_registry.subscription_quota:
            self.subscriptions.max_quota = int(self.capability_registry.subscription_quota)
        self.lifecycle.quota_available = self.subscriptions.max_quota

    def _start_moomoo_push_feed(self) -> None:
        import sys
        from pathlib import Path

        tools_moomoo = Path(__file__).resolve().parents[3] / "tools" / "moomoo"
        if str(tools_moomoo) not in sys.path:
            sys.path.insert(0, str(tools_moomoo))
        import push_feed

        self.feed = push_feed.MoomooPushFeed(
            subscriptions=self.subscriptions,
            on_record=self._on_feed_record,
            on_connected=self._on_feed_connected,
            on_disconnected=self._on_feed_disconnected,
            on_reconnecting=self._on_feed_reconnecting,
            on_overflow=self._on_feed_overflow,
        )
        self.feed.start()

    def _on_feed_connected(self) -> None:
        generation = self.feed.provider_generation if self.feed else 0
        self.lifecycle.mark_connected(
            quota_available=self.subscriptions.max_quota,
            provider_generation_id=generation,
        )
        self.admission.on_connect()
        self.execution_buffer.on_generation_change(generation)
        self._update_execution_use()

    def _on_feed_disconnected(self, reason: str) -> None:
        self.lifecycle.mark_disconnected(reason)
        self.admission.on_disconnect()
        self._update_execution_use()

    def _on_feed_reconnecting(self) -> None:
        self.lifecycle.mark_reconnecting()
        self.admission.on_reconnect()
        self._update_execution_use()

    def _on_feed_overflow(self) -> None:
        self.lifecycle.mark_degraded("INGEST_QUEUE_OVERFLOW")
        self._update_execution_use()

    def _on_feed_record(self, record: dict[str, Any]) -> None:
        generation = int(record.get("provider_generation") or 0)
        if generation and generation != self.lifecycle.provider_generation_id:
            self.execution_buffer.on_generation_change(generation)
        result = self.ingest_record(
            record,
            is_first_push=bool(record.get("is_first_push")),
            is_cached=bool(record.get("is_cached")),
        )
        execution = str(result.get("admission", {}).get("execution") or "")
        first_kind = str(record.get("first_push_class") or "")
        if execution == "EXECUTION_ADMITTED" and first_kind not in {"CACHED", "SNAPSHOT"}:
            self._fresh_event_count += 1
            if self._fresh_event_count >= 1 and self.lifecycle.connection_state == ProviderConnectionState.CONNECTED_DEGRADED:
                self.lifecycle.connection_state = ProviderConnectionState.CONNECTED
        if self.feed is not None:
            self.feed_metrics = self.feed.metrics()
            self.lifecycle.feed_metrics = dict(self.feed_metrics)
        self._update_execution_use()

    def _update_execution_use(self) -> None:
        gate = evaluate_internal_simulation_gates(
            runtime=self,
            probe_stale=self.capability_registry.is_stale,
        )
        if live_internal_simulation_enabled() and gate.status == "AUTHORIZED":
            self.lifecycle.execution_use = "INTERNAL_PAPER_ELIGIBLE"
        else:
            self.lifecycle.execution_use = "DISPLAY_ONLY"

    def ingest_record(
        self,
        record: dict[str, Any],
        *,
        is_first_push: bool = False,
        is_cached: bool = False,
        wall_now_ns: int | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            clocks = record.get("clocks") if isinstance(record.get("clocks"), dict) else {}
            received = int(clocks.get("received_time_ns") or monotonic_wall_ns())
            effective_wall = wall_now_ns if wall_now_ns is not None else monotonic_wall_ns()
            result = self.admission.evaluate_record(
                record,
                wall_now_ns=effective_wall,
                is_first_push=is_first_push,
                is_cached=is_cached,
            )
            if result.get("envelope"):
                admitted = self.state.apply_admitted(result)
                if admitted:
                    clocks = record.get("clocks") if isinstance(record.get("clocks"), dict) else {}
                    received = int(clocks.get("received_time_ns") or monotonic_wall_ns())
                    self.lifecycle.record_event(received)
                    instrument = str(record.get("instrument_id") or "").upper()
                    if instrument and instrument not in self.scope_symbols:
                        self.scope_symbols.append(instrument)
                    self.execution_buffer.append_admitted(
                        result,
                        provider_generation=int(
                            record.get("provider_generation") or self.lifecycle.provider_generation_id or 0
                        ),
                    )
            if self.recorder is not None and result.get("envelope"):
                self.recorder.append(record, result)
            if self.shadow_recorder is not None:
                self.shadow_recorder.on_admitted(self.state, result.get("envelope") or {}, result)
            return result

    def feed_fixture_path(self, path: Path) -> int:
        count = 0
        for record in read_envelopes(path):
            clocks = record.get("clocks") if isinstance(record.get("clocks"), dict) else {}
            received = int(clocks.get("received_time_ns") or monotonic_wall_ns())
            self.ingest_record(record, wall_now_ns=received + 1_000_000)
            count += 1
        return count

    def _replay_fixture(self, path: Path) -> None:
        self.feed_fixture_path(path)

    def subscribe(
        self,
        *,
        instrument_id: str,
        capabilities: list[str],
        consumer_id: str,
        priority: int = SubscriptionPriority.ACTIVE_WORKSPACE,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for capability in capabilities:
            result = self.subscriptions.acquire(
                instrument_id=instrument_id,
                capability=capability,
                consumer_id=consumer_id,
                priority=priority,
            )
            results.append(
                {
                    "accepted": result.accepted,
                    "capability": result.key.capability,
                    "instrument_id": result.key.instrument_id,
                    "provider_subscription_active": result.provider_subscription_active,
                    "reason": result.reason,
                    "ref_count": result.ref_count,
                }
            )
        self.lifecycle.active_subscriptions = self.subscriptions.active_subscriptions()
        self.lifecycle.quota_used = len(self.subscriptions.active_keys)
        symbol = instrument_id.upper()
        if symbol not in self.scope_symbols:
            self.scope_symbols.append(symbol)
        return results

    def unsubscribe(
        self,
        *,
        instrument_id: str,
        capabilities: list[str],
        consumer_id: str,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for capability in capabilities:
            result = self.subscriptions.release(
                instrument_id=instrument_id,
                capability=capability,
                consumer_id=consumer_id,
            )
            results.append(
                {
                    "accepted": result.accepted,
                    "capability": result.key.capability,
                    "instrument_id": result.key.instrument_id,
                    "provider_subscription_active": result.provider_subscription_active,
                    "ref_count": result.ref_count,
                }
            )
        self.lifecycle.active_subscriptions = self.subscriptions.active_subscriptions()
        self.lifecycle.quota_used = len(self.subscriptions.active_keys)
        return results

    def simulate_disconnect(self) -> None:
        self.lifecycle.mark_disconnected("SIMULATED_DISCONNECT")
        self.admission.on_disconnect()

    def simulate_reconnect(self) -> None:
        self.lifecycle.mark_reconnecting()
        self.admission.on_reconnect()
        self.lifecycle.mark_connected(provider_generation_id=self.lifecycle.provider_generation_id + 1)
        self.admission.on_connect()
        self.execution_buffer.on_generation_change(self.lifecycle.provider_generation_id)

    def search_symbols(self, query: str) -> list[dict[str, Any]]:
        text = query.strip().upper()
        if not text:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for instrument_id, meta in KNOWN_INSTRUMENTS.items():
            if text in instrument_id or text in meta["provider_symbol"]:
                rows.append(
                    {
                        "instrument_id": instrument_id,
                        "provider_symbol": meta["provider_symbol"],
                        "venue_id": meta["venue_id"],
                    }
                )
                seen.add(instrument_id)
        if text.isalpha() and 1 <= len(text) <= 6 and text not in seen:
            rows.append(
                {
                    "instrument_id": text,
                    "provider_symbol": provider_symbol_for(text),
                    "venue_id": "US_EQUITY",
                }
            )
        return rows

    def instrument_capabilities(self, instrument_id: str) -> list[dict[str, Any]]:
        symbol = instrument_id.upper()
        configured = moomoo_live_enabled()
        stale = self.capability_registry.is_stale
        fresh = self.state.freshness_ms(symbol)
        quote = self.state.quote_for(symbol)
        trades = self.state.trades_for(symbol)
        book = self.state.book_for(symbol)
        rows: list[dict[str, Any]] = []

        def _subscribed(moomoo_cap: MarketCapability) -> bool:
            return any(
                row.get("instrument_id") == symbol and row.get("capability") == moomoo_cap.value
                for row in (self.lifecycle.active_subscriptions or [])
            )

        def _moomoo_row(
            *,
            cap_id: str,
            label: str,
            moomoo_cap: MarketCapability,
            receiving: bool,
        ) -> dict[str, Any]:
            probe = self.capability_probe.get(moomoo_cap.value) or self.capability_registry.get(moomoo_cap)
            entitled = False if probe is None else bool(probe.account_entitled)
            subscribed = _subscribed(moomoo_cap)
            if not configured:
                state, reason = "NOT_CONFIGURED", "IMP_MOOMOO_LIVE_DISABLED"
            elif stale or (probe is not None and probe.reason_code == "PROBE_STALE"):
                state, reason = "UNAVAILABLE", "PROBE_STALE"
            elif not entitled:
                state, reason = "ENTITLEMENT_MISSING", (probe.reason_code if probe else "NOT_PROBED")
            elif subscribed and receiving:
                state, reason = "HEALTHY", None
            elif entitled:
                state, reason = "AVAILABLE", "NOT_SUBSCRIBED" if not subscribed else "AWAITING_FIRST_EVENT"
            else:
                state, reason = "UNAVAILABLE", "NOT_SUBSCRIBED"
            return {
                "capability_id": cap_id,
                "data_provider": "MOOMOO",
                "freshness_ms": fresh,
                "label": label,
                "reason": reason,
                "registry_capability": moomoo_cap.value,
                "state": state,
                "subscribed": subscribed,
            }

        rows.append(
            _moomoo_row(
                cap_id="BASIC_QUOTE",
                label="Live basic quote",
                moomoo_cap=MarketCapability.US_EQUITY_L1,
                receiving=quote is not None,
            )
        )
        rows.append(
            _moomoo_row(
                cap_id="TRADES",
                label="Tick-by-tick trades",
                moomoo_cap=MarketCapability.US_EQUITY_TICKS,
                receiving=bool(trades),
            )
        )
        depth_entitled = False
        depth_probe = self.capability_probe.get(MarketCapability.US_EQUITY_DEPTH.value) or self.capability_registry.get(
            MarketCapability.US_EQUITY_DEPTH
        )
        if depth_probe is not None:
            depth_entitled = bool(depth_probe.account_entitled) and not stale
        rows.append(
            _moomoo_row(
                cap_id="ORDER_BOOK",
                label="MOOMOO ORDER BOOK · MBP" if depth_entitled else "Level 2 order book",
                moomoo_cap=MarketCapability.US_EQUITY_DEPTH,
                receiving=book is not None,
            )
        )
        rows.append(
            _moomoo_row(
                cap_id="ORDER_FLOW",
                label="Order flow / CVD",
                moomoo_cap=MarketCapability.US_EQUITY_TICKS,
                receiving=bool(trades),
            )
        )
        rows.append(
            {
                "capability_id": "REPLAY_FIXTURE",
                "data_provider": "INTERNAL",
                "state": "AVAILABLE" if symbol in {"BIYA", "NVDA"} else "UNAVAILABLE",
                "label": "Replay fixture",
                "reason": None if symbol in {"BIYA", "NVDA"} else "NO_ADMITTED_FIXTURE",
            }
        )
        paper_configured = live_internal_simulation_enabled()
        paper_eligible = paper_configured and self.lifecycle.execution_use == "INTERNAL_PAPER_ELIGIBLE"
        if not paper_configured:
            paper_state, paper_reason = "NOT_CONFIGURED", "INTERNAL_SIMULATION_DISABLED"
        elif paper_eligible:
            paper_state, paper_reason = "AVAILABLE", None
        else:
            paper_state, paper_reason = "AVAILABLE", "AWAITING_ELIGIBLE_LIVE_EVENT"
        rows.append(
            {
                "capability_id": "INTERNAL_PAPER",
                "data_provider": "INTERNAL",
                "state": paper_state,
                "label": "Internal paper simulation",
                "reason": paper_reason,
            }
        )
        return rows

    def live_mark_for(self, instrument_id: str) -> dict[str, Any] | None:
        quote = self.state.quote_for(instrument_id)
        if quote is None:
            return None
        freshness = self.state.freshness_ms(instrument_id)
        quality = quote.quality
        if freshness is not None and freshness > 5000:
            quality = "STALE"
        if self.lifecycle.connection_state in {
            ProviderConnectionState.DISCONNECTED,
            ProviderConnectionState.RECONNECTING,
        }:
            quality = "DISCONNECTED"
        price = quote.last_price or quote.bid_price or quote.ask_price
        if price is None:
            return None
        scale = 100
        mark_minor = int(round(float(price) * scale))
        return {
            "instrument_id": instrument_id.upper(),
            "mark_as_of_ns": quote.available_time_ns,
            "mark_display": f"{price:.4f}",
            "mark_minor": mark_minor,
            "mark_provider": "MOOMOO",
            "mark_quality": quality,
            "freshness_ms": freshness,
        }

    def health_payload(self) -> dict[str, Any]:
        gate = evaluate_internal_simulation_gates(
            runtime=self,
            probe_stale=self.capability_registry.is_stale,
        )
        report = {
            "capability_registry": self.capability_registry.to_dict(),
            "execution_buffer": self.execution_buffer.report(),
            "execution_gate": gate.to_dict(),
            "lifecycle": self.lifecycle.to_dict(),
            "metrics": self.state.metrics_report(),
            "quota": self.subscriptions.quota_report(),
            "scope_symbols": list(self.scope_symbols),
        }
        if self.shadow_recorder is not None:
            report["shadow"] = self.shadow_recorder.health()
        else:
            report["shadow"] = {"shadow_recording_enabled": False}
        return report

    def stop(self) -> None:
        self._stop_event.set()
        if self.feed is not None:
            self.feed.stop()


def get_live_runtime(*, create: bool = True) -> LiveObservationalRuntime | None:
    global _RUNTIME
    if not live_observational_enabled():
        return None
    with _RUNTIME_LOCK:
        if _RUNTIME is None and create:
            _RUNTIME = LiveObservationalRuntime()
            _RUNTIME.configure()
        return _RUNTIME


def reset_live_runtime() -> None:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is not None:
            _RUNTIME.stop()
        _RUNTIME = None
