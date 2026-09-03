"""Scoring logic mapping options features to confirmation outputs (v2 + 0DTE).

Purpose
-------
Convert the feature-layer float dict into ``options_score`` (0–100),
``options_bias``, and a compact ``reasoning_summary`` for downstream gates.

Features / API role
-------------------
Each directional feature maps to a bullish-normalized sub-score in [0, 1]
(0.5 == neutral), combined with configurable weights, then rescaled to 0–100.
Only features with ``*_available`` flags contribute; unavailable inputs are
dropped from numerator and weight sum. GEX modulates the final score post-weight
(positive GEX pulls toward 50; negative GEX amplifies extremes). Liquidity reject
and data-quality flags can force ``no_data`` or damp extremes.

How ``news_momentum_agent`` consumes it
---------------------------------------
Called indirectly via ``runner.run_ticker`` / ``options_client.score_ticker``.
``decision_engine`` / ``odte_decision`` read ``options_score``, ``options_bias``,
and ``liquidity_reject``. ``evaluation/spy_qqq_replay.score_snapshot`` imports
this module directly for historical replay.

Options-specific vs reusable
----------------------------
Options-specific: PCR/skew/GEX/max-pain weight model and bias thresholds.
Reusable: availability-aware weighted averaging and quality-score damping pattern.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def compute_data_quality_score(flags: List[str]) -> float:
    """Compute a simple quality score from data quality flags."""
    penalties = {
        "fetch_error": 0.6,
        "missing_auth_token": 0.6,
        "invalid_auth_token": 0.9,
        "no_expirations": 0.5,
        "empty_chain": 0.5,
        "illiquid_chain": 0.3,
        "missing_spot_price": 0.2,
        "liquidity_reject": 0.4,
    }
    score = 1.0
    for flag in flags:
        score -= penalties.get(flag, 0.1)
    return _clamp(score, 0.0, 1.0)


# Calibration constants for mapping raw features to bullish sub-scores.
_PCR_VOL_NEUTRAL = 0.9       # put/call volume ratio considered directionally flat
_PCR_VOL_GAIN = 0.6          # sensitivity per unit of ratio deviation
_PCR_OI_NEUTRAL = 1.0        # put/call OI ratio considered flat
_PCR_OI_GAIN = 0.5
_NET_DELTA_GAIN = 1.5        # sensitivity of net delta-weighted OI
_SKEW_SCALE = 0.04           # IV-skew (vol points) that maps to a full-strength signal
_MAX_PAIN_GAIN = 0.08        # % distance from spot that maps toward a full lean


def _bullish_subscores(f: Dict[str, float]) -> Dict[str, float]:
    """Map raw directional features to bullish-normalized sub-scores in [0, 1]."""
    pcr_vol = f.get("put_call_volume_ratio", 1.0)
    pcr_oi = f.get("put_call_oi_ratio", 1.0)
    skew = f.get("iv_skew", 0.0)
    # Max pain / OI wall above spot → mild bullish magnet for longs into the pin.
    max_pain_dist = f.get("max_pain_distance_pct", 0.0)

    # Prefer precomputed flow trend score when available.
    flow_trend = f.get("flow_trend_score", 0.5)

    # IV rank: cheap premium (low rank) → higher subscore for long premium.
    iv_rank = f.get("iv_rank", 0.5)
    iv_rank_sub = _clamp(1.0 - float(iv_rank), 0.0, 1.0)

    # gex_regime is scored as a *passthrough placeholder* (always 0.5). Real GEX
    # effect is applied in ``_apply_gex_regime_modulation`` after the weighted sum
    # so positive-GEX pin regimes damp extremes rather than inventing direction.
    return {
        # Higher call share -> bullish (already 0..1).
        "call_volume_share": _clamp(f.get("call_volume_share", 0.5), 0.0, 1.0),
        # Lower put/call volume -> bullish.
        "put_call_volume_ratio": _clamp(0.5 + (_PCR_VOL_NEUTRAL - pcr_vol) * _PCR_VOL_GAIN, 0.0, 1.0),
        # Lower put/call OI -> bullish.
        "put_call_oi_ratio": _clamp(0.5 + (_PCR_OI_NEUTRAL - pcr_oi) * _PCR_OI_GAIN, 0.0, 1.0),
        # Positive net delta-weighted OI -> bullish positioning.
        "net_delta_oi": _clamp(0.5 + f.get("net_delta_oi", 0.0) * _NET_DELTA_GAIN, 0.0, 1.0),
        # Put IV richer than call IV (positive skew) -> bearish.
        "iv_skew": _clamp(0.5 - skew / (2.0 * _SKEW_SCALE), 0.0, 1.0),
        # 0DTE extensions
        "gex_regime": 0.5,
        "max_pain_distance": _clamp(0.5 + (max_pain_dist / 100.0) / _MAX_PAIN_GAIN * 0.5, 0.0, 1.0),
        "flow_trend": _clamp(flow_trend, 0.0, 1.0),
        "iv_rank_penalty": iv_rank_sub,
    }


def _availability(f: Dict[str, float]) -> Dict[str, bool]:
    """Resolve which directional sub-scores have valid inputs this run."""
    vol_ok = f.get("volume_available", 1.0) >= 1.0
    oi_ok = f.get("oi_available", 1.0) >= 1.0
    return {
        "call_volume_share": vol_ok,
        "put_call_volume_ratio": vol_ok,
        "put_call_oi_ratio": oi_ok,
        "net_delta_oi": f.get("greeks_available", 0.0) >= 1.0,
        "iv_skew": f.get("iv_skew_available", 0.0) >= 1.0,
        "gex_regime": f.get("gex_available", 0.0) >= 1.0,
        "max_pain_distance": f.get("max_pain_available", 0.0) >= 1.0,
        "flow_trend": f.get("flow_trend_available", 0.0) >= 1.0,
        "iv_rank_penalty": f.get("atm_iv", 0.0) > 0 or f.get("iv_rank", -1.0) >= 0.0,
    }


def _weighted_score(
    subscores: Dict[str, float],
    availability: Dict[str, bool],
    weights: Dict[str, Any],
) -> Tuple[float, int]:
    """Combine available sub-scores into a 0-100 score; returns (score, n_used)."""
    weighted = 0.0
    weight_sum = 0.0
    used = 0
    for key, sub in subscores.items():
        if not availability.get(key, False):
            continue
        weight = float(weights.get(key, 0.0))
        if weight <= 0:
            continue
        weighted += sub * weight
        weight_sum += weight
        used += 1
    if weight_sum <= 0:
        return 50.0, 0
    return (weighted / weight_sum) * 100.0, used


def _resolve_weights(settings: Dict[str, Any]) -> Dict[str, float]:
    """Merge base scoring weights with odte_signals.*.weight overrides."""
    scoring_cfg = settings.get("scoring", {})
    weights = {k: float(v) for k, v in (scoring_cfg.get("weights") or {}).items()}
    odte = settings.get("odte_signals") or {}
    mapping = {
        "gex": "gex_regime",
        "max_pain": "max_pain_distance",
        "flow_trend": "flow_trend",
        "iv_rank": "iv_rank_penalty",
    }
    for cfg_key, weight_key in mapping.items():
        block = odte.get(cfg_key) or {}
        if not bool(block.get("enabled", True)):
            weights[weight_key] = 0.0
            continue
        if "weight" in block:
            weights[weight_key] = float(block["weight"])
    # GEX is applied as post-score modulation; do not dilute the weighted sum with
    # a neutral 0.5 placeholder even if a weight is configured.
    weights["gex_regime"] = 0.0
    return weights


def _apply_gex_regime_modulation(
    score: float,
    feature_values: Dict[str, float],
    settings: Dict[str, Any],
) -> float:
    """
    Positive GEX (pin): pull score toward 50.
    Negative GEX (trend): amplify distance from 50.
    """
    odte = (settings.get("odte_signals") or {}).get("gex") or {}
    if not bool(odte.get("enabled", True)):
        return score
    if feature_values.get("gex_available", 0.0) < 1.0:
        return score
    code = float(feature_values.get("gex_regime_code", 0.0))
    pin_pull = float(odte.get("positive_pin_pull", 0.35))  # 0=no effect, 1=full collapse to 50
    trend_boost = float(odte.get("negative_trend_boost", 0.15))
    if code > 0.5:
        return 50.0 + (score - 50.0) * (1.0 - _clamp(pin_pull, 0.0, 1.0))
    if code < -0.5:
        return 50.0 + (score - 50.0) * (1.0 + _clamp(trend_boost, 0.0, 1.0))
    return score


def score_options(
    ticker: str,
    feature_values: Dict[str, float],
    data_quality_flags: List[str],
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    """Produce options_score, bias, and a concise reasoning summary."""
    scoring_cfg = settings.get("scoring", {})
    weights = _resolve_weights(settings)
    bullish_threshold = float(scoring_cfg.get("bullish_threshold", 60))
    bearish_threshold = float(scoring_cfg.get("bearish_threshold", 40))
    min_quality = float(scoring_cfg.get("min_data_quality_score", 0.6))
    min_signals = int(scoring_cfg.get("min_directional_signals", 2))

    flags = list(data_quality_flags or [])
    if feature_values.get("liquidity_reject", 0.0) >= 1.0:
        if "liquidity_reject" not in flags:
            flags.append("liquidity_reject")

    quality_score = compute_data_quality_score(flags)
    subscores = _bullish_subscores(feature_values)
    availability = _availability(feature_values)
    raw_score, signals_used = _weighted_score(subscores, availability, weights)
    raw_score = _apply_gex_regime_modulation(raw_score, feature_values, settings)

    if quality_score < min_quality:
        # Pull score toward neutral (50) in proportion to the quality shortfall.
        raw_score = 50.0 + (raw_score - 50.0) * quality_score

    options_score = _clamp(raw_score, 0.0, 100.0)
    if (flags and quality_score <= 0.2) or signals_used < min_signals:
        bias = "no_data"
    elif options_score >= bullish_threshold:
        bias = "bullish"
    elif options_score <= bearish_threshold:
        bias = "bearish"
    else:
        bias = "neutral"

    gex_code = feature_values.get("gex_regime_code", 0.0)
    gex_label = "positive" if gex_code > 0.5 else ("negative" if gex_code < -0.5 else "neutral")
    reasoning = (
        f"{ticker}: score={options_score:.1f}, bias={bias}, quality={quality_score:.2f}, "
        f"signals={signals_used}, pcr_vol={feature_values.get('put_call_volume_ratio', 0.0):.2f}, "
        f"pcr_oi={feature_values.get('put_call_oi_ratio', 0.0):.2f}, "
        f"net_delta_oi={feature_values.get('net_delta_oi', 0.0):.3f}, "
        f"iv_skew={feature_values.get('iv_skew', 0.0):.3f}, "
        f"gex={gex_label}, max_pain_dist={feature_values.get('max_pain_distance_pct', 0.0):.2f}%, "
        f"flow_trend={feature_values.get('flow_trend_score', 0.5):.2f}, "
        f"liq_ok={int(feature_values.get('liquidity_ok', 1.0))}"
    )
    return {
        "ticker": ticker,
        "options_score": round(options_score, 3),
        "options_bias": bias,
        "feature_values": feature_values,
        "feature_subscores": {k: round(v, 4) for k, v in subscores.items()},
        "feature_weights_used": {
            k: float(weights.get(k, 0.0))
            for k in subscores
            if availability.get(k) and float(weights.get(k, 0.0)) > 0
        },
        "data_quality": {"quality_score": round(quality_score, 3), "flags": flags},
        "reasoning_summary": reasoning,
        "liquidity_reject": bool(feature_values.get("liquidity_reject", 0.0) >= 1.0),
    }
