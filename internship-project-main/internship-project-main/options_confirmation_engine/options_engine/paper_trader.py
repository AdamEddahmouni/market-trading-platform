"""Simulated paper trading: long/short stock positions driven by options signals.

Purpose
-------
Optional engine-local demo book: translate ``options_bias`` into signed stock
positions in ``state/portfolio.json`` — **not** connected to the news agent broker.

Features / API role
-------------------
``update(signals)`` applies open/close/flip rules; ``portfolio_summary`` and
``compute_equity`` for dashboard metrics.

How ``news_momentum_agent`` consumes it
---------------------------------------
**Does not.** Live agent paper trading is ``news_momentum_agent/agent/paper_trader.py``.
Engine paper trader is for standalone ``scheduler.py`` experiments only.

Options-specific vs reusable
----------------------------
Bias-driven position rules are options-signal-specific; portfolio JSON accounting
is reusable simulation infrastructure.

Consumes scored signal items (``options_bias``, ``spot_price``) and maintains a
virtual portfolio in ``state/portfolio.json``. No broker, no real money.

Position rules (default):
- ``bullish`` -> open/maintain long
- ``bearish`` -> open/maintain short (if ``allow_short``)
- ``neutral`` / ``no_data`` -> exit to flat (if ``exit_on_neutral``)

Uses signed-share accounting: long qty > 0, short qty < 0.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from options_engine.utils import PROJECT_ROOT, load_json, save_json


PORTFOLIO_PATH = PROJECT_ROOT / "state" / "portfolio.json"
EXECUTIONS_PATH = PROJECT_ROOT / "state" / "executions.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_portfolio(starting_cash: float) -> Dict[str, Any]:
    """Return an empty paper portfolio dict with starting cash."""
    return {
        "starting_cash": float(starting_cash),
        "cash": float(starting_cash),
        "realized_pnl": 0.0,
        "positions": {},
        "equity_history": [],
        "updated_at": _now_iso(),
    }


def load_portfolio(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Load portfolio from disk or initialize from ``trading.starting_cash``."""
    starting = float(settings.get("trading", {}).get("starting_cash", 100000))
    data = load_json(PORTFOLIO_PATH, default_portfolio(starting))
    if not isinstance(data, dict):
        return default_portfolio(starting)
    if "positions" not in data or not isinstance(data["positions"], dict):
        data["positions"] = {}
    if "equity_history" not in data or not isinstance(data["equity_history"], list):
        data["equity_history"] = []
    return data


def save_portfolio(portfolio: Dict[str, Any], atomic: bool = True) -> None:
    """Persist portfolio to ``state/portfolio.json``."""
    portfolio["updated_at"] = _now_iso()
    save_json(PORTFOLIO_PATH, portfolio, atomic=atomic)


def load_executions() -> List[Dict[str, Any]]:
    """Load fill history from ``state/executions.json``."""
    data = load_json(EXECUTIONS_PATH, [])
    return data if isinstance(data, list) else []


def append_execution(fill: Dict[str, Any], atomic: bool = True) -> None:
    """Append one fill record to ``state/executions.json``."""
    rows = load_executions()
    rows.append(fill)
    save_json(EXECUTIONS_PATH, rows, atomic=atomic)


def target_side(bias: str, settings: Dict[str, Any]) -> int:
    """Return desired position sign: +1 long, -1 short, 0 flat."""
    trading = settings.get("trading", {})
    allow_short = bool(trading.get("allow_short", True))
    bias_l = str(bias).lower().strip()
    if bias_l == "bullish":
        return 1
    if bias_l == "bearish" and allow_short:
        return -1
    return 0


def _position_sign(pos: Dict[str, Any]) -> int:
    qty = float(pos.get("qty", 0))
    if qty > 0:
        return 1
    if qty < 0:
        return -1
    return 0


def compute_equity(portfolio: Dict[str, Any], prices: Dict[str, float]) -> float:
    """Mark-to-market equity using signed quantities."""
    equity = float(portfolio.get("cash", 0.0))
    positions = portfolio.get("positions", {})
    if not isinstance(positions, dict):
        return equity
    for ticker, pos in positions.items():
        if not isinstance(pos, dict):
            continue
        qty = float(pos.get("qty", 0.0))
        price = float(prices.get(ticker, pos.get("entry_price", 0.0)) or 0.0)
        equity += qty * price
    return equity


def _compute_unrealized(portfolio: Dict[str, Any], prices: Dict[str, float]) -> float:
    total = 0.0
    for ticker, pos in portfolio.get("positions", {}).items():
        if not isinstance(pos, dict):
            continue
        qty = float(pos.get("qty", 0.0))
        entry = float(pos.get("entry_price", 0.0))
        mark = float(prices.get(ticker, entry) or entry)
        total += qty * (mark - entry)
    return total


def _size_qty(equity: float, price: float, max_positions: int, open_count: int) -> int:
    if price <= 0 or open_count >= max_positions:
        return 0
    slots = max(1, max_positions - open_count)
    alloc = equity / max_positions
    qty = int(math.floor(alloc / price))
    return max(1, qty) if qty >= 1 else 0


def _close_position(
    portfolio: Dict[str, Any],
    ticker: str,
    price: float,
    request_id: str,
    reason: str,
) -> Optional[Dict[str, Any]]:
    positions = portfolio.setdefault("positions", {})
    pos = positions.get(ticker)
    if not pos or not isinstance(pos, dict):
        return None
    qty = float(pos.get("qty", 0.0))
    if qty == 0:
        del positions[ticker]
        return None
    entry = float(pos.get("entry_price", 0.0))
    realized = qty * (price - entry)
    portfolio["cash"] = float(portfolio.get("cash", 0.0)) + qty * price
    portfolio["realized_pnl"] = float(portfolio.get("realized_pnl", 0.0)) + realized
    side = "long" if qty > 0 else "short"
    fill = {
        "timestamp": _now_iso(),
        "request_id": request_id,
        "ticker": ticker,
        "action": "close",
        "side": side,
        "qty": abs(qty),
        "signed_qty": qty,
        "price": price,
        "realized_pnl": round(realized, 2),
        "reason": reason,
    }
    del positions[ticker]
    return fill


def _open_position(
    portfolio: Dict[str, Any],
    ticker: str,
    side_sign: int,
    price: float,
    qty: int,
    request_id: str,
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
        "qty": signed_qty,
        "entry_price": price,
        "side": "long" if signed_qty > 0 else "short",
        "opened_at": _now_iso(),
    }
    return {
        "timestamp": _now_iso(),
        "request_id": request_id,
        "ticker": ticker,
        "action": "open",
        "side": "long" if signed_qty > 0 else "short",
        "qty": abs(signed_qty),
        "signed_qty": signed_qty,
        "price": price,
        "realized_pnl": 0.0,
        "reason": reason,
    }


def update(signals: List[Dict[str, Any]], settings: Dict[str, Any], request_id: str = "") -> Dict[str, Any]:
    """Apply signal-driven trades and persist portfolio state."""
    trading = settings.get("trading", {})
    if not bool(trading.get("enabled", True)):
        return load_portfolio(settings)

    portfolio = load_portfolio(settings)
    max_positions = max(1, int(trading.get("max_positions", 10)))
    exit_on_neutral = bool(trading.get("exit_on_neutral", True))
    atomic = bool(settings.get("runtime", {}).get("state_write_atomic", True))

    prices: Dict[str, float] = {}
    for item in signals:
        ticker = str(item.get("ticker", "")).upper().strip()
        price = float(item.get("spot_price", 0.0) or 0.0)
        if ticker and price > 0:
            prices[ticker] = price

    equity_before = compute_equity(portfolio, prices)
    fills: List[Dict[str, Any]] = []

    for item in signals:
        ticker = str(item.get("ticker", "")).upper().strip()
        if not ticker:
            continue
        price = prices.get(ticker, 0.0)
        if price <= 0:
            continue
        bias = str(item.get("options_bias", "no_data"))
        desired = target_side(bias, settings)
        if desired == 0 and not exit_on_neutral:
            continue

        positions = portfolio.get("positions", {})
        current = positions.get(ticker) if isinstance(positions, dict) else None
        current_sign = _position_sign(current) if isinstance(current, dict) else 0

        if desired == 0 and current_sign != 0:
            fill = _close_position(portfolio, ticker, price, request_id, reason=f"signal_{bias}")
            if fill:
                fills.append(fill)
                append_execution(fill, atomic=atomic)
            continue

        if desired == 0:
            continue

        if current_sign == desired:
            continue

        if current_sign != 0:
            fill = _close_position(portfolio, ticker, price, request_id, reason="signal_flip")
            if fill:
                fills.append(fill)
                append_execution(fill, atomic=atomic)

        open_count = len(portfolio.get("positions", {}))
        qty = _size_qty(compute_equity(portfolio, prices), price, max_positions, open_count)
        fill = _open_position(portfolio, ticker, desired, price, qty, request_id, reason=f"signal_{bias}")
        if fill:
            fills.append(fill)
            append_execution(fill, atomic=atomic)

    equity_after = compute_equity(portfolio, prices)
    unrealized = _compute_unrealized(portfolio, prices)
    starting = float(portfolio.get("starting_cash", trading.get("starting_cash", 100000)))
    history = portfolio.setdefault("equity_history", [])
    history.append(
        {
            "timestamp": _now_iso(),
            "request_id": request_id,
            "equity": round(equity_after, 2),
            "cash": round(float(portfolio.get("cash", 0.0)), 2),
            "open_positions": len(portfolio.get("positions", {})),
            "realized_pnl": round(float(portfolio.get("realized_pnl", 0.0)), 2),
            "unrealized_pnl": round(unrealized, 2),
            "return_pct": round((equity_after / starting - 1.0) * 100.0, 3) if starting else 0.0,
        }
    )
    if len(history) > 500:
        portfolio["equity_history"] = history[-500:]

    save_portfolio(portfolio, atomic=atomic)
    return {
        "portfolio": portfolio,
        "fills": fills,
        "equity_before": round(equity_before, 2),
        "equity_after": round(equity_after, 2),
        "cycle_pnl": round(equity_after - equity_before, 2),
        "unrealized_pnl": round(unrealized, 2),
    }


def portfolio_summary(portfolio: Dict[str, Any], prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Build a summary dict for logging / dashboard."""
    prices = prices or {}
    equity = compute_equity(portfolio, prices)
    starting = float(portfolio.get("starting_cash", 100000))
    return {
        "equity": round(equity, 2),
        "cash": round(float(portfolio.get("cash", 0.0)), 2),
        "realized_pnl": round(float(portfolio.get("realized_pnl", 0.0)), 2),
        "unrealized_pnl": round(_compute_unrealized(portfolio, prices), 2),
        "return_pct": round((equity / starting - 1.0) * 100.0, 3) if starting else 0.0,
        "open_positions": len(portfolio.get("positions", {})),
    }
