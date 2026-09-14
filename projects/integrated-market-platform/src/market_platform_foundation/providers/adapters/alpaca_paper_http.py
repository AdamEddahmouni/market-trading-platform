"""Alpaca Paper HTTPS transport — paper-api.alpaca.markets only, never live.

Fail-closed: any URL that is not the Paper origin is refused before the socket
is opened. ``api.alpaca.markets`` and other live hosts raise ``LIVE_FORBIDDEN``.
Stdlib urllib only. Do not import the Alpaca SDK.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

from ...clock import monotonic_wall_ns
from ...numeric import decimal_to_minor_units

ALPACA_PAPER_ORIGIN = "https://paper-api.alpaca.markets"
ALPACA_PAPER_API_ROOT = f"{ALPACA_PAPER_ORIGIN}/v2"
ALPACA_LIVE_HOST = "api.alpaca.markets"

_LIVE_HOSTS = frozenset(
    {
        "api.alpaca.markets",
        "api.tradier.com",
        "stream.tradier.com",
    }
)

_WIRE_STATUS_TO_CANONICAL: dict[str, str] = {
    "new": "accepted",
    "accepted": "accepted",
    "pending_new": "accepted",
    "partially_filled": "partially_filled",
    "filled": "filled",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "expired": "expired",
    "rejected": "rejected",
    "pending_cancel": "working",
    "pending_replace": "working",
    "replaced": "cancelled",
    "done_for_day": "expired",
    "stopped": "cancelled",
    "suspended": "working",
    "calculated": "working",
}

_SIDE_TO_WIRE = {
    "BUY": "buy",
    "SELL": "sell",
    "buy": "buy",
    "sell": "sell",
    "long": "buy",
    "short": "sell",
}

_ORDER_TYPE_TO_WIRE = {
    "MARKET": "market",
    "LIMIT": "limit",
    "market": "market",
    "limit": "limit",
}


class AlpacaPaperHttpError(ValueError):
    """Paper HTTP transport refused or failed closed."""


class AlpacaHttpTransport(Protocol):
    """Injectable HTTPS client used by the Alpaca paper adapter."""

    def request(
        self,
        method: str,
        url: str,
        *,
        key_id: str,
        secret_key: str,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        ...


def assert_alpaca_paper_url(url: str) -> str:
    """Return the URL if and only if it is the Alpaca Paper origin. Else raise."""
    candidate = str(url or "").strip()
    if not candidate:
        raise AlpacaPaperHttpError("ALPACA_HOST_FORBIDDEN")
    parsed = urllib.parse.urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if host == ALPACA_LIVE_HOST or host in _LIVE_HOSTS:
        raise AlpacaPaperHttpError("LIVE_FORBIDDEN")
    if host != "paper-api.alpaca.markets":
        raise AlpacaPaperHttpError("ALPACA_HOST_FORBIDDEN")
    if parsed.scheme != "https":
        raise AlpacaPaperHttpError("ALPACA_HOST_FORBIDDEN")
    if not candidate.startswith(ALPACA_PAPER_ORIGIN):
        raise AlpacaPaperHttpError("ALPACA_HOST_FORBIDDEN")
    return candidate


def map_alpaca_wire_status(status_raw: str) -> str:
    raw = str(status_raw or "").strip().lower()
    if raw not in _WIRE_STATUS_TO_CANONICAL:
        return "ambiguous"
    return _WIRE_STATUS_TO_CANONICAL[raw]


def _parse_iso_to_ns(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return int(parsed.timestamp() * 1_000_000_000)


def _dollars_to_minor(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return decimal_to_minor_units(str(value), scale=100)
    except ValueError:
        try:
            return int(round(float(value) * 100))
        except (TypeError, ValueError):
            return None


def normalize_alpaca_wire_order(
    body: Any,
    *,
    receive_time_ns: int,
    instrument_id: str = "",
) -> dict[str, Any] | None:
    """Map an Alpaca Paper JSON order object into the fixture-normalized record."""
    record = body if isinstance(body, dict) else None
    if record is None:
        return None
    broker_order_id = record.get("id")
    if broker_order_id in (None, ""):
        return None
    status_raw = str(record.get("status") or "")
    event_time_ns = (
        _parse_iso_to_ns(record.get("filled_at"))
        or _parse_iso_to_ns(record.get("updated_at"))
        or _parse_iso_to_ns(record.get("submitted_at"))
        or _parse_iso_to_ns(record.get("created_at"))
        or receive_time_ns
    )
    avg_fill = _dollars_to_minor(record.get("filled_avg_price"))
    filled_quantity = int(float(record.get("filled_qty") or record.get("filled_quantity") or 0))
    fills: list[dict[str, Any]] = []
    if filled_quantity > 0 and avg_fill is not None:
        fills.append(
            {
                "broker_fill_id": f"{broker_order_id}:{event_time_ns}:{filled_quantity}",
                "quantity": filled_quantity,
                "price_minor": avg_fill,
                "event_time_ns": event_time_ns,
                "receive_time_ns": receive_time_ns,
            }
        )
    return {
        "broker_order_id": str(broker_order_id),
        "status": map_alpaca_wire_status(status_raw),
        "status_raw": status_raw,
        "event_time_ns": event_time_ns,
        "receive_time_ns": receive_time_ns,
        "avg_fill_price_minor": avg_fill,
        "filled_quantity": filled_quantity,
        "symbol": str(record.get("symbol") or ""),
        "instrument_id": instrument_id or str(record.get("symbol") or ""),
        "fills": fills,
    }


def build_equity_order_json(request: Any) -> dict[str, Any]:
    order_type = _ORDER_TYPE_TO_WIRE.get(str(request.order_type), "")
    side = _SIDE_TO_WIRE.get(str(request.side), "")
    if not order_type or not side:
        raise AlpacaPaperHttpError("BROKER_REQUEST_INVALID")
    payload: dict[str, Any] = {
        "symbol": str(request.broker_symbol).upper(),
        "qty": str(int(request.quantity)),
        "side": side,
        "type": order_type,
        "time_in_force": "day",
        "client_order_id": str(request.client_order_id),
    }
    if order_type == "limit":
        if request.limit_price_minor is None:
            raise AlpacaPaperHttpError("BROKER_REQUEST_INVALID")
        payload["limit_price"] = f"{int(request.limit_price_minor) / 100:.2f}"
    return payload


class AlpacaPaperHttpTransport:
    """urllib transport that cannot target a non-Paper URL."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self.timeout_seconds = timeout_seconds

    def request(
        self,
        method: str,
        url: str,
        *,
        key_id: str,
        secret_key: str,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        assert_alpaca_paper_url(url)
        if not key_id or not secret_key:
            raise AlpacaPaperHttpError("ALPACA_KEYS_NOT_CONFIGURED")
        headers = {
            "APCA-API-KEY-ID": key_id,
            "APCA-API-SECRET-KEY": secret_key,
            "Accept": "application/json",
        }
        data = None
        if json_body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(json_body).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
                status = int(response.status)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            status = int(exc.code)
        except (urllib.error.URLError, OSError) as exc:
            raise AlpacaPaperHttpError(f"ALPACA_PAPER_NETWORK:{exc}") from exc
        try:
            body: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise AlpacaPaperHttpError("BROKER_RESPONSE_INVALID") from exc
        return status, body


def paper_api_url(origin: str, *parts: str) -> str:
    assert_alpaca_paper_url(origin)
    suffix = "/".join(urllib.parse.quote(str(part), safe="") for part in parts)
    base = origin.rstrip("/")
    if suffix:
        return f"{base}/{suffix}"
    return base


def alpaca_http_place_order(
    transport: AlpacaHttpTransport,
    *,
    origin: str,
    key_id: str,
    secret_key: str,
    request: Any,
    instrument_id: str,
) -> dict[str, Any]:
    url = paper_api_url(origin, "v2", "orders")
    payload = build_equity_order_json(request)
    status, body = transport.request(
        "POST", url, key_id=key_id, secret_key=secret_key, json_body=payload
    )
    if status in (401, 403):
        raise AlpacaPaperHttpError("ALPACA_PAPER_AUTH_REJECTED")
    if status not in (200, 201):
        raise AlpacaPaperHttpError("BROKER_RESPONSE_INVALID")
    receive_time_ns = monotonic_wall_ns()
    ack = normalize_alpaca_wire_order(
        body, receive_time_ns=receive_time_ns, instrument_id=instrument_id
    )
    if ack is None:
        raise AlpacaPaperHttpError("BROKER_RESPONSE_INVALID")
    broker_order_id = ack["broker_order_id"]
    fetched = alpaca_http_fetch_order(
        transport,
        origin=origin,
        key_id=key_id,
        secret_key=secret_key,
        broker_order_id=broker_order_id,
        instrument_id=instrument_id,
    )
    return fetched if fetched is not None else ack


def alpaca_http_fetch_order(
    transport: AlpacaHttpTransport,
    *,
    origin: str,
    key_id: str,
    secret_key: str,
    broker_order_id: str,
    instrument_id: str = "",
) -> dict[str, Any] | None:
    url = paper_api_url(origin, "v2", "orders", str(broker_order_id))
    status, body = transport.request("GET", url, key_id=key_id, secret_key=secret_key)
    if status in (401, 403):
        raise AlpacaPaperHttpError("ALPACA_PAPER_AUTH_REJECTED")
    if status != 200:
        return None
    return normalize_alpaca_wire_order(
        body, receive_time_ns=monotonic_wall_ns(), instrument_id=instrument_id
    )


def alpaca_http_cancel_order(
    transport: AlpacaHttpTransport,
    *,
    origin: str,
    key_id: str,
    secret_key: str,
    broker_order_id: str,
    instrument_id: str = "",
) -> dict[str, Any] | None:
    url = paper_api_url(origin, "v2", "orders", str(broker_order_id))
    status, body = transport.request("DELETE", url, key_id=key_id, secret_key=secret_key)
    if status in (401, 403):
        raise AlpacaPaperHttpError("ALPACA_PAPER_AUTH_REJECTED")
    if status not in (200, 204):
        return None
    if status == 204 or body in (None, ""):
        return {
            "broker_order_id": str(broker_order_id),
            "status": "cancelled",
            "status_raw": "canceled",
            "event_time_ns": monotonic_wall_ns(),
            "receive_time_ns": monotonic_wall_ns(),
            "avg_fill_price_minor": None,
            "filled_quantity": 0,
            "symbol": "",
            "instrument_id": instrument_id,
            "fills": [],
        }
    return normalize_alpaca_wire_order(
        body, receive_time_ns=monotonic_wall_ns(), instrument_id=instrument_id
    )


def alpaca_http_fetch_account(
    transport: AlpacaHttpTransport,
    *,
    origin: str,
    key_id: str,
    secret_key: str,
) -> dict[str, Any] | None:
    """Read-only first probe: GET /v2/account on the Paper origin only."""
    url = paper_api_url(origin, "v2", "account")
    status, body = transport.request("GET", url, key_id=key_id, secret_key=secret_key)
    if status in (401, 403):
        raise AlpacaPaperHttpError("ALPACA_PAPER_AUTH_REJECTED")
    if status != 200 or not isinstance(body, dict):
        return None
    cash = _dollars_to_minor(body.get("cash"))
    buying = _dollars_to_minor(body.get("buying_power"))
    return {
        "cash_minor": cash if cash is not None else 0,
        "buying_power_minor": buying,
        "as_of_ns": monotonic_wall_ns(),
        "account_id": str(body.get("id") or body.get("account_number") or ""),
        "status_raw": str(body.get("status") or ""),
    }


def alpaca_http_fetch_positions(
    transport: AlpacaHttpTransport,
    *,
    origin: str,
    key_id: str,
    secret_key: str,
) -> dict[str, Any] | None:
    url = paper_api_url(origin, "v2", "positions")
    status, body = transport.request("GET", url, key_id=key_id, secret_key=secret_key)
    if status != 200:
        return None
    rows = body if isinstance(body, list) else []
    return {"positions": rows, "as_of_ns": monotonic_wall_ns()}


__all__ = [
    "ALPACA_LIVE_HOST",
    "ALPACA_PAPER_API_ROOT",
    "ALPACA_PAPER_ORIGIN",
    "AlpacaHttpTransport",
    "AlpacaPaperHttpError",
    "AlpacaPaperHttpTransport",
    "alpaca_http_cancel_order",
    "alpaca_http_fetch_account",
    "alpaca_http_fetch_order",
    "alpaca_http_fetch_positions",
    "alpaca_http_place_order",
    "assert_alpaca_paper_url",
    "build_equity_order_json",
    "map_alpaca_wire_status",
    "normalize_alpaca_wire_order",
    "paper_api_url",
]
