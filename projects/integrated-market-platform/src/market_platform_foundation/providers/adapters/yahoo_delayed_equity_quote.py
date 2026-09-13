"""Yahoo Finance delayed/EOD equity snapshot. Not real-time L1 and not ES."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from ...clock import monotonic_wall_ns
from ..contracts import ProviderResult

YAHOO_PROVIDER_ID = "yahoo.finance.delayed"
YAHOO_CAPABILITY = "US_EQUITY_SNAPSHOT"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
USER_AGENT = "IMP-path-a-prospective/1.0 (+research; delayed-overlay)"

HttpFetch = Callable[[str], tuple[int, bytes]]


def _default_fetch(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
            return int(getattr(resp, "status", 200) or 200), resp.read(2_000_000)
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read(1024)
        except Exception:
            body = b""
        return int(exc.code), body


class YahooDelayedEquityQuoteProvider:
    """Prospective delayed/EOD quotes. Never labeled REAL_TIME."""

    provider_id = YAHOO_PROVIDER_ID
    capability = YAHOO_CAPABILITY
    timeliness = "DELAYED"

    def __init__(self, *, fetch: HttpFetch | None = None) -> None:
        self._fetch = fetch or _default_fetch

    def fetch_quote(self, symbol: str) -> ProviderResult:
        wanted = str(symbol or "").strip().upper()
        if not wanted:
            return ProviderResult(
                status="unavailable",
                reason_code="INSTRUMENT_ID_REQUIRED",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        url = YAHOO_CHART_URL.format(symbol=urllib.parse.quote(wanted, safe=""))
        try:
            status, body = self._fetch(url)
        except TimeoutError:
            return ProviderResult(
                status="unavailable",
                reason_code="PROVIDER_TIMEOUT",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        except Exception:
            return ProviderResult(
                status="unavailable",
                reason_code="PROVIDER_DISCONNECTED",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        if status == 429:
            return ProviderResult(
                status="unavailable",
                reason_code="RATE_LIMIT",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        if status >= 400:
            return ProviderResult(
                status="unavailable",
                reason_code="PROVIDER_HTTP_ERROR",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return ProviderResult(
                status="unavailable",
                reason_code="MALFORMED_RECORD",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        event = _quote_event_from_chart(payload, symbol=wanted, received_ns=monotonic_wall_ns())
        if event is None:
            return ProviderResult(
                status="unavailable",
                reason_code=str(payload.get("reason_code") or "MALFORMED_RECORD"),
                provider_id=self.provider_id,
                capability=self.capability,
            )
        return ProviderResult(
            status="available",
            events=(event,),
            provider_id=self.provider_id,
            capability=self.capability,
        )


def _quote_event_from_chart(payload: dict[str, Any], *, symbol: str, received_ns: int) -> dict[str, Any] | None:
    chart = payload.get("chart") if isinstance(payload, dict) else None
    if not isinstance(chart, dict):
        payload["reason_code"] = "MALFORMED_RECORD"
        return None
    error = chart.get("error")
    if error:
        payload["reason_code"] = "PROVIDER_HTTP_ERROR"
        return None
    results = chart.get("result")
    if not isinstance(results, list) or not results:
        payload["reason_code"] = "MALFORMED_RECORD"
        return None
    row = results[0] if isinstance(results[0], dict) else None
    if row is None:
        payload["reason_code"] = "MALFORMED_RECORD"
        return None
    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
    last = meta.get("regularMarketPrice")
    timestamps = row.get("timestamp") if isinstance(row.get("timestamp"), list) else []
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
        payload["reason_code"] = "MALFORMED_RECORD"
        return None
    try:
        last_f = float(last)
    except (TypeError, ValueError):
        payload["reason_code"] = "MALFORMED_RECORD"
        return None
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
        payload["reason_code"] = "MISSING_TIMESTAMP"
        return None
    event_time_ns = event_epoch * 1_000_000_000
    bid = meta.get("bid")
    ask = meta.get("ask")
    try:
        bid_f = float(bid) if bid not in {None, ""} else last_f
        ask_f = float(ask) if ask not in {None, ""} else last_f
    except (TypeError, ValueError):
        bid_f = last_f
        ask_f = last_f
    return {
        "capability": "US_EQUITY_L1",
        "clocks": {
            "event_time_ns": event_time_ns,
            "provider_time_ns": event_time_ns,
            "received_time_ns": received_ns,
        },
        "instrument_id": symbol,
        "provider": YAHOO_PROVIDER_ID,
        "provider_symbol": symbol,
        "raw_payload": {
            "ask_price": ask_f,
            "ask_vol": 0,
            "bid_price": bid_f,
            "bid_vol": 0,
            "last_price": last_f,
        },
        "sequence": event_epoch,
        "timeliness": "DELAYED",
        "entitlement": "DELAYED",
        "normalization_version": "yahoo.finance.delayed/1.0.0",
    }


__all__ = ["YAHOO_PROVIDER_ID", "YahooDelayedEquityQuoteProvider"]
