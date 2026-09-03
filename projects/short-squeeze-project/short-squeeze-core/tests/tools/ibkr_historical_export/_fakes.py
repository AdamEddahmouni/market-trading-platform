"""Synthetic fakes for exporter tests. No socket, no ibapi calls, no real bars."""

from __future__ import annotations

from tools.ibkr_historical_export.models import (
    ApiDiagnostic,
    BarRecord,
    ContractCandidate,
)


def make_candidate(symbol: str = "XNCR", con_id: int = 111, **overrides) -> ContractCandidate:
    base = dict(
        con_id=con_id, symbol=symbol, local_symbol=symbol, sec_type="STK",
        currency="USD", exchange="SMART", primary_exchange="NASDAQ",
        trading_class=symbol, long_name=f"{symbol} Inc", time_zone_id="US/Eastern",
        trading_hours="", liquid_hours="", valid_exchanges="SMART,NASDAQ",
    )
    base.update(overrides)
    return ContractCandidate(**base)


def make_bar(symbol: str, request_name: str, con_id: int, epoch: int, **overrides) -> BarRecord:
    base = dict(
        request_id=1, request_name=request_name, requested_symbol=symbol,
        resolved_con_id=con_id, timestamp_epoch=epoch,
        timestamp_utc="2026-07-17T13:38:00Z", open="10.0", high="11.0",
        low="9.5", close="10.5", volume="1000", wap="10.25", bar_count=42,
    )
    base.update(overrides)
    return BarRecord(**base)


class FakeSession:
    """Scripted stand-in for :class:`IbkrSession` (no socket, no ibapi calls)."""

    def __init__(
        self,
        *,
        connect_ports: set[int] | None = None,
        ready_ports: set[int] | None = None,
        contract_script: dict | None = None,
        historical_script: dict | None = None,
        server_version: int = 187,
        current_time: int = 1_784_000_000,
        occupied_client_ids: set[int] | None = None,
    ) -> None:
        self.connect_ports = connect_ports if connect_ports is not None else {4001, 4002}
        self.ready_ports = ready_ports if ready_ports is not None else {4001, 4002}
        self.contract_script = contract_script or {}
        self.historical_script = historical_script or {}
        self._server_version = server_version
        self._current_time = current_time
        self.occupied_client_ids = occupied_client_ids or set()
        self._connected = False
        self._port: int | None = None
        self._client_id: int | None = None
        self._host: str | None = None
        self._connection_closed = False
        self.diagnostics: list[ApiDiagnostic] = []
        self.contract_calls: list[str] = []
        self.historical_calls: list[tuple[str, str]] = []

    # connection surface
    def connect(self, host, port, client_id):
        self._host, self._port, self._client_id = host, port, client_id
        self._connected = port in self.connect_ports
        self._connection_closed = False

    def record_endpoint(self, host, port, client_id):
        self._host, self._port, self._client_id = host, port, client_id

    def start_run_loop(self):
        pass

    def isConnected(self):  # noqa: N802
        return self._connected and not self._connection_closed

    def is_live(self):
        return self.isConnected()

    def ping(self, timeout):
        return self.isConnected()

    def connection_closed(self):
        self._connection_closed = True
        self._connected = False

    def reconnect(self, timeout):
        if self._port is None or self._client_id is None:
            return False
        self._connected = self._port in self.connect_ports
        self._connection_closed = False
        return self._connected and self._port in self.ready_ports

    def wait_ready(self, timeout):
        if self._client_id in self.occupied_client_ids:
            return False
        return self._connected and self._port in self.ready_ports

    def get_server_version(self):
        return self._server_version

    def fetch_current_time(self, timeout):
        return self._current_time

    def shutdown(self):
        self._connected = False

    # request surface
    def request_contract_details(self, req_id, symbol, timeout):
        self.contract_calls.append(symbol)
        return list(self.contract_script.get(symbol, [])), []

    def request_historical(self, req_id, spec, symbol, con_id, contract, timeout):
        self.historical_calls.append((symbol, spec.request_name))
        entry = self.historical_script.get((symbol, spec.request_name), {})
        bars = list(entry.get("bars", []))
        errors = list(entry.get("errors", []))
        completed = entry.get("completed", True)
        return bars, errors, completed

    def all_diagnostics(self):
        return list(self.diagnostics)


def session_factory(**kwargs):
    """Return a zero-arg factory that yields fresh FakeSessions with the same script."""
    created: list[FakeSession] = []

    def make(**_):
        session = FakeSession(**kwargs)
        created.append(session)
        return session

    make.created = created  # type: ignore[attr-defined]
    return make
