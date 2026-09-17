"""OpenD quote snapshot transport — quote context only, never trade APIs.

``moomoo-api`` is optional and is imported lazily. Missing SDK, auth failure,
and protocol errors fail closed. This module never synthesizes ``last_price``.
"""

from __future__ import annotations

import importlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_TOOLS_DIR = Path(__file__).resolve().parent.parent
_US_EQUITY_TZ = ZoneInfo("America/New_York")
# Vendor history kline is oldest-first inside [start, end]. One extended US
# session is ~960 1m bars; 1000 is the SDK per-request cap.
US_EQUITY_1M_HISTORY_MIN_COUNT = 1000

MOOMOO_SDK_MISSING = "MOOMOO_SDK_MISSING"
MOOMOO_AUTH_FAILURE = "MOOMOO_AUTH_FAILURE"
MOOMOO_PROTOCOL_ERROR = "MOOMOO_PROTOCOL_ERROR"
OPEND_NON_LOOPBACK_BLOCKED = "OPEND_NON_LOOPBACK_BLOCKED"
MOOMOO_LAST_PRICE_MISSING = "MOOMOO_LAST_PRICE_MISSING"
KLINE_PROTOCOL_UNCLASSIFIED = "protocol_unclassified"


def load_vendor_sdk() -> Any | None:
    """Return the vendor ``moomoo`` module, or None. Never a tick."""

    return _import_sdk()


def sdk_available() -> bool:
    """True when the vendor quote SDK imports. Never treated as a tick."""

    return load_vendor_sdk() is not None


def us_equity_session_date(*, observation_time_ns: int | None = None) -> str:
    """America/New_York calendar date for an observation clock (ns) or now."""

    if observation_time_ns is None:
        now = datetime.now(_US_EQUITY_TZ)
    else:
        now = datetime.fromtimestamp(int(observation_time_ns) / 1_000_000_000, tz=_US_EQUITY_TZ)
    return now.strftime("%Y-%m-%d")


def _bounded_vendor_msg(value: Any, *, limit: int = 500) -> str | None:
    """Copy a vendor retMsg/error string. Never treat a kline table as a message."""

    if value is None:
        return None
    if hasattr(value, "to_dict") and hasattr(value, "columns"):
        return None
    if isinstance(value, (list, tuple)):
        return None
    text = str(value).strip()
    if not text or text in {"None", "nan", "NaN"}:
        return None
    if len(text) > limit:
        return text[:limit]
    return text


def _kline_time_keys(rows: list[dict[str, Any]]) -> tuple[str | None, str | None, int]:
    keys = [str(row.get("time_key") or "") for row in rows if isinstance(row, dict) and row.get("time_key")]
    if not keys:
        return None, None, len(rows)
    return keys[0], keys[-1], len(rows)


def classify_kline_protocol_error_category(
    *,
    reason_code: str | None,
    vendor_ret: Any = None,
    vendor_ret_msg: str | None = None,
) -> str | None:
    """Structured transport category for logs — not a root-cause verdict."""

    if reason_code is None:
        return None
    if reason_code == MOOMOO_AUTH_FAILURE:
        return "auth_failure"
    if reason_code == MOOMOO_SDK_MISSING:
        return "sdk_missing"
    if reason_code == OPEND_NON_LOOPBACK_BLOCKED:
        return "connection_blocked_non_loopback"
    if reason_code != MOOMOO_PROTOCOL_ERROR:
        return "transport_unavailable"
    msg = (vendor_ret_msg or "").lower()
    if "freq" in msg or "frequency" in msg or "too many" in msg:
        return "vendor_frequency_limit"
    if "timeout" in msg or "timed out" in msg:
        return "transport_timeout"
    if "ret_error" in msg or "no right" in msg:
        return "vendor_ret_error"
    if vendor_ret is not None and vendor_ret != 0:
        return "vendor_ret_not_ok"
    return KLINE_PROTOCOL_UNCLASSIFIED


def _kline_fetch_result(
    *,
    reason_code: str | None,
    session_date: str,
    rows: list[dict[str, Any]] | None = None,
    vendor_ret: Any = None,
    vendor_ret_msg: str | None = None,
    connection_host: str | None = None,
    connection_port: int | None = None,
    kline_start: str | None = None,
    kline_end: str | None = None,
    max_count_requested: int | None = None,
    request_duration_ms: float | None = None,
    protocol_error_category: str | None = None,
) -> dict[str, Any]:
    """Fail-closed kline payload plus diagnostics (stderr JSON, no PIT change)."""

    raw_rows = list(rows) if rows is not None else []
    first_key, last_key, raw_count = _kline_time_keys(raw_rows)
    window_start = kline_start if kline_start is not None else session_date
    window_end = kline_end if kline_end is not None else session_date
    category = protocol_error_category
    if category is None:
        category = classify_kline_protocol_error_category(
            reason_code=reason_code,
            vendor_ret=vendor_ret,
            vendor_ret_msg=vendor_ret_msg,
        )
    payload: dict[str, Any] = {
        "reason_code": reason_code,
        "rows": None if reason_code else raw_rows,
        "session_date": session_date,
        "raw_row_count": 0 if reason_code else raw_count,
        "first_raw_time_key": None if reason_code else first_key,
        "last_raw_time_key": None if reason_code else last_key,
        "vendor_ret": vendor_ret,
        "vendor_ret_msg": vendor_ret_msg,
        "connection_host": connection_host,
        "connection_port": connection_port,
        "kline_start": window_start,
        "kline_end": window_end,
        "max_count_requested": max_count_requested,
        "request_duration_ms": request_duration_ms,
        "protocol_error_category": category,
    }
    print(
        json.dumps(
            {
                "item9_kline_fetch": True,
                "connection_host": connection_host,
                "connection_port": connection_port,
                "first_raw_time_key": payload["first_raw_time_key"],
                "kline_end": window_end,
                "kline_start": window_start,
                "last_raw_time_key": payload["last_raw_time_key"],
                "max_count_requested": max_count_requested,
                "protocol_error_category": category,
                "raw_row_count": payload["raw_row_count"],
                "reason_code": reason_code,
                "request_duration_ms": request_duration_ms,
                "session_date": session_date,
                "vendor_ret": vendor_ret,
                "vendor_ret_msg": vendor_ret_msg,
            },
            sort_keys=True,
            default=str,
        ),
        file=sys.stderr,
        flush=True,
    )
    return payload


def _close_quote_context(ctx: Any) -> None:
    if ctx is None:
        return
    closer = getattr(ctx, "close", None)
    if callable(closer):
        try:
            closer()
        except Exception:  # noqa: BLE001
            pass


class OpendQuoteKlineSession:
    """Reuse one loopback OpenD quote context across bounded Mode B poll steps."""

    __slots__ = ("_ctx", "_ft", "_host", "_port", "_sdk")

    def __init__(self, *, host: str, port: int, sdk: Any | None = None) -> None:
        self._host = host
        self._port = int(port)
        self._sdk = sdk
        self._ft: Any | None = None
        self._ctx: Any | None = None

    @property
    def is_open(self) -> bool:
        return self._ctx is not None

    def close(self) -> None:
        _close_quote_context(self._ctx)
        self._ctx = None
        self._ft = None

    def _invalidate_context(self) -> None:
        self.close()

    def _ensure_quote_context(self) -> tuple[Any, Any] | None:
        if self._ctx is not None and self._ft is not None:
            return self._ctx, self._ft
        if self._host not in _LOOPBACK_HOSTS:
            return None
        ft = self._sdk if self._sdk is not None else load_vendor_sdk()
        if ft is None or not hasattr(ft, "OpenQuoteContext"):
            return None
        if not hasattr(ft, "RET_OK") or not hasattr(ft, "KLType"):
            return None
        try:
            ctx = ft.OpenQuoteContext(host=self._host, port=self._port)
        except Exception:  # noqa: BLE001
            return None
        self._ft = ft
        self._ctx = ctx
        return ctx, ft

    def fetch_history_kline_1m(
        self,
        symbol: str,
        *,
        max_count: int = US_EQUITY_1M_HISTORY_MIN_COUNT,
        session_date: str | None = None,
    ) -> dict[str, Any]:
        """History kline on the persistent quote context (caller closes the session)."""

        return fetch_history_kline_1m(
            symbol,
            host=self._host,
            port=self._port,
            max_count=max_count,
            sdk=self._sdk,
            session_date=session_date,
            opend_kline_session=self,
        )


def _history_kline_on_open_context(
    ctx: Any,
    ft: Any,
    *,
    symbol: str,
    day: str,
    request_count: int,
    started: float,
    host: str,
    port: int,
) -> dict[str, Any]:
    def _finish(**kwargs: Any) -> dict[str, Any]:
        duration_ms = round((time.monotonic() - started) * 1000.0, 3)
        return _kline_fetch_result(
            session_date=day,
            connection_host=host,
            connection_port=int(port),
            kline_start=day,
            kline_end=day,
            max_count_requested=request_count,
            request_duration_ms=duration_ms,
            **kwargs,
        )

    code = _provider_code(symbol)
    if not code:
        return _finish(reason_code=MOOMOO_PROTOCOL_ERROR, rows=None)
    try:
        ret, state = ctx.get_global_state()
        if ret != ft.RET_OK:
            return _finish(
                reason_code=MOOMOO_PROTOCOL_ERROR,
                vendor_ret=ret,
                vendor_ret_msg=_bounded_vendor_msg(state),
            )
        if not _qot_logined(state):
            return _finish(
                reason_code=MOOMOO_AUTH_FAILURE,
                vendor_ret=ret,
                vendor_ret_msg="qot_logined=false",
            )
        k_ret, data, _page = ctx.request_history_kline(
            code,
            start=day,
            end=day,
            ktype=ft.KLType.K_1M,
            autype=ft.AuType.QFQ,
            max_count=request_count,
            extended_time=True,
            session=ft.Session.ALL,
        )
        if k_ret != ft.RET_OK:
            return _finish(
                reason_code=MOOMOO_PROTOCOL_ERROR,
                vendor_ret=k_ret,
                vendor_ret_msg=_bounded_vendor_msg(data),
            )
        rows = _snapshot_rows(data)
        return _finish(
            reason_code=None,
            rows=rows,
            vendor_ret=k_ret,
            vendor_ret_msg=None,
        )
    except Exception as exc:  # noqa: BLE001
        return _finish(
            reason_code=MOOMOO_PROTOCOL_ERROR,
            vendor_ret=None,
            vendor_ret_msg=_bounded_vendor_msg(f"{type(exc).__name__}: {exc}"),
        )


def fetch_history_kline_1m(
    symbol: str,
    *,
    host: str,
    port: int,
    max_count: int = US_EQUITY_1M_HISTORY_MIN_COUNT,
    sdk: Any | None = None,
    session_date: str | None = None,
    opend_kline_session: OpendQuoteKlineSession | None = None,
) -> dict[str, Any]:
    """Return completed 1m klines for the US equity session day (quote context only).

    Do not pass ``start=None, end=None``: the vendor SDK expands that to
    ``[today-365d, today]``. For ``K_1M`` we infer (same API as proven
    ``K_DAY`` oldest-first paging + SDK window) that the **oldest** ``max_count``
    bars may be returned — not a live-sampled 1m receipt. Year-old pages fail
    ``available_time > signal_time``.

    When ``opend_kline_session`` is set, reuse its quote context and do not
    close it after this call (bounded Mode B ``--poll``).
    """

    day = str(session_date or "").strip() or us_equity_session_date()
    request_count = max(int(max_count), US_EQUITY_1M_HISTORY_MIN_COUNT)
    started = time.monotonic()

    def _finish(**kwargs: Any) -> dict[str, Any]:
        duration_ms = round((time.monotonic() - started) * 1000.0, 3)
        return _kline_fetch_result(
            session_date=day,
            connection_host=host,
            connection_port=int(port),
            kline_start=day,
            kline_end=day,
            max_count_requested=request_count,
            request_duration_ms=duration_ms,
            **kwargs,
        )

    if host not in _LOOPBACK_HOSTS:
        return _finish(reason_code=OPEND_NON_LOOPBACK_BLOCKED, rows=None)
    ft = sdk if sdk is not None else load_vendor_sdk()
    if ft is None or not hasattr(ft, "OpenQuoteContext"):
        return _finish(reason_code=MOOMOO_SDK_MISSING, rows=None)
    if not hasattr(ft, "RET_OK") or not hasattr(ft, "KLType"):
        return _finish(reason_code=MOOMOO_PROTOCOL_ERROR, rows=None)

    owns_context = False
    ctx: Any | None = None
    if opend_kline_session is not None:
        pair = opend_kline_session._ensure_quote_context()
        if pair is None:
            return _finish(reason_code=MOOMOO_SDK_MISSING, rows=None)
        ctx, ft = pair
    else:
        owns_context = True
        try:
            ctx = ft.OpenQuoteContext(host=host, port=port)
        except Exception as exc:  # noqa: BLE001
            return _finish(
                reason_code=MOOMOO_PROTOCOL_ERROR,
                vendor_ret=None,
                vendor_ret_msg=_bounded_vendor_msg(f"{type(exc).__name__}: {exc}"),
            )

    try:
        payload = _history_kline_on_open_context(
            ctx,
            ft,
            symbol=symbol,
            day=day,
            request_count=request_count,
            started=started,
            host=host,
            port=port,
        )
        if (
            opend_kline_session is not None
            and payload.get("reason_code") == MOOMOO_PROTOCOL_ERROR
            and payload.get("vendor_ret") is None
            and payload.get("vendor_ret_msg")
        ):
            msg = str(payload.get("vendor_ret_msg") or "").lower()
            if "disconnect" in msg or "connection" in msg or "broken pipe" in msg:
                opend_kline_session._invalidate_context()
        return payload
    except Exception as exc:  # noqa: BLE001
        if opend_kline_session is not None:
            opend_kline_session._invalidate_context()
        return _finish(
            reason_code=MOOMOO_PROTOCOL_ERROR,
            vendor_ret=None,
            vendor_ret_msg=_bounded_vendor_msg(f"{type(exc).__name__}: {exc}"),
        )
    finally:
        if owns_context:
            _close_quote_context(ctx)


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
    ft = sdk if sdk is not None else load_vendor_sdk()
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


def is_vendor_sdk(module: Any) -> bool:
    """True only for the vendor quote package, not ``tools/moomoo``."""

    opener = getattr(module, "OpenQuoteContext", None)
    return callable(opener)


def _import_sdk() -> Any | None:
    """Load vendor ``moomoo-api``, ignoring a shadowed ``tools/moomoo`` package.

    ``python tools/*.py`` and ``python tools/validation_worker.py`` put
    ``tools/`` on ``sys.path[0]``. That makes ``import moomoo`` resolve to this
    directory (no ``OpenQuoteContext``) and would otherwise report a fake SDK
    while also hiding a real site-packages install. Quote fetch stays
    fail-closed: missing vendor SDK is ``MOOMOO_SDK_MISSING``, never a tick.
    """

    cached = sys.modules.get("moomoo")
    if cached is not None and is_vendor_sdk(cached):
        return cached

    tools_resolved = _TOOLS_DIR.resolve()
    filtered: list[str] = []
    for entry in sys.path:
        try:
            if Path(entry).resolve() == tools_resolved:
                continue
        except OSError:
            pass
        filtered.append(entry)

    prior_path = list(sys.path)
    popped = None
    if cached is not None and not is_vendor_sdk(cached):
        popped = sys.modules.pop("moomoo", None)
    try:
        sys.path[:] = filtered
        importlib.invalidate_caches()
        try:
            import moomoo as ft  # type: ignore[import-not-found]
        except ImportError:
            return None
        return ft if is_vendor_sdk(ft) else None
    finally:
        sys.path[:] = prior_path
        if popped is not None and "moomoo" not in sys.modules:
            sys.modules["moomoo"] = popped


def _unavailable(reason_code: str) -> dict[str, Any]:
    return {"reason_code": reason_code, "row": None}


def _provider_code(symbol: str) -> str:
    wanted = str(symbol or "").strip().upper()
    if not wanted:
        return ""
    if "." in wanted:
        return wanted
    return f"US.{wanted}"


def probe_quote_login(*, host: str, port: int) -> dict[str, Any]:
    """Quote-login diagnostic for operator tooling. Not a market-data tick."""

    if host not in _LOOPBACK_HOSTS:
        sdk = load_vendor_sdk()
        return {
            "sdk": "PRESENT" if sdk is not None else "ABSENT",
            "quote_login": "INVALID",
            "qot_entitled": False,
            "reason": "OPEND_NOT_LOOPBACK",
        }
    ft = load_vendor_sdk()
    if ft is None:
        return {
            "sdk": "ABSENT",
            "quote_login": "UNAVAILABLE",
            "qot_entitled": False,
            "reason": "MOOMOO_SDK_NOT_INSTALLED",
        }
    import socket

    try:
        sock = socket.create_connection((host, port), timeout=2.0)
        sock.close()
    except OSError as exc:
        return {
            "sdk": "PRESENT",
            "quote_login": "UNAVAILABLE",
            "qot_entitled": False,
            "reason": type(exc).__name__,
        }

    ctx = None
    try:
        ctx = ft.OpenQuoteContext(host=host, port=port)
        ret, state = ctx.get_global_state()
        if ret != ft.RET_OK or not isinstance(state, dict):
            return {
                "sdk": "PRESENT",
                "quote_login": "INVALID",
                "qot_entitled": False,
                "reason": "MOOMOO_PROTOCOL_ERROR",
                "ret": ret,
            }
        entitled = _qot_logined(state)
        return {
            "sdk": "PRESENT",
            "quote_login": "VALID" if entitled else "INVALID",
            "qot_entitled": entitled,
        }
    except Exception as exc:  # noqa: BLE001 — operator diagnostic only
        return {
            "sdk": "PRESENT",
            "quote_login": "UNAVAILABLE",
            "qot_entitled": False,
            "reason": type(exc).__name__,
        }
    finally:
        if ctx is not None:
            closer = getattr(ctx, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:  # noqa: BLE001
                    pass


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
    "US_EQUITY_1M_HISTORY_MIN_COUNT",
    "KLINE_PROTOCOL_UNCLASSIFIED",
    "OpendQuoteKlineSession",
    "classify_kline_protocol_error_category",
    "fetch_history_kline_1m",
    "fetch_snapshot",
    "probe_quote_login",
    "is_vendor_sdk",
    "load_vendor_sdk",
    "sdk_available",
    "us_equity_session_date",
]
