"""Fetch and normalize options chain snapshots from the configured provider.

Purpose
-------
Provider router: returns a ``Snapshot`` with ``data_quality_flags`` instead of
raising on fetch failures.

Features / API role
-------------------
``fetch_options_snapshot(ticker, settings, as_of)`` dispatches to Unusual Whales,
Finviz, replay, yfinance, or ``auto`` (UW then yfinance). yfinance path may
Alpaca-patch same-day 0DTE expiries when the news agent is on ``PYTHONPATH``.

How ``news_momentum_agent`` consumes it
---------------------------------------
Only via ``runner.run_ticker`` → ``options_client.score_ticker``. Agent settings
merge ``chain.provider`` (`auto`, `replay`, etc.) before each batch call.

Options-specific vs reusable
----------------------------
Options-specific: multi-provider chain normalization and 0DTE expiry patching.
Reusable: fail-soft snapshot + flags pattern for any downstream scorer.

``pandas`` / ``yfinance`` are lazy-imported on the yfinance path only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from options_engine.data_models import ContractRow, Snapshot


def _safe_float(value: Any) -> float:
    """Convert value to float safely."""
    import pandas as pd

    try:
        if pd.isna(value):  # type: ignore[arg-type]
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _contract_rows_from_frame(frame: Any, side: str, expiration: str) -> List[ContractRow]:
    """Convert yfinance options frame into normalized rows."""
    rows: List[ContractRow] = []
    if frame is None or frame.empty:
        return rows
    for _, row in frame.iterrows():
        rows.append(
            ContractRow(
                contract_symbol=str(row.get("contractSymbol", "")),
                side=side,
                strike=_safe_float(row.get("strike", 0.0)),
                expiration=expiration,
                implied_volatility=_safe_float(row.get("impliedVolatility", 0.0)),
                volume=_safe_float(row.get("volume", 0.0)),
                open_interest=_safe_float(row.get("openInterest", 0.0)),
                bid=_safe_float(row.get("bid", 0.0)),
                ask=_safe_float(row.get("ask", 0.0)),
                last_price=_safe_float(row.get("lastPrice", 0.0)),
                in_the_money=bool(row.get("inTheMoney", False)),
            )
        )
    return rows


_FINVIZ_FAILURE_FLAGS = {
    "missing_auth_token",
    "invalid_auth_token",
    "fetch_error",
    "empty_chain",
    "client_error",
}


def _snapshot_usable(snapshot: Snapshot) -> bool:
    """True when a snapshot has enough contracts to score."""
    if not snapshot.contracts:
        return False
    flags = {str(flag).lower() for flag in snapshot.data_quality_flags}
    if flags.intersection(_FINVIZ_FAILURE_FLAGS) and len(snapshot.contracts) < 5:
        return False
    return True


def fetch_options_snapshot(ticker: str, settings: Dict[str, Any], as_of: str | None = None) -> Snapshot:
    """
    Fetch options chain snapshot for one ticker using the configured provider.

    Provider ``auto`` order (Finviz Elite is not used — too unreliable):
    1. Unusual Whales (if API token present)
    2. yfinance (free fallback)

    Explicit ``finviz`` is still supported if forced in settings, but auto never
    calls it.

    Returns a normalized Snapshot with data-quality flags instead of raising.
    """
    provider = str(settings.get("chain", {}).get("provider", "yfinance")).lower().strip()
    if provider == "replay":
        from options_engine.replay_provider import fetch_options_snapshot_replay

        return fetch_options_snapshot_replay(ticker=ticker, settings=settings, as_of=as_of)

    if provider in {"unusual_whales", "uw"}:
        from options_engine.unusual_whales_provider import fetch_options_snapshot_unusual_whales

        return fetch_options_snapshot_unusual_whales(ticker=ticker, settings=settings, as_of=as_of)

    if provider == "finviz":
        from options_engine.finviz_provider import fetch_options_snapshot_finviz

        return fetch_options_snapshot_finviz(ticker=ticker, settings=settings, as_of=as_of)

    if provider == "auto":
        from options_engine.unusual_whales_provider import (
            fetch_options_snapshot_unusual_whales,
            has_unusual_whales_token,
        )

        failed_flags: List[str] = []

        if has_unusual_whales_token(settings):
            uw_snapshot = fetch_options_snapshot_unusual_whales(
                ticker=ticker, settings=settings, as_of=as_of
            )
            if _snapshot_usable(uw_snapshot):
                return uw_snapshot
            failed_flags.extend([f"uw_{f}" for f in uw_snapshot.data_quality_flags])

        yf_snapshot = _fetch_options_snapshot_yfinance(ticker=ticker, settings=settings, as_of=as_of)
        for flag in failed_flags:
            if flag not in yf_snapshot.data_quality_flags:
                yf_snapshot.data_quality_flags.append(flag)
        if "provider_fallback_yfinance" not in yf_snapshot.data_quality_flags:
            yf_snapshot.data_quality_flags.append("provider_fallback_yfinance")
        yf_snapshot.provider = "yfinance_fallback"
        return yf_snapshot

    return _fetch_options_snapshot_yfinance(ticker=ticker, settings=settings, as_of=as_of)


def _fetch_options_snapshot_yfinance(ticker: str, settings: Dict[str, Any], as_of: str | None = None) -> Snapshot:
    """Fetch options chain snapshot for one ticker via yfinance.

    When Yahoo omits the ET session's same-day expiry (common for SPY/QQQ
    dailies), merge today's date if Alpaca confirms contracts exist, then try
    yfinance option_chain(today) and/or Alpaca-derived ContractRows.
    """
    import yfinance as yf

    chain_cfg = settings.get("chain", {})
    max_expiries = max(1, int(chain_cfg.get("expiries_to_scan", 2)))
    min_oi = float(chain_cfg.get("min_open_interest", 50))
    min_volume = float(chain_cfg.get("min_contract_volume", 10))
    now_text = as_of or datetime.now(timezone.utc).isoformat()
    normalized_ticker = ticker.upper().strip()
    snapshot = Snapshot(ticker=normalized_ticker, as_of=now_text, spot_price=0.0, provider="yfinance")

    try:
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
    except Exception:
        et = timezone.utc
    try:
        if as_of:
            today_et = datetime.fromisoformat(str(as_of).replace("Z", "+00:00")).astimezone(et).date()
        else:
            today_et = datetime.now(timezone.utc).astimezone(et).date()
    except Exception:
        today_et = datetime.now(timezone.utc).astimezone(et).date()
    today_text = today_et.isoformat()

    try:
        asset = yf.Ticker(normalized_ticker)
        history = asset.history(period="1d", interval="1m")
        if not history.empty:
            snapshot.spot_price = float(history["Close"].iloc[-1])
        else:
            snapshot.data_quality_flags.append("missing_spot_price")
        expirations = list(asset.options or [])
        # Patch Yahoo gap: confirm ET today via Alpaca when missing from list.
        if today_text not in expirations:
            alpaca_today, alpaca_flag = _alpaca_confirm_and_rows(
                normalized_ticker, today_text, spot=float(snapshot.spot_price or 0.0), settings=settings
            )
            if alpaca_flag:
                snapshot.data_quality_flags.append(alpaca_flag)
            if alpaca_today:
                expirations = [today_text] + [e for e in expirations if e != today_text]
                if "expiry_calendar_alpaca_patch" not in snapshot.data_quality_flags:
                    snapshot.data_quality_flags.append("expiry_calendar_alpaca_patch")
                snapshot.contracts.extend(alpaca_today)
        expirations = expirations[:max_expiries]
        snapshot.expirations = expirations
        if not expirations and not snapshot.contracts:
            snapshot.data_quality_flags.append("no_expirations")
            return snapshot
        for expiration in expirations:
            if expiration == today_text and any(c.expiration == today_text for c in snapshot.contracts):
                # Already loaded via Alpaca patch.
                continue
            try:
                chain = asset.option_chain(expiration)
                snapshot.contracts.extend(_contract_rows_from_frame(chain.calls, "call", expiration))
                snapshot.contracts.extend(_contract_rows_from_frame(chain.puts, "put", expiration))
            except Exception:
                if expiration == today_text:
                    # Yahoo cannot serve today's chain even when we know it exists.
                    rows, alpaca_flag = _alpaca_confirm_and_rows(
                        normalized_ticker,
                        today_text,
                        spot=float(snapshot.spot_price or 0.0),
                        settings=settings,
                    )
                    if alpaca_flag and alpaca_flag not in snapshot.data_quality_flags:
                        snapshot.data_quality_flags.append(alpaca_flag)
                    if rows:
                        snapshot.contracts.extend(rows)
                        if "expiry_calendar_alpaca_patch" not in snapshot.data_quality_flags:
                            snapshot.data_quality_flags.append("expiry_calendar_alpaca_patch")
                else:
                    snapshot.data_quality_flags.append(f"chain_fetch_error_{expiration}")
        if not snapshot.contracts:
            snapshot.data_quality_flags.append("empty_chain")
        liquid = [c for c in snapshot.contracts if c.open_interest >= min_oi and c.volume >= min_volume]
        if not liquid:
            snapshot.data_quality_flags.append("illiquid_chain")
        if "expiry_calendar_alpaca_patch" in snapshot.data_quality_flags:
            snapshot.provider = "yfinance+alpaca_expiry_patch"
    except Exception:
        snapshot.data_quality_flags.append("fetch_error")
    return snapshot


def _alpaca_confirm_and_rows(
    ticker: str,
    expiration: str,
    *,
    spot: float,
    settings: Dict[str, Any],
) -> Tuple[List[ContractRow], Optional[str]]:
    """
    Return (ContractRows, quality_flag).

    quality_flag is set when the probe did not successfully find contracts:
      alpaca_confirmed_empty | alpaca_error | alpaca_no_credentials | None
    """
    # Prefer news-agent alpaca helper when importable (same process / path).
    try:
        from agent.alpaca_broker import fetch_option_latest_quote, probe_option_contracts_for_expiry

        probe = probe_option_contracts_for_expiry(ticker, expiration, settings=None, limit=400)
        outcome = str(probe.get("outcome") or "error")
        rows_raw = list(probe.get("contracts") or [])
        if outcome == "no_credentials":
            return [], "alpaca_no_credentials"
        if outcome == "error":
            kind = str(probe.get("error_kind") or "api")
            return [], f"alpaca_error_{kind}"
        if outcome == "confirmed_empty" or not rows_raw:
            return [], "alpaca_confirmed_empty"

        out: List[ContractRow] = []
        # Cap rows around ATM to keep feature calc cheap.
        if spot > 0:
            rows_raw = sorted(rows_raw, key=lambda r: abs(float(r.get("strike") or 0) - spot))[:80]
        for row in rows_raw:
            side = str(row.get("side") or "")
            if side not in {"call", "put"}:
                continue
            sym = str(row.get("symbol") or "")
            strike = float(row.get("strike") or 0.0)
            bid = ask = last = 0.0
            if sym:
                q = fetch_option_latest_quote(sym, settings=None)
                bid = float(q.get("bid") or 0.0)
                ask = float(q.get("ask") or 0.0)
                last = float(q.get("last") or 0.0)
            oi = row.get("open_interest")
            try:
                oi_f = float(oi) if oi not in (None, "") else 0.0
            except Exception:
                oi_f = 0.0
            out.append(
                ContractRow(
                    contract_symbol=sym,
                    side=side,
                    strike=strike,
                    expiration=expiration,
                    implied_volatility=0.0,
                    volume=0.0,
                    open_interest=oi_f,
                    bid=bid,
                    ask=ask,
                    last_price=last,
                    in_the_money=(strike <= spot) if side == "call" else (strike >= spot),
                )
            )
        return out, None
    except Exception:
        pass

    # Standalone Alpaca call when news-agent package is not on path.
    try:
        import os

        key = str(os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID") or "").strip()
        secret = str(os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY") or "").strip()
        if not key or not secret:
            return [], "alpaca_no_credentials"
        from datetime import date as date_cls

        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetOptionContractsRequest

        client = TradingClient(key, secret, paper=True)
        exp = date_cls.fromisoformat(expiration)
        resp = client.get_option_contracts(
            GetOptionContractsRequest(underlying_symbols=[ticker], expiration_date=exp, limit=100)
        )
        rows = list(getattr(resp, "option_contracts", None) or [])
        if not rows:
            return [], "alpaca_confirmed_empty"
        out = []
        for row in rows[:80]:
            ctype = str(getattr(row, "type", "") or "").lower()
            side = "call" if "call" in ctype else ("put" if "put" in ctype else "")
            if side not in {"call", "put"}:
                continue
            strike = float(getattr(row, "strike_price", 0) or 0)
            out.append(
                ContractRow(
                    contract_symbol=str(getattr(row, "symbol", "") or ""),
                    side=side,
                    strike=strike,
                    expiration=expiration,
                    implied_volatility=0.0,
                    volume=0.0,
                    open_interest=0.0,
                    bid=0.0,
                    ask=0.0,
                    last_price=0.0,
                    in_the_money=False,
                )
            )
        return out, None
    except Exception as error:
        text = str(error or "").lower()
        if "429" in text or "rate" in text:
            return [], "alpaca_error_rate_limit"
        if "401" in text or "403" in text or "auth" in text:
            return [], "alpaca_error_auth"
        return [], "alpaca_error_api"

