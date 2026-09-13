"""Yahoo Finance delayed cloud overlay — never Primary L1, never real-time, never ES.

Moomoo OpenD observational quotes are the Primary L1 for the no-additional-cost
stack (DoD item 2). This adapter is a distinctly-identified, cloud-reachable
*overlay* used only when a caller explicitly asks for a delayed snapshot; it
is never substituted into the OpenD/Moomoo provider identity and never
labeled ``REAL_TIME``. It also refuses futures/ES-style symbols outright: the
ES campaign (FTEP-V1-001) is frozen pending genuine futures entitlement and
must not be quietly satisfied by an equity-delayed feed.
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from ...clock import monotonic_wall_ns
from ..contracts import ProviderResult

YAHOO_PROVIDER_ID = "yahoo.finance.delayed"
YAHOO_CAPABILITY = "US_EQUITY_SNAPSHOT"
YAHOO_TIMELINESS = "DELAYED"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
USER_AGENT = "IMP-opend-primary-l1/1.0 (+research; delayed-overlay)"

SYMBOL_REQUIRED = "INSTRUMENT_ID_REQUIRED"
ES_SYMBOL_BLOCKED = "ES_FUTURES_NOT_SUPPORTED_BY_DELAYED_EQUITY_OVERLAY"
PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
PROVIDER_DISCONNECTED = "PROVIDER_DISCONNECTED"
RATE_LIMIT = "RATE_LIMIT"
PROVIDER_HTTP_ERROR = "PROVIDER_HTTP_ERROR"
MALFORMED_RECORD = "MALFORMED_RECORD"
MISSING_TIMESTAMP = "MISSING_TIMESTAMP"

# Yahoo continuous-futures suffix ("ES=F") and common ES aliases. Equity
# tickers never match this; blocking here keeps the ES campaign fail-closed
# on this overlay even if a caller passes a futures-looking symbol by mistake.
_FUTURES_SUFFIX = re.compile(r"=F$")
_ES_ALIASES = frozenset({"ES", "ES=F", "/ES", "ES1!", "MES", "MES=F", "/MES"})

HttpFetch = Callable[[str], tuple[int, bytes]]


def _default_fetch(url: str) -> tuple[int, bytes]:
    """Never called in CI/tests — real network I/O only when explicitly used."""

    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=12, context=context) as response:
            return int(getattr(response, "status", 200) or 200), response.read(2_000_000)
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read(1024)
        except OSError:
            body = b""
        return int(exc.code), body


def is_es_futures_symbol(symbol: str) -> bool:
    wanted = symbol.strip().upper()
    return wanted in _ES_ALIASES or bool(_FUTURES_SUFFIX.search(wanted))


class YahooDelayedEquityQuoteProvider:
    """Cloud-reachable delayed/EOD equity overlay. Never claims REAL_TIME or ES."""

    provider_id = YAHOO_PROVIDER_ID
    capability = YAHOO_CAPABILITY
    timeliness = YAHOO_TIMELINESS

    def __init__(self, *, fetch: HttpFetch | None = None) -> None:
        self._fetch = fetch or _default_fetch

    def fetch_quote(self, symbol: str) -> ProviderResult:
        wanted = str(symbol or "").strip().upper()
        if not wanted:
            return self._unavailable(SYMBOL_REQUIRED)
        if is_es_futures_symbol(wanted):
            return self._unavailable(ES_SYMBOL_BLOCKED)

        url = YAHOO_CHART_URL.format(symbol=urllib.parse.quote(wanted, safe=""))
        try:
            status, body = self._fetch(url)
        except TimeoutError:
            return self._unavailable(PROVIDER_TIMEOUT)
        except OSError:
            return self._unavailable(PROVIDER_DISCONNECTED)

        if status == 429:
            return self._unavailable(RATE_LIMIT)
        if status >= 400:
            return self._unavailable(PROVIDER_HTTP_ERROR)

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return self._unavailable(MALFORMED_RECORD)

        event, reason_code = _quote_event_from_chart(
            payload, symbol=wanted, received_ns=monotonic_wall_ns()
        )
        if event is None:
            return self._unavailable(reason_code or MALFORMED_RECORD)
        return ProviderResult(
            status="available",
            events=(event,),
            provider_id=self.provider_id,
            capability=self.capability,
        )

    def _unavailable(self, reason_code: str) -> ProviderResult:
        return ProviderResult(
            status="unavailable",
            reason_code=reason_code,
            provider_id=self.provider_id,
            capability=self.capability,
        )


def _quote_event_from_chart(
    payload: dict[str, Any], *, symbol: str, received_ns: int
) -> tuple[dict[str, Any] | None, str | None]:
    chart = payload.get("chart") if isinstance(payload, dict) else None
    if not isinstance(chart, dict):
        return None, MALFORMED_RECORD
    if chart.get("error"):
        return None, PROVIDER_HTTP_ERROR
    results = chart.get("result")
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        return None, MALFORMED_RECORD
    row = results[0]
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    timestamps = row.get("timestamp") if isinstance(row.get("timestamp"), list) else []

    last = meta.get("regularMarketPrice")
    if last is None:
        indicators = row.get("indicators") if isinstance(row.get("indicators"), dict) else {}
        quotes = indicators.get("quote") if isinstance(indicators.get("quote"), list) else []
        closes = quotes[0].get("close") if quotes and isinstance(quotes[0], dict) else None
        if isinstance(closes, list):
            for value in reversed(closes):
                if value is not None:
                    last = value
                    break
    if last is None:
        return None, MALFORMED_RECORD
    try:
        last_price = float(last)
    except (TypeError, ValueError):
        return None, MALFORMED_RECORD

    event_epoch = None
    if timestamps:
        try:
            event_epoch = int(timestamps[-1])
        except (TypeError, ValueError):
            event_epoch = None
    if event_epoch is None:
        regular = meta.get("regularMarketTime")
        try:
            event_epoch = int(regular) if regular is not None else None
        except (TypeError, ValueError):
            event_epoch = None
    if event_epoch is None:
        return None, MISSING_TIMESTAMP
    event_time_ns = event_epoch * 1_000_000_000

    bid = meta.get("bid")
    ask = meta.get("ask")
    try:
        bid_price = float(bid) if bid not in {None, ""} else last_price
        ask_price = float(ask) if ask not in {None, ""} else last_price
    except (TypeError, ValueError):
        bid_price, ask_price = last_price, last_price

    return (
        {
            "capability": YAHOO_CAPABILITY,
            "clocks": {
                "event_time_ns": event_time_ns,
                "provider_time_ns": event_time_ns,
                "received_time_ns": received_ns,
            },
            "entitlement": "DELAYED",
            "instrument_id": symbol,
            "normalization_version": "yahoo.finance.delayed/1.0.0",
            "provider": YAHOO_PROVIDER_ID,
            "provider_symbol": symbol,
            "raw_payload": {
                "ask_price": ask_price,
                "ask_vol": 0,
                "bid_price": bid_price,
                "bid_vol": 0,
                "last_price": last_price,
            },
            "sequence": event_epoch,
            "timeliness": YAHOO_TIMELINESS,
        },
        None,
    )


__all__ = [
    "ES_SYMBOL_BLOCKED",
    "YAHOO_CAPABILITY",
    "YAHOO_PROVIDER_ID",
    "YAHOO_TIMELINESS",
    "YahooDelayedEquityQuoteProvider",
    "is_es_futures_symbol",
]
