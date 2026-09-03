"""Local paper portfolio: executes BUY/SELL decisions into simulated positions.

Pipeline role
-------------
Sits at the **execution tail** of the news-momentum agent. ``decision_engine``
and ``odte_decision`` emit BUY/SELL/REVIEW/LOG; ``paper_trader`` logs every
decision; this module turns approved BUY/SELL into fills when ``auto_execute``
is on (or when ``force=True`` from Telegram/dashboard approvals).

Supports two instrument modes via ``settings.trading.instrument``:
  - **stock** — long/short equity shares (reusable in a stocks/futures fork).
  - **options** / **auto** — long ATM calls (BUY) or puts (SELL) via
    ``execute_options_decision``; options-specific sizing, flip guards, and
    exit manager live here.

State files (under ``state/``)
------------------------------
  - ``portfolio.json`` — cash, positions, realized PnL, equity history.
  - ``executions.json`` — append-only fill ledger (opens/closes).
  - Reads ``eod_flattened.json`` (via ``eod_flatten_state``) on startup reconcile.
  - Writes through ``risk_manager.record_realized_pnl`` on closes.

Merge notes for stocks/futures
------------------------------
  - **Reusable:** ``load_portfolio`` / ``save_portfolio``, equity math
    (``compute_equity``, ``compute_unrealized``), stock path in
    ``execute_decision``, ``portfolio_summary``, ``refresh_portfolio_prices``.
  - **Options-only:** ``execute_options_decision``, ``manage_option_exits``,
    ``evaluate_option_exit_rule``, contract marks via ``option_contracts``,
    flip integration (``flip_guard``), Alpaca mirror orders.
  - **Futures fork:** replace stock qty sizing with contract multipliers;
    drop or stub options branches; keep JSON state pattern and execution ledger.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.paper_trader import fetch_price_at_signal
from agent.option_contracts import fetch_option_mark, select_atm_contract

OPTION_MULTIPLIER = 100


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
PORTFOLIO_PATH = STATE_DIR / "portfolio.json"
EXECUTIONS_PATH = STATE_DIR / "executions.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, payload: Any) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(path)


def default_portfolio(starting_cash: float) -> Dict[str, Any]:
    """Return a fresh portfolio dict with empty positions and equity history."""
    return {
        "starting_cash": float(starting_cash),
        "cash": float(starting_cash),
        "realized_pnl": 0.0,
        "positions": {},
        "equity_history": [],
        "updated_at": _now_iso(),
    }


def load_portfolio(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Load ``state/portfolio.json`` or initialize from ``trading.starting_cash``."""
    trading = settings.get("trading", {})
    starting = float(trading.get("starting_cash", 100000))
    data = _load_json(PORTFOLIO_PATH, default_portfolio(starting))
    if not isinstance(data, dict):
        return default_portfolio(starting)
    data.setdefault("positions", {})
    data.setdefault("equity_history", [])
    return data


def save_portfolio(portfolio: Dict[str, Any]) -> None:
    """Persist portfolio to ``state/portfolio.json`` with an updated timestamp."""
    portfolio["updated_at"] = _now_iso()
    _save_json(PORTFOLIO_PATH, portfolio)


def load_executions() -> List[Dict[str, Any]]:
    """Load the append-only execution ledger from ``state/executions.json``."""
    data = _load_json(EXECUTIONS_PATH, [])
    return data if isinstance(data, list) else []


def append_execution(fill: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> None:
    """Append one open/close fill dict to ``state/executions.json``."""
    enriched = dict(fill)
    if "bid" not in enriched and "ask" not in enriched:
        contract_symbol = (
            str(enriched.get("contract_symbol") or "")
            if str(enriched.get("instrument_type", "")).lower() == "option"
            else None
        )
        quote = _nbbo_snapshot(
            str(enriched.get("ticker") or ""),
            contract_symbol=contract_symbol or None,
            settings=settings,
        )
        _attach_nbbo(enriched, quote)
    rows = load_executions()
    rows.append(enriched)
    _save_json(EXECUTIONS_PATH, rows)


def compute_equity(portfolio: Dict[str, Any], prices: Dict[str, float]) -> float:
    """Return mark-to-market equity (cash + stock qty × mark + option contracts × 100 × mark)."""
    equity = float(portfolio.get("cash", 0.0))
    positions = portfolio.get("positions", {})
    if not isinstance(positions, dict):
        return equity
    for key, pos in positions.items():
        if not isinstance(pos, dict):
            continue
        instrument = str(pos.get("instrument_type", "stock")).lower()
        if instrument == "option":
            contracts = float(pos.get("contracts", 0.0))
            mark = float(
                prices.get(str(pos.get("contract_symbol", key)), pos.get("mark_price", pos.get("entry_price", 0.0)))
                or 0.0
            )
            equity += contracts * mark * OPTION_MULTIPLIER
            continue
        qty = float(pos.get("qty", 0.0))
        mark = float(prices.get(key, pos.get("mark_price", pos.get("entry_price", 0.0))) or 0.0)
        equity += qty * mark
    return equity


def compute_unrealized(portfolio: Dict[str, Any], prices: Dict[str, float]) -> float:
    """Sum unrealized PnL across all open positions using supplied marks."""
    total = 0.0
    for key, pos in portfolio.get("positions", {}).items():
        if not isinstance(pos, dict):
            continue
        instrument = str(pos.get("instrument_type", "stock")).lower()
        if instrument == "option":
            contracts = float(pos.get("contracts", 0.0))
            entry = float(pos.get("entry_price", 0.0))
            mark = float(
                prices.get(str(pos.get("contract_symbol", key)), pos.get("mark_price", entry)) or entry
            )
            total += contracts * (mark - entry) * OPTION_MULTIPLIER
            continue
        qty = float(pos.get("qty", 0.0))
        entry = float(pos.get("entry_price", 0.0))
        mark = float(prices.get(key, pos.get("mark_price", entry)) or entry)
        total += qty * (mark - entry)
    return total


def _position_sign(pos: Optional[Dict[str, Any]]) -> int:
    if not isinstance(pos, dict):
        return 0
    qty = float(pos.get("qty", 0.0))
    if qty > 0:
        return 1
    if qty < 0:
        return -1
    return 0


def _size_qty(equity: float, price: float, max_positions: int, open_count: int) -> int:
    if price <= 0 or open_count >= max_positions:
        return 0
    alloc = equity / max(1, max_positions)
    qty = int(math.floor(alloc / price))
    return max(1, qty) if qty >= 1 else 0


def _close_position(portfolio: Dict[str, Any], ticker: str, price: float, reason: str) -> Optional[Dict[str, Any]]:
    positions = portfolio.setdefault("positions", {})
    pos = positions.get(ticker)
    if not isinstance(pos, dict):
        return None
    qty = float(pos.get("qty", 0.0))
    if qty == 0:
        positions.pop(ticker, None)
        return None
    entry = float(pos.get("entry_price", 0.0))
    realized = qty * (price - entry)
    portfolio["cash"] = float(portfolio.get("cash", 0.0)) + qty * price
    portfolio["realized_pnl"] = float(portfolio.get("realized_pnl", 0.0)) + realized
    fill = {
        "timestamp": _now_iso(),
        "ticker": ticker,
        "instrument_type": "stock",
        "action": "close",
        "side": "long" if qty > 0 else "short",
        "qty": abs(qty),
        "price": round(price, 4),
        "realized_pnl": round(realized, 2),
        "reason": reason,
    }
    positions.pop(ticker, None)
    return fill


def _open_position(
    portfolio: Dict[str, Any],
    ticker: str,
    side_sign: int,
    price: float,
    qty: int,
    reason: str,
) -> Optional[Dict[str, Any]]:
    if side_sign == 0 or qty <= 0 or price <= 0:
        return None
    signed_qty = qty if side_sign > 0 else -qty
    cost = signed_qty * price
    cash = float(portfolio.get("cash", 0.0))
    if side_sign > 0 and cash < cost:
        qty = int(math.floor(cash / price))
        if qty < 1:
            return None
        signed_qty = qty
        cost = signed_qty * price
    portfolio["cash"] = cash - cost
    portfolio.setdefault("positions", {})[ticker] = {
        "instrument_type": "stock",
        "qty": signed_qty,
        "entry_price": price,
        "mark_price": price,
        "side": "long" if signed_qty > 0 else "short",
        "opened_at": _now_iso(),
    }
    return {
        "timestamp": _now_iso(),
        "ticker": ticker,
        "instrument_type": "stock",
        "action": "open",
        "side": "long" if signed_qty > 0 else "short",
        "qty": abs(signed_qty),
        "price": round(price, 4),
        "realized_pnl": 0.0,
        "reason": reason,
    }


def decision_to_side(decision: str, settings: Dict[str, Any]) -> int:
    """Map BUY/SELL to desired position sign."""
    decision_u = decision.upper().strip()
    allow_short = bool(settings.get("trading", {}).get("allow_short", True))
    if decision_u == "BUY":
        return 1
    if decision_u == "SELL":
        return -1 if allow_short else 0
    return 0


def _size_option_contracts(equity: float, premium: float, max_positions: int, open_count: int) -> int:
    if premium <= 0 or open_count >= max_positions:
        return 0
    alloc = equity / max(1, max_positions)
    cost_per_contract = premium * OPTION_MULTIPLIER
    contracts = int(math.floor(alloc / cost_per_contract))
    return max(1, contracts) if contracts >= 1 else 0


def _attach_broker_result(fill: Dict[str, Any], broker_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(fill, dict):
        return fill
    if not broker_result:
        fill["broker"] = "local"
        return fill
    fill["broker"] = str(broker_result.get("broker") or "alpaca_paper")
    fill["broker_ok"] = bool(broker_result.get("ok"))
    if broker_result.get("order_id"):
        fill["broker_order_id"] = broker_result.get("order_id")
    if broker_result.get("status"):
        fill["broker_status"] = broker_result.get("status")
    if broker_result.get("filled_avg_price") is not None:
        fill["broker_fill_price"] = broker_result.get("filled_avg_price")
    if broker_result.get("error"):
        fill["broker_error"] = broker_result.get("error")
    return fill


def _nbbo_snapshot(
    symbol: str,
    *,
    contract_symbol: str | None = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Best-effort bid/ask/last snapshot at execution time."""
    if contract_symbol:
        try:
            from agent.alpaca_broker import fetch_option_latest_quote

            quote = fetch_option_latest_quote(contract_symbol, settings=settings)
            return {
                "bid": float(quote.get("bid") or 0.0),
                "ask": float(quote.get("ask") or 0.0),
                "last": float(quote.get("last") or 0.0),
            }
        except Exception:
            pass
    ticker = str(symbol or "").upper().strip()
    if not ticker:
        return {"bid": 0.0, "ask": 0.0, "last": 0.0}
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).fast_info
        bid = float(info.get("bid") or info.get("lastPrice") or 0.0)
        ask = float(info.get("ask") or info.get("lastPrice") or 0.0)
        last = float(info.get("lastPrice") or 0.0)
        return {"bid": bid, "ask": ask, "last": last}
    except Exception:
        return {"bid": 0.0, "ask": 0.0, "last": 0.0}


def _attach_nbbo(fill: Dict[str, Any], quote: Dict[str, float]) -> Dict[str, Any]:
    if quote.get("bid"):
        fill["bid"] = round(float(quote["bid"]), 4)
    if quote.get("ask"):
        fill["ask"] = round(float(quote["ask"]), 4)
    if quote.get("last"):
        fill["last"] = round(float(quote["last"]), 4)
    return fill


def _maybe_alpaca_open(contract_symbol: str, contracts: int, settings: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    try:
        from agent.alpaca_broker import is_alpaca_paper_enabled, submit_option_open

        if not is_alpaca_paper_enabled(settings):
            return None
        result = submit_option_open(contract_symbol, contracts, settings)
        cfg = (settings or {}).get("alpaca") or {}
        if not result.get("ok") and bool(cfg.get("require_broker_ack", False)):
            return result
        return result
    except Exception as error:
        print(f"[portfolio] Alpaca open mirror failed: {error}")
        return {"ok": False, "error": str(error), "broker": "alpaca_paper"}


def _maybe_alpaca_close(contract_symbol: str, contracts: int, settings: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    try:
        from agent.alpaca_broker import is_alpaca_paper_enabled, submit_option_close

        if not is_alpaca_paper_enabled(settings):
            return None
        return submit_option_close(contract_symbol, contracts, settings)
    except Exception as error:
        print(f"[portfolio] Alpaca close mirror failed: {error}")
        return {"ok": False, "error": str(error), "broker": "alpaca_paper"}


def _close_option_position(
    portfolio: Dict[str, Any],
    position_key: str,
    mark_premium: float,
    reason: str,
    settings: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    positions = portfolio.setdefault("positions", {})
    pos = positions.get(position_key)
    if not isinstance(pos, dict):
        return None
    contracts = float(pos.get("contracts", 0.0))
    if contracts <= 0:
        positions.pop(position_key, None)
        return None
    entry = float(pos.get("entry_price", 0.0))
    realized = contracts * (mark_premium - entry) * OPTION_MULTIPLIER
    portfolio["cash"] = float(portfolio.get("cash", 0.0)) + contracts * mark_premium * OPTION_MULTIPLIER
    portfolio["realized_pnl"] = float(portfolio.get("realized_pnl", 0.0)) + realized
    try:
        from agent.risk_manager import record_realized_pnl

        record_realized_pnl(
            realized,
            settings={
                "trading": {"starting_cash": float(portfolio.get("starting_cash", 100000))},
                "risk": {},
            },
        )
    except Exception:
        pass
    contract_symbol = str(pos.get("contract_symbol", position_key))
    broker_result = _maybe_alpaca_close(contract_symbol, int(contracts), settings)
    cfg = (settings or {}).get("alpaca") or {}
    if (
        broker_result is not None
        and not broker_result.get("ok")
        and bool(cfg.get("require_broker_ack", False))
    ):
        # Roll back local close if broker ack required and failed.
        portfolio["cash"] = float(portfolio.get("cash", 0.0)) - contracts * mark_premium * OPTION_MULTIPLIER
        portfolio["realized_pnl"] = float(portfolio.get("realized_pnl", 0.0)) - realized
        print(f"[portfolio] Alpaca close rejected — local close aborted for {contract_symbol}")
        return None

    fill = {
        "timestamp": _now_iso(),
        "ticker": str(pos.get("underlying", position_key)),
        "instrument_type": "option",
        "contract_symbol": contract_symbol,
        "action": "close",
        "side": str(pos.get("side", "call")),
        "contracts": int(contracts),
        "price": round(mark_premium, 4),
        "realized_pnl": round(realized, 2),
        "reason": reason,
    }
    try:
        from agent.pattern_learner import record_calibration_outcome_for_close

        record_calibration_outcome_for_close(
            ticker=str(fill["ticker"]),
            realized_pnl=float(fill["realized_pnl"]),
            exit_reason=str(reason),
            contract_symbol=contract_symbol,
            closed_at=str(fill["timestamp"]),
        )
    except Exception:
        pass
    fill = _attach_broker_result(fill, broker_result)
    if broker_result and broker_result.get("order_id"):
        # Keep trail of last Alpaca order on the closed position metadata before pop.
        pass
    positions.pop(position_key, None)
    return fill


def _open_option_position(
    portfolio: Dict[str, Any],
    contract: Dict[str, Any],
    contracts: int,
    reason: str,
    settings: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    premium = float(contract.get("premium", 0.0))
    if premium <= 0 or contracts <= 0:
        return None
    cost = contracts * premium * OPTION_MULTIPLIER
    cash = float(portfolio.get("cash", 0.0))
    if cash < cost:
        contracts = int(math.floor(cash / (premium * OPTION_MULTIPLIER)))
        if contracts < 1:
            return None
        cost = contracts * premium * OPTION_MULTIPLIER
    contract_symbol = str(contract.get("contract_symbol", ""))
    if not contract_symbol:
        return None

    broker_result = _maybe_alpaca_open(contract_symbol, contracts, settings)
    cfg = (settings or {}).get("alpaca") or {}
    if (
        broker_result is not None
        and not broker_result.get("ok")
        and bool(cfg.get("require_broker_ack", False))
    ):
        print(f"[portfolio] Alpaca open rejected — local open aborted for {contract_symbol}")
        return None

    # Prefer Alpaca fill price when present (more “official” mark).
    if broker_result and broker_result.get("filled_avg_price"):
        try:
            premium = float(broker_result["filled_avg_price"])
            cost = contracts * premium * OPTION_MULTIPLIER
        except (TypeError, ValueError):
            pass

    portfolio["cash"] = cash - cost
    pos_payload = {
        "instrument_type": "option",
        "underlying": str(contract.get("underlying", "")),
        "contract_symbol": contract_symbol,
        "side": str(contract.get("side", "call")),
        "contracts": contracts,
        "entry_price": premium,
        "mark_price": premium,
        "strike": float(contract.get("strike", 0.0)),
        "expiration": str(contract.get("expiration", "")),
        "opened_at": _now_iso(),
    }
    if broker_result and broker_result.get("order_id"):
        pos_payload["broker"] = "alpaca_paper"
        pos_payload["broker_order_id"] = broker_result.get("order_id")
    portfolio.setdefault("positions", {})[contract_symbol] = pos_payload
    fill = {
        "timestamp": _now_iso(),
        "ticker": str(contract.get("underlying", "")),
        "instrument_type": "option",
        "contract_symbol": contract_symbol,
        "action": "open",
        "side": str(contract.get("side", "call")),
        "contracts": contracts,
        "price": round(premium, 4),
        "realized_pnl": 0.0,
        "reason": reason,
    }
    return _attach_broker_result(fill, broker_result)


def _find_option_positions_for_underlying(portfolio: Dict[str, Any], underlying: str) -> List[str]:
    keys: List[str] = []
    for key, pos in portfolio.get("positions", {}).items():
        if isinstance(pos, dict) and str(pos.get("instrument_type", "")).lower() == "option":
            if str(pos.get("underlying", "")).upper() == underlying.upper():
                keys.append(str(key))
    return keys


def _now_et(now_et: datetime | None = None) -> datetime:
    from agent.market_session import now_et as _session_now

    return _session_now(now_et)


def _is_regular_trading_hours_et(now_et: datetime | None = None) -> bool:
    from agent.market_session import is_equity_rth

    return is_equity_rth(now_et)


def _past_eod_flatten_et(settings: Dict[str, Any], now_et: datetime | None = None) -> bool:
    from agent.market_session import is_past_eod_flatten

    return is_past_eod_flatten(settings, now_et)


def execute_options_decision(
    ticker: str,
    decision: str,
    price: float,
    reason: str,
    settings: Dict[str, Any],
    option_side: str | None = None,
    now_et: datetime | None = None,
    signal_confidence: float | None = None,
) -> Optional[Dict[str, Any]]:
    """Paper-buy ATM calls on BUY and ATM puts on SELL (or explicit side).

    Same-side reaffirm → hold (no Telegram churn).
    Opposite-side signal → close only when flip guards pass (no same-turn reverse open).
    """
    trading = settings.get("trading", {})
    decision_u = decision.upper().strip()
    if decision_u not in {"BUY", "SELL"}:
        return None

    # Refuse opens until startup reconcile completes (paper safety).
    if not bool((settings.get("_runtime") or {}).get("portfolio_reconciled", True)):
        print(f"[portfolio] Skip {ticker} {decision_u}: portfolio not reconciled yet")
        return {
            "fills": [],
            "action": "not_reconciled",
            "reason": "startup_reconcile",
            "decision_reason_code": "not_reconciled",
        }

    symbol = ticker.upper().strip()
    spot = float(price) if price > 0 else fetch_price_at_signal(symbol)
    if spot <= 0:
        print(f"[portfolio] Skipping options {decision_u} for {symbol}: no spot price")
        return None

    side = str(option_side or ("call" if decision_u == "BUY" else "put")).lower().strip()
    if side not in {"call", "put"}:
        side = "call" if decision_u == "BUY" else "put"
    option_side = side
    from agent.market_session import effective_options_max_dte

    max_dte = int(effective_options_max_dte(settings))

    portfolio = load_portfolio(settings)
    fills: List[Dict[str, Any]] = []
    existing_keys = _find_option_positions_for_underlying(portfolio, symbol)

    exec_cfg = settings.get("execution") or {}
    exit_on_signal_flip = bool(exec_cfg.get("exit_on_signal_flip", False))
    conf = signal_confidence
    if conf is None:
        conf = float(exec_cfg.get("default_signal_confidence", 50))

    if existing_keys:
        from agent.flip_guard import append_flip_audit, evaluate_flip_close, record_flip_close

        same_side_keys: List[str] = []
        opposite_keys: List[str] = []
        for key in existing_keys:
            pos = portfolio.get("positions", {}).get(key, {})
            open_side = str(pos.get("side") or pos.get("option_side") or "").lower().strip()
            if open_side == option_side:
                same_side_keys.append(key)
            else:
                opposite_keys.append(key)

        if same_side_keys and not opposite_keys:
            print(f"[portfolio] Hold {symbol} {option_side}: same-side signal (no flip)")
            return {
                "fills": [],
                "ticker": symbol,
                "decision": decision_u,
                "instrument_type": "option",
                "action": "hold",
                "option_side": option_side,
                "contracts": 0,
                "decision_reason_code": "same_side_hold",
            }

        # Opposite signal path — apply anti-churn guards.
        primary_key = opposite_keys[0] if opposite_keys else existing_keys[0]
        primary_pos = portfolio.get("positions", {}).get(primary_key, {})
        allowed, flip_reason, flip_details = evaluate_flip_close(
            ticker=symbol,
            position=primary_pos if isinstance(primary_pos, dict) else {},
            settings=settings,
            signal_confidence=conf,
        )
        append_flip_audit(
            {
                "ticker": symbol,
                "decision": decision_u,
                "option_side": option_side,
                "flip_decision": flip_details.get("flip_decision"),
                "reason": flip_reason,
                "details": flip_details,
            }
        )
        if not allowed:
            print(
                f"[portfolio] Flip suppressed {symbol}: {flip_reason} "
                f"(decision={flip_details.get('flip_decision')})"
            )
            return {
                "fills": [],
                "ticker": symbol,
                "decision": decision_u,
                "instrument_type": "option",
                "action": "hold",
                "option_side": option_side,
                "contracts": 0,
                "flip_decision": "suppressed",
                "flip_reason": flip_reason,
                "decision_reason_code": f"flip_suppressed_{flip_reason}",
            }

        if not exit_on_signal_flip:
            # Defensive: evaluate_flip_close already returns flip_disabled.
            return {
                "fills": [],
                "ticker": symbol,
                "decision": decision_u,
                "instrument_type": "option",
                "action": "hold",
                "option_side": option_side,
                "contracts": 0,
                "flip_decision": "suppressed",
                "flip_reason": "flip_disabled",
                "decision_reason_code": "flip_suppressed_flip_disabled",
            }

        for key in existing_keys:
            pos = portfolio.get("positions", {}).get(key, {})
            closed_side = str(pos.get("side") or "call")
            mark = fetch_option_mark(str(pos.get("contract_symbol", key))) or float(
                pos.get("mark_price", pos.get("entry_price", 0.0)) or 0.0
            )
            fill = _close_option_position(
                portfolio, key, mark, reason="signal_flip", settings=settings
            )
            if fill:
                fill["flip_decision"] = "accepted"
                fill["flip_reason"] = "accepted"
                fills.append(fill)
                append_execution(fill, settings)
                record_flip_close(symbol, closed_side, settings)
                try:
                    from agent.telegram_notifier import notify_option_exit

                    notify_option_exit(fill, settings)
                except Exception as error:
                    print(f"[portfolio] Telegram exit notify failed: {error}")
        prices_close = {
            str(f.get("contract_symbol", "")): float(f.get("price", 0.0))
            for f in fills
            if f.get("contract_symbol")
        }
        _record_equity_snapshot(portfolio, prices_close, note=f"close_option_{decision_u.lower()}_{symbol}")
        save_portfolio(portfolio)
        return {
            "fills": fills,
            "ticker": symbol,
            "decision": decision_u,
            "instrument_type": "option",
            "action": "close_only",
            "contracts": 0,
            "flip_decision": "accepted",
            "flip_reason": "accepted",
            "decision_reason_code": "signal_flip",
        }

    # New opens: only while listed options are live, and before eod_flatten.
    from agent.market_session import is_options_entry_allowed, is_options_session_open
    from agent.flip_guard import evaluate_opposite_reentry

    if not is_options_session_open(settings, now_et):
        print(f"[portfolio] Skip new options open {symbol} {decision_u}: options market closed")
        return {
            "fills": [],
            "action": "outside_rth",
            "reason": "options_market_closed",
            "decision_reason_code": "outside_rth",
        }
    if not is_options_entry_allowed(settings, now_et):
        print(f"[portfolio] Skip new options open {symbol} {decision_u}: past eod_flatten")
        return {
            "fills": [],
            "action": "past_eod",
            "reason": "eod_flatten_window",
            "decision_reason_code": "past_eod",
        }

    reentry_ok, reentry_reason, reentry_details = evaluate_opposite_reentry(
        ticker=symbol,
        option_side=option_side,
        settings=settings,
        signal_confidence=conf,
    )
    if not reentry_ok:
        print(f"[portfolio] Flip re-entry blocked {symbol} {option_side}: {reentry_reason}")
        return {
            "fills": [],
            "action": "flip_reentry_blocked",
            "reason": reentry_reason,
            "details": reentry_details,
            "decision_reason_code": "flip_reentry_cooldown",
        }

    try:
        from agent.risk_manager import check_new_trade_allowed

        allowed, risk_reason, risk_details = check_new_trade_allowed(
            ticker=symbol,
            decision=decision_u,
            portfolio=portfolio,
            settings=settings,
            option_side=option_side,
        )
        if not allowed:
            print(f"[portfolio] Risk block {symbol} {decision_u}: {risk_reason} ({risk_details})")
            return {
                "fills": [],
                "action": "risk_blocked",
                "reason": risk_reason,
                "risk": risk_details,
                "decision_reason_code": "risk_blocked",
            }
    except Exception as error:
        print(f"[portfolio] Risk manager error (continuing cautiously): {error}")

    contract = select_atm_contract(symbol, option_side, spot, max_dte=max_dte, settings=settings)
    if not contract:
        print(f"[portfolio] Skipping options {decision_u} for {symbol}: no liquid {option_side} chain")
        return {
            "fills": [],
            "action": "no_contract",
            "reason": "no_liquid_chain",
            "decision_reason_code": "no_contract",
        }

    from agent.quote_sanity import check_and_record_quote

    contract_symbol = str(contract["contract_symbol"])
    premium = float(contract["premium"])
    has_nbbo = bool(contract.get("has_nbbo"))
    quote_ok, quote_reason, quote_details = check_and_record_quote(
        symbol,
        contract_symbol,
        premium,
        settings=settings,
        has_nbbo=has_nbbo,
    )
    if not quote_ok:
        print(f"[portfolio] Quote rejected {symbol} {contract_symbol}: {quote_reason} ({quote_details})")
        return {
            "fills": [],
            "action": "quote_rejected",
            "reason": quote_reason,
            "details": quote_details,
            "decision_reason_code": quote_reason,
        }

    max_positions = max(1, int(trading.get("max_positions", 10)))
    prices = {contract_symbol: premium}
    equity = compute_equity(portfolio, prices)
    open_count = len(portfolio.get("positions", {}))
    risk_cfg = settings.get("risk") or {}
    if bool(risk_cfg.get("enabled", True)) and float(risk_cfg.get("risk_fraction_per_trade", 0) or 0) > 0:
        from agent.risk_manager import fixed_fractional_contracts

        exits = trading.get("options_exits") or {}
        contracts = fixed_fractional_contracts(
            equity=equity,
            premium=premium,
            risk_fraction=float(risk_cfg.get("risk_fraction_per_trade", 0.01)),
            stop_loss_pct=float(exits.get("stop_loss_pct", 0.30)),
            max_contracts=int(risk_cfg.get("max_contracts_per_trade", 20)),
        )
        try:
            dte = int(contract.get("dte") if contract.get("dte") is not None else -1)
        except (TypeError, ValueError):
            dte = -1
        if dte < 0:
            from agent.market_session import now_et

            exp = str(contract.get("expiration") or "")
            today_iso = now_et().date().isoformat()
            dte = 1 if exp and exp > today_iso else 0
        overnight_mult = float(risk_cfg.get("overnight_size_mult", 1.0) or 1.0)
        if dte > 0 and 0 < overnight_mult < 1.0:
            contracts = max(0, int(contracts * overnight_mult))
        if contracts <= 0:
            print(f"[portfolio] Risk sizing produced 0 contracts for {symbol}")
            return {
                "fills": [],
                "action": "size_zero",
                "reason": "fixed_fractional_zero",
                "decision_reason_code": "size_zero",
            }
    else:
        contracts = _size_option_contracts(equity, premium, max_positions, open_count)
    fill = _open_option_position(
        portfolio,
        contract,
        contracts,
        reason=reason or f"options_{decision_u.lower()}",
        settings=settings,
    )
    if fill:
        fills.append(fill)
        append_execution(fill, settings)
        try:
            from agent.risk_manager import record_new_entry

            record_new_entry(symbol, settings)
        except Exception:
            pass

    _record_equity_snapshot(portfolio, {contract_symbol: premium}, note=f"execute_option_{decision_u.lower()}_{symbol}")
    save_portfolio(portfolio)
    return {
        "fills": fills,
        "ticker": symbol,
        "decision": decision_u,
        "instrument_type": "option",
        "contract_symbol": contract_symbol,
        "option_side": option_side,
        "premium": premium,
        "contracts": contracts,
        "decision_reason_code": "opened",
    }


def _parse_eod_flatten_et(value: str) -> tuple[int, int]:
    text = str(value or "15:45").strip()
    parts = text.split(":")
    hour = int(parts[0]) if parts else 15
    minute = int(parts[1]) if len(parts) > 1 else 45
    return hour, minute


def evaluate_option_exit_rule(
    *,
    entry: float,
    mark: float,
    expiration: str,
    settings: Dict[str, Any],
    now_et: Optional[datetime] = None,
    today: Optional[str] = None,
) -> str:
    """
    Return exit reason if TP/SL/deadline/EOD/expiry rules would close, else empty string.

    Shared by live manage_option_exits and shadow near-miss simulation.
    In deadline horizon mode, on ``deadline_date`` at eod_flatten_et, open options
    with expiry <= deadline close as ``deadline_flatten``. Mid-week same-day expiry
    still uses ``eod_flatten``. Range / same_day modes never emit deadline_flatten.
    """
    try:
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
    except Exception:  # pragma: no cover
        et = timezone.utc

    now = now_et or datetime.now(et)
    if now.tzinfo is None:
        now = now.replace(tzinfo=et)

    trading = settings.get("trading", {})
    exits_cfg = trading.get("options_exits") or {}
    take_profit_pct = float(exits_cfg.get("take_profit_pct", 0.40))
    stop_loss_pct = float(exits_cfg.get("stop_loss_pct", 0.30))
    eod_hour, eod_minute = _parse_eod_flatten_et(str(exits_cfg.get("eod_flatten_et", "15:45")))
    session_today = today or now.date().isoformat()
    past_eod = (now.hour, now.minute) >= (eod_hour, eod_minute)
    exp = str(expiration or "").strip()

    if exp and exp < session_today:
        return "expired"
    if exp == session_today and mark <= 0:
        return "expired"
    if entry > 0 and mark >= entry * (1.0 + take_profit_pct):
        return "take_profit"
    if entry > 0 and mark <= entry * (1.0 - stop_loss_pct):
        return "stop_loss"

    from agent.market_session import deadline_flatten_enabled, resolve_deadline_date_et

    if deadline_flatten_enabled(settings):
        deadline_iso = resolve_deadline_date_et(settings, now).isoformat()
        if past_eod and session_today == deadline_iso:
            # Deadline backstop: flatten any still-open option at/before deadline.
            if not exp or exp <= deadline_iso:
                return "deadline_flatten"
        if exp == session_today and past_eod:
            # Prefer deadline label on deadline day even for same-day expiry.
            if session_today == deadline_iso:
                return "deadline_flatten"
            return "eod_flatten"
        return ""

    if exp == session_today and past_eod:
        return "eod_flatten"
    return ""


def manage_option_exits(
    settings: Dict[str, Any],
    now_et: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Close open option positions on take-profit, stop-loss, EOD flatten, or expiry.

    Returns list of close fills.
    """
    try:
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
    except Exception:  # pragma: no cover
        et = timezone.utc

    now = now_et or datetime.now(et)
    if now.tzinfo is None:
        now = now.replace(tzinfo=et)

    today = now.date().isoformat()

    # After the equity-options close, marks are stale — do not keep flattening/notifying.
    from agent.market_session import is_options_session_open, market_hours_only_enabled

    if market_hours_only_enabled(settings) and not is_options_session_open(settings, now):
        return []

    portfolio = load_portfolio(settings)
    positions = portfolio.get("positions", {})
    if not isinstance(positions, dict) or not positions:
        return []

    fills: List[Dict[str, Any]] = []
    for key in list(positions.keys()):
        pos = positions.get(key)
        if not isinstance(pos, dict):
            continue
        if str(pos.get("instrument_type", "")).lower() != "option":
            continue

        entry = float(pos.get("entry_price", 0.0) or 0.0)
        contract_symbol = str(pos.get("contract_symbol", key))
        expiration = str(pos.get("expiration", "")).strip()
        mark = fetch_option_mark(contract_symbol)
        if mark <= 0:
            mark = float(pos.get("mark_price", entry) or 0.0)

        from agent.eod_flatten_state import already_flattened, mark_flattened

        reason = evaluate_option_exit_rule(
            entry=entry,
            mark=mark,
            expiration=expiration,
            settings=settings,
            now_et=now,
            today=today,
        )
        if reason == "expired" and mark <= 0:
            mark = 0.0
        if reason in {"eod_flatten", "deadline_flatten"}:
            if already_flattened(key):
                # Idempotent: already flattened this key today — drop ghost if still present.
                print(f"[portfolio] Skip duplicate {reason} for {key}")
                portfolio.get("positions", {}).pop(key, None)
                continue

        if not reason:
            continue

        fill = _close_option_position(
            portfolio, key, mark, reason=reason, settings=settings
        )
        if fill:
            if reason in {"eod_flatten", "deadline_flatten"}:
                mark_flattened(key)
            fills.append(fill)
            append_execution(fill, settings)
            print(
                f"[portfolio] Option exit {reason}: {contract_symbol} "
                f"@ ${mark:.2f} pnl=${fill.get('realized_pnl', 0):+.2f}"
            )
            try:
                from agent.telegram_notifier import notify_option_exit

                notify_option_exit(fill, settings)
            except Exception as error:
                print(f"[portfolio] Telegram exit notify failed: {error}")

    if fills:
        prices = {str(f.get("contract_symbol", "")): float(f.get("price", 0.0)) for f in fills}
        _record_equity_snapshot(portfolio, prices, note="option_exit_manager")
        save_portfolio(portfolio)
    return fills


def reconcile_portfolio_on_startup(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Paper reconcile: load portfolio, drop keys already EOD-flattened today, log opens.

    Returns summary dict. Sets settings['_runtime']['portfolio_reconciled'] = True.
    """
    from agent.eod_flatten_state import flattened_keys_today

    portfolio = load_portfolio(settings)
    positions = portfolio.get("positions") or {}
    if not isinstance(positions, dict):
        positions = {}
    flat_keys = flattened_keys_today()
    removed: List[str] = []
    for key in list(positions.keys()):
        if key in flat_keys:
            positions.pop(key, None)
            removed.append(str(key))
    portfolio["positions"] = positions
    if removed:
        save_portfolio(portfolio)
        print(f"[portfolio] Startup reconcile removed already-flattened keys: {removed}")

    open_opts = []
    for key, pos in positions.items():
        if isinstance(pos, dict) and str(pos.get("instrument_type", "")).lower() == "option":
            open_opts.append(
                {
                    "key": key,
                    "contract": pos.get("contract_symbol"),
                    "side": pos.get("side"),
                    "contracts": pos.get("contracts"),
                }
            )
    print(f"[portfolio] Startup reconcile: {len(open_opts)} open option position(s)")
    runtime = settings.setdefault("_runtime", {})
    runtime["portfolio_reconciled"] = True
    runtime["reconcile_open_options"] = open_opts
    runtime["reconcile_removed"] = removed
    return {
        "open_options": open_opts,
        "removed_flattened": removed,
        "reconciled": True,
    }


def execute_decision(
    ticker: str,
    decision: str,
    price: float,
    reason: str,
    settings: Dict[str, Any],
    instrument_hint: str | None = None,
    force: bool = False,
    signal_confidence: float | None = None,
) -> Optional[Dict[str, Any]]:
    """
    Execute a paper trade for BUY/SELL decisions.

    instrument_hint: stock | call | put when trading.instrument is "auto".
    force: bypass auto_execute (used for Telegram/dashboard approvals).

    Returns execution summary dict or None if no trade placed.
    """
    trading = settings.get("trading", {})
    if not force and not bool(trading.get("auto_execute", True)):
        print(f"[portfolio] auto_execute disabled — no trade for {ticker} {decision}")
        return None

    instrument = str(trading.get("instrument", "stock")).lower().strip()
    hint = str(instrument_hint or "").lower().strip()
    if hint == "stock":
        instrument = "stock"
    elif instrument == "auto":
        if hint in {"call", "put"}:
            return execute_options_decision(
                ticker,
                decision,
                price,
                reason,
                settings,
                option_side=hint,
                signal_confidence=signal_confidence,
            )
        instrument = "stock"
    if instrument == "options" or hint in {"call", "put"}:
        side = hint if hint in {"call", "put"} else None
        return execute_options_decision(
            ticker,
            decision,
            price,
            reason,
            settings,
            option_side=side,
            signal_confidence=signal_confidence,
        )

    decision_u = decision.upper().strip()
    if decision_u not in {"BUY", "SELL"}:
        return None

    symbol = ticker.upper().strip()
    mark_price = float(price) if price > 0 else fetch_price_at_signal(symbol)
    if mark_price <= 0:
        print(f"[portfolio] Skipping {decision_u} for {symbol}: no price")
        return None

    portfolio = load_portfolio(settings)
    max_positions = max(1, int(trading.get("max_positions", 10)))
    desired = decision_to_side(decision_u, settings)

    positions = portfolio.get("positions", {})
    current = positions.get(symbol) if isinstance(positions, dict) else None
    current_sign = _position_sign(current)
    fills: List[Dict[str, Any]] = []

    if decision_u == "SELL" and not bool(trading.get("allow_short", True)):
        if current_sign == 1:
            fill = _close_position(portfolio, symbol, mark_price, reason=reason or "signal_sell")
            if fill:
                fills.append(fill)
                append_execution(fill, settings)
        save_portfolio(portfolio)
        return {"fills": fills, "action": "close_long_only"} if fills else None

    if desired == 0:
        return None

    if current_sign == desired:
        if isinstance(current, dict):
            current["mark_price"] = mark_price
        save_portfolio(portfolio)
        return {"fills": [], "action": "hold", "ticker": symbol, "side": current.get("side") if current else None}

    if current_sign != 0:
        fill = _close_position(portfolio, symbol, mark_price, reason="signal_flip")
        if fill:
            fills.append(fill)
            append_execution(fill, settings)

    open_count = len(portfolio.get("positions", {}))
    prices = {symbol: mark_price}
    equity = compute_equity(portfolio, prices)
    qty = _size_qty(equity, mark_price, max_positions, open_count)
    fill = _open_position(portfolio, symbol, desired, mark_price, qty, reason=reason or f"signal_{decision_u.lower()}")
    if fill:
        fills.append(fill)
        append_execution(fill, settings)

    _record_equity_snapshot(portfolio, {symbol: mark_price}, note=f"execute_{decision_u.lower()}_{symbol}")
    save_portfolio(portfolio)
    return {"fills": fills, "ticker": symbol, "decision": decision_u, "price": mark_price}


def _record_equity_snapshot(portfolio: Dict[str, Any], prices: Dict[str, float], note: str = "") -> None:
    trading_cfg: Dict[str, Any] = {}
    starting = float(portfolio.get("starting_cash", 100000))
    equity = compute_equity(portfolio, prices)
    unrealized = compute_unrealized(portfolio, prices)
    history = portfolio.setdefault("equity_history", [])
    history.append(
        {
            "timestamp": _now_iso(),
            "equity": round(equity, 2),
            "cash": round(float(portfolio.get("cash", 0.0)), 2),
            "open_positions": len(portfolio.get("positions", {})),
            "realized_pnl": round(float(portfolio.get("realized_pnl", 0.0)), 2),
            "unrealized_pnl": round(unrealized, 2),
            "return_pct": round((equity / starting - 1.0) * 100.0, 3) if starting else 0.0,
            "note": note,
        }
    )
    if len(history) > 500:
        portfolio["equity_history"] = history[-500:]


def refresh_portfolio_prices(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Mark all open positions to market and record equity snapshot."""
    portfolio = load_portfolio(settings)
    positions = portfolio.get("positions", {})
    if not isinstance(positions, dict) or not positions:
        return portfolio_summary(portfolio, {})

    prices: Dict[str, float] = {}
    for key, pos in positions.items():
        if not isinstance(pos, dict):
            continue
        if str(pos.get("instrument_type", "stock")).lower() == "option":
            contract_symbol = str(pos.get("contract_symbol", key))
            mark = fetch_option_mark(contract_symbol)
            if mark <= 0:
                mark = float(pos.get("mark_price", pos.get("entry_price", 0.0)) or 0.0)
            if mark > 0:
                prices[contract_symbol] = mark
                pos["mark_price"] = mark
            continue
        mark = fetch_price_at_signal(str(key))
        if mark > 0:
            prices[str(key).upper()] = mark
            pos["mark_price"] = mark

    _record_equity_snapshot(portfolio, prices, note="mark_to_market")
    save_portfolio(portfolio)
    return portfolio_summary(portfolio, prices)


def portfolio_summary(portfolio: Dict[str, Any], prices: Dict[str, float]) -> Dict[str, Any]:
    """Return equity, cash, realized/unrealized PnL, return pct, and open position count."""
    equity = compute_equity(portfolio, prices)
    starting = float(portfolio.get("starting_cash", 100000))
    return {
        "equity": round(equity, 2),
        "cash": round(float(portfolio.get("cash", 0.0)), 2),
        "realized_pnl": round(float(portfolio.get("realized_pnl", 0.0)), 2),
        "unrealized_pnl": round(compute_unrealized(portfolio, prices), 2),
        "return_pct": round((equity / starting - 1.0) * 100.0, 3) if starting else 0.0,
        "open_positions": len(portfolio.get("positions", {})),
        "starting_cash": starting,
    }


def build_open_positions_table(portfolio: Dict[str, Any], prices: Dict[str, float]) -> List[Dict[str, Any]]:
    """Build dashboard rows for each open stock or option position with unrealized PnL."""
    rows: List[Dict[str, Any]] = []
    for key, pos in portfolio.get("positions", {}).items():
        if not isinstance(pos, dict):
            continue
        instrument = str(pos.get("instrument_type", "stock")).lower()
        if instrument == "option":
            contracts = float(pos.get("contracts", 0.0))
            entry = float(pos.get("entry_price", 0.0))
            contract_symbol = str(pos.get("contract_symbol", key))
            mark = float(prices.get(contract_symbol, pos.get("mark_price", entry)) or entry)
            upnl = contracts * (mark - entry) * OPTION_MULTIPLIER
            rows.append(
                {
                    "ticker": str(pos.get("underlying", key)),
                    "instrument": f"{pos.get('side', 'call').upper()} opt",
                    "side": str(pos.get("side", "call")),
                    "qty": int(contracts),
                    "entry": round(entry, 2),
                    "mark": round(mark, 2),
                    "unrealized_pnl": round(upnl, 2),
                    "opened_at": pos.get("opened_at", ""),
                    "contract": contract_symbol,
                    "expiration": pos.get("expiration", ""),
                }
            )
            continue
        qty = float(pos.get("qty", 0.0))
        entry = float(pos.get("entry_price", 0.0))
        mark = float(prices.get(str(key).upper(), pos.get("mark_price", entry)) or entry)
        upnl = qty * (mark - entry)
        rows.append(
            {
                "ticker": key,
                "instrument": "stock",
                "side": pos.get("side", "long" if qty > 0 else "short"),
                "qty": abs(qty),
                "entry": round(entry, 2),
                "mark": round(mark, 2),
                "unrealized_pnl": round(upnl, 2),
                "opened_at": pos.get("opened_at", ""),
                "contract": "",
                "expiration": "",
            }
        )
    return rows
