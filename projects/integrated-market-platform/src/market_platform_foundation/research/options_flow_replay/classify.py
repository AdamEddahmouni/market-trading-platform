"""Transparent decomposition of replay fixture prints (no vendor composite score)."""

from __future__ import annotations

from typing import Any

from ...options.flow import classify_signed_flow

BLOCK_SIZE_THRESHOLD = 500
BLOCK_NOTIONAL_THRESHOLD_USD = 250_000.0
SWEEP_LEG_COUNT_MIN = 2
SWEEP_EXCHANGE_DISPERSION_MIN = 0.35
QUOTE_AGE_STALE_MS = 500


def _positive_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and float(value) >= 0:
        return float(value)
    return None


def classify_sweep_or_block(activity: dict[str, Any]) -> dict[str, Any]:
    leg_count = int(activity.get("leg_count", 1) or 1)
    dispersion = float(activity.get("exchange_dispersion", 0.0) or 0.0)
    size = int(activity.get("size", activity.get("volume", 0)) or 0)
    premium = float(activity.get("premium", 0.0) or 0.0)
    notional = premium * size * 100.0

    reasons: list[str] = []
    if leg_count >= SWEEP_LEG_COUNT_MIN:
        reasons.append("LEG_COUNT_AT_OR_ABOVE_SWEEP_THRESHOLD")
    if dispersion >= SWEEP_EXCHANGE_DISPERSION_MIN:
        reasons.append("EXCHANGE_DISPERSION_AT_OR_ABOVE_SWEEP_THRESHOLD")
    if reasons:
        return {
            "trade_class": "sweep",
            "classification_reasons": reasons,
            "leg_count": leg_count,
            "exchange_dispersion": round(dispersion, 4),
        }
    if size >= BLOCK_SIZE_THRESHOLD or notional >= BLOCK_NOTIONAL_THRESHOLD_USD:
        return {
            "trade_class": "block",
            "classification_reasons": ["SIZE_OR_NOTIONAL_BLOCK_THRESHOLD"],
            "leg_count": leg_count,
            "exchange_dispersion": round(dispersion, 4),
            "notional_usd": round(notional, 2),
        }
    return {
        "trade_class": "unclassified_print",
        "classification_reasons": ["BELOW_SWEEP_AND_BLOCK_THRESHOLDS"],
        "leg_count": leg_count,
        "exchange_dispersion": round(dispersion, 4),
    }


def assess_aggressor_confidence(activity: dict[str, Any]) -> dict[str, Any]:
    raw = activity.get("aggressor_confidence")
    if raw is None:
        signed = classify_signed_flow(activity)
        if not signed.get("flow_confirmed"):
            return {"available": False, "reason": "AGGRESSOR_CONFIDENCE_MISSING_AND_FLOW_UNCERTAIN"}
        return {"available": False, "reason": "AGGRESSOR_CONFIDENCE_MISSING"}
    confidence = _positive_float(raw)
    if confidence is None:
        return {"available": False, "reason": "AGGRESSOR_CONFIDENCE_INVALID"}
    band = "low"
    if confidence >= 0.85:
        band = "high"
    elif confidence >= 0.7:
        band = "medium"
    return {
        "available": True,
        "confidence": round(confidence, 4),
        "band": band,
    }


def assess_quote_age(activity: dict[str, Any]) -> dict[str, Any]:
    raw = activity.get("quote_age_ms")
    if raw is None:
        return {"available": False, "reason": "QUOTE_AGE_MISSING"}
    if not isinstance(raw, (int, float)) or float(raw) < 0:
        return {"available": False, "reason": "QUOTE_AGE_INVALID"}
    age = int(raw)
    return {
        "available": True,
        "quote_age_ms": age,
        "staleness": "stale" if age > QUOTE_AGE_STALE_MS else "fresh",
    }


def assess_volume_oi(activity: dict[str, Any]) -> dict[str, Any]:
    volume = int(activity.get("volume", 0) or 0)
    oi = int(activity.get("open_interest", 0) or 0)
    ratio = round(volume / oi, 4) if oi > 0 else None
    return {
        "volume": volume,
        "open_interest": oi,
        "volume_oi_ratio": ratio,
        "volume_oi_ratio_fixture": activity.get("volume_oi_ratio"),
    }


def assess_gex_context(activity: dict[str, Any]) -> dict[str, Any]:
    ctx = activity.get("gex_context")
    if not isinstance(ctx, dict):
        return {"available": False, "reason": "GEX_CONTEXT_MISSING"}
    net = ctx.get("net_gamma_oi_weighted")
    regime = ctx.get("regime_label")
    missing: list[str] = []
    if net is None:
        missing.append("net_gamma_oi_weighted")
    payload: dict[str, Any] = {
        "available": True,
        "regime_label": regime,
        "missing_fields": missing,
    }
    if net is not None:
        payload["net_gamma_oi_weighted"] = net
    if missing:
        payload["partial"] = True
    return payload


def assess_premium(activity: dict[str, Any]) -> dict[str, Any]:
    premium = activity.get("premium")
    size = int(activity.get("size", activity.get("volume", 0)) or 0)
    if premium is None:
        return {"available": False, "reason": "PREMIUM_MISSING"}
    prem_f = float(premium)
    return {
        "available": True,
        "premium_per_contract": round(prem_f, 4),
        "size": size,
        "premium_times_size": round(prem_f * size, 4),
    }


def decompose_replay_print(activity: dict[str, Any], *, index: int) -> dict[str, Any]:
    """Single-print transparent evidence row for artifact emission."""

    sweep_block = classify_sweep_or_block(activity)
    signed = classify_signed_flow(activity)
    missing_data: list[str] = []
    if activity.get("quote_age_ms") is None:
        missing_data.append("quote_age_ms")
    gex = assess_gex_context(activity)
    if not gex.get("available"):
        missing_data.append("gex_context")
    elif gex.get("partial"):
        missing_data.extend([f"gex_context.{field}" for field in gex.get("missing_fields", [])])

    evidence_for: list[str] = []
    evidence_against: list[str] = []
    if sweep_block["trade_class"] == "sweep":
        evidence_for.append("REPLAY_CLASSIFIED_SWEEP")
    if sweep_block["trade_class"] == "block":
        evidence_for.append("REPLAY_CLASSIFIED_BLOCK")
    aggressor = assess_aggressor_confidence(activity)
    if aggressor.get("available") and aggressor.get("band") == "high":
        evidence_for.append("HIGH_AGGRESSOR_CONFIDENCE")
    if missing_data:
        evidence_against.append("REPLAY_FIELD_GAPS")
    quote = assess_quote_age(activity)
    if quote.get("available") and quote.get("staleness") == "stale":
        evidence_against.append("STALE_QUOTE_CONTEXT")

    return {
        "print_index": index,
        "event_time": str(activity.get("event_time", "")),
        "strike": activity.get("strike"),
        "expiry": activity.get("expiry"),
        "option_type": activity.get("option_type"),
        "trade_classification": sweep_block,
        "premium": assess_premium(activity),
        "signed_flow": {
            "direction": signed.get("direction"),
            "open_close": signed.get("open_close"),
            "quality_flags": list(signed.get("quality_flags") or []),
        },
        "aggressor_confidence": aggressor,
        "quote_age": quote,
        "volume_oi": assess_volume_oi(activity),
        "gex_context": gex,
        "missing_data_fields": missing_data,
        "evidence_contribution": {
            "evidence_for": evidence_for,
            "evidence_against": evidence_against,
            "directional_score": None,
            "excluded_vendor_fields": ["confirmation_score", "vendor_composite_score"],
        },
    }


__all__ = [
    "assess_aggressor_confidence",
    "assess_gex_context",
    "assess_premium",
    "assess_quote_age",
    "assess_volume_oi",
    "classify_sweep_or_block",
    "decompose_replay_print",
]
