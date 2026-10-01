"""IBKR delayed futures quotes and bars for the Screener (read-only, outer boundary).

Implements ``DelayedFuturesSource`` over one read-only IB Gateway/TWS connection that
lives on its own thread. It requests *delayed* market data only (market data type 3),
places no orders, and reads no account data. ``src/market_platform_foundation`` never
imports this module; ``install_delayed_futures_source`` injects it.

A contract is used only when IBKR returns exactly one USD future for the catalog's
root and contract month whose last trade date is within a week of the catalog's
expiry. Anything ambiguous or unknown stays unavailable; nothing is guessed.
"""

from __future__ import annotations

import logging
import math
import os
import queue
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from market_platform_foundation.market_data.delayed_futures_bridge import (
    FuturesContractRef,
    inject_delayed_futures_source,
)

from .config import IbkrConfig

ROOT = Path(__file__).resolve().parents[2]
DELAYED_MARKET_DATA = 3
MAX_LINES = 60                 # concurrent delayed subscriptions (IBKR allows 100 lines by default)
IDLE_SECONDS = 90.0            # a contract nobody asked for in this long is unsubscribed
RECONNECT_SECONDS = 20.0
RESOLVE_PER_STEP = 8
BAR_CACHE_SECONDS = 60.0
BAR_WAIT_SECONDS = 12.0
EXPIRY_TOLERANCE_DAYS = 7
CLIENT_ID_OFFSET = 31          # distinct from the observational transport's client id
BAR_REQUEST = {"1m": ("1 D", "1 min", 60), "5m": ("2 D", "5 mins", 300), "15m": ("5 D", "15 mins", 900)}


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _default_ib() -> Any:
    from ib_insync import IB

    logging.getLogger("ib_insync").setLevel(logging.CRITICAL)
    return IB()


def _default_future(root: str, contract_month: str) -> Any:
    from ib_insync import Future

    return Future(symbol=root, lastTradeDateOrContractMonth=contract_month, currency="USD")


def _expiry_of(contract: Any) -> date | None:
    raw = str(getattr(contract, "lastTradeDateOrContractMonth", "") or "")[:8]
    try:
        return datetime.strptime(raw, "%Y%m%d").date()
    except ValueError:
        return None


class IbkrDelayedFutures:
    def __init__(self, *, host: str, port: int, client_id: int,
                 ib_factory: Callable[[], Any] = _default_ib,
                 future_factory: Callable[[str, str], Any] = _default_future,
                 clock: Callable[[], float] = time.time) -> None:
        self._host, self._port, self._client_id = host, port, client_id
        self._ib_factory, self._future_factory, self._clock = ib_factory, future_factory, clock
        self._lock = threading.Lock()
        self._wanted: dict[str, tuple[FuturesContractRef, float]] = {}
        self._quotes: dict[str, dict[str, Any]] = {}
        self._bars: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
        self._bar_requests: queue.Queue[tuple[FuturesContractRef, str, threading.Event]] = queue.Queue()
        self._status: dict[str, Any] = {"connected": False, "reason": "NOT_STARTED"}
        # Worker-thread state only:
        self._contracts: dict[str, Any | None] = {}      # key -> qualified contract, None = no unique match
        self._tickers: dict[str, Any] = {}
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ public (any thread)
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="ibkr-delayed-futures", daemon=True)
            self._thread.start()

    def quotes(self, contracts: list[FuturesContractRef]) -> dict[str, dict[str, Any]]:
        now = self._clock()
        with self._lock:
            for contract in contracts:
                self._wanted[contract.key] = (contract, now)
            return {contract.key: dict(self._quotes[contract.key]) for contract in contracts if contract.key in self._quotes}

    def bars(self, contract: FuturesContractRef, timeframe: str) -> list[dict[str, Any]] | None:
        if timeframe not in BAR_REQUEST:
            return None
        with self._lock:
            self._wanted.setdefault(contract.key, (contract, self._clock()))
            cached = self._bars.get((contract.key, timeframe))
            connected = self._status["connected"]
        if cached and self._clock() - cached[0] < BAR_CACHE_SECONDS:
            return cached[1]
        if not connected:
            return cached[1] if cached else None
        done = threading.Event()
        self._bar_requests.put((contract, timeframe, done))
        done.wait(BAR_WAIT_SECONDS)
        with self._lock:
            cached = self._bars.get((contract.key, timeframe))
        return cached[1] if cached else None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    # ------------------------------------------------------------------ worker thread
    def _set_status(self, connected: bool, reason: str | None) -> None:
        with self._lock:
            self._status = {"connected": connected, "reason": reason}

    def _run(self) -> None:
        import asyncio

        asyncio.set_event_loop(asyncio.new_event_loop())
        while True:
            ib = None
            try:
                ib = self._ib_factory()
                ib.connect(self._host, self._port, clientId=self._client_id, readonly=True, timeout=15)
                ib.reqMarketDataType(DELAYED_MARKET_DATA)
                self._set_status(True, None)
                while ib.isConnected():
                    self._step(ib)
                    ib.sleep(0.5)
                self._set_status(False, "DISCONNECTED")
            except Exception as exc:  # noqa: BLE001 — provider boundary: report and retry
                self._set_status(False, f"IBKR_UNAVAILABLE:{type(exc).__name__}")
            finally:
                self._contracts.clear()
                self._tickers.clear()
                with self._lock:
                    self._quotes.clear()
                try:
                    if ib is not None:
                        ib.disconnect()
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(RECONNECT_SECONDS)

    def _resolve(self, ib: Any, ref: FuturesContractRef) -> Any | None:
        try:
            expected = date.fromisoformat(ref.expiry)
        except ValueError:
            return None
        details = ib.reqContractDetails(self._future_factory(ref.root, ref.contract_month))
        matches: dict[Any, Any] = {}
        # IBKR lists one contract (one conId) once per routing venue; its algo venues carry no chart data,
        # so the listing exchange is taken first.
        ordered = sorted((detail.contract for detail in details or []),
                         key=lambda contract: str(getattr(contract, "exchange", "")).upper().endswith("ALGO"))
        for contract in ordered:
            expiry = _expiry_of(contract)
            if (str(getattr(contract, "currency", "")) == "USD" and expiry is not None
                    and abs((expiry - expected).days) <= EXPIRY_TOLERANCE_DAYS):
                matches.setdefault(getattr(contract, "conId", None), contract)
        return next(iter(matches.values())) if len(matches) == 1 else None

    def _step(self, ib: Any) -> None:
        """One pass: resolve and subscribe what is wanted, drop what is idle, publish values, serve bar requests."""

        now = self._clock()
        with self._lock:
            wanted = dict(self._wanted)
        resolved = 0
        for key, (ref, asked) in sorted(wanted.items(), key=lambda item: -item[1][1]):
            if now - asked > IDLE_SECONDS:
                continue
            if key not in self._contracts and resolved < RESOLVE_PER_STEP:
                self._contracts[key] = self._resolve(ib, ref)
                resolved += 1
            contract = self._contracts.get(key)
            if contract is not None and key not in self._tickers and len(self._tickers) < MAX_LINES:
                self._tickers[key] = ib.reqMktData(contract, "", False, False)
        for key in [key for key in self._tickers if key not in wanted or now - wanted[key][1] > IDLE_SECONDS]:
            ib.cancelMktData(self._contracts[key])
            del self._tickers[key]
        published = {}
        for key, ticker in self._tickers.items():
            # IBKR reports 0 (or -1) for a price it does not have; only a positive price is a price.
            values = {name: (_finite(getattr(ticker, attr, None)) or None)
                      for name, attr in (("last", "last"), ("bid", "bid"), ("ask", "ask"), ("prev_close", "close"))}
            values["volume"] = _finite(getattr(ticker, "volume", None))
            if all(values[name] is None for name in ("last", "bid", "ask")):
                continue
            stamp = getattr(ticker, "time", None)
            values["updated_s"] = stamp.timestamp() if isinstance(stamp, datetime) else now
            published[key] = values
        with self._lock:
            self._quotes = published
            self._wanted = {key: item for key, item in self._wanted.items() if now - item[1] <= IDLE_SECONDS}
        while True:
            try:
                ref, timeframe, done = self._bar_requests.get_nowait()
            except queue.Empty:
                break
            try:
                self._fetch_bars(ib, ref, timeframe)
            finally:
                done.set()

    def _fetch_bars(self, ib: Any, ref: FuturesContractRef, timeframe: str) -> None:
        if ref.key not in self._contracts:
            self._contracts[ref.key] = self._resolve(ib, ref)
        contract = self._contracts.get(ref.key)
        if contract is None:
            return
        duration, size, seconds = BAR_REQUEST[timeframe]
        raw = ib.reqHistoricalData(contract, "", duration, size, "TRADES", False, formatDate=2, timeout=10)
        now = self._clock()
        bars = []
        for bar in raw or []:
            start = getattr(bar, "date", None)
            values = [_finite(getattr(bar, name, None)) for name in ("open", "high", "low", "close")]
            if not isinstance(start, datetime) or any(value is None for value in values):
                continue
            start_s = start.timestamp()
            if start_s + seconds > now:      # still forming
                continue
            bars.append({"start_s": start_s, "end_s": start_s + seconds, "open": values[0], "high": values[1],
                         "low": values[2], "close": values[3], "volume": _finite(getattr(bar, "volume", None))})
        if bars:
            with self._lock:
                self._bars[(ref.key, timeframe)] = (now, bars)


def install_delayed_futures_source(env: Any = os.environ) -> IbkrDelayedFutures | None:
    """Inject the delayed source when IBKR TWS access is explicitly enabled; otherwise leave it absent."""

    cfg = IbkrConfig.from_env(env, root=ROOT)
    if not cfg.live_enabled or str(env.get("IMP_IBKR_TRANSPORT", "")).strip().lower() != "tws":
        return None
    source = IbkrDelayedFutures(host=cfg.tws_host, port=cfg.tws_port, client_id=cfg.tws_client_id + CLIENT_ID_OFFSET)
    inject_delayed_futures_source(source)
    source.start()
    return source


__all__ = ["IbkrDelayedFutures", "install_delayed_futures_source"]
