"""Decision engine combining social signal, news sentiment, and options confirmation.

Pipeline role
-------------
Produces BUY / SELL / REVIEW / LOG after news (or Path B expiry) preliminaries,
options confirmation, Path B urgency override, and the ODTE post-layer
(``agent.odte_decision``: liquidity, conflict, agreement confidence).

Lean vs confidence (why both exist)
-----------------------------------
``compute_action_probs`` → lean (BUY/SELL/WAIT/AVOID %) is a *direction strength*
heuristic from news + social + options. Agreement confidence in
``odte_decision`` is a separate *evidence-count* gate.

Path B historically could override to BUY/SELL on urgency while lean was still
coin-flip vs WAIT. The Path B lean-strength gate below exists so a weak lean
cannot execute even when override + confidence look green.

Merge notes for stocks/futures
------------------------------
  - **Reusable:** lean/probability math, social gate, instrument hint resolution.
  - **Options-heavy:** Path B urgency override, options confirmation integration,
    hands off to ``odte_decision`` for agreement/liquidity bars.
  - No state files; returns ``DecisionResult`` tuple to ``paper_trader``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple  # Any used for news_published_at / settings

from agent.herd_scorer import compute_herd_urgency, social_score_from_level


DecisionResult = Tuple[str, str, Dict[str, Any]]


def _empty_meta() -> Dict[str, Any]:
    return {
        "action_probs": {"BUY": 0.25, "SELL": 0.25, "WAIT": 0.25, "AVOID": 0.25},
        "lean": "WAIT",
        "lean_pct": 25,
        "instrument_hint": "stock",
        "review_reason_code": "",
        "signal_source": "news",
        "herd_stage": "quiet",
        "quadrant": "Q4",
    }


def compute_action_probs(
    news_score: float,
    social_signal_level: str,
    options_bias: str | None = None,
    options_score: float | None = None,
    herd_urgency: float = 0.0,
    decision: str = "REVIEW",
) -> Dict[str, float]:
    """
    Deterministic BUY/SELL/WAIT/AVOID probability mass (sums to 1.0).

    This is the lean input — not agreement confidence. High lean% with thin
    ``n_dir`` still fails the ODTE confidence gate (and vice versa).
    """
    buy = max(0.0, float(news_score))
    sell = max(0.0, -float(news_score))
    wait = max(0.0, 1.0 - abs(float(news_score)))
    avoid = 0.05

    social = str(social_signal_level or "IGNORE").upper().strip()
    if social == "HIGH_ALERT":
        buy *= 1.25
        sell *= 1.25
        wait *= 0.7
    elif social == "WATCH":
        wait += 0.15
    else:
        avoid += 0.2
        wait += 0.1

    bias = str(options_bias or "no_data").lower().strip()
    opt = float(options_score) if options_score is not None else 50.0
    if bias == "bullish" or opt >= 60:
        buy += (opt - 50.0) / 50.0
        sell *= 0.6
    elif bias == "bearish" or opt <= 40:
        sell += (50.0 - opt) / 50.0
        buy *= 0.6
    elif bias == "no_data":
        wait += 0.15
        avoid += 0.1

    # Options conflict with news direction.
    if float(news_score) > 0.3 and bias == "bearish":
        wait += 0.25
        avoid += 0.1
        buy *= 0.7
    if float(news_score) < -0.3 and bias == "bullish":
        wait += 0.25
        avoid += 0.1
        sell *= 0.7

    urgency = float(herd_urgency)
    if urgency >= 60:
        buy *= 1.15
        sell *= 1.15
        wait *= 0.8
    elif urgency < 30:
        wait += 0.15

    decision_u = str(decision).upper().strip()
    if decision_u == "BUY":
        buy += 0.5
    elif decision_u == "SELL":
        sell += 0.5
    elif decision_u == "LOG":
        avoid += 0.4
        wait += 0.2

    total = buy + sell + wait + avoid
    if total <= 0:
        return {"BUY": 0.25, "SELL": 0.25, "WAIT": 0.25, "AVOID": 0.25}
    probs = {
        "BUY": round(buy / total, 4),
        "SELL": round(sell / total, 4),
        "WAIT": round(wait / total, 4),
        "AVOID": round(avoid / total, 4),
    }
    # Fix rounding drift.
    drift = round(1.0 - sum(probs.values()), 4)
    probs["WAIT"] = round(probs["WAIT"] + drift, 4)
    return probs


def resolve_instrument_hint(
    decision: str,
    options_bias: str | None,
    options_score: float | None,
    herd_urgency: float,
    advisor_hint: str | None = None,
    *,
    liquidity_reject: bool = False,
    equity_fallback: bool = False,
) -> str:
    """Pick stock/call/put from advisor hint or simple rules."""
    if equity_fallback or liquidity_reject:
        return "stock"

    decision_u = str(decision).upper().strip()
    if advisor_hint:
        hint = str(advisor_hint).lower().strip()
        if hint in {"stock", "call", "put", "spread"}:
            # Prefer directional option legs for 0DTE paper mode.
            if hint == "spread":
                if decision_u == "BUY":
                    return "call"
                if decision_u == "SELL":
                    return "put"
                return "stock"
            if hint == "stock" and decision_u in {"BUY", "SELL"}:
                return "call" if decision_u == "BUY" else "put"
            return hint

    bias = str(options_bias or "no_data").lower().strip()
    score = float(options_score) if options_score is not None else 50.0
    lean_buy = decision_u == "BUY" or (decision_u == "REVIEW" and score >= 55)
    lean_sell = decision_u == "SELL" or (decision_u == "REVIEW" and score <= 45)

    if decision_u == "BUY":
        return "call"
    if decision_u == "SELL":
        return "put"

    if bias == "no_data" or herd_urgency < 40:
        return "stock"
    if lean_buy and (bias == "bullish" or score >= 60):
        return "call"
    if lean_sell and (bias == "bearish" or score <= 40):
        return "put"
    return "stock"


def _review_reason_code(
    decision: str,
    preliminary_decision: str,
    options_bias: str | None,
    social_signal_level: str,
) -> str:
    if decision != "REVIEW":
        return ""
    bias = str(options_bias or "").lower()
    social = str(social_signal_level or "").upper()
    if bias == "no_data":
        return "no_data"
    if preliminary_decision in {"BUY", "SELL"} and bias in {"bullish", "bearish"}:
        if (preliminary_decision == "BUY" and bias == "bearish") or (
            preliminary_decision == "SELL" and bias == "bullish"
        ):
            return "options_conflict"
    if social == "WATCH":
        return "weak_social"
    return "ambiguous_news"


def _decide_news_only(
    ticker: str,
    social_signal_level: str,
    claude_response: Dict[str, object],
    news_headline: str,
    news_source: str,
    buy_threshold: float,
    sell_threshold: float,
    require_social_signal: bool,
) -> Tuple[str, str]:
    """Apply news+social rules without options confirmation."""
    score = float(claude_response.get("score", 0.0))
    confidence = str(claude_response.get("confidence", "low"))
    reasoning = str(claude_response.get("reasoning", "No reasoning provided."))
    social = social_signal_level.upper().strip()
    high_threshold = float(buy_threshold)
    low_threshold = float(sell_threshold)

    if require_social_signal and social == "IGNORE":
        return (
            "LOG",
            f"{ticker}: Social signal is IGNORE and require_social_signal is enabled. Score={score:.2f}.",
        )
    if score > high_threshold and social == "HIGH_ALERT":
        return (
            "BUY",
            f"{ticker}: Strong positive score ({score:.2f}) with HIGH_ALERT social signal. "
            f"{reasoning} [{news_source}] {news_headline}",
        )
    if score < low_threshold and social == "HIGH_ALERT":
        return (
            "SELL",
            f"{ticker}: Strong negative score ({score:.2f}) with HIGH_ALERT social signal. "
            f"{reasoning} [{news_source}] {news_headline}",
        )
    if score > high_threshold and social == "WATCH":
        return (
            "REVIEW",
            f"{ticker}: Positive score ({score:.2f}) but only WATCH social signal. "
            f"Manual review required ({confidence} confidence).",
        )
    if score < low_threshold and social == "WATCH":
        return (
            "REVIEW",
            f"{ticker}: Negative score ({score:.2f}) but only WATCH social signal. "
            f"Manual review required ({confidence} confidence).",
        )
    if low_threshold <= score <= high_threshold:
        return (
            "REVIEW",
            f"{ticker}: Ambiguous score ({score:.2f}) requires human judgment. "
            f"[{news_source}] {news_headline}",
        )
    if social == "IGNORE":
        return (
            "LOG",
            f"{ticker}: Social signal is IGNORE, so action is logged quietly. Score={score:.2f}.",
        )

    return ("REVIEW", f"{ticker}: Fallback review for uncommon rule combination. Score={score:.2f}.")


def _decide_news_catalyst(
    ticker: str,
    social_signal_level: str,
    claude_response: Dict[str, object],
    news_headline: str,
    news_source: str,
    buy_threshold: float,
    sell_threshold: float,
    review_threshold: float,
) -> Tuple[str, str]:
    """
    Path A.2 — strong headline score alone; social is optional confirmation only.
    """
    score = float(claude_response.get("score", 0.0))
    confidence = str(claude_response.get("confidence", "low"))
    reasoning = str(claude_response.get("reasoning", "No reasoning provided."))
    social = social_signal_level.upper().strip()
    buy_thr = float(buy_threshold)
    sell_thr = float(sell_threshold)
    review_thr = float(review_threshold)

    if score >= buy_thr:
        if social == "HIGH_ALERT":
            return (
                "BUY",
                f"{ticker}: Path A.2 BUY — strong news ({score:.2f}) + HIGH_ALERT social. "
                f"{reasoning} [{news_source}] {news_headline}",
            )
        if confidence in {"high", "medium"} or score >= buy_thr + 0.08:
            return (
                "BUY",
                f"{ticker}: Path A.2 BUY — strong news catalyst (score={score:.2f}, conf={confidence}). "
                f"{reasoning} [{news_source}] {news_headline}",
            )
        return (
            "REVIEW",
            f"{ticker}: Path A.2 REVIEW — positive news ({score:.2f}) below auto-buy confidence. "
            f"[{news_source}] {news_headline}",
        )

    if score <= sell_thr:
        if social == "HIGH_ALERT" or confidence in {"high", "medium"} or score <= sell_thr - 0.08:
            return (
                "SELL",
                f"{ticker}: Path A.2 SELL — strong bearish news (score={score:.2f}). "
                f"{reasoning} [{news_source}] {news_headline}",
            )
        return (
            "REVIEW",
            f"{ticker}: Path A.2 REVIEW — bearish news ({score:.2f}) needs confirmation. "
            f"[{news_source}] {news_headline}",
        )

    if abs(score) >= review_thr:
        return (
            "REVIEW",
            f"{ticker}: Path A.2 REVIEW — moderate catalyst (score={score:.2f}). "
            f"[{news_source}] {news_headline}",
        )

    return (
        "LOG",
        f"{ticker}: Path A.2 LOG — weak news score ({score:.2f}). [{news_source}] {news_headline}",
    )


def _options_data_unreliable(
    options_data_quality: float | None,
    options_data_flags: list[str] | None,
    min_options_quality_to_trust: float,
) -> bool:
    """True when no_data likely means engine failure, not a thin options chain."""
    quality = float(options_data_quality if options_data_quality is not None else 0.0)
    flags = {str(flag).lower().strip() for flag in (options_data_flags or [])}
    if quality < min_options_quality_to_trust:
        return True
    return bool(flags.intersection({"invalid_auth_token", "client_error", "invalid_data_quality"}))


def _resolve_no_data_decision(
    preliminary_decision: str,
    preliminary_reason: str,
    news_score: float,
    no_data_policy: str,
    no_data_strong_news_threshold: float,
    options_score: float,
    audit_suffix: str,
) -> Tuple[str, str]:
    """Apply configured policy when options bias is no_data."""
    policy = str(no_data_policy or "block").lower().strip()
    if policy == "allow_news_only":
        return (
            preliminary_decision,
            preliminary_reason + f"{audit_suffix} | Options no_data: news+social only (no chain)",
        )
    if policy == "allow_strong_news" and abs(news_score) >= float(no_data_strong_news_threshold):
        return (
            preliminary_decision,
            preliminary_reason
            + (f"{audit_suffix} | Options no_data: strong news ({news_score:+.2f}) bypass"),
        )
    if policy == "allow_strong_news":
        return (
            "REVIEW",
            f"News {preliminary_decision} blocked: options no_data and news score "
            f"({news_score:+.2f}) below strong-news bypass ({no_data_strong_news_threshold:.2f}). "
            f"{preliminary_reason}",
        )
    return (
        "REVIEW",
        f"News {preliminary_decision} blocked: options no_data (score={options_score:.1f}). "
        f"{preliminary_reason}",
    )


def _apply_options_gate(
    preliminary_decision: str,
    preliminary_reason: str,
    news_score: float,
    options_bias: str | None,
    options_score: float | None,
    options_data_quality: float | None,
    options_data_flags: list[str] | None,
    min_options_score_bullish: float,
    max_options_score_bearish: float,
    require_confirmation_for_buy: bool,
    require_confirmation_for_sell: bool,
    no_data_policy: str = "block",
    no_data_strong_news_threshold: float = 0.75,
    min_options_quality_to_trust: float = 0.25,
) -> Tuple[str, str]:
    """Apply options confirmation gate after news-only preliminary decision."""
    bias = str(options_bias or "no_data").lower().strip()
    score = float(options_score if options_score is not None else 50.0)
    audit_suffix = f" | Options: bias={bias}, score={score:.1f}"

    if bias == "no_data" and preliminary_decision in {"BUY", "SELL"}:
        if _options_data_unreliable(options_data_quality, options_data_flags, min_options_quality_to_trust):
            return (
                "REVIEW",
                f"News {preliminary_decision} blocked: options unavailable "
                f"(quality={float(options_data_quality or 0.0):.2f}). {preliminary_reason}",
            )
        return _resolve_no_data_decision(
            preliminary_decision=preliminary_decision,
            preliminary_reason=preliminary_reason,
            news_score=news_score,
            no_data_policy=no_data_policy,
            no_data_strong_news_threshold=no_data_strong_news_threshold,
            options_score=score,
            audit_suffix=audit_suffix,
        )

    if preliminary_decision == "BUY":
        if not require_confirmation_for_buy:
            return preliminary_decision, preliminary_reason + audit_suffix
        if bias == "bullish" or (bias == "neutral" and score >= min_options_score_bullish):
            return (
                preliminary_decision,
                preliminary_reason + f" | Options confirmed (bias={bias}, score={score:.1f})",
            )
        if bias == "bearish":
            return (
                "REVIEW",
                f"News BUY blocked: options contradicts (bias={bias}, score={score:.1f}). {preliminary_reason}",
            )
        return (
            "REVIEW",
            f"News BUY: options unclear (bias={bias}, score={score:.1f}). {preliminary_reason}",
        )

    if preliminary_decision == "SELL":
        if not require_confirmation_for_sell:
            return preliminary_decision, preliminary_reason + audit_suffix
        if bias == "bearish" or (bias == "neutral" and score <= max_options_score_bearish):
            return (
                preliminary_decision,
                preliminary_reason + f" | Options confirmed (bias={bias}, score={score:.1f})",
            )
        if bias == "bullish":
            return (
                "REVIEW",
                f"News SELL blocked: options contradicts (bias={bias}, score={score:.1f}). {preliminary_reason}",
            )
        return (
            "REVIEW",
            f"News SELL: options unclear (bias={bias}, score={score:.1f}). {preliminary_reason}",
        )

    return preliminary_decision, preliminary_reason + audit_suffix


def _apply_path_b_override(
    decision: str,
    reason: str,
    options_bias: str | None,
    options_score: float | None,
    herd_urgency: float,
    signal_source: str,
    expiry_override_review: bool,
    expiry_buy_min_options_score: float,
    expiry_buy_min_urgency: float,
    options_data_quality: float | None,
    min_options_quality_to_trust: float,
) -> Tuple[str, str, str]:
    """
    Path B can upgrade REVIEW / act without news when options are urgent and directional.

    Only *proposes* BUY/SELL from options score + urgency. Lean-strength gate in
    decide_trade_action (post action_probs) is authoritative for Path B execute —
    override must not bypass a weak lean.

    Returns (decision, reason, signal_source).
    """
    source = str(signal_source or "news").lower().strip()
    bias = str(options_bias or "no_data").lower().strip()
    score = float(options_score if options_score is not None else 50.0)
    urgency = float(herd_urgency)
    quality = float(options_data_quality if options_data_quality is not None else 1.0)

    if not expiry_override_review:
        return decision, reason, source
    if quality < min_options_quality_to_trust or bias == "no_data":
        return decision, reason, source
    if urgency < expiry_buy_min_urgency:
        return decision, reason, source

    bullish_ok = bias == "bullish" and score >= expiry_buy_min_options_score
    bearish_ok = bias == "bearish" and score <= (100.0 - expiry_buy_min_options_score)

    if decision == "REVIEW" and bullish_ok:
        new_source = "both" if source == "news" else "expiry"
        return (
            "BUY",
            reason + f" | Path B override: expiry bullish+urgent (score={score:.1f}, urgency={urgency:.0f})",
            new_source,
        )
    if decision == "REVIEW" and bearish_ok:
        new_source = "both" if source == "news" else "expiry"
        return (
            "SELL",
            reason + f" | Path B override: expiry bearish+urgent (score={score:.1f}, urgency={urgency:.0f})",
            new_source,
        )
    if source == "expiry" and decision in {"LOG", "REVIEW"}:
        if bullish_ok:
            return "BUY", f"Path B expiry BUY (score={score:.1f}, urgency={urgency:.0f}). {reason}", "expiry"
        if bearish_ok:
            return "SELL", f"Path B expiry SELL (score={score:.1f}, urgency={urgency:.0f}). {reason}", "expiry"
    if decision in {"BUY", "SELL"} and source == "news" and (bullish_ok or bearish_ok):
        return decision, reason + " | Path A+B agree", "both"
    return decision, reason, source


def decide_trade_action(
    ticker: str,
    social_signal_level: str,
    claude_response: Dict[str, object],
    news_headline: str,
    news_source: str,
    buy_threshold: float = 0.5,
    sell_threshold: float = -0.5,
    require_social_signal: bool = True,
    options_bias: str | None = None,
    options_score: float | None = None,
    options_data_quality: float | None = None,
    options_data_flags: list[str] | None = None,
    options_enabled: bool = False,
    min_options_score_bullish: float = 60,
    max_options_score_bearish: float = 40,
    require_confirmation_for_buy: bool = True,
    require_confirmation_for_sell: bool = True,
    no_data_policy: str = "block",
    no_data_strong_news_threshold: float = 0.75,
    min_options_quality_to_trust: float = 0.25,
    signal_source: str = "news",
    relative_volume: float | None = None,
    dte: int | None = None,
    volume_oi_spike: float | None = None,
    instrument_hint: str | None = None,
    expiry_override_review: bool = True,
    expiry_buy_min_options_score: float = 65,
    expiry_buy_min_urgency: float = 60,
    options_features: Optional[Dict[str, Any]] = None,
    news_published_at: Any = None,
    setup_quality_score: float | None = None,
    settings: Optional[Dict[str, Any]] = None,
    apply_odte_layer: bool = True,
) -> DecisionResult:
    """
    Apply decision rules to produce BUY/SELL/REVIEW/LOG with meta.

    Optional 0DTE layer (``apply_odte_layer``) applies news freshness decay,
    liquidity/setup gates, conflict-only REVIEW, and code-derived confidence.

    Output:
    - Tuple of (decision, reason_string, meta_dict).
    """
    meta = _empty_meta()
    meta["signal_source"] = str(signal_source or "news")

    # Path B-only entries may have no news; synthesize neutral Claude payload.
    if not claude_response:
        claude_response = {"score": 0.0, "confidence": "low", "reasoning": "No news scored."}

    # News freshness decay (does not mutate caller's Claude payload).
    raw_news_score = float(claude_response.get("score", 0.0))
    decayed_news_score = raw_news_score
    decay_info: Dict[str, Any] = {
        "raw_score": raw_news_score,
        "decayed_score": raw_news_score,
        "age_minutes": 0.0,
        "decay_multiplier": 1.0,
    }
    if apply_odte_layer and settings is not None:
        try:
            from agent.news_decay import apply_news_decay

            decay_info = apply_news_decay(raw_news_score, news_published_at, settings)
            decayed_news_score = float(decay_info["decayed_score"])
            claude_response = dict(claude_response)
            claude_response["score"] = decayed_news_score
        except Exception:
            pass

    source_key = str(meta["signal_source"] or "news").lower().strip()
    catalyst_cfg = (settings or {}).get("news_catalyst") or {}
    if source_key == "news_catalyst":
        preliminary_decision, preliminary_reason = _decide_news_catalyst(
            ticker=ticker,
            social_signal_level=social_signal_level,
            claude_response=claude_response,
            news_headline=news_headline,
            news_source=news_source,
            buy_threshold=float(catalyst_cfg.get("buy_threshold", buy_threshold)),
            sell_threshold=float(catalyst_cfg.get("sell_threshold", sell_threshold)),
            review_threshold=float(catalyst_cfg.get("review_threshold", 0.35)),
        )
    else:
        preliminary_decision, preliminary_reason = _decide_news_only(
            ticker=ticker,
            social_signal_level=social_signal_level,
            claude_response=claude_response,
            news_headline=news_headline,
            news_source=news_source,
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
            require_social_signal=require_social_signal
            and source_key not in {"expiry", "news_catalyst"},
        )

    news_score = float(claude_response.get("score", 0.0))
    if options_enabled:
        decision, reason = _apply_options_gate(
            preliminary_decision=preliminary_decision,
            preliminary_reason=preliminary_reason,
            news_score=news_score,
            options_bias=options_bias,
            options_score=options_score,
            options_data_quality=options_data_quality,
            options_data_flags=options_data_flags,
            min_options_score_bullish=min_options_score_bullish,
            max_options_score_bearish=max_options_score_bearish,
            require_confirmation_for_buy=require_confirmation_for_buy,
            require_confirmation_for_sell=require_confirmation_for_sell,
            no_data_policy=no_data_policy,
            no_data_strong_news_threshold=no_data_strong_news_threshold,
            min_options_quality_to_trust=min_options_quality_to_trust,
        )
    else:
        decision, reason = preliminary_decision, preliminary_reason

    social_score = social_score_from_level(social_signal_level)
    herd_urgency = compute_herd_urgency(
        relative_volume=relative_volume,
        social_score=social_score,
        dte=dte,
        volume_oi_spike=volume_oi_spike,
    )

    decision, reason, source = _apply_path_b_override(
        decision=decision,
        reason=reason,
        options_bias=options_bias,
        options_score=options_score,
        herd_urgency=herd_urgency,
        signal_source=meta["signal_source"],
        expiry_override_review=expiry_override_review,
        expiry_buy_min_options_score=expiry_buy_min_options_score,
        expiry_buy_min_urgency=expiry_buy_min_urgency,
        options_data_quality=options_data_quality,
        min_options_quality_to_trust=min_options_quality_to_trust,
    )
    if source_key == "news_catalyst":
        # Keep Path A.2 thesis news-driven; do not morph into Path B expiry override.
        meta["signal_source"] = "news_catalyst"
    else:
        meta["signal_source"] = source

    # 0DTE post-layer: conflict-only REVIEW, liquidity/setup gates, confidence.
    if apply_odte_layer and settings is not None:
        try:
            from agent.odte_decision import apply_odte_decision_policy

            decision, reason, odte_meta = apply_odte_decision_policy(
                decision=decision,
                reason=reason,
                decayed_news_score=decayed_news_score,
                buy_threshold=buy_threshold,
                sell_threshold=sell_threshold,
                options_bias=options_bias,
                options_score=options_score,
                feature_values=options_features,
                setup_quality_score=setup_quality_score,
                settings=settings,
                data_quality=float(options_data_quality if options_data_quality is not None else 1.0),
                signal_source=str(meta.get("signal_source") or signal_source or "news"),
            )
            meta.update(odte_meta)
            if odte_meta.get("review_reason_code_odte"):
                meta["review_reason_code"] = odte_meta["review_reason_code_odte"]
        except Exception as error:
            meta["odte_layer_error"] = str(error)

    meta["news_decay"] = decay_info

    action_probs = compute_action_probs(
        news_score=news_score,
        social_signal_level=social_signal_level,
        options_bias=options_bias,
        options_score=options_score,
        herd_urgency=herd_urgency,
        decision=decision,
    )
    lean = max(action_probs, key=action_probs.get)
    lean_pct = int(round(action_probs[lean] * 100))
    wait_pct = int(round(float(action_probs.get("WAIT", 0.0)) * 100))

    # Path B lean-strength gate (independent of agreement confidence).
    # Motivating bug: Path B override could stamp BUY/SELL while lean was still
    # WAIT-heavy / coin-flip; those printed as "actionable" but were noise.
    # Require: lean direction matches decision, lean_pct ≥ min, and margin over WAIT.
    source_final = str(meta.get("signal_source") or signal_source or "news").lower().strip()
    if (
        source_final in {"expiry", "both"}
        and str(decision).upper() in {"BUY", "SELL"}
    ):
        exec_cfg = (settings or {}).get("execution") or {}
        min_lean = int(exec_cfg.get("min_lean_pct_for_path_b_execute", 60))
        min_over_wait = int(exec_cfg.get("min_lean_over_wait_pct", 10))
        decision_u = str(decision).upper()
        lean_u = str(lean).upper()
        lean_ok = lean_u == decision_u
        lean_strong = lean_pct >= min_lean
        lean_beats_wait = (lean_pct - wait_pct) >= min_over_wait
        if not (lean_ok and lean_strong and lean_beats_wait):
            decision = "LOG"
            reason = (
                f"{reason} | weak_lean (lean={lean_u} {lean_pct}% vs need "
                f"{decision_u}≥{min_lean} and ≥WAIT+{min_over_wait}; WAIT={wait_pct}%) → LOG"
            )
            meta["review_reason_code"] = "weak_lean"
            meta["decision_reason_code"] = "weak_lean"
            meta["lean_gate"] = {
                "passed": False,
                "lean": lean_u,
                "lean_pct": lean_pct,
                "wait_pct": wait_pct,
                "min_lean_pct": min_lean,
                "min_over_wait_pct": min_over_wait,
                "direction_ok": lean_ok,
                "strength_ok": lean_strong,
                "margin_ok": lean_beats_wait,
            }
        else:
            meta["lean_gate"] = {
                "passed": True,
                "lean": lean_u,
                "lean_pct": lean_pct,
                "wait_pct": wait_pct,
                "min_lean_pct": min_lean,
                "min_over_wait_pct": min_over_wait,
            }

    hint = resolve_instrument_hint(
        decision=decision,
        options_bias=options_bias,
        options_score=options_score,
        herd_urgency=herd_urgency,
        advisor_hint=instrument_hint,
        liquidity_reject=float((options_features or {}).get("liquidity_reject", 0.0) or 0.0) >= 1.0,
        equity_fallback=bool(meta.get("equity_fallback_liquidity")),
    )

    review_code = meta.get("review_reason_code") or meta.get("review_reason_code_odte") or _review_reason_code(
        decision, preliminary_decision, options_bias, social_signal_level
    )
    conf_pct = meta.get("confidence_pct")
    if conf_pct is None:
        conf_pct = lean_pct
    conf_label = meta.get("confidence_label") or (
        "high" if conf_pct >= 70 else ("medium" if conf_pct >= 40 else "low")
    )
    agreement_confidence = meta.get("agreement_confidence")
    if agreement_confidence is None and meta.get("confidence_pct") is not None:
        agreement_confidence = meta.get("confidence_pct")
    n_dir = meta.get("n_dir")
    if n_dir is None:
        n_dir = meta.get("n_directional")
    if n_dir is None:
        detail = meta.get("agreement_detail") or {}
        n_dir = detail.get("n_directional")

    meta.update(
        {
            "action_probs": action_probs,
            "lean": lean,
            "lean_pct": lean_pct,
            "instrument_hint": hint,
            "review_reason_code": review_code,
            "decision_reason_code": meta.get("decision_reason_code") or review_code,
            "herd_urgency": herd_urgency,
            "relative_volume": relative_volume,
            "dte": dte,
            "confidence_pct": conf_pct,
            "confidence_label": conf_label,
            "agreement_confidence": agreement_confidence,
            "n_dir": n_dir,
            "n_directional": n_dir,
            "options_features": options_features or {},
        }
    )

    if decision == "REVIEW":
        reason = (
            f"{reason} | Lean {lean} {lean_pct}% "
            f"(BUY {action_probs['BUY']*100:.0f}% / SELL {action_probs['SELL']*100:.0f}% / "
            f"WAIT {action_probs['WAIT']*100:.0f}% / AVOID {action_probs['AVOID']*100:.0f}%)"
        )

    return decision, reason, meta
