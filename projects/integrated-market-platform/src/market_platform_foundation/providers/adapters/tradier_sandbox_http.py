"""Tradier sandbox HTTPS transport — sandbox.tradier.com only, never production.

Fail-closed: any URL that is not exactly the sandbox origin is refused before
the socket is opened. ``api.tradier.com`` and Alpaca live hosts are blocked.
No Live orders. Stdlib urllib only.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

from ...clock import monotonic_wall_ns
from ...numeric import decimal_to_minor_units

TRADIER_SANDBOX_ORIGIN = "https://sandbox.tradier.com"
TRADIER_SANDBOX_ENDPOINT = f"{TRADIER_SANDBOX_ORIGIN}/v1"

_BLOCKED_HOSTS = frozenset(
    {
        "api.tradier.com",
        "stream.tradier.com",
        "api.alpaca.markets",
    }
)

# Documented wire → canonical broker status (TRADIER_PAPER.md §1.5 / §3).
_WIRE_STATUS_TO_CANONICAL: dict[str, str] = {
    "ok": "accepted",
    "pending": "working",
    "open": "accepted",
    "partially_filled": "partially_filled",
    "filled": "filled",
    "expired": "expired",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "rejected": "rejected",
    "pending_cancel": "working",
    "error": "rejected",
    "timeout": "ambiguous",
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


class TradierSandboxHttpError(ValueError):
    """Sandbox HTTP transport refused or failed closed."""


class TradierHttpTransport(Protocol):
    """Injectable HTTPS client used by the Tradier paper adapter."""

    def request(
        self,
        method: str,
        url: str,
        *,
        token: str,
        form: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        ...


def assert_tradier_sandbox_url(url: str) -> str:
    """Return the URL if and only if it is the Tradier sandbox. Else raise."""
    candidate = str(url or "").strip()
    if not candidate:
        raise TradierSandboxHttpError("TRADIER_PRODUCTION_ENDPOINT_BLOCKED")
    parsed = urllib.parse.urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if host in _BLOCKED_HOSTS:
        raise TradierSandboxHttpError("TRADIER_PRODUCTION_ENDPOINT_BLOCKED")
    if host == "paper-api.alpaca.markets":
        raise TradierSandboxHttpError("TRADIER_ALPACA_HOST_FORBIDDEN")
    if not candidate.startswith(TRADIER_SANDBOX_ENDPOINT):
        raise TradierSandboxHttpError("TRADIER_PRODUCTION_ENDPOINT_BLOCKED")
    if parsed.scheme != "https":
        raise TradierSandboxHttpError("TRADIER_PRODUCTION_ENDPOINT_BLOCKED")
    return candidate


def map_tradier_wire_status(status_raw: str) -> str:
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


def _unwrap_order_body(body: Any) -> dict[str, Any] | None:
    if not isinstance(body, dict):
        return None
    if isinstance(body.get("order"), dict):
        return dict(body["order"])
    orders = body.get("orders")
    if isinstance(orders, dict):
        inner = orders.get("order")
        if isinstance(inner, dict):
            return dict(inner)
        if isinstance(inner, list) and inner and isinstance(inner[0], dict):
            return dict(inner[0])
    return None


def normalize_tradier_wire_order(
    body: Any,
    *,
    receive_time_ns: int,
    instrument_id: str = "",
) -> dict[str, Any] | None:
    """Map a sandbox JSON order object into the fixture-normalized record."""
    record = _unwrap_order_body(body)
    if record is None and isinstance(body, dict) and body.get("id") is not None:
        record = dict(body)
    if record is None:
        return None
    broker_order_id = record.get("id")
    if broker_order_id in (None, ""):
        return None
    status_raw = str(record.get("status") or "")
    event_time_ns = (
        _parse_iso_to_ns(record.get("transaction_date"))
        or _parse_iso_to_ns(record.get("create_date"))
        or receive_time_ns
    )
    avg_fill = _dollars_to_minor(record.get("avg_fill_price"))
    filled_quantity = int(record.get("exec_quantity") or record.get("filled_quantity") or 0)
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
        "status": map_tradier_wire_status(status_raw),
        "status_raw": status_raw,
        "event_time_ns": event_time_ns,
        "receive_time_ns": receive_time_ns,
        "avg_fill_price_minor": avg_fill,
        "filled_quantity": filled_quantity,
        "symbol": str(record.get("symbol") or ""),
        "instrument_id": instrument_id or str(record.get("symbol") or ""),
        "fills": fills,
    }


def build_equity_order_form(request: Any) -> dict[str, str]:
    order_type = _ORDER_TYPE_TO_WIRE.get(str(request.order_type), "")
    side = _SIDE_TO_WIRE.get(str(request.side), "")
    if not order_type or not side:
        raise TradierSandboxHttpError("BROKER_REQUEST_INVALID")
    form = {
        "class": "equity",
        "symbol": str(request.broker_symbol).upper(),
        "side": side,
        "quantity": str(int(request.quantity)),
        "type": order_type,
        "duration": "day",
    }
    if order_type == "limit":
        if request.limit_price_minor is None:
            raise TradierSandboxHttpError("BROKER_REQUEST_INVALID")
        form["price"] = f"{int(request.limit_price_minor) / 100:.2f}"
    return form


class TradierSandboxHttpTransport:
    """urllib transport that cannot target a non-sandbox URL."""

    def __init__(self, *, timeout_seconds: float = 15.0) -> None:
        self.timeout_seconds = timeout_seconds

    def request(
        self,
        method: str,
        url: str,
        *,
        token: str,
        form: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        assert_tradier_sandbox_url(url)
        if not token:
            raise TradierSandboxHttpError("TRADIER_TOKEN_NOT_CONFIGURED")
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        data = None
        if form is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            data = urllib.parse.urlencode(form).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
                status = int(response.status)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            status = int(exc.code)
        except (urllib.error.URLError, OSError) as exc:
            raise TradierSandboxHttpError(f"TRADIER_SANDBOX_NETWORK:{exc}") from exc
        try:
            body: Any = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise TradierSandboxHttpError("BROKER_RESPONSE_INVALID") from exc
        return status, body


def sandbox_account_url(endpoint: str, account_id: str, *parts: str) -> str:
    assert_tradier_sandbox_url(endpoint)
    quoted = urllib.parse.quote(str(account_id), safe="")
    suffix = "/".join(urllib.parse.quote(str(part), safe="") for part in parts)
    if suffix:
        return f"{endpoint}/accounts/{quoted}/{suffix}"
    return f"{endpoint}/accounts/{quoted}"


def tradier_http_place_order(
    transport: TradierHttpTransport,
    *,
    endpoint: str,
    token: str,
    account_id: str,
    request: Any,
    instrument_id: str,
) -> dict[str, Any]:
    url = sandbox_account_url(endpoint, account_id, "orders")
    form = build_equity_order_form(request)
    status, body = transport.request("POST", url, token=token, form=form)
    if status in (401, 403):
        raise TradierSandboxHttpError("TRADIER_SANDBOX_AUTH_REJECTED")
    if status != 200:
        raise TradierSandboxHttpError("BROKER_RESPONSE_INVALID")
    receive_time_ns = monotonic_wall_ns()
    ack = normalize_tradier_wire_order(
        body, receive_time_ns=receive_time_ns, instrument_id=instrument_id
    )
    if ack is None:
        raise TradierSandboxHttpError("BROKER_RESPONSE_INVALID")
    broker_order_id = ack["broker_order_id"]
    fetched = tradier_http_fetch_order(
        transport,
        endpoint=endpoint,
        token=token,
        account_id=account_id,
        broker_order_id=broker_order_id,
        instrument_id=instrument_id,
    )
    return fetched if fetched is not None else ack


def tradier_http_fetch_order(
    transport: TradierHttpTransport,
    *,
    endpoint: str,
    token: str,
    account_id: str,
    broker_order_id: str,
    instrument_id: str = "",
) -> dict[str, Any] | None:
    url = sandbox_account_url(endpoint, account_id, "orders", str(broker_order_id))
    status, body = transport.request("GET", url, token=token)
    if status in (401, 403):
        raise TradierSandboxHttpError("TRADIER_SANDBOX_AUTH_REJECTED")
    if status != 200:
        return None
    return normalize_tradier_wire_order(
        body, receive_time_ns=monotonic_wall_ns(), instrument_id=instrument_id
    )


def tradier_http_cancel_order(
    transport: TradierHttpTransport,
    *,
    endpoint: str,
    token: str,
    account_id: str,
    broker_order_id: str,
    instrument_id: str = "",
) -> dict[str, Any] | None:
    url = sandbox_account_url(endpoint, account_id, "orders", str(broker_order_id))
    status, body = transport.request("DELETE", url, token=token)
    if status in (401, 403):
        raise TradierSandboxHttpError("TRADIER_SANDBOX_AUTH_REJECTED")
    if status != 200:
        return None
    return normalize_tradier_wire_order(
        body, receive_time_ns=monotonic_wall_ns(), instrument_id=instrument_id
    )


def tradier_http_fetch_account(
    transport: TradierHttpTransport,
    *,
    endpoint: str,
    token: str,
    account_id: str,
) -> dict[str, Any] | None:
    url = sandbox_account_url(endpoint, account_id, "balances")
    status, body = transport.request("GET", url, token=token)
    if status != 200 or not isinstance(body, dict):
        return None
    balances = body.get("balances") if isinstance(body.get("balances"), dict) else body
    cash = _dollars_to_minor(balances.get("total_cash") or balances.get("cash"))
    buying = _dollars_to_minor(
        balances.get("option_buying_power") or balances.get("stock_buying_power")
    )
    return {
        "cash_minor": cash if cash is not None else 0,
        "buying_power_minor": buying,
        "as_of_ns": monotonic_wall_ns(),
        "account_id": account_id,
    }


def tradier_http_fetch_positions(
    transport: TradierHttpTransport,
    *,
    endpoint: str,
    token: str,
    account_id: str,
) -> dict[str, Any] | None:
    url = sandbox_account_url(endpoint, account_id, "positions")
    status, body = transport.request("GET", url, token=token)
    if status != 200 or not isinstance(body, dict):
        return None
    positions = body.get("positions")
    rows: list[Any] = []
    if isinstance(positions, dict):
        inner = positions.get("position")
        if isinstance(inner, list):
            rows = inner
        elif isinstance(inner, dict):
            rows = [inner]
    return {"positions": rows, "as_of_ns": monotonic_wall_ns(), "account_id": account_id}


__all__ = [
    "TRADIER_SANDBOX_ENDPOINT",
    "TRADIER_SANDBOX_ORIGIN",
    "TradierHttpTransport",
    "TradierSandboxHttpError",
    "TradierSandboxHttpTransport",
    "assert_tradier_sandbox_url",
    "build_equity_order_form",
    "map_tradier_wire_status",
    "normalize_tradier_wire_order",
    "sandbox_account_url",
    "tradier_http_cancel_order",
    "tradier_http_fetch_account",
    "tradier_http_fetch_order",
    "tradier_http_fetch_positions",
    "tradier_http_place_order",
]
