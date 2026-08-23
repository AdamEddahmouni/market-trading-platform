"""Tradier sandbox paper execution adapter (Platformization P4 sub-milestone 4A).

Fixture-first: CI exercises the adapter deterministically against recorded
sandbox responses (``tests/fixtures/providers/tradier_sandbox_*.json``,
mirroring the ``IMP_LIVE_FIXTURE_FEED`` philosophy). A live HTTP transport is
intentionally **not** implemented until the sandbox wire contract is verified
and recorded in ``docs/providers/TRADIER_PAPER.md``; without a fixture record
the adapter fails closed (``BROKER_TRANSPORT_NOT_IMPLEMENTED``).

Every broker event is serialized through
``broker_execution.build_broker_execution_envelope``, which reuses
``build_provider_metadata`` + ``validate_envelope`` (ADR-PROV-001, audit F2).
"""

from __future__ import annotations

import glob
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from ..broker_execution import (
    BrokerOrderStatusEvent,
    build_broker_execution_envelope,
    build_broker_order_request,
    ensure_broker_fill_ids,
    is_ambiguous_broker_status,
    new_ingest_run_id,
)
from ..contracts import EXECUTION_DISABLED, ProviderResult, SymbolMapping

TRADIER_SANDBOX_ENDPOINT = "https://sandbox.tradier.com/v1"
TRADIER_PROVIDER_ID = "tradier.paper"
TRADIER_CAPABILITY = "paper_execution"
TRADIER_ENTITLEMENT_SANDBOX = "TRADIER_PAPER_SANDBOX"

_FIXTURE_GLOB = "tradier_sandbox_*.json"
_DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "providers"


class TradierReplayStore:
    """Deterministic recorded-response store for sandbox-contract fixtures."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self._records = list(records or [])
        self._calls: Counter[str] = Counter()

    def add_record(self, *, operation: str, match: dict[str, Any], response: dict[str, Any]) -> None:
        self._records.append({"operation": operation, "match": dict(match), "response": dict(response)})

    @classmethod
    def load(cls, directory: Path | None = None) -> TradierReplayStore:
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
        self._calls[operation] += 1
        for record in self._records:
            if record["operation"] != operation:
                continue
            if self._matches(record["match"], match):
                return self._calls[operation], dict(record["response"])
        return self._calls[operation], None

    def call_count(self, operation: str) -> int:
        return self._calls.get(operation, 0)


class TradierPaperExecutionProvider:
    """Paper execution adapter behind the ``PaperExecutionProvider`` contract.

    Fail-closed configuration (P4-SAFE-001): no broker request is possible
    unless all of ``IMP_TRADIER_PAPER``, ``IMP_BROKER_PAPER_EXECUTION``,
    ``IMP_TRADIER_TOKEN`` are set and the endpoint is the sandbox. None of
    these are set in CI.
    """

    provider_id = TRADIER_PROVIDER_ID
    capability = TRADIER_CAPABILITY

    def __init__(
        self,
        *,
        env: dict[str, str] | None = None,
        symbol_map: dict[str, str] | None = None,
        replay_store: TradierReplayStore | None = None,
        enable_identity_symbol: bool = True,
    ) -> None:
        self._env = dict(os.environ if env is None else env)
        self._symbol_map = dict(symbol_map or {})
        self._replay = replay_store if replay_store is not None else TradierReplayStore()
        self._enable_identity_symbol = enable_identity_symbol
        self._entitlement = TRADIER_ENTITLEMENT_SANDBOX

    # -- gates -----------------------------------------------------------------

    def _gate_check(self) -> ProviderResult | None:
        if self._env.get("IMP_TRADIER_PAPER") != "1":
            return ProviderResult(status="unavailable", reason_code=EXECUTION_DISABLED, provider_id=self.provider_id, capability=self.capability)
        if self._env.get("IMP_BROKER_PAPER_EXECUTION") != "1":
            return ProviderResult(status="unavailable", reason_code=EXECUTION_DISABLED, provider_id=self.provider_id, capability=self.capability)
        if not self._env.get("IMP_TRADIER_TOKEN", ""):
            return ProviderResult(status="unavailable", reason_code="TRADIER_TOKEN_NOT_CONFIGURED", provider_id=self.provider_id, capability=self.capability)
        endpoint = self._env.get("IMP_TRADIER_ENDPOINT") or TRADIER_SANDBOX_ENDPOINT
        if endpoint != TRADIER_SANDBOX_ENDPOINT:
            return ProviderResult(status="blocked", reason_code="TRADIER_PRODUCTION_ENDPOINT_BLOCKED", provider_id=self.provider_id, capability=self.capability)
        return None

    # -- symbol resolution (P4-MAP-001) ----------------------------------------

    def resolve_symbol_mapping(self, *, instrument_id: str, symbol: str) -> SymbolMapping:
        """Map a canonical instrument to a Tradier symbol, failing closed."""
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

        _, record = self._replay.dispatch(
            "place_order",
            client_order_id=request.client_order_id,
            idempotency_key=request.idempotency_key,
        )
        if record is None:
            return self._unavailable("BROKER_TRANSPORT_NOT_IMPLEMENTED")

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
                    raw_source_reference=f"tradier:place_order:{request.client_order_id}",
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
        _, record = self._replay.dispatch("fetch_order", broker_order_id=broker_order_id)
        if record is None:
            return self._unavailable("BROKER_TRANSPORT_NOT_IMPLEMENTED")
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
                    raw_source_reference=f"tradier:fetch_order:{broker_order_id}",
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
        _, record = self._replay.dispatch(
            "cancel_order",
            client_order_id=client_order_id,
            broker_order_id=broker_order_id,
        )
        if record is None:
            return self._unavailable("BROKER_TRANSPORT_NOT_IMPLEMENTED")
        status = str(record.get("status", ""))
        if is_ambiguous_broker_status(status):
            return ProviderResult(status="ambiguous", reason_code="BROKER_AMBIGUOUS_OUTCOME", provider_id=self.provider_id, capability=self.capability)
        try:
            status_event = ensure_broker_fill_ids(BrokerOrderStatusEvent.from_record(record))
        except (KeyError, ValueError, TypeError):
            return self._unavailable("BROKER_RESPONSE_INVALID")
        return ProviderResult(status="ok", events=(), provider_id=self.provider_id, capability=self.capability)

    def fetch_account(self) -> ProviderResult:
        gated = self._gate_check()
        if gated is not None:
            return gated
        _, record = self._replay.dispatch("fetch_account")
        if record is None:
            return self._unavailable("BROKER_TRANSPORT_NOT_IMPLEMENTED")
        return ProviderResult(status="ok", events=({**record, "provider_id": self.provider_id, "capability": self.capability},), provider_id=self.provider_id, capability=self.capability)

    def fetch_positions(self) -> ProviderResult:
        gated = self._gate_check()
        if gated is not None:
            return gated
        _, record = self._replay.dispatch("fetch_positions")
        if record is None:
            return self._unavailable("BROKER_TRANSPORT_NOT_IMPLEMENTED")
        return ProviderResult(status="ok", events=({**record, "provider_id": self.provider_id, "capability": self.capability},), provider_id=self.provider_id, capability=self.capability)


def make_tradier_paper_provider(
    *,
    env: dict[str, str] | None = None,
    symbol_map: dict[str, str] | None = None,
    replay_store: TradierReplayStore | None = None,
    enable_identity_symbol: bool = True,
) -> TradierPaperExecutionProvider:
    """Factory: build the Tradier paper adapter with optional explicit config."""
    return TradierPaperExecutionProvider(
        env=env,
        symbol_map=symbol_map,
        replay_store=replay_store,
        enable_identity_symbol=enable_identity_symbol,
    )


__all__ = [
    "TRADIER_CAPABILITY",
    "TRADIER_ENTITLEMENT_SANDBOX",
    "TRADIER_PROVIDER_ID",
    "TRADIER_SANDBOX_ENDPOINT",
    "TradierPaperExecutionProvider",
    "TradierReplayStore",
    "make_tradier_paper_provider",
]
