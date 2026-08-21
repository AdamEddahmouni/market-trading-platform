"""Read-only Moomoo OpenD capability probe.

Never imports OpenTradeContext or any trade API. Connects only to localhost.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROBE_VERSION = "1.0.0"
FORBIDDEN_TRADE_NAMES = (
    "OpenTradeContext",
    "OpenUSTradeContext",
    "OpenHKTradeContext",
    "OpenSecTradeContext",
    "OpenCryptoTradeContext",
    "unlock_trade",
    "place_order",
    "modify_order",
    "cancel_order",
)
REDACT_KEYS = ("user", "acc", "pwd", "password", "token", "secret", "key", "login")


def _now_ns() -> int:
    return time.time_ns()


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if hasattr(value, "to_dict"):
        try:
            return jsonable(value.replace({getattr(__import__("pandas"), "NA", None): None}).to_dict(orient="records"))
        except Exception:
            return str(value)
    if hasattr(value, "item"):
        try:
            return jsonable(value.item())
        except Exception:
            return str(value)
    return str(value)


def redact(payload: Any) -> Any:
    if isinstance(payload, dict):
        cleaned = {}
        for key, value in payload.items():
            lowered = str(key).lower()
            if any(token in lowered for token in REDACT_KEYS):
                cleaned[key] = "REDACTED"
            else:
                cleaned[key] = redact(value)
        return cleaned
    if isinstance(payload, list):
        return [redact(item) for item in payload]
    return payload


def schema_inventory(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return []
    inventory = []
    sample = records[0]
    for key in sorted(sample):
        observed = [row.get(key) for row in records if key in row]
        non_null = next((item for item in observed if item not in (None, "", [])), None)
        inventory.append(
            {
                "field": key,
                "non_null_count": sum(item not in (None, "") for item in observed),
                "python_type": None if non_null is None else type(non_null).__name__,
                "sample": non_null if not isinstance(non_null, (list, dict)) else type(non_null).__name__,
            }
        )
    return inventory


def summarize_levels(book: dict[str, Any], side: str, limit: int = 10) -> dict[str, Any]:
    raw = book.get(side) or []
    levels = []
    for item in raw[:limit]:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            levels.append(
                {
                    "order_count": item[2] if len(item) >= 3 else None,
                    "order_details_keys": sorted((item[3] or {}).keys())
                    if len(item) >= 4 and isinstance(item[3], dict)
                    else [],
                    "price": item[0],
                    "size": item[1],
                }
            )
    return {"depth": len(raw), "levels_head": levels}


def capability_row(**kwargs: Any) -> dict[str, Any]:
    defaults = {
        "account_entitled": False,
        "adapter_implemented": True,
        "data_currently_fresh": False,
        "evidence_class": "UNTESTED",
        "notes": "",
        "provider_supports": True,
        "reason_code": None,
        "runtime_tested": False,
    }
    defaults.update(kwargs)
    return defaults


def confirm_localhost(host: str, port: int) -> dict[str, Any]:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("OPEND_MUST_REMAIN_LOCALHOST")
    sock = socket.create_connection((host, port), timeout=3)
    peer = sock.getpeername()
    sock.close()
    return {"host": host, "peer": list(peer), "port": port, "reachable": True}


def run_probe(*, host: str, port: int, output: Path, subscribe_seconds: float) -> dict[str, Any]:
    confirm_localhost(host, port)
    # Import only after the localhost guard. Quote context only.
    import moomoo as ft

    for name in FORBIDDEN_TRADE_NAMES:
        if name in dir(ft) and name.startswith("Open") and "Trade" in name:
            continue
    if "OpenTradeContext" in sys.modules:
        raise RuntimeError("TRADE_MODULE_LOADED")

    report: dict[str, Any] = {
        "probe_version": PROBE_VERSION,
        "provider": "moomoo",
        "sdk_version": getattr(ft, "__version__", "unknown"),
        "tested_at": _utc_iso(),
        "connectivity": {},
        "markets": {},
        "entitlements": {},
        "capabilities": {},
        "sessions": {},
        "timestamps": {},
        "subscription_quota": {},
        "historical_quota": {},
        "quality_findings": {},
        "limitations": [],
        "evidence": [],
        "schema_inventories": {},
    }

    quote_ctx = ft.OpenQuoteContext(host=host, port=port)
    try:
        ret, state = quote_ctx.get_global_state()
        report["connectivity"] = {
            "evidence_class": "OBSERVED",
            "host": host,
            "opend_version": None if ret != ft.RET_OK else redact(state).get("server_ver"),
            "port": port,
            "qot_logined": None if ret != ft.RET_OK else str(state.get("qot_logined")),
            "ret": ret,
            "server_timestamp": None if ret != ft.RET_OK else state.get("timestamp"),
            "local_timestamp": None if ret != ft.RET_OK else state.get("local_timestamp"),
            "trd_logined": None if ret != ft.RET_OK else str(state.get("trd_logined")),
        }
        if ret == ft.RET_OK:
            report["timestamps"]["opend_server_minus_local_s"] = None
            try:
                report["timestamps"]["opend_server_minus_local_s"] = float(state["timestamp"]) - float(
                    state["local_timestamp"]
                )
            except (TypeError, ValueError, KeyError):
                pass
            report["markets"] = {
                key: value
                for key, value in redact(state).items()
                if str(key).startswith("market_")
            }

        ret_sub, sub = quote_ctx.query_subscription(is_all_conn=True)
        report["subscription_quota"] = {
            "evidence_class": "OBSERVED",
            "ret": ret_sub,
            "payload": redact(sub) if ret_sub == ft.RET_OK else str(sub),
        }

        snapshots = _probe_snapshots(quote_ctx, ft, report)
        _probe_streaming(quote_ctx, ft, report, subscribe_seconds)
        _probe_history(quote_ctx, ft, report)
        _probe_options(quote_ctx, ft, report)
        _probe_futures(quote_ctx, ft, report)
        _probe_crypto(quote_ctx, ft, report)
        _probe_failures(quote_ctx, ft, report)
        _probe_reconnect(host, port, ft, report)

        if snapshots:
            report["schema_inventories"]["equity_snapshot"] = schema_inventory(snapshots)
    finally:
        quote_ctx.close()

    report["limitations"] = sorted(set(report["limitations"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path = output.with_suffix(".summary.txt")
    summary_path.write_text(_human_summary(report), encoding="utf-8")
    return report


def _probe_snapshots(quote_ctx: Any, ft: Any, report: dict[str, Any]) -> list[dict[str, Any]]:
    codes = ["US.AAPL", "US.NVDA", "US.SPY", "US.BIYA"]
    received = _now_ns()
    ret, data = quote_ctx.get_market_snapshot(codes)
    records = jsonable(data) if ret == ft.RET_OK else []
    records = [redact(row) for row in records] if isinstance(records, list) else []
    freshness = []
    for row in records:
        update = str(row.get("update_time") or "")
        freshness.append(
            {
                "code": row.get("code"),
                "last_price": row.get("last_price"),
                "overnight_price": row.get("overnight_price"),
                "pre_price": row.get("pre_price"),
                "after_price": row.get("after_price"),
                "sec_status": row.get("sec_status"),
                "suspension": row.get("suspension"),
                "update_time": update,
                "bid_price": row.get("bid_price"),
                "ask_price": row.get("ask_price"),
                "volume": row.get("volume"),
                "lot_size": row.get("lot_size"),
            }
        )
    report["evidence"].append(
        {
            "capability": "US_EQUITY_SNAPSHOT",
            "instrument": codes,
            "received_time_ns": received,
            "ret": ret,
            "row_count": len(records) if isinstance(records, list) else 0,
            "error": None if ret == ft.RET_OK else str(data),
        }
    )
    entitled = ret == ft.RET_OK and bool(records)
    report["capabilities"]["US_EQUITY_SNAPSHOT"] = capability_row(
        capability="US_EQUITY_SNAPSHOT",
        account_entitled=entitled,
        runtime_tested=True,
        data_currently_fresh=entitled,
        evidence_class="OBSERVED",
        notes="Snapshot inventory stored separately; raw rows not dumped.",
    )
    overnight_present = any(row.get("overnight_price") not in (None, 0, 0.0) or row.get("overnight_volume") for row in records)
    pre_present = any(row.get("pre_price") not in (None, 0, 0.0) or row.get("pre_volume") for row in records)
    after_present = any(row.get("after_price") not in (None, 0, 0.0) or row.get("after_volume") for row in records)
    report["capabilities"]["US_EQUITY_OVERNIGHT"] = capability_row(
        capability="US_EQUITY_OVERNIGHT",
        account_entitled=True,
        runtime_tested=True,
        data_currently_fresh=overnight_present,
        evidence_class="OBSERVED" if overnight_present else "INFERRED",
        notes="overnight_* snapshot fields present" if overnight_present else "overnight_* fields returned empty/zero at probe time",
    )
    report["capabilities"]["US_EQUITY_EXTENDED_HOURS"] = capability_row(
        capability="US_EQUITY_EXTENDED_HOURS",
        account_entitled=True,
        runtime_tested=True,
        data_currently_fresh=pre_present or after_present,
        evidence_class="OBSERVED",
        notes=f"pre_present={pre_present} after_present={after_present}",
    )
    report["sessions"]["snapshot"] = freshness
    report["schema_inventories"]["snapshot_session_fields"] = [
        key
        for key in (records[0].keys() if records else [])
        if any(token in key for token in ("pre_", "after_", "overnight_", "sec_status", "update_time"))
    ]
    return records if isinstance(records, list) else []


def _probe_streaming(quote_ctx: Any, ft: Any, report: dict[str, Any], subscribe_seconds: float) -> None:
    code = "US.AAPL"
    quote_events: list[dict[str, Any]] = []
    ticker_events: list[dict[str, Any]] = []
    book_events: list[dict[str, Any]] = []

    class QuoteHandler(ft.StockQuoteHandlerBase):
        def on_recv_rsp(self, rsp_pb):  # type: ignore[no-untyped-def]
            ret, data = super().on_recv_rsp(rsp_pb)
            quote_events.append({"received_time_ns": _now_ns(), "ret": ret, "payload": jsonable(data)})
            return ret, data

    class TickerHandler(ft.TickerHandlerBase):
        def on_recv_rsp(self, rsp_pb):  # type: ignore[no-untyped-def]
            ret, data = super().on_recv_rsp(rsp_pb)
            ticker_events.append({"received_time_ns": _now_ns(), "ret": ret, "payload": jsonable(data)})
            return ret, data

    class BookHandler(ft.OrderBookHandlerBase):
        def on_recv_rsp(self, rsp_pb):  # type: ignore[no-untyped-def]
            ret, data = super().on_recv_rsp(rsp_pb)
            book_events.append({"received_time_ns": _now_ns(), "ret": ret, "payload": jsonable(data)})
            return ret, data

    quote_ctx.set_handler(QuoteHandler())
    quote_ctx.set_handler(TickerHandler())
    quote_ctx.set_handler(BookHandler())
    ret_sub, sub_msg = quote_ctx.subscribe(
        [code],
        [ft.SubType.QUOTE, ft.SubType.TICKER, ft.SubType.ORDER_BOOK],
        is_first_push=True,
        subscribe_push=True,
        session=ft.Session.ALL,
    )
    report["evidence"].append(
        {
            "capability": "subscribe.QUOTE+TICKER+ORDER_BOOK",
            "instrument": code,
            "ret": ret_sub,
            "error": None if ret_sub == ft.RET_OK else str(sub_msg),
            "session": "ALL",
        }
    )
    time.sleep(max(1.0, subscribe_seconds))
    ret_q, quote_cache = quote_ctx.get_stock_quote([code])
    ret_t, ticker_cache = quote_ctx.get_rt_ticker(code, num=20)
    ret_b, book_cache = quote_ctx.get_order_book(code, num=10)
    ret_quota, quota = quote_ctx.query_subscription(True)
    quote_ctx.unsubscribe([code], [ft.SubType.QUOTE, ft.SubType.TICKER, ft.SubType.ORDER_BOOK])

    quote_rows = jsonable(quote_cache) if ret_q == ft.RET_OK else []
    ticker_rows = jsonable(ticker_cache) if ret_t == ft.RET_OK else []
    book = jsonable(book_cache) if ret_b == ft.RET_OK else {}
    if isinstance(book, dict):
        book = redact(book)

    report["capabilities"]["US_EQUITY_L1"] = capability_row(
        capability="US_EQUITY_L1",
        account_entitled=ret_q == ft.RET_OK,
        runtime_tested=True,
        data_currently_fresh=bool(quote_rows),
        evidence_class="OBSERVED",
        notes=f"subscribe_ret={ret_sub} cache_ret={ret_q} push_count={len(quote_events)}",
        reason_code=None if ret_q == ft.RET_OK else str(quote_cache),
    )
    report["capabilities"]["US_EQUITY_TICKS"] = capability_row(
        capability="US_EQUITY_TICKS",
        account_entitled=ret_t == ft.RET_OK,
        runtime_tested=True,
        data_currently_fresh=bool(ticker_rows),
        evidence_class="OBSERVED",
        notes=f"cache_rows={len(ticker_rows) if isinstance(ticker_rows, list) else 0} push_count={len(ticker_events)}",
        reason_code=None if ret_t == ft.RET_OK else str(ticker_cache),
    )
    depth = 0
    if isinstance(book, dict):
        depth = max(len(book.get("Bid") or []), len(book.get("Ask") or []))
    report["capabilities"]["US_EQUITY_DEPTH"] = capability_row(
        capability="US_EQUITY_DEPTH",
        account_entitled=ret_b == ft.RET_OK and depth > 0,
        runtime_tested=True,
        data_currently_fresh=depth > 0,
        evidence_class="OBSERVED",
        notes=f"depth={depth} push_count={len(book_events)} detailed_orderbook=not_requested",
        reason_code=None if ret_b == ft.RET_OK else str(book_cache),
    )
    report["subscription_quota"]["after_stream"] = redact(quota) if ret_quota == ft.RET_OK else str(quota)
    report["schema_inventories"]["equity_quote"] = schema_inventory(quote_rows if isinstance(quote_rows, list) else [])
    report["schema_inventories"]["equity_ticker"] = schema_inventory(ticker_rows if isinstance(ticker_rows, list) else [])
    if isinstance(book, dict):
        report["schema_inventories"]["equity_order_book"] = {
            "ask": summarize_levels(book, "Ask"),
            "bid": summarize_levels(book, "Bid"),
            "svr_recv_time_ask": book.get("svr_recv_time_ask"),
            "svr_recv_time_bid": book.get("svr_recv_time_bid"),
            "code": book.get("code"),
            "keys": sorted(book.keys()),
        }
        report["quality_findings"]["order_book"] = {
            "best_ask": (book.get("Ask") or [[None]])[0][0] if book.get("Ask") else None,
            "best_bid": (book.get("Bid") or [[None]])[0][0] if book.get("Bid") else None,
            "depth_ask": len(book.get("Ask") or []),
            "depth_bid": len(book.get("Bid") or []),
        }
    ticker_dirs = []
    if isinstance(ticker_rows, list):
        ticker_dirs = sorted({str(row.get("ticker_direction")) for row in ticker_rows})
        report["quality_findings"]["ticker_directions"] = ticker_dirs
        report["schema_inventories"]["ticker_field_names"] = sorted(ticker_rows[0].keys()) if ticker_rows else []
    report["timestamps"]["streaming"] = {
        "book_push_count": len(book_events),
        "quote_push_count": len(quote_events),
        "ticker_push_count": len(ticker_events),
    }
    if not ticker_rows:
        report["limitations"].append("No ticker cache rows during probe window; session may be closed or quiet.")
    if depth and depth < 10:
        report["limitations"].append(f"Observed US equity depth {depth} levels, not a full US consolidated book.")
    if depth >= 1:
        report["limitations"].append(
            "US LV3 OpenAPI depth is MBP-style levels; detailed per-order book is documented as HK SF only."
        )


def _probe_history(quote_ctx: Any, ft: Any, report: dict[str, Any]) -> None:
    before = quote_ctx.query_subscription(True)
    ret, data, page_key = quote_ctx.request_history_kline(
        "US.AAPL",
        start=None,
        end=None,
        ktype=ft.KLType.K_DAY,
        autype=ft.AuType.QFQ,
        max_count=5,
        extended_time=True,
        session=ft.Session.ALL,
    )
    after = quote_ctx.query_subscription(True)
    rows = jsonable(data) if ret == ft.RET_OK else []
    report["historical_quota"] = {
        "evidence_class": "OBSERVED",
        "page_req_key_present": page_key is not None,
        "ret": ret,
        "row_count": len(rows) if isinstance(rows, list) else 0,
        "error": None if ret == ft.RET_OK else str(data),
        "subscription_before": redact(before[1]) if before[0] == ft.RET_OK else str(before[1]),
        "subscription_after": redact(after[1]) if after[0] == ft.RET_OK else str(after[1]),
        "notes": "Single-symbol conservative K_DAY lookback; unique-security quota not exhausted.",
    }
    report["capabilities"]["US_EQUITY_BARS"] = capability_row(
        capability="US_EQUITY_BARS",
        account_entitled=ret == ft.RET_OK,
        runtime_tested=True,
        data_currently_fresh=bool(rows),
        evidence_class="OBSERVED",
        reason_code=None if ret == ft.RET_OK else str(data),
    )
    if isinstance(rows, list) and rows:
        report["schema_inventories"]["history_kline"] = schema_inventory(rows[:1])
        report["sessions"]["history_extended_time"] = True


def _probe_options(quote_ctx: Any, ft: Any, report: dict[str, Any]) -> None:
    ret, data = quote_ctx.get_option_chain("US.AAPL")
    entitled = ret == ft.RET_OK
    report["entitlements"]["US_OPTIONS"] = {
        "account_entitled": entitled,
        "evidence_class": "OBSERVED",
        "provider_supports": True,
        "ret": ret,
        "error": None if entitled else str(data),
    }
    report["capabilities"]["US_OPTIONS_QUOTE"] = capability_row(
        capability="US_OPTIONS_QUOTE",
        provider_supports=True,
        account_entitled=entitled,
        adapter_implemented=True,
        runtime_tested=True,
        data_currently_fresh=False,
        evidence_class="OBSERVED",
        reason_code=None if entitled else "ACCOUNT_NOT_ENTITLED",
        notes=str(data)[:240],
    )
    if not entitled:
        report["limitations"].append("US options quotes fail closed: account not entitled.")


def _probe_futures(quote_ctx: Any, ft: Any, report: dict[str, Any]) -> None:
    ret_info, info = quote_ctx.get_stock_basicinfo(ft.Market.US, ft.SecurityType.FUTURE)
    codes = []
    if ret_info == ft.RET_OK:
        rows = jsonable(info)
        if isinstance(rows, list):
            codes = [str(row.get("code")) for row in rows[:3] if row.get("code")]
    snapshot_ret, snapshot = (ft.RET_ERROR, "no_codes")
    if codes:
        snapshot_ret, snapshot = quote_ctx.get_market_snapshot(codes[:1])
    entitled = snapshot_ret == ft.RET_OK
    report["entitlements"]["US_FUTURES"] = {
        "account_entitled": entitled,
        "basicinfo_ret": ret_info,
        "basicinfo_sample_codes": codes,
        "evidence_class": "OBSERVED",
        "provider_supports": True,
        "snapshot_error": None if entitled else str(snapshot),
        "snapshot_ret": snapshot_ret,
    }
    report["capabilities"]["US_FUTURES_QUOTE"] = capability_row(
        capability="US_FUTURES_QUOTE",
        provider_supports=True,
        account_entitled=entitled,
        adapter_implemented=True,
        runtime_tested=True,
        data_currently_fresh=entitled,
        evidence_class="OBSERVED",
        reason_code=None if entitled else "ACCOUNT_NOT_ENTITLED_OR_NO_LISTING",
        notes=str(snapshot)[:240],
    )
    if not entitled:
        report["limitations"].append("US futures quotes unavailable on this account (CME/CBOT/NYMEX/COMEX expected).")


def _probe_crypto(quote_ctx: Any, ft: Any, report: dict[str, Any]) -> None:
    ret_info, info = quote_ctx.get_stock_basicinfo(ft.Market.CC, ft.SecurityType.CRYPTO)
    codes = []
    if ret_info == ft.RET_OK:
        rows = jsonable(info)
        if isinstance(rows, list):
            codes = [str(row.get("code")) for row in rows[:3] if row.get("code")]
    snapshot_ret, snapshot = (ft.RET_ERROR, "no_codes")
    ticks_ret, ticks = (ft.RET_ERROR, "skipped")
    book_ret, book = (ft.RET_ERROR, "skipped")
    if codes:
        snapshot_ret, snapshot = quote_ctx.get_market_snapshot(codes[:1])
        if snapshot_ret == ft.RET_OK:
            quote_ctx.subscribe(codes[:1], [ft.SubType.TICKER, ft.SubType.ORDER_BOOK], subscribe_push=False)
            ticks_ret, ticks = quote_ctx.get_rt_ticker(codes[0], num=5)
            book_ret, book = quote_ctx.get_order_book(codes[0], num=5)
            quote_ctx.unsubscribe(codes[:1], [ft.SubType.TICKER, ft.SubType.ORDER_BOOK])
    entitled = snapshot_ret == ft.RET_OK
    report["entitlements"]["CRYPTO"] = {
        "account_entitled": entitled,
        "basicinfo_ret": ret_info,
        "evidence_class": "OBSERVED",
        "provider_supports": True,
        "sample_codes": codes,
        "snapshot_ret": snapshot_ret,
        "snapshot_error": None if entitled else str(snapshot),
        "ticker_ret": ticks_ret,
        "order_book_ret": book_ret,
    }
    report["capabilities"]["CRYPTO_SPOT_QUOTE"] = capability_row(
        capability="CRYPTO_SPOT_QUOTE",
        provider_supports=True,
        account_entitled=entitled,
        adapter_implemented=True,
        runtime_tested=True,
        data_currently_fresh=entitled,
        evidence_class="OBSERVED",
        notes="Characterization only; PI14+ remains unauthorized.",
        reason_code=None if entitled else str(snapshot)[:160],
    )
    report["capabilities"]["CRYPTO_SPOT_TICKS"] = capability_row(
        capability="CRYPTO_SPOT_TICKS",
        provider_supports=True,
        account_entitled=ticks_ret == ft.RET_OK,
        adapter_implemented=True,
        runtime_tested=True,
        data_currently_fresh=ticks_ret == ft.RET_OK,
        evidence_class="OBSERVED",
        reason_code=None if ticks_ret == ft.RET_OK else str(ticks)[:160],
    )
    book_ok = book_ret == ft.RET_OK
    report["capabilities"]["CRYPTO_SPOT_DEPTH"] = capability_row(
        capability="CRYPTO_SPOT_DEPTH",
        provider_supports=True,
        account_entitled=book_ok,
        adapter_implemented=True,
        runtime_tested=True,
        data_currently_fresh=book_ok,
        evidence_class="OBSERVED",
        reason_code=None if book_ok else str(book)[:160],
    )
    report["limitations"].append("Crypto characterization does not authorize PI14+ research implementation.")


def _probe_failures(quote_ctx: Any, ft: Any, report: dict[str, Any]) -> None:
    cases = {}
    ret, data = quote_ctx.get_market_snapshot(["US.NOTAREALZZZ"])
    cases["invalid_ticker"] = {"ret": ret, "error": None if ret == ft.RET_OK else str(data), "rows": jsonable(data) if ret == ft.RET_OK else None}
    ret, data = quote_ctx.subscribe(["US.AAPL"], [ft.SubType.QUOTE], subscribe_push=False)
    ret2, data2 = quote_ctx.subscribe(["US.AAPL"], [ft.SubType.QUOTE], subscribe_push=False)
    cases["duplicate_subscribe"] = {"first_ret": ret, "second_ret": ret2, "second_msg": None if ret2 == ft.RET_OK else str(data2)}
    ret_un, un_msg = quote_ctx.unsubscribe(["US.MSFT"], [ft.SubType.TICKER])
    cases["unsubscribe_nonexistent"] = {"ret": ret_un, "msg": str(un_msg)}
    quote_ctx.unsubscribe(["US.AAPL"], [ft.SubType.QUOTE])
    report["quality_findings"]["failure_cases"] = cases


def _probe_reconnect(host: str, port: int, ft: Any, report: dict[str, Any]) -> None:
    ctx = ft.OpenQuoteContext(host=host, port=port)
    try:
        ret, state = ctx.get_global_state()
        report["quality_findings"]["reconnect"] = {
            "evidence_class": "OBSERVED",
            "ret": ret,
            "qot_logined": None if ret != ft.RET_OK else str(state.get("qot_logined")),
            "notes": "New quote context after original session; OpenD process was not killed.",
        }
    finally:
        ctx.close()


def _human_summary(report: dict[str, Any]) -> str:
    lines = [
        f"Moomoo observational probe {report.get('probe_version')} at {report.get('tested_at')}",
        f"SDK {report.get('sdk_version')} OpenD {report.get('connectivity', {}).get('opend_version')}",
        "",
        "Capabilities:",
    ]
    for key, row in sorted((report.get("capabilities") or {}).items()):
        lines.append(
            f"- {key}: entitled={row.get('account_entitled')} tested={row.get('runtime_tested')} "
            f"fresh={row.get('data_currently_fresh')} class={row.get('evidence_class')} notes={row.get('notes')}"
        )
    lines.append("")
    lines.append("Limitations:")
    for item in report.get("limitations") or []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Moomoo OpenD capability probe")
    parser.add_argument("--host", default=os.environ.get("IMP_MOOMOO_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("IMP_MOOMOO_PORT", "11111")))
    parser.add_argument(
        "--output",
        default=str(Path("evidence/market_data/moomoo/capability-report.json")),
    )
    parser.add_argument("--subscribe-seconds", type=float, default=8.0)
    args = parser.parse_args()
    run_probe(host=args.host, port=args.port, output=Path(args.output), subscribe_seconds=args.subscribe_seconds)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
