"""OpenD quote snapshot transport — quote context only, never trade APIs.

``moomoo-api`` is optional and is imported lazily. Missing SDK, auth failure,
and protocol errors fail closed. This module never synthesizes ``last_price``.
"""

from __future__ import annotations

from typing import Any

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

MOOMOO_SDK_MISSING = "MOOMOO_SDK_MISSING"
MOOMOO_AUTH_FAILURE = "MOOMOO_AUTH_FAILURE"
MOOMOO_PROTOCOL_ERROR = "MOOMOO_PROTOCOL_ERROR"
OPEND_NON_LOOPBACK_BLOCKED = "OPEND_NON_LOOPBACK_BLOCKED"
MOOMOO_LAST_PRICE_MISSING = "MOOMOO_LAST_PRICE_MISSING"


def sdk_available() -> bool:
    """True when the vendor quote SDK imports. Never treated as a tick."""

    return _import_sdk() is not None


def fetch_snapshot(
    symbol: str,
    *,
    host: str,
    port: int,
    sdk: Any | None = None,
) -> dict[str, Any]:
    """Return ``{"reason_code": str|None, "row": dict|None}``.

    ``row`` is a vendor snapshot record. ``last_price`` is copied from the
    vendor only; this function never fills it from bid/ask/close.
    """

    if host not in _LOOPBACK_HOSTS:
        return _unavailable(OPEND_NON_LOOPBACK_BLOCKED)
    ft = sdk if sdk is not None else _import_sdk()
    if ft is None or not hasattr(ft, "OpenQuoteContext"):
        return _unavailable(MOOMOO_SDK_MISSING)
    if not hasattr(ft, "RET_OK"):
        return _unavailable(MOOMOO_PROTOCOL_ERROR)

    code = _provider_code(symbol)
    if not code:
        return _unavailable(MOOMOO_PROTOCOL_ERROR)

    ctx = None
    try:
        ctx = ft.OpenQuoteContext(host=host, port=port)
        ret, state = ctx.get_global_state()
        if ret != ft.RET_OK:
            return _unavailable(MOOMOO_PROTOCOL_ERROR)
        if not _qot_logined(state):
            return _unavailable(MOOMOO_AUTH_FAILURE)
        snap_ret, data = ctx.get_market_snapshot([code])
        if snap_ret != ft.RET_OK:
            return _unavailable(MOOMOO_PROTOCOL_ERROR)
        row = _matching_row(_snapshot_rows(data), code)
        if row is None:
            return _unavailable(MOOMOO_PROTOCOL_ERROR)
        if _vendor_last_price(row) is None:
            return _unavailable(MOOMOO_LAST_PRICE_MISSING)
        return {"reason_code": None, "row": row}
    except Exception:  # noqa: BLE001 — vendor SDK/protocol surface is fail-closed
        return _unavailable(MOOMOO_PROTOCOL_ERROR)
    finally:
        if ctx is not None:
            closer = getattr(ctx, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:  # noqa: BLE001
                    pass


def _import_sdk() -> Any | None:
    try:
        import moomoo as ft  # type: ignore[import-not-found]
    except ImportError:
        return None
    return ft


def _unavailable(reason_code: str) -> dict[str, Any]:
    return {"reason_code": reason_code, "row": None}


def _provider_code(symbol: str) -> str:
    wanted = str(symbol or "").strip().upper()
    if not wanted:
        return ""
    if "." in wanted:
        return wanted
    return f"US.{wanted}"


def _qot_logined(state: Any) -> bool:
    if not isinstance(state, dict):
        return False
    flag = state.get("qot_logined")
    if flag is True or flag == 1:
        return True
    return str(flag).strip().lower() in {"true", "1", "yes"}


def _snapshot_rows(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if hasattr(data, "to_dict") and hasattr(data, "columns"):
        try:
            records = data.to_dict(orient="records")
        except Exception:  # noqa: BLE001
            return []
        return [_jsonable_row(dict(row)) for row in records if isinstance(row, dict)]
    if isinstance(data, list):
        rows: list[dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict):
                rows.append(_jsonable_row(item))
        return rows
    if isinstance(data, dict):
        return [_jsonable_row(data)]
    return []


def _matching_row(rows: list[dict[str, Any]], code: str) -> dict[str, Any] | None:
    wanted = code.strip().upper()
    for row in rows:
        candidate = str(row.get("code") or "").strip().upper()
        if candidate == wanted:
            return row
    if len(rows) == 1:
        return rows[0]
    return None


def _vendor_last_price(row: dict[str, Any]) -> float | None:
    if "last_price" not in row:
        return None
    value = row.get("last_price")
    if value in {None, ""}:
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price != price or price in {float("inf"), float("-inf")}:
        return None
    return price


def _jsonable_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _jsonable(value) for key, value in row.items()}


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            return None
        return value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    item = getattr(value, "item", None)
    if callable(item) and not isinstance(value, (bytes, bytearray)):
        try:
            return _jsonable(value.item())
        except Exception:  # noqa: BLE001
            return None
    text = str(value)
    if text in {"nan", "NaN", "None", "<NA>", "NaT"}:
        return None
    return text


__all__ = [
    "MOOMOO_AUTH_FAILURE",
    "MOOMOO_LAST_PRICE_MISSING",
    "MOOMOO_PROTOCOL_ERROR",
    "MOOMOO_SDK_MISSING",
    "OPEND_NON_LOOPBACK_BLOCKED",
    "fetch_snapshot",
    "sdk_available",
]
