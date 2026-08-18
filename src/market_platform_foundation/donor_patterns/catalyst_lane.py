"""Catalyst discovery lane patterns — reimplemented from internship agent concepts."""

from __future__ import annotations

from typing import Any


def confidence_score(
    *,
    news_score: float,
    social_score: float,
    volume_score: float,
    weights: tuple[float, float, float] = (0.4, 0.3, 0.3),
) -> float:
    w_news, w_social, w_volume = weights
    total = w_news + w_social + w_volume
    if total <= 0:
        return 0.0
    raw = (news_score * w_news + social_score * w_social + volume_score * w_volume) / total
    return max(0.0, min(1.0, raw))


def lean_direction(
    *,
    signed_score: float,
    threshold: float = 0.15,
) -> str:
    if signed_score >= threshold:
        return "BULLISH"
    if signed_score <= -threshold:
        return "BEARISH"
    return "NEUTRAL"


def gate_catalyst(
    *,
    confidence: float,
    min_confidence: float,
    lean: str,
    liquidity_ok: bool,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if confidence < min_confidence:
        reasons.append("CONFIDENCE_BELOW_THRESHOLD")
    if lean == "NEUTRAL":
        reasons.append("LEAN_NEUTRAL")
    if not liquidity_ok:
        reasons.append("LIQUIDITY_REJECT")
    return len(reasons) == 0, reasons


def lean_to_direction_label(lean: str) -> str:
    if lean == "BULLISH":
        return "supports_long"
    if lean == "BEARISH":
        return "supports_short"
    return "neutral"


def project_catalyst_evidence(
    *,
    symbol: str,
    headline: str,
    confidence: float,
    lean: str,
    source: str,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "headline": headline,
        "confidence": round(confidence, 4),
        "lean": lean,
        "source": source,
        "epistemic_class": "INFERRED",
        "lane": "catalyst",
        "research_only": True,
    }
