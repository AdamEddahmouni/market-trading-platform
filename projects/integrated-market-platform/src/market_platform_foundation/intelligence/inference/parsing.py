"""Structured model response parsing and validation."""

from __future__ import annotations

import json
import re
from typing import Any

from .contracts import (
    ImpactHorizon,
    MarketImpactLevel,
    ParsingStatus,
    SentimentLabel,
    StructuredIntelligenceOutput,
)

FORBIDDEN_TRADE_TERMS = re.compile(
    r"\b(BUY|SELL|SHORT|LONG|QUANTITY|LIMIT_PRICE)\b",
    re.IGNORECASE,
)


def _extract_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fence:
        return fence.group(1)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return stripped


def _parse_float(value: Any, *, field_name: str, low: float, high: float) -> tuple[float | None, ParsingStatus | None]:
    if value is None:
        return None, None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None, ParsingStatus.SCORE_OUT_OF_RANGE
    if parsed < low or parsed > high:
        return None, ParsingStatus.SCORE_OUT_OF_RANGE
    return parsed, None


def _parse_sentiment(value: Any) -> tuple[SentimentLabel | None, ParsingStatus | None]:
    if value is None:
        return None, None
    try:
        return SentimentLabel(str(value)), None
    except ValueError:
        return None, ParsingStatus.INVALID_ENUM


def _parse_impact(value: Any) -> tuple[MarketImpactLevel | None, ParsingStatus | None]:
    if value is None:
        return None, None
    try:
        return MarketImpactLevel(str(value)), None
    except ValueError:
        return None, ParsingStatus.INVALID_ENUM


def _parse_horizon(value: Any) -> tuple[ImpactHorizon | None, ParsingStatus | None]:
    if value is None:
        return None, None
    try:
        return ImpactHorizon(str(value)), None
    except ValueError:
        return None, ParsingStatus.INVALID_ENUM


def parse_structured_output(raw_text: str) -> tuple[StructuredIntelligenceOutput | None, ParsingStatus, str]:
    if not raw_text or not raw_text.strip():
        return None, ParsingStatus.MISSING_FIELDS, "empty provider response"

    if FORBIDDEN_TRADE_TERMS.search(raw_text):
        return None, ParsingStatus.INVALID_ENUM, "forbidden trading terms in response"

    try:
        payload = json.loads(_extract_json(raw_text))
    except json.JSONDecodeError as exc:
        return None, ParsingStatus.MALFORMED, f"json decode failed: {exc}"

    if not isinstance(payload, dict):
        return None, ParsingStatus.MALFORMED, "response must be object"

    rationale = str(payload.get("rationale", "") or "")
    if len(rationale) > 4000:
        return None, ParsingStatus.UNSUPPORTED_SCHEMA, "rationale exceeds limit"

    sentiment_label, err = _parse_sentiment(payload.get("sentiment_label"))
    if err:
        return None, err, "invalid sentiment_label"

    sentiment_score, err = _parse_float(
        payload.get("sentiment_score"), field_name="sentiment_score", low=-1.0, high=1.0
    )
    if err:
        return None, err, "invalid sentiment_score"

    market_impact, err = _parse_impact(payload.get("market_impact_level"))
    if err:
        return None, err, "invalid market_impact_level"

    impact_horizon, err = _parse_horizon(payload.get("impact_horizon"))
    if err:
        return None, err, "invalid impact_horizon"

    model_confidence, err = _parse_float(
        payload.get("model_confidence"), field_name="model_confidence", low=0.0, high=1.0
    )
    if err:
        return None, err, "invalid model_confidence"

    warnings_raw = payload.get("warnings", [])
    warnings: tuple[str, ...] = ()
    if warnings_raw is not None:
        if not isinstance(warnings_raw, list):
            return None, ParsingStatus.MALFORMED, "warnings must be list"
        warnings = tuple(str(item) for item in warnings_raw if item)

    output = StructuredIntelligenceOutput(
        sentiment_label=sentiment_label,
        sentiment_score=sentiment_score,
        catalyst_interpretation=str(payload.get("catalyst_interpretation", "") or ""),
        catalyst_strength=str(payload.get("catalyst_strength", "") or ""),
        market_impact_level=market_impact,
        impact_horizon=impact_horizon,
        rationale=rationale,
        model_confidence=model_confidence,
        warnings=warnings,
    )
    return output, ParsingStatus.VALID, ""


__all__ = ["FORBIDDEN_TRADE_TERMS", "parse_structured_output"]
