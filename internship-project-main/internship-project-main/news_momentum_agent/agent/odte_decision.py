"""0DTE / near-expiry decision fusion: factor agreement, conflict, confidence.

Why this module exists
----------------------
Early paper trades showed that a BUY/SELL *lean* could look convincing while
only one or two features agreed. Confidence used to track agreement too loosely,
so thin vote sets cleared execution bars and produced real losses.

This layer builds **independent directional votes**, measures agreement, then
derives **code confidence** (not Claude-invented) with a **sample-size penalty**:
``n_dir=2`` cannot clear Path B's ~65 bar on agreement alone.

Vote semantics: +1 bullish / -1 bearish / 0 neutral (uncounted). GEX is regime
only and does not vote. REVIEW is for genuine conflicts when configured;
medium confidence with agreement can still resolve to BUY/SELL/LOG on its own.

Merge notes for stocks/futures
------------------------------
  - **Core reusable layer** — keep this module for any multi-factor intraday system.
  - **Options-specific votes:** GEX regime (non-directional), options_score bias,
    liquidity/setup quality gates tied to option chains.
  - No state files; pure decision fusion from upstream feature dicts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


SignalLean = int  # -1, 0, +1


def _lean_from_score(score: float, bull: float, bear: float) -> SignalLean:
    if score >= bull:
        return 1
    if score <= bear:
        return -1
    return 0


def _lean_from_news(decayed_score: float, buy_thr: float, sell_thr: float) -> SignalLean:
    if decayed_score >= buy_thr:
        return 1
    if decayed_score <= sell_thr:
        return -1
    return 0


def extract_independent_signals(
    *,
    decayed_news_score: float,
    buy_threshold: float,
    sell_threshold: float,
    options_bias: str | None,
    options_score: float | None,
    feature_values: Optional[Dict[str, Any]] = None,
    setup_quality_score: float | None = None,
    min_options_bullish: float = 60.0,
    max_options_bearish: float = 40.0,
) -> Dict[str, SignalLean]:
    """
    Build named independent leans for agreement / conflict math.

    Only keys with lean != 0 count toward ``n_directional`` / agreement.
    Path B often has news=0, so practical voters are options + max_pain +
    flow_trend when available — which is why sample_factor matters there.
    """
    feats = feature_values or {}
    signals: Dict[str, SignalLean] = {
        "news": _lean_from_news(decayed_news_score, buy_threshold, sell_threshold),
    }

    bias = str(options_bias or "no_data").lower().strip()
    opt = float(options_score) if options_score is not None else 50.0
    if bias == "bullish" or opt >= min_options_bullish:
        signals["options"] = 1
    elif bias == "bearish" or opt <= max_options_bearish:
        signals["options"] = -1
    elif bias == "no_data":
        pass
    else:
        signals["options"] = 0

    # Flow trend (if available)
    if float(feats.get("flow_trend_available", 0.0) or 0.0) >= 1.0:
        ft = float(feats.get("flow_trend_score", 0.5))
        if ft >= 0.58:
            signals["flow_trend"] = 1
        elif ft <= 0.42:
            signals["flow_trend"] = -1
        else:
            signals["flow_trend"] = 0

    # Max pain magnet relative to spot
    if float(feats.get("max_pain_available", 0.0) or 0.0) >= 1.0:
        dist = float(feats.get("max_pain_distance_pct", 0.0))
        if dist >= 0.35:
            signals["max_pain"] = 1
        elif dist <= -0.35:
            signals["max_pain"] = -1
        else:
            signals["max_pain"] = 0

    # GEX is a regime signal, not a directional lean — exposed separately.
    if setup_quality_score is not None:
        sq = float(setup_quality_score)
        if sq >= 70:
            signals["screener"] = 0  # quality only; does not vote direction
        # intentionally not directional

    return signals


def compute_agreement(signals: Dict[str, SignalLean]) -> Dict[str, Any]:
    """Return agreement ratio and dominant lean among non-zero votes."""
    votes = [(name, lean) for name, lean in signals.items() if lean != 0]
    if not votes:
        return {
            "agreement": 0.0,
            "dominant_lean": 0,
            "bullish_votes": 0,
            "bearish_votes": 0,
            "n_directional": 0,
            "voters": [],
        }
    bull = sum(1 for _, lean in votes if lean > 0)
    bear = sum(1 for _, lean in votes if lean < 0)
    dominant = 1 if bull > bear else (-1 if bear > bull else 0)
    agreeing = max(bull, bear)
    agreement = agreeing / len(votes) if votes else 0.0
    return {
        "agreement": float(agreement),
        "dominant_lean": dominant,
        "bullish_votes": bull,
        "bearish_votes": bear,
        "n_directional": len(votes),
        "voters": votes,
    }


def detect_conflicts(
    signals: Dict[str, SignalLean],
    *,
    feature_values: Optional[Dict[str, Any]] = None,
    min_conflict_sources: int = 2,
    conflict_score_gap: float = 0.0,
) -> Tuple[bool, List[str]]:
    """
    True when independent sources actively disagree.

    Also flags GEX-vs-flow conflict: positive GEX (pin) vs strong directional
    flow trend breakout lean.
    """
    reasons: List[str] = []
    bull = [n for n, lean in signals.items() if lean > 0]
    bear = [n for n, lean in signals.items() if lean < 0]
    if bull and bear and (len(bull) + len(bear)) >= min_conflict_sources:
        reasons.append(f"directional_conflict bull={bull} bear={bear}")

    feats = feature_values or {}
    if float(feats.get("gex_available", 0.0) or 0.0) >= 1.0:
        gex = float(feats.get("gex_regime_code", 0.0))
        flow = signals.get("flow_trend", 0)
        # Positive GEX + strong directional flow = pin vs breakout tension
        if gex > 0.5 and flow != 0:
            reasons.append("gex_pin_vs_flow_trend")
        # Max pain magnet opposite to options lean
        mp = signals.get("max_pain", 0)
        opt = signals.get("options", 0)
        if mp != 0 and opt != 0 and mp != opt:
            reasons.append("max_pain_vs_options")

    # conflict_score_gap reserved for future magnitude checks
    _ = conflict_score_gap
    hard = any(
        r.startswith("directional_conflict") or r.startswith("max_pain_vs_options") for r in reasons
    )
    # gex_pin_vs_flow alone is a soft conflict — still REVIEW-worthy when configured
    if reasons and not hard:
        hard = "gex_pin_vs_flow_trend" in reasons and min_conflict_sources <= 2
    return bool(reasons) and hard, reasons


def confidence_from_agreement(
    agreement: float,
    *,
    data_quality: float = 1.0,
    tod_multiplier: float = 1.0,
    regime_multiplier: float = 1.0,
    iv_rank: float = 0.5,
    n_directional: int = 0,
) -> Tuple[float, str]:
    """
    Code-derived confidence 0–100. Claude should justify this, not invent it.

    Motivating bug: perfect agreement of two thin signals looked like "high
    confidence" and cleared Path B. Sample-size factor
    ``min(1.0, max(0, n_dir - 1) / 3.0)`` so n_dir=2 caps ~33% even at
    agreement=1.0 (cannot clear Path B's 65 bar on agreement alone).

    Late-day tod_multiplier > 1 raises the bar (effective confidence shrinks).
    """
    iv_penalty = max(0.0, float(iv_rank) - 0.5)  # 0..0.5
    n_dir = int(n_directional or 0)
    # Discount small samples: n_dir=1 → 0, n_dir=2 → 0.33, n_dir=3 → 0.67, n_dir≥4 → 1.0
    sample_factor = min(1.0, max(0.0, n_dir - 1) / 3.0) if n_dir else 0.0
    raw = 100.0 * float(agreement) * float(data_quality) * float(regime_multiplier) * sample_factor
    raw *= 1.0 - 0.3 * iv_penalty
    # Higher tod multiplier → require more conviction → lower reported confidence
    if tod_multiplier > 1.0:
        raw /= tod_multiplier
    conf = max(0.0, min(100.0, raw))
    if conf >= 70:
        label = "high"
    elif conf >= 40:
        label = "medium"
    else:
        label = "low"
    return conf, label


def apply_odte_decision_policy(
    *,
    decision: str,
    reason: str,
    decayed_news_score: float,
    buy_threshold: float,
    sell_threshold: float,
    options_bias: str | None,
    options_score: float | None,
    feature_values: Optional[Dict[str, Any]],
    setup_quality_score: float | None,
    settings: Optional[Dict[str, Any]],
    data_quality: float = 1.0,
    signal_source: str = "news",
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Post-process a preliminary decision with conflict / confidence / liquidity rules.

    High-level order:
      1. Liquidity floor fail → LOG (``liquidity_reject``). Thresholds unchanged;
         detail strings are observation-only (wide spreads / no chain debugging).
      2. Setup-quality soft gate when configured.
      3. Force-REVIEW / true signal conflict → REVIEW.
      4. Non-conflict REVIEW may auto-resolve only if confidence, options clarity,
         and (for expiry) n_dir meet Path bars — else LOG.
      5. Final floor: any BUY/SELL still blocked by low confidence / unclear options.

    Lean strength is enforced separately in ``decision_engine`` (Path B).
    Confidence and lean are **independent** gates — both must pass to trade.

    Returns (decision, reason, odte_meta).
    """
    cfg = (settings or {}).get("execution") or {}
    risk_cfg = (settings or {}).get("risk") or {}
    feats = feature_values or {}
    source = str(signal_source or "news").lower().strip()

    review_only_on_conflict = bool(cfg.get("review_only_on_conflict", True))
    force_review_all = bool(cfg.get("force_review_all", False)) or bool(
        risk_cfg.get("force_review_all", False)
    )
    min_conflict_sources = int(cfg.get("conflict_min_sources", 2))
    conflict_gap = float(cfg.get("conflict_score_gap", 0.0))
    min_conf_buy = float(cfg.get("min_confidence_for_action", 40.0))
    # Path B (expiry-only) needs a higher bar — seed ETFs otherwise spam trades.
    if source in {"expiry", "both"}:
        min_conf_buy = float(cfg.get("min_confidence_for_path_b", max(min_conf_buy, 65.0)))
    min_setup = float((settings or {}).get("odte_screener", {}).get("min_setup_score", 0.0))
    require_options_for_resolve = bool(cfg.get("require_options_bias_to_autoresolve", True))

    signals = extract_independent_signals(
        decayed_news_score=decayed_news_score,
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
        options_bias=options_bias,
        options_score=options_score,
        feature_values=feats,
        setup_quality_score=setup_quality_score,
    )
    agreement_info = compute_agreement(signals)
    conflict, conflict_reasons = detect_conflicts(
        signals,
        feature_values=feats,
        min_conflict_sources=min_conflict_sources,
        conflict_score_gap=conflict_gap,
    )

    tod_mult = float(feats.get("tod_confidence_multiplier", 1.0) or 1.0)
    regime_mult = float(feats.get("regime_trust_multiplier", 1.0) or 1.0)
    iv_rank = float(feats.get("iv_rank", 0.5) or 0.5)
    conf, conf_label = confidence_from_agreement(
        float(agreement_info["agreement"]),
        data_quality=data_quality,
        tod_multiplier=tod_mult,
        regime_multiplier=regime_mult,
        iv_rank=iv_rank,
        n_directional=int(agreement_info["n_directional"]),
    )

    # Late day: raise effective bar
    effective_min_conf = min_conf_buy * tod_mult

    new_decision = str(decision).upper().strip()
    new_reason = reason
    review_reason = ""

    # Hard liquidity reject (thresholds unchanged — detail is observation only).
    # Motivating finding: many Path A catalysts die here with primary codes like
    # no_listed_chain / spread_too_wide (often 46–60%+) / oi_below_min — not a
    # soft downgrade. See options_engine.features_liquidity.
    liquidity_detail = ""
    equity_fallback_liquidity = False
    if float(feats.get("liquidity_reject", 0.0) or 0.0) >= 1.0:
        trading_cfg = (settings or {}).get("trading") or {}
        prefer_equity = bool(trading_cfg.get("prefer_equity_on_liquidity_reject", True))
        min_news = float(trading_cfg.get("equity_fallback_min_news_score", 0.5))
        decision_u = str(decision).upper().strip()
        strong_catalyst = abs(float(decayed_news_score)) >= min_news
        try:
            from options_engine.features_liquidity import format_liquidity_reject_detail

            liquidity_detail = str(
                feats.get("liquidity_reject_detail") or format_liquidity_reject_detail(feats) or ""
            ).strip()
        except Exception:
            liquidity_detail = str(feats.get("liquidity_reject_detail") or "").strip()
            if not liquidity_detail:
                primary = str(feats.get("liquidity_reject_primary") or "").strip()
                spread = feats.get("atm_median_spread_pct")
                min_oi = feats.get("atm_min_oi")
                max_spread = feats.get("liquidity_max_spread_pct")
                min_req = feats.get("liquidity_min_oi_required")
                bits = [primary or "liquidity_reject"]
                if spread is not None and max_spread is not None:
                    bits.append(f"spread={float(spread):.1%} (max allowed {float(max_spread):.1%})")
                if min_oi is not None and min_req is not None:
                    bits.append(f"OI={float(min_oi):.0f} (min required {float(min_req):.0f})")
                liquidity_detail = " | ".join(bits)

        if prefer_equity and strong_catalyst and decision_u in {"BUY", "SELL", "REVIEW"}:
            equity_fallback_liquidity = True
            new_decision = "REVIEW" if decision_u in {"BUY", "SELL"} else decision_u
            detail_bit = liquidity_detail or "spread/OI"
            new_reason = (
                reason
                + f" | equity fallback — options illiquid ({detail_bit}); routing to stock"
            )
            review_reason = "equity_fallback_liquidity"
        else:
            new_decision = "LOG"
            try:
                from agent.market_session import options_horizon_label

                horizon = options_horizon_label(settings)
            except Exception:
                horizon = "near-expiry"
            if liquidity_detail:
                new_reason = reason + f" | {horizon} liquidity floor failed ({liquidity_detail})"
            else:
                new_reason = reason + f" | {horizon} liquidity floor failed (spread/OI)"
            review_reason = "liquidity_reject"

    # Screener gate (soft): below threshold → LOG unless already LOG
    if (
        setup_quality_score is not None
        and min_setup > 0
        and float(setup_quality_score) < min_setup
        and new_decision in {"BUY", "SELL", "REVIEW"}
    ):
        new_decision = "LOG"
        new_reason = reason + f" | setup quality {setup_quality_score:.0f} < min {min_setup:.0f}"
        review_reason = "setup_quality_gate"

    if force_review_all and new_decision in {"BUY", "SELL"}:
        new_decision = "REVIEW"
        new_reason = reason + " | kill-switch force_review_all"
        review_reason = "force_review_all"
    elif conflict and new_decision != "LOG":
        new_decision = "REVIEW"
        new_reason = reason + " | signal conflict: " + "; ".join(conflict_reasons)
        review_reason = "signal_conflict"
    elif review_only_on_conflict and new_decision == "REVIEW" and not conflict and not equity_fallback_liquidity:
        # Resolve non-conflict REVIEW using agreement + confidence.
        # Do NOT trade off max-pain / flow alone when options bias is neutral —
        # that caused SPY/QQQ seed spam with lean WAIT.
        dominant = int(agreement_info["dominant_lean"])
        opt_lean = int(signals.get("options", 0) or 0)
        bias = str(options_bias or "no_data").lower().strip()
        options_clear = bias in {"bullish", "bearish"} and opt_lean != 0
        options_agrees = opt_lean != 0 and opt_lean == dominant
        n_dir = int(agreement_info["n_directional"])

        can_autoresolve = conf >= effective_min_conf and dominant != 0
        if require_options_for_resolve:
            can_autoresolve = can_autoresolve and options_clear and options_agrees
        if source == "expiry":
            # Expiry path: need clear options bias + at least 2 directional votes.
            can_autoresolve = can_autoresolve and options_clear and n_dir >= 2

        if can_autoresolve and dominant == 1:
            new_decision = "BUY"
            new_reason = reason + (
                f" | auto-resolved REVIEW→BUY (agreement={agreement_info['agreement']:.2f}, conf={conf:.0f})"
            )
        elif can_autoresolve and dominant == -1:
            new_decision = "SELL"
            new_reason = reason + (
                f" | auto-resolved REVIEW→SELL (agreement={agreement_info['agreement']:.2f}, conf={conf:.0f})"
            )
        elif conf < effective_min_conf or (require_options_for_resolve and not options_clear):
            new_decision = "LOG"
            new_reason = reason + (
                f" | weak/unclear Path B setup (conf={conf:.0f}, options={bias}) → LOG"
            )
            review_reason = "low_confidence" if conf < effective_min_conf else "options_not_clear"
        elif dominant == 0:
            new_decision = "LOG"
            new_reason = reason + " | no directional agreement → LOG"
            review_reason = "no_lean"
        else:
            # Keep REVIEW only when genuinely conflicted/unclear but not LOG-worthy.
            review_reason = "ambiguous_setup"

    # Final floor: Path B override (and any other path) can emit BUY/SELL without
    # passing the REVIEW autoresolve branch — enforce confidence + options clarity here.
    if new_decision in {"BUY", "SELL"}:
        bias = str(options_bias or "no_data").lower().strip()
        opt_lean = int(signals.get("options", 0) or 0)
        options_clear = bias in {"bullish", "bearish"} and opt_lean != 0
        n_dir = int(agreement_info["n_directional"])
        block = False
        if conf < effective_min_conf:
            block = True
            review_reason = review_reason or "low_confidence"
        elif require_options_for_resolve and not options_clear:
            block = True
            review_reason = review_reason or "options_not_clear"
        elif source == "expiry" and (not options_clear or n_dir < 2):
            block = True
            review_reason = review_reason or "low_confidence"
        if block:
            new_decision = "LOG"
            new_reason = reason + (
                f" | actionable blocked (conf={conf:.0f}, min={effective_min_conf:.0f}, "
                f"options={bias}, n_dir={n_dir}) → LOG"
            )

    gex_code = float(feats.get("gex_regime_code", 0.0) or 0.0)
    gex_label = "positive" if gex_code > 0.5 else ("negative" if gex_code < -0.5 else "neutral")

    n_dir_out = int(agreement_info["n_directional"])
    conf_rounded = round(conf, 1)
    meta = {
        "odte_signals": signals,
        "agreement": agreement_info["agreement"],
        "agreement_detail": agreement_info,
        "conflict": conflict,
        "conflict_reasons": conflict_reasons,
        "confidence_pct": conf_rounded,
        "agreement_confidence": conf_rounded,
        "n_dir": n_dir_out,
        "n_directional": n_dir_out,
        "confidence_label": conf_label,
        "gex_regime": gex_label,
        "liquidity_ok": float(feats.get("liquidity_ok", 1.0) or 1.0) >= 1.0,
        "tod_is_late": float(feats.get("tod_is_late", 0.0) or 0.0) >= 1.0,
        "regime_risk_off": float(feats.get("regime_risk_off", 0.0) or 0.0) >= 1.0,
        "decayed_news_score": decayed_news_score,
        "setup_quality_score": setup_quality_score,
        "review_reason_code_odte": review_reason,
        "liquidity_reject_primary": str(feats.get("liquidity_reject_primary") or "") or None,
        "liquidity_reject_detail": liquidity_detail or str(feats.get("liquidity_reject_detail") or "") or None,
        "equity_fallback_liquidity": equity_fallback_liquidity,
        "liquidity_fail_counts": feats.get("liquidity_fail_counts")
        if isinstance(feats.get("liquidity_fail_counts"), dict)
        else None,
        "factor_snapshot": {
            "gex_regime": gex_label,
            "max_pain_distance_pct": feats.get("max_pain_distance_pct"),
            "oi_wall_strike": feats.get("oi_wall_strike"),
            "iv_rank": feats.get("iv_rank"),
            "flow_trend_score": feats.get("flow_trend_score"),
            "atm_median_spread_pct": feats.get("atm_median_spread_pct"),
            "atm_min_oi": feats.get("atm_min_oi"),
            "atm_max_oi": feats.get("atm_max_oi"),
            "atm_contract_count": feats.get("atm_contract_count"),
            "atm_max_volume": feats.get("atm_max_volume"),
            "liquidity_max_spread_pct": feats.get("liquidity_max_spread_pct"),
            "liquidity_min_oi_required": feats.get("liquidity_min_oi_required"),
            "liquidity_nearest_dte": feats.get("liquidity_nearest_dte"),
            "liquidity_reject_primary": feats.get("liquidity_reject_primary"),
            "liquidity_reject_detail": feats.get("liquidity_reject_detail") or liquidity_detail or None,
            "vix_level": feats.get("vix_level"),
            "tod_theta_remaining_frac": feats.get("tod_theta_remaining_frac"),
        },
    }
    return new_decision, new_reason, meta
