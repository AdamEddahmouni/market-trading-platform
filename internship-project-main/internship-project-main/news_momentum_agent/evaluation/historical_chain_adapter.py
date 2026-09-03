"""Map IVolatility (or fixture) option/stock rows → production Snapshot/ContractRow.

Purpose
-------
Vendor-agnostic CSV normalization so historical replay uses the same types as live
``options_engine`` ingest.

Features / API role
-------------------
``rows_to_snapshot``, ``normalize_option_row``, ``spot_from_stock_rows``,
``schema_mapping_report``.

How this uses ``options_confirmation_engine``
-----------------------------------------------
Imports ``options_engine.data_models.ContractRow`` and ``Snapshot`` after adding
``ENGINE_ROOT`` to ``sys.path``.

Options-specific vs reusable
----------------------------
Maps vendor columns to engine contract schema (options-specific). Normalization
helpers are reusable for any CSV chain vendor.
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = PROJECT_ROOT.parent / "options_confirmation_engine"
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from options_engine.data_models import ContractRow, Snapshot  # noqa: E402


INTERNAL_SCHEMA_FIELDS = (
    "as_of",
    "underlying",
    "expiration",
    "strike",
    "call_put",
    "bid",
    "ask",
    "last",
    "volume",
    "open_interest",
    "iv",
    "spot",
    "delta",
    "contract_symbol",
)


def _pick(row: Dict[str, Any], *keys: str) -> Any:
    lower = {str(k).lower().replace(" ", "_"): v for k, v in row.items()}
    for key in keys:
        if key.lower() in lower and lower[key.lower()] not in (None, ""):
            return lower[key.lower()]
    return None


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _side(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"C", "CALL", "CALLS"}:
        return "call"
    if text in {"P", "PUT", "PUTS"}:
        return "put"
    text_l = text.lower()
    if "call" in text_l:
        return "call"
    if "put" in text_l:
        return "put"
    return ""


def _exp_iso(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip().replace("Z", "")
    if "T" in text:
        text = text.split("T", 1)[0]
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    # e.g. 20260724
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text


def normalize_option_row(row: Dict[str, Any], *, default_as_of: str = "") -> Dict[str, Any]:
    """Map vendor columns onto the internal research schema."""
    as_of = str(
        _pick(row, "_trade_date", "tradeDate", "trade_date", "c_date", "date", "t_date", "as_of")
        or default_as_of
        or ""
    )[:10]
    underlying = str(
        _pick(row, "stock_symbol", "symbol", "underlying", "underlying_symbol", "ticker") or ""
    ).upper()
    expiration = _exp_iso(_pick(row, "expiration_date", "expiration", "expiry", "expDate"))
    strike = _f(_pick(row, "strike", "strike_price", "strikePrice", "price_strike"))
    cp = _side(_pick(row, "call_put", "callPut", "option_type", "type", "cp", "right"))
    bid = _f(_pick(row, "bid", "Bid", "bid_price", "best_bid"))
    ask = _f(_pick(row, "ask", "Ask", "ask_price", "best_ask"))
    last = _f(_pick(row, "last", "last_price", "price", "close", "mid"))
    if last <= 0 and bid > 0 and ask > 0:
        last = (bid + ask) / 2.0
    volume = _f(_pick(row, "volume", "vol"))
    oi = _f(_pick(row, "open_interest", "openInterest", "oi", "openinterest"))
    iv = _f(_pick(row, "iv", "implied_volatility", "impliedVolatility", "raw_iv", "vega_iv", "preiv"))
    spot = _f(
        _pick(
            row,
            "spot",
            "underlying_price",
            "stock_price",
            "price_underlying",
            "close_underlying",
        )
    )
    delta = _f(_pick(row, "delta"))
    symbol = str(
        _pick(row, "option_symbol", "optionSymbol", "contract_symbol", "osymbol", "ticker_option")
        or ""
    )
    return {
        "as_of": as_of,
        "underlying": underlying,
        "expiration": expiration,
        "strike": strike,
        "call_put": cp,
        "bid": bid,
        "ask": ask,
        "last": last,
        "volume": volume,
        "open_interest": oi,
        "iv": iv,
        "spot": spot,
        "delta": delta,
        "contract_symbol": symbol,
    }


def normalize_stock_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map vendor stock/underlying row to ``as_of``, ``symbol``, ``close``."""
    as_of = str(_pick(row, "date", "tradeDate", "trade_date", "t_date", "as_of") or "")[:10]
    close = _f(_pick(row, "close", "adj_close", "adjusted_close", "price", "last"))
    symbol = str(_pick(row, "symbol", "stock_symbol", "ticker") or "").upper()
    return {"as_of": as_of, "symbol": symbol, "close": close}


def schema_mapping_report(sample_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate that normalized rows cover fields the replay harness needs."""
    if not sample_rows:
        return {"ok": False, "reason": "no_rows", "covered": {}, "missing_required": list(INTERNAL_SCHEMA_FIELDS)}
    normalized = [normalize_option_row(r) for r in sample_rows[:50]]
    covered = {}
    for field in INTERNAL_SCHEMA_FIELDS:
        non_empty = sum(
            1
            for r in normalized
            if r.get(field) not in (None, "", 0, 0.0) or field in {"bid", "ask", "last", "volume", "iv", "delta"}
        )
        # For numeric quote fields, presence of key after normalize counts.
        covered[field] = non_empty > 0 or any(field in r for r in normalized)
    required = ("as_of", "expiration", "strike", "call_put")
    missing = [f for f in required if not covered.get(f)]
    # Need at least one usable price field
    if not (covered.get("bid") or covered.get("ask") or covered.get("last")):
        missing.append("bid|ask|last")
    return {
        "ok": len(missing) == 0,
        "n_sample": len(normalized),
        "covered": covered,
        "missing_required": missing,
        "sample_normalized": normalized[:3],
    }


def rows_to_snapshot(
    underlying: str,
    as_of: str,
    option_rows: Sequence[Dict[str, Any]],
    *,
    spot: float = 0.0,
    provider: str = "ivolatility",
) -> Snapshot:
    """Build a production Snapshot from normalized (or raw vendor) option rows."""
    symbol = underlying.upper().strip()
    contracts: List[ContractRow] = []
    expirations: List[str] = []
    spot_acc = float(spot or 0.0)

    for raw in option_rows:
        row = normalize_option_row(raw, default_as_of=as_of)
        if row["underlying"] and row["underlying"] != symbol:
            # Allow rows without underlying filled if caller scoped the file.
            if row["underlying"] not in {symbol, ""}:
                continue
        side = row["call_put"]
        if side not in {"call", "put"}:
            continue
        exp = row["expiration"]
        strike = float(row["strike"] or 0.0)
        if not exp or strike <= 0:
            continue
        if row["spot"] > 0 and spot_acc <= 0:
            spot_acc = float(row["spot"])
        if exp not in expirations:
            expirations.append(exp)
        itm = (strike <= spot_acc) if side == "call" else (strike >= spot_acc) if spot_acc > 0 else False
        contracts.append(
            ContractRow(
                contract_symbol=str(row["contract_symbol"] or f"{symbol}{exp.replace('-', '')}{side[0].upper()}{int(strike*1000):08d}"),
                side=side,
                strike=strike,
                expiration=exp,
                implied_volatility=float(row["iv"] or 0.0),
                volume=float(row["volume"] or 0.0),
                open_interest=float(row["open_interest"] or 0.0),
                bid=float(row["bid"] or 0.0),
                ask=float(row["ask"] or 0.0),
                last_price=float(row["last"] or 0.0),
                in_the_money=bool(itm),
                delta=float(row["delta"] or 0.0),
            )
        )

    expirations = sorted(expirations)
    flags: List[str] = []
    if not contracts:
        flags.append("empty_chain")
    if spot_acc <= 0:
        flags.append("missing_spot_price")
    return Snapshot(
        ticker=symbol,
        as_of=as_of if "T" in as_of else f"{as_of}T21:00:00+00:00",
        spot_price=float(spot_acc),
        expirations=expirations,
        contracts=contracts,
        data_quality_flags=flags,
        provider=provider,
    )


def spot_from_stock_rows(stock_rows: Sequence[Dict[str, Any]], as_of: str) -> float:
    """Resolve underlying close for ``as_of`` from normalized stock rows."""
    target = as_of[:10]
    for raw in stock_rows:
        row = normalize_stock_row(raw)
        if row["as_of"] == target and row["close"] > 0:
            return float(row["close"])
    # fallback: last available on or before
    best = 0.0
    best_date = ""
    for raw in stock_rows:
        row = normalize_stock_row(raw)
        if row["as_of"] and row["as_of"] <= target and row["close"] > 0:
            if row["as_of"] >= best_date:
                best_date = row["as_of"]
                best = float(row["close"])
    return best
