"""Alpaca Paper broker adapter — optional mirror fills and contract discovery.

Pipeline role
-------------
When ``settings.alpaca.enabled`` and paper API keys are present, option
opens/closes from ``portfolio`` are mirrored to Alpaca's paper account so fills
appear in the Alpaca dashboard alongside local ``state/portfolio.json``.

Read-only helpers (``probe_option_contracts_for_expiry``, ``fetch_option_latest_quote``)
work whenever credentials exist — even if paper trading is disabled — so
``option_contracts`` can confirm expiries Yahoo omits (e.g. same-day ETF dailies).

Environment
-----------
  ALPACA_API_KEY / ALPACA_SECRET_KEY (or APCA_* aliases) from
  https://app.alpaca.markets → Paper Trading → API Keys.
  ``paper=True`` is forced — never route internship flows to live.

Merge notes for stocks/futures
------------------------------
  - **Reusable pattern:** credential resolution, read-only client for data,
    ``status_line`` for health dashboards.
  - **Options-only:** all ``submit_option_*`` and contract probe/quote helpers.
  - **Stocks fork:** swap option order helpers for equity market orders; keep
    the dual local+broker ledger idea if you want external reconciliation.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union


def alpaca_settings(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return the ``alpaca`` block from settings (empty dict if missing)."""
    return dict((settings or {}).get("alpaca") or {})


def is_alpaca_paper_enabled(settings: Optional[Dict[str, Any]] = None) -> bool:
    """True when Alpaca paper trading is enabled in settings and API keys are present."""
    cfg = alpaca_settings(settings)
    if not bool(cfg.get("enabled", False)):
        return False
    provider = str(cfg.get("provider", "alpaca_paper")).lower().strip()
    if provider not in {"alpaca_paper", "alpaca", "paper"}:
        return False
    key, secret = _credentials(cfg)
    return bool(key and secret)


def _credentials(cfg: Dict[str, Any]) -> tuple[str, str]:
    key_env = str(cfg.get("api_key_env", "ALPACA_API_KEY"))
    secret_env = str(cfg.get("secret_key_env", "ALPACA_SECRET_KEY"))
    key = str(cfg.get("api_key") or os.getenv(key_env) or "").strip()
    secret = str(cfg.get("secret_key") or os.getenv(secret_env) or "").strip()
    return key, secret


def has_alpaca_credentials(settings: Optional[Dict[str, Any]] = None) -> bool:
    """True when API keys are present (paper trading toggle not required)."""
    key, secret = _credentials(alpaca_settings(settings))
    if key and secret:
        return True
    # Also accept default env names when settings block is empty.
    key2 = str(os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID") or "").strip()
    secret2 = str(os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY") or "").strip()
    return bool(key2 and secret2)


def _resolve_credentials(settings: Optional[Dict[str, Any]] = None) -> tuple[str, str]:
    cfg = alpaca_settings(settings)
    key, secret = _credentials(cfg)
    if key and secret:
        return key, secret
    key = str(os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID") or "").strip()
    secret = str(os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY") or "").strip()
    return key, secret


def get_trading_client(settings: Optional[Dict[str, Any]] = None):
    """Return alpaca TradingClient in paper mode, or None."""
    if not is_alpaca_paper_enabled(settings):
        return None
    key, secret = _resolve_credentials(settings)
    try:
        from alpaca.trading.client import TradingClient

        # Force paper endpoint — never route internship flows to live.
        return TradingClient(key, secret, paper=True)
    except Exception as error:
        print(f"[alpaca] Could not create TradingClient: {error}")
        return None


def get_readonly_trading_client(settings: Optional[Dict[str, Any]] = None):
    """Paper TradingClient whenever credentials exist (for contract discovery)."""
    key, secret = _resolve_credentials(settings)
    if not key or not secret:
        return None
    try:
        from alpaca.trading.client import TradingClient

        return TradingClient(key, secret, paper=True)
    except Exception as error:
        print(f"[alpaca] readonly TradingClient failed: {error}")
        return None


def _as_date(value: Union[str, date, datetime, None]) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def fetch_option_contracts_for_expiry(
    ticker: str,
    expiration: Union[str, date],
    *,
    side: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """
    List option contracts for one underlying + expiration via Alpaca.

    Backward-compatible list return. Prefer ``probe_option_contracts_for_expiry``
    when callers need to distinguish API errors from confirmed-empty.
    """
    probe = probe_option_contracts_for_expiry(
        ticker, expiration, side=side, settings=settings, limit=limit
    )
    return list(probe.get("contracts") or [])


def probe_option_contracts_for_expiry(
    ticker: str,
    expiration: Union[str, date],
    *,
    side: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    """
    Probe Alpaca for contracts on one expiry with explicit outcome.

    Returns:
      {
        "ok": bool,                 # True when the API call succeeded
        "contracts": list[dict],
        "outcome": "ok" | "confirmed_empty" | "error" | "no_credentials",
        "error": str | None,
        "error_kind": str | None,   # auth | rate_limit | network | client_init | api | ...
      }
    """
    empty_ok = {
        "ok": True,
        "contracts": [],
        "outcome": "confirmed_empty",
        "error": None,
        "error_kind": None,
    }
    if not has_alpaca_credentials(settings):
        return {
            "ok": False,
            "contracts": [],
            "outcome": "no_credentials",
            "error": "missing ALPACA_API_KEY / ALPACA_SECRET_KEY",
            "error_kind": "no_credentials",
        }

    client = get_readonly_trading_client(settings)
    if client is None:
        return {
            "ok": False,
            "contracts": [],
            "outcome": "error",
            "error": "TradingClient init failed",
            "error_kind": "client_init",
        }

    symbol = ticker.upper().strip()
    exp = _as_date(expiration)
    if not symbol or exp is None:
        return {
            "ok": False,
            "contracts": [],
            "outcome": "error",
            "error": "invalid ticker or expiration",
            "error_kind": "invalid_args",
        }

    try:
        from alpaca.trading.requests import GetOptionContractsRequest

        side_l = str(side or "").lower().strip()
        collected: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        pages = 0
        while pages < 10 and len(collected) < limit:
            kwargs: Dict[str, Any] = {
                "underlying_symbols": [symbol],
                "expiration_date": exp,
                "limit": min(100, limit - len(collected)),
            }
            if page_token:
                kwargs["page_token"] = page_token
            req = GetOptionContractsRequest(**kwargs)
            resp = client.get_option_contracts(req)
            rows = list(getattr(resp, "option_contracts", None) or [])
            for row in rows:
                ctype = str(getattr(row, "type", "") or "").lower()
                row_side = "call" if "call" in ctype else ("put" if "put" in ctype else "")
                if side_l in {"call", "put"} and row_side != side_l:
                    continue
                collected.append(
                    {
                        "symbol": str(getattr(row, "symbol", "") or ""),
                        "strike": float(getattr(row, "strike_price", 0) or 0),
                        "expiration": exp.isoformat(),
                        "side": row_side,
                        "status": str(getattr(row, "status", "") or ""),
                        "open_interest": getattr(row, "open_interest", None),
                        "close_price": getattr(row, "close_price", None),
                    }
                )
            page_token = getattr(resp, "next_page_token", None)
            pages += 1
            if not page_token or not rows:
                break

        if collected:
            return {
                "ok": True,
                "contracts": collected,
                "outcome": "ok",
                "error": None,
                "error_kind": None,
            }
        return empty_ok
    except Exception as error:
        kind = _classify_alpaca_error(error)
        print(f"[alpaca] get_option_contracts failed for {symbol} {exp}: {error} kind={kind}")
        return {
            "ok": False,
            "contracts": [],
            "outcome": "error",
            "error": str(error),
            "error_kind": kind,
        }


def _classify_alpaca_error(error: Exception) -> str:
    text = str(error or "").lower()
    name = type(error).__name__.lower()
    if "401" in text or "403" in text or "unauthorized" in text or "forbidden" in text or "auth" in text:
        return "auth"
    if "429" in text or "rate" in text or "too many" in text:
        return "rate_limit"
    if "timeout" in text or "timed out" in text or "connection" in text or "network" in text:
        return "network"
    if "http" in name or "api" in name:
        return "api"
    return "api"


def has_option_expiry(
    ticker: str,
    expiration: Union[str, date],
    *,
    settings: Optional[Dict[str, Any]] = None,
) -> bool:
    """True when Alpaca lists at least one contract for ticker+expiration."""
    probe = probe_option_contracts_for_expiry(
        ticker, expiration, settings=settings, limit=5
    )
    return bool(probe.get("ok") and probe.get("contracts"))


def fetch_option_latest_quote(
    contract_symbol: str,
    *,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Best-effort bid/ask/last for an OCC symbol via Alpaca options data."""
    key, secret = _resolve_credentials(settings)
    symbol = str(contract_symbol or "").upper().strip()
    if not key or not secret or not symbol:
        return {"bid": 0.0, "ask": 0.0, "last": 0.0}
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.data.requests import OptionLatestQuoteRequest

        client = OptionHistoricalDataClient(key, secret)
        raw = client.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=symbol))
        quote = None
        if isinstance(raw, dict):
            quote = raw.get(symbol)
        else:
            quote = getattr(raw, "get", lambda _k: None)(symbol) if raw is not None else None
            if quote is None and hasattr(raw, "data"):
                quote = (raw.data or {}).get(symbol)
        if quote is None:
            return {"bid": 0.0, "ask": 0.0, "last": 0.0}
        bid = float(getattr(quote, "bid_price", None) or (quote.get("bid_price") if isinstance(quote, dict) else 0) or 0)
        ask = float(getattr(quote, "ask_price", None) or (quote.get("ask_price") if isinstance(quote, dict) else 0) or 0)
        return {"bid": bid, "ask": ask, "last": 0.0}
    except Exception as error:
        print(f"[alpaca] option quote failed for {symbol}: {error}")
        return {"bid": 0.0, "ask": 0.0, "last": 0.0}

def submit_option_market_order(
    *,
    contract_symbol: str,
    qty: int,
    side: str,
    settings: Optional[Dict[str, Any]] = None,
    intent: str = "open",
) -> Dict[str, Any]:
    """
    Submit a single-leg options market order to Alpaca paper.

    side: buy|sell (for long premium: open=buy, close=sell)
    Returns {ok, order_id, status, raw_error, ...}
    """
    symbol = str(contract_symbol or "").upper().strip()
    contracts = int(qty or 0)
    side_l = str(side or "").lower().strip()
    if not symbol or contracts < 1 or side_l not in {"buy", "sell"}:
        return {"ok": False, "error": "invalid_args", "symbol": symbol, "qty": contracts}

    client = get_trading_client(settings)
    if client is None:
        return {"ok": False, "error": "alpaca_disabled_or_unconfigured"}

    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        order_side = OrderSide.BUY if side_l == "buy" else OrderSide.SELL
        req = MarketOrderRequest(
            symbol=symbol,
            qty=contracts,
            side=order_side,
            time_in_force=TimeInForce.DAY,
        )
        order = client.submit_order(req)
        order_id = str(getattr(order, "id", "") or "")
        status = str(getattr(order, "status", "") or "")
        filled_avg = getattr(order, "filled_avg_price", None)
        print(
            f"[alpaca] paper {intent} {side_l.upper()} {contracts}x {symbol} "
            f"order_id={order_id} status={status}"
        )
        return {
            "ok": True,
            "broker": "alpaca_paper",
            "order_id": order_id,
            "status": status,
            "filled_avg_price": float(filled_avg) if filled_avg not in (None, "") else None,
            "symbol": symbol,
            "qty": contracts,
            "side": side_l,
            "intent": intent,
        }
    except Exception as error:
        print(f"[alpaca] order failed ({intent} {side_l} {symbol}): {error}")
        return {
            "ok": False,
            "broker": "alpaca_paper",
            "error": str(error),
            "symbol": symbol,
            "qty": contracts,
            "side": side_l,
            "intent": intent,
        }


def submit_option_open(
    contract_symbol: str,
    qty: int,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Buy-to-open long call/put on Alpaca paper."""
    return submit_option_market_order(
        contract_symbol=contract_symbol,
        qty=qty,
        side="buy",
        settings=settings,
        intent="open",
    )


def submit_option_close(
    contract_symbol: str,
    qty: int,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Sell-to-close long call/put on Alpaca paper."""
    return submit_option_market_order(
        contract_symbol=contract_symbol,
        qty=qty,
        side="sell",
        settings=settings,
        intent="close",
    )


def fetch_account_summary(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Account equity / cash from Alpaca paper (for dashboard proof)."""
    client = get_trading_client(settings)
    if client is None:
        return {"ok": False, "enabled": is_alpaca_paper_enabled(settings)}
    try:
        account = client.get_account()
        return {
            "ok": True,
            "enabled": True,
            "broker": "alpaca_paper",
            "account_number": str(getattr(account, "account_number", "") or ""),
            "status": str(getattr(account, "status", "") or ""),
            "equity": float(getattr(account, "equity", 0) or 0),
            "cash": float(getattr(account, "cash", 0) or 0),
            "buying_power": float(getattr(account, "buying_power", 0) or 0),
            "pattern_day_trader": bool(getattr(account, "pattern_day_trader", False)),
            "options_approved_level": getattr(account, "options_approved_level", None),
        }
    except Exception as error:
        return {"ok": False, "enabled": True, "error": str(error)}


def fetch_option_positions(settings: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Open option positions from Alpaca paper."""
    client = get_trading_client(settings)
    if client is None:
        return []
    try:
        positions = client.get_all_positions()
        out: List[Dict[str, Any]] = []
        for pos in positions or []:
            asset_class = str(getattr(pos, "asset_class", "") or "").lower()
            symbol = str(getattr(pos, "symbol", "") or "")
            # Options OCC symbols are long; equities are short tickers.
            if asset_class and "option" not in asset_class and len(symbol) < 10:
                continue
            if len(symbol) < 10 and asset_class == "us_equity":
                continue
            out.append(
                {
                    "symbol": symbol,
                    "qty": float(getattr(pos, "qty", 0) or 0),
                    "avg_entry_price": float(getattr(pos, "avg_entry_price", 0) or 0),
                    "market_value": float(getattr(pos, "market_value", 0) or 0),
                    "unrealized_pl": float(getattr(pos, "unrealized_pl", 0) or 0),
                    "side": str(getattr(pos, "side", "") or ""),
                    "asset_class": asset_class,
                }
            )
        return out
    except Exception as error:
        print(f"[alpaca] get positions failed: {error}")
        return []


def status_line(settings: Optional[Dict[str, Any]] = None) -> str:
    """One-line Alpaca paper connection summary for console/dashboard health."""
    if not bool(alpaca_settings(settings).get("enabled", False)):
        return "Alpaca paper: OFF (local sim only)"
    if not is_alpaca_paper_enabled(settings):
        return "Alpaca paper: ENABLED but missing ALPACA_API_KEY / ALPACA_SECRET_KEY"
    summary = fetch_account_summary(settings)
    if not summary.get("ok"):
        return f"Alpaca paper: configured but account fetch failed ({summary.get('error', 'unknown')})"
    return (
        f"Alpaca paper: CONNECTED acct={summary.get('account_number')} "
        f"equity=${summary.get('equity', 0):,.0f} cash=${summary.get('cash', 0):,.0f}"
    )
