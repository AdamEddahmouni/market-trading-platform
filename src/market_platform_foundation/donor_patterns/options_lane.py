"""Options confirmation lane patterns — reimplemented from options_confirmation_engine concepts."""

from __future__ import annotations

from typing import Any


def liquidity_gate(
    *,
    bid: float,
    ask: float,
    open_interest: int,
    min_open_interest: int = 100,
    max_spread_pct: float = 0.25,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if open_interest < min_open_interest:
        reasons.append("LOW_OPEN_INTEREST")
    mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else 0.0
    if mid > 0:
        spread_pct = (ask - bid) / mid
        if spread_pct > max_spread_pct:
            reasons.append("WIDE_SPREAD")
    else:
        reasons.append("INVALID_QUOTES")
    return len(reasons) == 0, reasons


def confirmation_score(
    *,
    iv_rank: float,
    volume_ratio: float,
    skew_signal: float,
    weights: tuple[float, float, float] = (0.35, 0.35, 0.30),
) -> float:
    w_iv, w_vol, w_skew = weights
    total = w_iv + w_vol + w_skew
    if total <= 0:
        return 0.0
    raw = (iv_rank * w_iv + volume_ratio * w_vol + skew_signal * w_skew) / total
    return max(0.0, min(100.0, raw * 100.0))


def project_options_confirmation(
    *,
    symbol: str,
    expiry: str,
    strike: float,
    option_type: str,
    score: float,
    liquidity_ok: bool,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "expiry": expiry,
        "strike": strike,
        "option_type": option_type,
        "confirmation_score": round(score, 2),
        "liquidity_ok": liquidity_ok,
        "lane": "options_confirmation",
        "epistemic_class": "DERIVED",
        "research_only": True,
        "note": "Separate from futures lane; not a trade recommendation.",
    }
