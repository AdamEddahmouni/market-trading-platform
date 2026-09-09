"""Shared fakes for IBKR observational adapter tests (G6).

Kept outside the ``test_*.py`` glob so it is never discovered as a test
module. The fake transport records every observational request; it has no
execution surface at all, mirroring the adapter's safety boundary.
"""

from __future__ import annotations

from typing import Any

from market_platform_foundation.providers.ibkr_observational.adapter import (
    IbkrObservationalAdapter,
    IbkrObservationalConfig,
)
from market_platform_foundation.xa01.contracts import (
    CanonicalInstrumentIdentity,
    InstrumentDescriptor,
    InstrumentRecord,
)
from market_platform_foundation.xa01.enums import (
    IDENTITY_PROFILE,
    InstrumentKind,
    XaAssetClass,
)


class FakeTransport:
    """Observational-only fake transport (records requests; never executes)."""

    def __init__(self) -> None:
        self.connected = False
        self.connect_calls: list[dict[str, Any]] = []
        self.disconnect_calls = 0
        self.mkt_data_requests: list[tuple[int, Any]] = []
        self.mkt_depth_requests: list[tuple[int, Any, int, bool]] = []
        self.tick_by_tick_requests: list[tuple[int, Any]] = []
        self.mkt_data_cancels: list[int] = []
        self.mkt_depth_cancels: list[tuple[int, bool]] = []
        self.tick_by_tick_cancels: list[int] = []

    def connect(self, *, host: str, port: int, client_id: int, readonly: bool = True) -> None:
        self.connected = True
        self.connect_calls.append(
            {"host": host, "port": port, "client_id": client_id, "readonly": readonly}
        )

    def disconnect(self) -> None:
        self.connected = False
        self.disconnect_calls += 1

    def is_connected(self) -> bool:
        return self.connected

    def req_mkt_data(
        self, req_id: int, contract: Any, *, generic_ticks: str = "", snapshot: bool = False
    ) -> None:
        self.mkt_data_requests.append((req_id, contract))

    def cancel_mkt_data(self, req_id: int) -> None:
        self.mkt_data_cancels.append(req_id)

    def req_mkt_depth(
        self, req_id: int, contract: Any, *, num_rows: int, is_smart_depth: bool = False
    ) -> None:
        self.mkt_depth_requests.append((req_id, contract, num_rows, is_smart_depth))

    def cancel_mkt_depth(self, req_id: int, *, is_smart_depth: bool = False) -> None:
        self.mkt_depth_cancels.append((req_id, is_smart_depth))

    def req_tick_by_tick_data(
        self, req_id: int, contract: Any, *, tick_type: str = "AllLast", number_of_ticks: int = 0, ignore_size: bool = False
    ) -> None:
        self.tick_by_tick_requests.append((req_id, contract))

    def cancel_tick_by_tick_data(self, req_id: int) -> None:
        self.tick_by_tick_cancels.append(req_id)


def make_record(
    canonical_id: str,
    *,
    kind: InstrumentKind = InstrumentKind.TRADABLE_SECURITY,
    asset_class: XaAssetClass = XaAssetClass.EQUITY,
) -> InstrumentRecord:
    return InstrumentRecord(
        descriptor=InstrumentDescriptor(
            identity=CanonicalInstrumentIdentity(
                canonical_id=canonical_id,
                instrument_kind=kind,
                asset_class=asset_class,
                identity_profile=IDENTITY_PROFILE,
                identity_key={"ticker": canonical_id},
            ),
            display_name=canonical_id,
        )
    )


class FakeLookup:
    """Minimal ``InstrumentLookup`` over canned canonical records."""

    def __init__(self, *records: InstrumentRecord) -> None:
        self._records = {record.descriptor.identity.canonical_id: record for record in records}

    def get(self, canonical_id: str) -> InstrumentRecord:
        try:
            return self._records[canonical_id]
        except KeyError as exc:
            raise KeyError(f"unknown instrument {canonical_id!r}") from exc


def make_adapter(
    *,
    live: bool = True,
    store: Any | None = None,
    lookup: FakeLookup | None = None,
    transport: FakeTransport | None = None,
    max_l1: int = 50,
    max_l2: int = 20,
    max_reconnect: int = 3,
    default_depth_levels: int = 20,
) -> tuple[IbkrObservationalAdapter, FakeTransport]:
    transport = transport or FakeTransport()
    config = IbkrObservationalConfig(
        live_enabled=live,
        max_l1_subscriptions=max_l1,
        max_l2_subscriptions=max_l2,
        max_reconnect_attempts=max_reconnect,
        default_depth_levels=default_depth_levels,
    )
    adapter = IbkrObservationalAdapter(
        config,
        transport=transport,
        store=store,
        lookup=lookup,
    )
    return adapter, transport


def connected_adapter(
    *,
    store: Any | None = None,
    lookup: FakeLookup | None = None,
    transport: FakeTransport | None = None,
    max_l1: int = 50,
    max_l2: int = 20,
    max_reconnect: int = 3,
) -> tuple[IbkrObservationalAdapter, FakeTransport]:
    adapter, transport = make_adapter(
        live=True,
        store=store,
        lookup=lookup,
        transport=transport,
        max_l1=max_l1,
        max_l2=max_l2,
        max_reconnect=max_reconnect,
    )
    adapter.connect()
    return adapter, transport


class FakeQueryProvider:
    """Read-only fake query provider for G11 offline tests."""

    def __init__(
        self,
        *,
        secdef_rows: dict[str, list[dict[str, Any]]] | None = None,
        history_payloads: dict[int, dict[str, Any]] | None = None,
        accounts_payload: dict[str, Any] | None = None,
        available: bool = True,
    ) -> None:
        self.secdef_rows = secdef_rows or {}
        self.history_payloads = history_payloads or {}
        self.accounts_payload = accounts_payload or {"accounts": ["DU1234567"]}
        self.available = available
        self.shutdown_calls = 0
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def is_available(self) -> bool:
        return self.available and self.shutdown_calls == 0

    def fetch_secdef_search(self, symbol: str) -> list[dict[str, Any]]:
        self.requests.append(("secdef", {"symbol": symbol}))
        return list(self.secdef_rows.get(symbol.upper(), []))

    def fetch_historical_bars(
        self,
        *,
        con_id: int,
        period: str,
        bar: str,
    ) -> dict[str, Any]:
        self.requests.append(
            ("history", {"con_id": con_id, "period": period, "bar": bar})
        )
        return dict(
            self.history_payloads.get(
                con_id,
                {
                    "data": [
                        {
                            "t": 1_700_000_000,
                            "o": 1,
                            "h": 2,
                            "l": 0.5,
                            "c": 1.5,
                            "v": 100,
                        }
                    ]
                },
            )
        )

    def fetch_portfolio_accounts(self) -> dict[str, Any]:
        self.requests.append(("accounts", {}))
        return dict(self.accounts_payload)

    def shutdown(self) -> None:
        self.shutdown_calls += 1
        self.available = False