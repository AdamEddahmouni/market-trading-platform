"""Select ATM option contracts for paper execution and mark-to-market.

Pipeline role
-------------
Bridges underlying tickers to tradable OCC symbols before ``portfolio`` opens
a position:
  - ``lookup_atm_contract`` — full result with explicit miss status codes.
  - ``select_atm_contract`` — convenience wrapper returning contract dict or None.
  - ``fetch_option_mark`` — current premium for exit manager and MTM.

Provider chain: yfinance option chains first; Alpaca probe fallback when Yahoo
omits near-expiry listings (common on ETF 0DTE). DTE window comes from
``market_session.effective_options_*_dte`` and ``options_expiry_horizon``.

Merge notes for stocks/futures
------------------------------
  - **Options-only module** — not needed for pure equity/futures execution.
  - **Reusable idea:** explicit status codes (``no_0dte_chain_exists``,
    ``alpaca_confirmed_empty``) for observability; port the pattern to
    futures roll/contract selection in a larger system.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import yfinance as yf

try:
    from zoneinfo import ZoneInfo

    _ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    _ET = timezone.utc


def _now_et() -> datetime:
    return datetime.now(_ET)


def _calendar_dte(expiry: str, now: Optional[datetime] = None) -> Optional[int]:
    """Days from today (ET calendar) to expiry date. 0 = same-day (0DTE)."""
    try:
        exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
    except ValueError:
        return None
    current = (now or _now_et()).date()
    return (exp_date - current).days


def _mid_price(bid: float, ask: float, last: float) -> tuple[float, bool]:
    """Return (premium, has_nbbo). Prefer bid/ask mid."""
    if bid > 0 and ask > 0:
        return (bid + ask) / 2.0, True
    if last > 0:
        return last, False
    if bid > 0:
        return bid, False
    if ask > 0:
        return ask, False
    return 0.0, False


def _lookup_from_alpaca(
    symbol: str,
    option_side: str,
    spot: float,
    expiry: str,
    *,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Probe Alpaca for nearest-strike contract on one expiry.

    Returns:
      {
        "outcome": "ok" | "confirmed_empty" | "error" | "no_credentials",
        "contract": dict | None,
        "error": str | None,
        "error_kind": str | None,
      }
    """
    try:
        from agent.alpaca_broker import fetch_option_latest_quote, probe_option_contracts_for_expiry
    except Exception as error:
        return {
            "outcome": "error",
            "contract": None,
            "error": f"import_failed: {error}",
            "error_kind": "client_init",
        }

    probe = probe_option_contracts_for_expiry(
        symbol, expiry, side=option_side, settings=settings, limit=500
    )
    outcome = str(probe.get("outcome") or "error")
    if outcome != "ok":
        return {
            "outcome": outcome if outcome in {"confirmed_empty", "error", "no_credentials"} else "error",
            "contract": None,
            "error": probe.get("error"),
            "error_kind": probe.get("error_kind"),
        }

    rows = list(probe.get("contracts") or [])
    if not rows:
        return {
            "outcome": "confirmed_empty",
            "contract": None,
            "error": None,
            "error_kind": None,
        }

    best_row = min(rows, key=lambda r: abs(float(r.get("strike") or 0.0) - spot))
    contract_symbol = str(best_row.get("symbol") or "")
    strike = float(best_row.get("strike") or 0.0)
    if not contract_symbol or strike <= 0:
        return {
            "outcome": "confirmed_empty",
            "contract": None,
            "error": "no usable strike/symbol in Alpaca response",
            "error_kind": None,
        }

    quote = fetch_option_latest_quote(contract_symbol, settings=settings)
    bid = float(quote.get("bid") or 0.0)
    ask = float(quote.get("ask") or 0.0)
    last = float(quote.get("last") or 0.0)
    close = best_row.get("close_price")
    if last <= 0 and close not in (None, ""):
        try:
            last = float(close)
        except Exception:
            last = 0.0
    premium, has_nbbo = _mid_price(bid, ask, last)

    now = _now_et()
    dte = _calendar_dte(expiry, now)
    contract = {
        "contract_symbol": contract_symbol,
        "underlying": symbol,
        "side": option_side,
        "strike": strike,
        "expiration": expiry,
        "premium": round(premium, 4),
        "spot_price": round(spot, 4),
        "dte": int(dte) if dte is not None else 0,
        "bid": bid,
        "ask": ask,
        "last": last,
        "has_nbbo": has_nbbo,
        "quote_as_of": datetime.now(timezone.utc).isoformat(),
        "provider": "alpaca_fallback",
    }
    return {
        "outcome": "ok",
        "contract": contract,
        "error": None,
        "error_kind": None,
    }


def lookup_atm_contract(
    ticker: str,
    side: str,
    spot_price: float,
    max_dte: int = 45,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Pick nearest liquid ATM call or put, with an explicit status for misses.

    Status codes:
      - ok — contract found with usable premium
      - no_options_listed — underlying has no option expiries at all
      - no_0dte_chain_exists — no eligible expiry in the DTE window
      - alpaca_confirmed_empty — Yahoo omitted target; Alpaca API succeeded with zero contracts
      - alpaca_error — Yahoo omitted target; Alpaca auth/rate-limit/network/API failure
      - alpaca_no_credentials — Yahoo omitted target; Alpaca fallback skipped (missing keys)
      - no_quoteable_premium — expiry/strike found but mid/last premium unusable
      - contract_lookup_failed — provider/exception while fetching the chain

    When max_dte == 0 (legacy / same_day), requires today's expiry (0DTE).
    With settings, prefers ``trading.options_expiry_horizon`` (same_day / deadline / range)
    via effective min/max DTE helpers.
    """
    symbol = ticker.upper().strip()
    option_side = side.lower().strip()
    empty: Dict[str, Any] = {
        "contract": None,
        "status": "contract_lookup_failed",
        "detail": "",
        "expiries_seen": [],
        "nearest_listed_dte": None,
        "provider": None,
    }
    if option_side not in {"call", "put"}:
        return {
            **empty,
            "status": "contract_lookup_failed",
            "detail": f"invalid_side={option_side}",
        }

    try:
        from agent.market_session import (
            effective_options_max_dte,
            effective_options_min_dte,
            normalize_options_expiry_horizon,
            resolve_deadline_date_et,
        )

        now = _now_et()
        horizon = "same_day"
        min_dte = 0
        deadline_iso: Optional[str] = None
        # Prefer horizon-aware caps when settings are provided (use same ET clock as DTE).
        if settings is not None:
            horizon = normalize_options_expiry_horizon(settings)
            max_dte = int(effective_options_max_dte(settings, now))
            min_dte = int(effective_options_min_dte(settings, now))
            if horizon == "deadline":
                deadline_iso = resolve_deadline_date_et(settings, now).isoformat()
        else:
            max_dte = int(max_dte)

        stock = yf.Ticker(symbol)
        expiries: List[str] = list(stock.options or [])
        today_et = now.date().isoformat()
        require_0dte = horizon == "same_day" or int(max_dte) == 0
        fetched_at = datetime.now(timezone.utc).isoformat()

        def _expiry_in_window(expiry: str, dte: int) -> bool:
            if require_0dte:
                return dte == 0
            if dte < min_dte or dte > max_dte:
                return False
            if deadline_iso and expiry > deadline_iso:
                return False
            return True

        spot = float(spot_price) if spot_price > 0 else 0.0
        if spot <= 0:
            try:
                spot = float(stock.fast_info.get("lastPrice") or 0.0)
            except Exception:
                spot = 0.0
        if spot <= 0:
            try:
                hist = stock.history(period="1d")
                if hist is not None and not hist.empty:
                    spot = float(hist["Close"].iloc[-1])
            except Exception:
                spot = 0.0

        nearest_listed_dte: Optional[int] = None
        eligible_expiries: List[str] = []
        for expiry in expiries:
            dte = _calendar_dte(expiry, now)
            if dte is None or dte < 0:
                continue
            if nearest_listed_dte is None or dte < nearest_listed_dte:
                nearest_listed_dte = dte
            if _expiry_in_window(expiry, dte):
                eligible_expiries.append(expiry)

        best: Optional[Dict[str, Any]] = None
        saw_in_window = False
        saw_zero_premium = False
        scan_pool = eligible_expiries if eligible_expiries else []
        if not scan_pool and require_0dte:
            scan_pool = [e for e in expiries if _calendar_dte(e, now) == 0]
        elif not scan_pool:
            # Fall back to scanning listed expiries within DTE window for premium attempts.
            for expiry in expiries[:12]:
                dte = _calendar_dte(expiry, now)
                if dte is None or dte < 0:
                    continue
                if not _expiry_in_window(expiry, dte):
                    continue
                scan_pool.append(expiry)

        for expiry in scan_pool[:12]:
            dte = _calendar_dte(expiry, now)
            if dte is None:
                continue
            if not _expiry_in_window(expiry, dte):
                continue
            saw_in_window = True

            chain = stock.option_chain(expiry)
            frame = chain.calls if option_side == "call" else chain.puts
            if frame is None or frame.empty:
                continue

            frame = frame.copy()
            frame["strike_dist"] = (frame["strike"] - spot).abs()
            row = frame.sort_values("strike_dist").iloc[0]
            bid = float(row.get("bid", 0.0) or 0.0)
            ask = float(row.get("ask", 0.0) or 0.0)
            last = float(row.get("lastPrice", 0.0) or 0.0)
            premium, has_nbbo = _mid_price(bid, ask, last)
            if premium <= 0:
                saw_zero_premium = True
                continue

            candidate = {
                "contract_symbol": str(row.get("contractSymbol", "")),
                "underlying": symbol,
                "side": option_side,
                "strike": float(row.get("strike", 0.0)),
                "expiration": expiry,
                "premium": round(premium, 4),
                "spot_price": round(spot, 4),
                "dte": dte,
                "bid": bid,
                "ask": ask,
                "last": last,
                "has_nbbo": has_nbbo,
                "quote_as_of": fetched_at,
                "provider": "yfinance",
            }
            if best is None or candidate["dte"] < best["dte"]:
                best = candidate
                if require_0dte:
                    break

        if best:
            return {
                "contract": best,
                "status": "ok",
                "detail": f"provider=yfinance dte={best.get('dte')} strike={best.get('strike')}",
                "expiries_seen": expiries[:8],
                "nearest_listed_dte": nearest_listed_dte if nearest_listed_dte is not None else 0,
                "provider": "yfinance",
            }

        # Build Alpaca candidate expiry dates within the active horizon window.
        alpaca_dates: List[str] = []
        if require_0dte:
            if today_et not in expiries:
                alpaca_dates = [today_et]
        else:
            # Prefer Yahoo-listed eligible dates missing usable premium, else weekday dates.
            for expiry in eligible_expiries:
                if expiry not in alpaca_dates:
                    alpaca_dates.append(expiry)
            if not alpaca_dates:
                from datetime import timedelta as _td

                cursor = now.date()
                if horizon == "deadline" and deadline_iso:
                    end = date.fromisoformat(deadline_iso)
                else:
                    end = now.date() + _td(days=max(0, int(max_dte)))
                d = cursor
                while d <= end:
                    dte_probe = (d - now.date()).days
                    if d.weekday() < 5 and dte_probe >= min_dte and dte_probe <= max_dte:
                        if not deadline_iso or d.isoformat() <= deadline_iso:
                            alpaca_dates.append(d.isoformat())
                    d = d + _td(days=1)

        if alpaca_dates and spot > 0:
            last_probe: Dict[str, Any] = {}
            for target_exp in alpaca_dates[:6]:
                dte = _calendar_dte(target_exp, now)
                if dte is None or dte < 0:
                    continue
                if not _expiry_in_window(target_exp, dte):
                    continue
                alpaca_probe = _lookup_from_alpaca(
                    symbol, option_side, spot, target_exp, settings=settings
                )
                last_probe = alpaca_probe
                alpaca_outcome = str(alpaca_probe.get("outcome") or "error")
                alpaca_contract = alpaca_probe.get("contract")
                if (
                    alpaca_outcome == "ok"
                    and isinstance(alpaca_contract, dict)
                    and float(alpaca_contract.get("premium") or 0.0) > 0
                ):
                    print(
                        f"[option_contracts] {symbol}: using alpaca_fallback "
                        f"{alpaca_contract.get('contract_symbol')} exp={target_exp}"
                    )
                    return {
                        "contract": alpaca_contract,
                        "status": "ok",
                        "detail": (
                            f"provider=alpaca_fallback dte={alpaca_contract.get('dte')} "
                            f"strike={alpaca_contract.get('strike')}"
                        ),
                        "expiries_seen": ([target_exp] + expiries)[:8],
                        "nearest_listed_dte": int(alpaca_contract.get("dte") or dte or 0),
                        "provider": "alpaca_fallback",
                    }
                if alpaca_outcome in {"error", "no_credentials"}:
                    # Surface credential/API issues without probing every date.
                    break
                # confirmed_empty → try next eligible date
                continue

            if last_probe:
                alpaca_outcome = str(last_probe.get("outcome") or "error")
                nearest_bit = (
                    f"nearest_yf_dte="
                    f"{nearest_listed_dte if nearest_listed_dte is not None else 'none'}"
                )
                if alpaca_outcome == "no_credentials":
                    status = "alpaca_no_credentials"
                    detail = f"alpaca_fallback skipped (no credentials); {nearest_bit}"
                    print(f"[option_contracts] {symbol}: {status} — {detail}")
                    return {
                        "contract": None,
                        "status": status,
                        "detail": detail,
                        "expiries_seen": expiries[:8],
                        "nearest_listed_dte": nearest_listed_dte,
                        "provider": "alpaca_no_credentials",
                    }
                if alpaca_outcome == "error":
                    err = str(last_probe.get("error") or "unknown")
                    kind = str(last_probe.get("error_kind") or "api")
                    status = "alpaca_error"
                    detail = (
                        f"alpaca_error kind={kind}: {err}; {nearest_bit} — "
                        f"NOT confirmed missing eligible expiry"
                    )
                    print(f"[option_contracts] {symbol}: {status} — {detail}")
                    return {
                        "contract": None,
                        "status": status,
                        "detail": detail,
                        "expiries_seen": expiries[:8],
                        "nearest_listed_dte": nearest_listed_dte,
                        "provider": "alpaca_error",
                        "alpaca_error_kind": kind,
                    }
                if alpaca_outcome == "confirmed_empty" and require_0dte:
                    status = "alpaca_confirmed_empty" if expiries else "no_options_listed"
                    detail = f"alpaca_confirmed_empty for today; {nearest_bit}"
                    print(f"[option_contracts] {symbol}: {status} — {detail}")
                    return {
                        "contract": None,
                        "status": status,
                        "detail": detail,
                        "expiries_seen": expiries[:8],
                        "nearest_listed_dte": nearest_listed_dte,
                        "provider": "alpaca_confirmed_empty",
                    }

        if not expiries and not alpaca_dates:
            return {
                "contract": None,
                "status": "no_options_listed",
                "detail": "yfinance returned zero expiries",
                "expiries_seen": [],
                "nearest_listed_dte": None,
                "provider": "yfinance",
            }

        if require_0dte and (nearest_listed_dte is None or nearest_listed_dte != 0):
            return {
                "contract": None,
                "status": "no_0dte_chain_exists",
                "detail": (
                    f"no same-day expiry listed; nearest_dte="
                    f"{nearest_listed_dte if nearest_listed_dte is not None else 'none'}"
                ),
                "expiries_seen": expiries[:8],
                "nearest_listed_dte": nearest_listed_dte,
                "provider": "yfinance",
            }
        if not saw_in_window:
            if horizon == "deadline" and deadline_iso:
                horizon_note = f"no eligible expiry through deadline ({deadline_iso}); "
            elif horizon == "range":
                horizon_note = f"no expiry in dte range [{min_dte}, {max_dte}]; "
            else:
                horizon_note = f"no expiry within max_dte={max_dte}; "
            return {
                "contract": None,
                "status": "no_0dte_chain_exists",
                "detail": (
                    f"{horizon_note}nearest_dte="
                    f"{nearest_listed_dte if nearest_listed_dte is not None else 'none'}"
                ),
                "expiries_seen": expiries[:8],
                "nearest_listed_dte": nearest_listed_dte,
                "provider": "yfinance",
            }
        if saw_zero_premium:
            return {
                "contract": None,
                "status": "no_quoteable_premium",
                "detail": "ATM row found but bid/ask/last premium unusable",
                "expiries_seen": expiries[:8],
                "nearest_listed_dte": nearest_listed_dte,
                "provider": "yfinance",
            }
        return {
            "contract": None,
            "status": "contract_lookup_failed",
            "detail": "expiry in window but option chain frame empty",
            "expiries_seen": expiries[:8],
            "nearest_listed_dte": nearest_listed_dte,
            "provider": "yfinance",
        }
    except Exception as error:
        print(f"[option_contracts] Could not select {option_side} for {symbol}: {error}")
        return {
            "contract": None,
            "status": "contract_lookup_failed",
            "detail": str(error),
            "expiries_seen": [],
            "nearest_listed_dte": None,
            "provider": None,
        }


def select_atm_contract(
    ticker: str,
    side: str,
    spot_price: float,
    max_dte: int = 45,
    settings: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Pick nearest liquid ATM call or put for paper execution.

    When max_dte == 0 (legacy / same_day), requires today's expiry. With settings,
    ``options_expiry_horizon`` (same_day / deadline / range) drives the DTE window.

    Returns contract metadata or None if chain unavailable.
    """
    result = lookup_atm_contract(ticker, side, spot_price, max_dte=max_dte, settings=settings)
    contract = result.get("contract")
    return contract if isinstance(contract, dict) else None


def fetch_option_mark(contract_symbol: str) -> float:
    """Best-effort mark for an OCC option symbol."""
    try:
        from agent.alpaca_broker import fetch_option_latest_quote, has_alpaca_credentials

        if has_alpaca_credentials():
            quote = fetch_option_latest_quote(contract_symbol)
            mid, _ = _mid_price(
                float(quote.get("bid") or 0.0),
                float(quote.get("ask") or 0.0),
                float(quote.get("last") or 0.0),
            )
            if mid > 0:
                return mid
    except Exception:
        pass
    try:
        ticker = yf.Ticker(contract_symbol)
        # Prefer live bid/ask when present.
        try:
            info = ticker.fast_info
            bid = float(info.get("lastBid") or info.get("bid") or 0.0)
            ask = float(info.get("lastAsk") or info.get("ask") or 0.0)
            last = float(info.get("lastPrice") or 0.0)
            mid, _ = _mid_price(bid, ask, last)
            if mid > 0:
                return mid
        except Exception:
            pass
        history = ticker.history(period="1d")
        if history is not None and not history.empty:
            return float(history["Close"].iloc[-1])
        info = ticker.fast_info
        last = info.get("lastPrice")
        return float(last) if last else 0.0
    except Exception:
        return 0.0
