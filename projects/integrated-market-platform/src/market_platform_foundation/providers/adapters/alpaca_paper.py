"""Alpaca Paper execution adapter — paper-api.alpaca.markets, stdlib urllib.

P4 amendment: Alpaca **Paper host** via stdlib urllib is authorized. Live
``api.alpaca.markets`` remains unauthorized. The Alpaca SDK is never imported
(Phase 0 ``alpaca`` module root stays prohibited).

Fixture-first: without ``IMP_ALPACA_PAPER_HTTP=1`` unmatched operations fail
closed (``BROKER_TRANSPORT_NOT_IMPLEMENTED``). Tradier #41 remains in tree.
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
from .alpaca_paper_http import (
    ALPACA_PAPER_ORIGIN,
    AlpacaHttpTransport,
    AlpacaPaperHttpError,
    AlpacaPaperHttpTransport,
    alpaca_http_cancel_order,
    alpaca_http_fetch_account,
    alpaca_http_fetch_order,
    alpaca_http_fetch_positions,
    alpaca_http_place_order,
    canonicalize_alpaca_paper_origin,
)

ALPACA_PROVIDER_ID = "alpaca.paper"
ALPACA_CAPABILITY = "paper_execution"
ALPACA_ENTITLEMENT_PAPER = "ALPACA_PAPER"
ALPACA_PAPER_HTTP_GATE = "IMP_ALPACA_PAPER_HTTP"

_FIXTURE_GLOB = "alpaca_paper_*.json"
_DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "providers"


class AlpacaReplayStore:
    """Deterministic recorded-response store for Paper-contract fixtures."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self._records = list(records or [])
        self._calls: Counter[str] = Counter()

    def add_record(self, *, operation: str, match: dict[str, Any], response: dict[str, Any]) -> None:
        self._records.append({"operation": operation, "match": dict(match), "response": dict(response)})

    @classmethod
    def load(cls, directory: Path | None = None) -> AlpacaReplayStore:
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
        self._calls[operation] += 1
        for record in self._records:
            if record["operation"] != operation:
                continue
            if self._matches(record["match"], match):
                return self._calls[operation], dict(record["response"])
        return self._calls[operation], None

    def call_count(self, operation: str) -> int:
        return self._calls.get(operation, 0)


class AlpacaPaperExecutionProvider:
    """Paper execution adapter behind the ``PaperExecutionProvider`` contract.

    Fail-closed: no broker request unless ``IMP_ALPACA_PAPER``,
    ``IMP_BROKER_PAPER_EXECUTION``, paper keys, and the Paper origin are set.
    None of these are set in CI.
    """

    provider_id = ALPACA_PROVIDER_ID
    capability = ALPACA_CAPABILITY

    def __init__(
        self,
        *,
        env: dict[str, str] | None = None,
        symbol_map: dict[str, str] | None = None,
        replay_store: AlpacaReplayStore | None = None,
        enable_identity_symbol: bool = True,
        http_transport: AlpacaHttpTransport | None = None,
    ) -> None:
        self._env = dict(os.environ if env is None else env)
        self._symbol_map = dict(symbol_map or {})
        self._replay = replay_store if replay_store is not None else AlpacaReplayStore()
        self._enable_identity_symbol = enable_identity_symbol
        self._entitlement = ALPACA_ENTITLEMENT_PAPER
        self._http = http_transport

    def _gate_check(self) -> ProviderResult | None:
        if self._env.get("IMP_ALPACA_PAPER") != "1":
            return ProviderResult(
                status="unavailable",
                reason_code=EXECUTION_DISABLED,
                provider_id=self.provider_id,
                capability=self.capability,
            )
        if self._env.get("IMP_BROKER_PAPER_EXECUTION") != "1":
            return ProviderResult(
                status="unavailable",
                reason_code=EXECUTION_DISABLED,
                provider_id=self.provider_id,
                capability=self.capability,
            )
        if not self._key_id() or not self._secret_key():
            return ProviderResult(
                status="unavailable",
                reason_code="COMPARATOR_NOT_CONFIGURED",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        try:
            canonicalize_alpaca_paper_origin(self._origin_raw())
        except AlpacaPaperHttpError as exc:
            code = str(exc)
            return ProviderResult(
                status="blocked",
                reason_code=code.split(":", 1)[0],
                provider_id=self.provider_id,
                capability=self.capability,
            )
        return None

    def _paper_http_enabled(self) -> bool:
        return self._env.get(ALPACA_PAPER_HTTP_GATE) == "1"

    def _key_id(self) -> str:
        return str(self._env.get("APCA_API_KEY_ID") or "").strip()

    def _secret_key(self) -> str:
        return str(self._env.get("APCA_API_SECRET_KEY") or "").strip()

    def _origin_raw(self) -> str:
        return str(
            self._env.get("APCA_API_BASE_URL") or self._env.get("ALPACA_BASE_URL") or ALPACA_PAPER_ORIGIN
        ).strip()

    def _origin(self) -> str:
        return canonicalize_alpaca_paper_origin(self._origin_raw() or None)

    def _http_transport(self) -> AlpacaHttpTransport:
        if self._http is not None:
            return self._http
        return AlpacaPaperHttpTransport()

    def _wire_or_unavailable(
        self,
        *,
        record: dict[str, Any] | None,
        wire_fn,
    ) -> dict[str, Any] | ProviderResult:
        if record is not None:
            return record
        if not self._paper_http_enabled():
            return self._unavailable("BROKER_TRANSPORT_NOT_IMPLEMENTED")
        try:
            wired = wire_fn()
        except AlpacaPaperHttpError as exc:
            code = str(exc)
            reason = code.split(":", 1)[0]
            if code.startswith("LIVE_FORBIDDEN") or "HOST_FORBIDDEN" in code:
                return ProviderResult(
                    status="blocked",
                    reason_code=reason,
                    provider_id=self.provider_id,
                    capability=self.capability,
                )
            return self._unavailable(reason)
        if wired is None:
            return self._unavailable("BROKER_TRANSPORT_NOT_IMPLEMENTED")
        return wired

    def resolve_symbol_mapping(self, *, instrument_id: str, symbol: str) -> SymbolMapping:
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
        return ProviderResult(
            status="unavailable",
            reason_code=reason_code,
            provider_id=self.provider_id,
            capability=self.capability,
        )

    def place_order(self, intent: dict[str, Any]) -> ProviderResult:
        gated = self._gate_check()
        if gated is not None:
            return gated
        instrument_id = str(intent.get("instrument_id", ""))
        symbol = str(intent.get("instrument", {}).get("symbol", instrument_id))
        try:
            mapping = self.resolve_symbol_mapping(instrument_id=instrument_id, symbol=symbol)
        except ValueError:
            return ProviderResult(
                status="error",
                reason_code="UNMAPPED_INSTRUMENT",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        try:
            request = build_broker_order_request(intent, broker_symbol=mapping.provider_symbol)
        except KeyError:
            return self._unavailable("BROKER_REQUEST_INVALID")
        _, record = self._replay.dispatch(
            "place_order",
            client_order_id=request.client_order_id,
            idempotency_key=request.idempotency_key,
        )
        resolved = self._wire_or_unavailable(
            record=record,
            wire_fn=lambda: alpaca_http_place_order(
                self._http_transport(),
                origin=self._origin(),
                key_id=self._key_id(),
                secret_key=self._secret_key(),
                request=request,
                instrument_id=mapping.instrument_id,
            ),
        )
        if isinstance(resolved, ProviderResult):
            return resolved
        record = resolved
        status = str(record.get("status", ""))
        if is_ambiguous_broker_status(status):
            return ProviderResult(
                status="ambiguous",
                reason_code="BROKER_AMBIGUOUS_OUTCOME",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        try:
            status_event = ensure_broker_fill_ids(BrokerOrderStatusEvent.from_record(record))
        except (KeyError, ValueError, TypeError):
            return self._unavailable("BROKER_RESPONSE_INVALID")
        return ProviderResult(
            status="ok",
            events=(
                self._status_envelope(
                    status_event,
                    mapping=mapping,
                    raw_source_reference=f"alpaca:place_order:{request.client_order_id}",
                    ingest_run_id=new_ingest_run_id(),
                ),
            ),
            provider_id=self.provider_id,
            capability=self.capability,
        )

    def fetch_order(self, broker_order_id: str) -> ProviderResult:
        gated = self._gate_check()
        if gated is not None:
            return gated
        _, record = self._replay.dispatch("fetch_order", broker_order_id=broker_order_id)
        resolved = self._wire_or_unavailable(
            record=record,
            wire_fn=lambda: alpaca_http_fetch_order(
                self._http_transport(),
                origin=self._origin(),
                key_id=self._key_id(),
                secret_key=self._secret_key(),
                broker_order_id=broker_order_id,
            ),
        )
        if isinstance(resolved, ProviderResult):
            return resolved
        record = resolved
        try:
            status_event = ensure_broker_fill_ids(BrokerOrderStatusEvent.from_record(record))
        except (KeyError, ValueError, TypeError):
            return self._unavailable("BROKER_RESPONSE_INVALID")
        mapping = SymbolMapping(
            provider_symbol=str(record.get("symbol", broker_order_id)),
            instrument_id=str(record.get("instrument_id", "")),
            venue_id="US_EQUITY",
        )
        return ProviderResult(
            status="ok",
            events=(
                self._status_envelope(
                    status_event,
                    mapping=mapping,
                    raw_source_reference=f"alpaca:fetch_order:{broker_order_id}",
                    ingest_run_id=new_ingest_run_id(),
                ),
            ),
            provider_id=self.provider_id,
            capability=self.capability,
        )

    def cancel_order(
        self, *, client_order_id: str | None = None, broker_order_id: str | None = None
    ) -> ProviderResult:
        gated = self._gate_check()
        if gated is not None:
            return gated
        _, record = self._replay.dispatch(
            "cancel_order",
            client_order_id=client_order_id,
            broker_order_id=broker_order_id,
        )
        resolved = self._wire_or_unavailable(
            record=record,
            wire_fn=lambda: alpaca_http_cancel_order(
                self._http_transport(),
                origin=self._origin(),
                key_id=self._key_id(),
                secret_key=self._secret_key(),
                broker_order_id=str(broker_order_id or ""),
            ),
        )
        if isinstance(resolved, ProviderResult):
            return resolved
        record = resolved
        status = str(record.get("status", ""))
        if is_ambiguous_broker_status(status):
            return ProviderResult(
                status="ambiguous",
                reason_code="BROKER_AMBIGUOUS_OUTCOME",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        try:
            status_event = ensure_broker_fill_ids(BrokerOrderStatusEvent.from_record(record))
        except (KeyError, ValueError, TypeError):
            return self._unavailable("BROKER_RESPONSE_INVALID")
        events = (
            self._status_envelope(
                status_event,
                mapping=SymbolMapping(
                    provider_symbol=str(record.get("symbol", broker_order_id or "")),
                    instrument_id=str(record.get("instrument_id", "")),
                    venue_id="US_EQUITY",
                ),
                raw_source_reference=f"alpaca:cancel_order:{broker_order_id}",
                ingest_run_id=new_ingest_run_id(),
            ),
        )
        return ProviderResult(
            status="ok", events=events, provider_id=self.provider_id, capability=self.capability
        )

    def fetch_account(self) -> ProviderResult:
        gated = self._gate_check()
        if gated is not None:
            return gated
        _, record = self._replay.dispatch("fetch_account")
        resolved = self._wire_or_unavailable(
            record=record,
            wire_fn=lambda: alpaca_http_fetch_account(
                self._http_transport(),
                origin=self._origin(),
                key_id=self._key_id(),
                secret_key=self._secret_key(),
            ),
        )
        if isinstance(resolved, ProviderResult):
            return resolved
        record = resolved
        return ProviderResult(
            status="ok",
            events=({**record, "provider_id": self.provider_id, "capability": self.capability},),
            provider_id=self.provider_id,
            capability=self.capability,
        )

    def fetch_positions(self) -> ProviderResult:
        gated = self._gate_check()
        if gated is not None:
            return gated
        _, record = self._replay.dispatch("fetch_positions")
        resolved = self._wire_or_unavailable(
            record=record,
            wire_fn=lambda: alpaca_http_fetch_positions(
                self._http_transport(),
                origin=self._origin(),
                key_id=self._key_id(),
                secret_key=self._secret_key(),
            ),
        )
        if isinstance(resolved, ProviderResult):
            return resolved
        record = resolved
        return ProviderResult(
            status="ok",
            events=({**record, "provider_id": self.provider_id, "capability": self.capability},),
            provider_id=self.provider_id,
            capability=self.capability,
        )


def make_alpaca_paper_provider(
    *,
    env: dict[str, str] | None = None,
    symbol_map: dict[str, str] | None = None,
    replay_store: AlpacaReplayStore | None = None,
    enable_identity_symbol: bool = True,
    http_transport: AlpacaHttpTransport | None = None,
) -> AlpacaPaperExecutionProvider:
    """Factory: build the Alpaca Paper adapter with optional explicit config."""
    return AlpacaPaperExecutionProvider(
        env=env,
        symbol_map=symbol_map,
        replay_store=replay_store,
        enable_identity_symbol=enable_identity_symbol,
        http_transport=http_transport,
    )


__all__ = [
    "ALPACA_CAPABILITY",
    "ALPACA_ENTITLEMENT_PAPER",
    "ALPACA_PAPER_HTTP_GATE",
    "ALPACA_PAPER_ORIGIN",
    "ALPACA_PROVIDER_ID",
    "AlpacaPaperExecutionProvider",
    "AlpacaReplayStore",
    "make_alpaca_paper_provider",
]
