"""Moomoo paper (simulated-environment) execution adapter (Platformization P4, sub-milestone 4C).

Implements the frozen broker-neutral ``PaperExecutionProvider`` contract
(sub-milestone 4A) for the **Moomoo OpenAPI simulated trading environment
only** — a separate environment from the live brokerage; real trading stays
unauthorized (``LIVE-001``). This adapter is explicitly separate from the
observational Moomoo market-data runtime
(``market_platform_foundation.market_data.*``, documented in
``docs/providers/MOOMOO_OBSERVATIONAL.md``): no shared module, no shared gate,
and the observational runtime never gains execution authority through it.

Transport reality (recorded limitation): Moomoo/Futu OpenAPI exposes a
**custom TCP protocol via the local OpenD gateway** — there is no official
HTTP/REST gateway — and the official SDKs wrap that proprietary protobuf
protocol. Under the Phase-0 stdlib-only dependency lock a real-wire transport
is therefore not implementable here. The adapter instead targets an
**injectable transport interface** whose primary implementation is
deterministic recorded-fixture replay (``tests/fixtures/providers/moomoo_*.json``,
mirroring the ``IMP_LIVE_FIXTURE_FEED`` philosophy). An unresolvable operation
fails closed with ``MOOMOO_TRANSPORT_NOT_IMPLEMENTED``; confirming the real
wire requires the vendor SDK outside this repository.

Every broker event is serialized through
``broker_execution.build_broker_execution_envelope``, which reuses
``build_provider_metadata`` + ``validate_envelope`` (ADR-PROV-001, audit F2).
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path
from typing import Any, Protocol

from ..broker_execution import (
    BrokerOrderStatusEvent,
    build_broker_execution_envelope,
    build_broker_order_request,
    ensure_broker_fill_ids,
    is_ambiguous_broker_status,
    new_ingest_run_id,
)
from ..contracts import EXECUTION_DISABLED, ProviderResult, SymbolMapping

MOOMOO_PROVIDER_ID = "moomoo.paper"
MOOMOO_CAPABILITY = "paper_execution"
# Entitlement marks the SEPARATE simulated trading environment of the Moomoo
# OpenAPI — never a live brokerage account.
MOOMOO_ENTITLEMENT_SIMULATED = "MOOMOO_PAPER_SIMULATED"
# The only trade environment this adapter may ever address.
MOOMOO_SIM_TRADE_ENV = "SIMULATE"

_DEFAULT_MOOMOO_HOST = "127.0.0.1"  # local OpenD gateway, loopback only
_DEFAULT_MOOMOO_PORT = "11111"
_ALLOWED_MOOMOO_HOSTS = ("127.0.0.1", "localhost")

_FIXTURE_GLOB = "moomoo_paper_*.json"
_DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "providers"


class MoomooPaperTransport(Protocol):
    """Injectable transport boundary between the adapter and the Moomoo wire.

    The real wire is the proprietary OpenD TCP/protobuf protocol (no official
    HTTP gateway), which cannot be spoken with the stdlib-only lock; recorded
    replay is the governed transport until an out-of-repo SDK confirmation
    lands. Implementations return ``(call_count_after, response_or_none)``
    for one operation call.
    """

    def dispatch(self, operation: str, **match: Any) -> tuple[int, dict[str, Any] | None]:
        ...


class MoomooReplayStore:
    """Deterministic recorded-response store for paper-contract fixtures."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self._records = list(records or [])
        self._calls: dict[str, int] = {}

    def add_record(self, *, operation: str, match: dict[str, Any], response: dict[str, Any]) -> None:
        self._records.append({"operation": operation, "match": dict(match), "response": dict(response)})

    @classmethod
    def load(cls, directory: Path | None = None) -> MoomooReplayStore:
        directory = directory or _DEFAULT_FIXTURE_DIR
        store = cls()
        for path in sorted(glob.glob(str(directory / _FIXTURE_GLOB))):
            with open(path, encoding="utf-8") as handle:
                doc = json.load(handle)
            for record in doc.get("replay", []):
                store.add_record(
                    operation=str(record["operation"]),
                    match=dict(record.get("match", {})),
                    response=dict(record["response"]),
                )
        return store

    def _matches(self, record: dict[str, Any], match: dict[str, Any]) -> bool:
        for key, value in match.items():
            candidate = record.get(key)
            if str(candidate) != str(value):
                return False
        return True

    def dispatch(self, operation: str, **match: Any) -> tuple[int, dict[str, Any] | None]:
        """Return ``(call_count_after, response_or_none)`` for one operation call."""
        self._calls[operation] = self._calls.get(operation, 0) + 1
        for record in self._records:
            if record["operation"] != operation:
                continue
            if self._matches(record["match"], match):
                return self._calls[operation], dict(record["response"])
        return self._calls[operation], None

    def call_count(self, operation: str) -> int:
        return self._calls.get(operation, 0)


class MoomooPaperExecutionProvider:
    """Paper execution adapter behind the ``PaperExecutionProvider`` contract.

    Fail-closed configuration (P4-SAFE-001): no broker request is possible
    unless all of ``IMP_MOOMOO_PAPER``, ``IMP_MOOMOO_PAPER_EXECUTION``, the
    OpenAPI key/secret pair are set, the gateway host is loopback, the port is
    valid, and the trade environment is exactly ``SIMULATE``. None of these
    are set in CI.
    """

    provider_id = MOOMOO_PROVIDER_ID
    capability = MOOMOO_CAPABILITY

    def __init__(
        self,
        *,
        env: dict[str, str] | None = None,
        symbol_map: dict[str, str] | None = None,
        transport: MoomooPaperTransport | None = None,
        enable_identity_symbol: bool = False,
    ) -> None:
        self._env = dict(os.environ if env is None else env)
        self._symbol_map = dict(symbol_map or {})
        # Default transport is recorded-fixture replay. A real OpenD wire
        # transport would be injected here by an out-of-repo integration once
        # the proprietary protocol is confirmed against the vendor SDK.
        self._transport: MoomooPaperTransport = (
            transport if transport is not None else MoomooReplayStore()
        )
        self._enable_identity_symbol = enable_identity_symbol
        self._entitlement = MOOMOO_ENTITLEMENT_SIMULATED

    # -- gates -----------------------------------------------------------------

    def _gate_check(self) -> ProviderResult | None:
        if self._env.get("IMP_MOOMOO_PAPER") != "1":
            return ProviderResult(status="unavailable", reason_code=EXECUTION_DISABLED, provider_id=self.provider_id, capability=self.capability)
        if self._env.get("IMP_MOOMOO_PAPER_EXECUTION") != "1":
            return ProviderResult(status="unavailable", reason_code=EXECUTION_DISABLED, provider_id=self.provider_id, capability=self.capability)
        if not self._env.get("IMP_MOOMOO_PAPER_KEY", "") or not self._env.get("IMP_MOOMOO_PAPER_SECRET", ""):
            return ProviderResult(status="unavailable", reason_code="MOOMOO_CREDENTIALS_NOT_CONFIGURED", provider_id=self.provider_id, capability=self.capability)
        host = self._env.get("IMP_MOOMOO_PAPER_HOST") or _DEFAULT_MOOMOO_HOST
        if host not in _ALLOWED_MOOMOO_HOSTS:
            return ProviderResult(status="blocked", reason_code="MOOMOO_NON_LOCALHOST_HOST_BLOCKED", provider_id=self.provider_id, capability=self.capability)
        port_raw = self._env.get("IMP_MOOMOO_PAPER_PORT") or _DEFAULT_MOOMOO_PORT
        try:
            port = int(port_raw)
        except ValueError:
            port = -1
        if not 1 <= port <= 65535:
            return ProviderResult(status="blocked", reason_code="MOOMOO_PORT_INVALID", provider_id=self.provider_id, capability=self.capability)
        trade_env = self._env.get("IMP_MOOMOO_PAPER_TRADE_ENV") or MOOMOO_SIM_TRADE_ENV
        if trade_env != MOOMOO_SIM_TRADE_ENV:
            return ProviderResult(status="blocked", reason_code="MOOMOO_PRODUCTION_TRADE_ENV_BLOCKED", provider_id=self.provider_id, capability=self.capability)
        return None

    # -- symbol resolution (P4-MAP-001) ----------------------------------------

    def resolve_symbol_mapping(self, *, instrument_id: str, symbol: str) -> SymbolMapping:
        """Map a canonical instrument to a Moomoo code (e.g. ``US.AAPL``),
        failing closed. Identity mapping is opt-in only — the Moomoo wire uses
        market-prefixed codes, so identity is wrong by default."""
        if instrument_id in self._symbol_map:
            provider_symbol = self._symbol_map[instrument_id]
        elif self._enable_identity_symbol and instrument_id == symbol:
            provider_symbol = symbol
        else:
            raise ValueError(f"UNMAPPED_INSTRUMENT: {instrument_id}")
        return SymbolMapping(
            provider_symbol=provider_symbol,
            instrument_id=instrument_id,
            venue_id="US_EQUITY",
        )

    # -- envelope helper --------------------------------------------------------

    def _status_envelope(
        self,
        status_event: BrokerOrderStatusEvent,
        *,
        mapping: SymbolMapping,
        raw_source_reference: str,
        ingest_run_id: str,
    ) -> dict[str, Any]:
        return build_broker_execution_envelope(
            broker_event_type="ORDER_STATUS",
            instrument_id=mapping.instrument_id,
            symbol_mapping=mapping,
            provider_id=self.provider_id,
            entitlement=self._entitlement,
            event_time_ns=status_event.event_time_ns,
            receive_time_ns=status_event.receive_time_ns,
            available_time_ns=status_event.receive_time_ns,
            raw_source_reference=raw_source_reference,
            source_record_id=status_event.broker_order_id,
            payload=status_event.to_dict(),
            ingest_run_id=ingest_run_id,
        )

    def _unavailable(self, reason_code: str) -> ProviderResult:
        return ProviderResult(status="unavailable", reason_code=reason_code, provider_id=self.provider_id, capability=self.capability)

    # -- PaperExecutionProvider -------------------------------------------------

    def place_order(self, intent: dict[str, Any]) -> ProviderResult:
        gated = self._gate_check()
        if gated is not None:
            return gated
        instrument_id = str(intent.get("instrument_id", ""))
        symbol = str(intent.get("instrument", {}).get("symbol", instrument_id))
        try:
            mapping = self.resolve_symbol_mapping(instrument_id=instrument_id, symbol=symbol)
        except ValueError:
            return ProviderResult(status="error", reason_code="UNMAPPED_INSTRUMENT", provider_id=self.provider_id, capability=self.capability)

        try:
            request = build_broker_order_request(intent, broker_symbol=mapping.provider_symbol)
        except KeyError:
            return self._unavailable("BROKER_REQUEST_INVALID")

        _, record = self._transport.dispatch(
            "place_order",
            client_order_id=request.client_order_id,
            idempotency_key=request.idempotency_key,
        )
        if record is None:
            return self._unavailable("MOOMOO_TRANSPORT_NOT_IMPLEMENTED")

        status = str(record.get("status", ""))
        if is_ambiguous_broker_status(status):
            return ProviderResult(
                status="ambiguous",
                reason_code="BROKER_AMBIGUOUS_OUTCOME",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        try:
            status_event = ensure_broker_fill_ids(
                BrokerOrderStatusEvent.from_record(record)
            )
        except (KeyError, ValueError, TypeError):
            return self._unavailable("BROKER_RESPONSE_INVALID")

        return ProviderResult(
            status="ok",
            events=(
                self._status_envelope(
                    status_event,
                    mapping=mapping,
                    raw_source_reference=f"moomoo:place_order:{request.client_order_id}",
                    ingest_run_id=new_ingest_run_id(),
                ),
            ),
            provider_id=self.provider_id,
            capability=self.capability,
        )

    # -- adapter-local methods (not on the Protocol) ----------------------------

    def fetch_order(self, broker_order_id: str) -> ProviderResult:
        gated = self._gate_check()
        if gated is not None:
            return gated
        _, record = self._transport.dispatch("fetch_order", broker_order_id=broker_order_id)
        if record is None:
            return self._unavailable("MOOMOO_TRANSPORT_NOT_IMPLEMENTED")
        try:
            status_event = ensure_broker_fill_ids(BrokerOrderStatusEvent.from_record(record))
        except (KeyError, ValueError, TypeError):
            return self._unavailable("BROKER_RESPONSE_INVALID")
        mapping = SymbolMapping(provider_symbol=str(record.get("symbol", broker_order_id)), instrument_id=str(record.get("instrument_id", "")), venue_id="US_EQUITY")
        return ProviderResult(
            status="ok",
            events=(
                self._status_envelope(
                    status_event,
                    mapping=mapping,
                    raw_source_reference=f"moomoo:fetch_order:{broker_order_id}",
                    ingest_run_id=new_ingest_run_id(),
                ),
            ),
            provider_id=self.provider_id,
            capability=self.capability,
        )

    def cancel_order(self, *, client_order_id: str | None = None, broker_order_id: str | None = None) -> ProviderResult:
        gated = self._gate_check()
        if gated is not None:
            return gated
        _, record = self._transport.dispatch(
            "cancel_order",
            client_order_id=client_order_id,
            broker_order_id=broker_order_id,
        )
        if record is None:
            return self._unavailable("MOOMOO_TRANSPORT_NOT_IMPLEMENTED")
        status = str(record.get("status", ""))
        if is_ambiguous_broker_status(status):
            return ProviderResult(status="ambiguous", reason_code="BROKER_AMBIGUOUS_OUTCOME", provider_id=self.provider_id, capability=self.capability)
        try:
            ensure_broker_fill_ids(BrokerOrderStatusEvent.from_record(record))
        except (KeyError, ValueError, TypeError):
            return self._unavailable("BROKER_RESPONSE_INVALID")
        return ProviderResult(status="ok", events=(), provider_id=self.provider_id, capability=self.capability)

    def fetch_account(self) -> ProviderResult:
        gated = self._gate_check()
        if gated is not None:
            return gated
        _, record = self._transport.dispatch("fetch_account")
        if record is None:
            return self._unavailable("MOOMOO_TRANSPORT_NOT_IMPLEMENTED")
        return ProviderResult(status="ok", events=({**record, "provider_id": self.provider_id, "capability": self.capability},), provider_id=self.provider_id, capability=self.capability)

    def fetch_positions(self) -> ProviderResult:
        gated = self._gate_check()
        if gated is not None:
            return gated
        _, record = self._transport.dispatch("fetch_positions")
        if record is None:
            return self._unavailable("MOOMOO_TRANSPORT_NOT_IMPLEMENTED")
        return ProviderResult(status="ok", events=({**record, "provider_id": self.provider_id, "capability": self.capability},), provider_id=self.provider_id, capability=self.capability)


def make_moomoo_paper_provider(
    *,
    env: dict[str, str] | None = None,
    symbol_map: dict[str, str] | None = None,
    transport: MoomooPaperTransport | None = None,
    enable_identity_symbol: bool = False,
) -> MoomooPaperExecutionProvider:
    """Factory: build the Moomoo paper adapter with optional explicit config."""
    return MoomooPaperExecutionProvider(
        env=env,
        symbol_map=symbol_map,
        transport=transport,
        enable_identity_symbol=enable_identity_symbol,
    )


__all__ = [
    "MOOMOO_CAPABILITY",
    "MOOMOO_ENTITLEMENT_SIMULATED",
    "MOOMOO_PROVIDER_ID",
    "MOOMOO_SIM_TRADE_ENV",
    "MoomooPaperExecutionProvider",
    "MoomooPaperTransport",
    "MoomooReplayStore",
    "make_moomoo_paper_provider",
]
