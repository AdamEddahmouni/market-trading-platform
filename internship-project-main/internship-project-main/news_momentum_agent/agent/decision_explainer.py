"""Build plain-English trade decision explanations (why / expect / confidence).

Pipeline role
-------------
Called from ``paper_trader.append_paper_trade_entry`` to assemble a decision
card for dashboard, Telegram, and JSON logs. Combines rule-based copy from
news/options/herd context with optional Claude advisor text when present.

``format_explanation_text`` flattens the card to multi-line prose.

Merge notes: fully reusable presentation layer; instrument labels (0DTE call/put)
are options-specific but the card schema works for stock/futures decisions too.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _pct(probs: Dict[str, Any], key: str) -> int:
    try:
        return int(round(float(probs.get(key, 0.0)) * 100))
    except Exception:
        return 0


def _confidence_from_lean(lean_pct: int, decision: str) -> tuple[str, int]:
    decision_u = str(decision).upper().strip()
    pct = int(lean_pct or 0)
    if decision_u in {"BUY", "SELL"}:
        if pct >= 65:
            return "high", pct
        if pct >= 50:
            return "medium", pct
        return "medium", max(pct, 50)
    if pct >= 60:
        return "medium", pct
    return "low", pct


def _instrument_label(instrument_hint: str, dte: int | None, decision: str) -> str:
    hint = str(instrument_hint or "stock").lower().strip()
    decision_u = str(decision).upper().strip()
    if hint not in {"call", "put"} and decision_u in {"BUY", "SELL"}:
        hint = "call" if decision_u == "BUY" else "put"
    if hint in {"call", "put"}:
        dte_bit = "0DTE ATM" if dte is not None and int(dte) == 0 else (
            f"{int(dte)}-DTE ATM" if dte is not None and int(dte) >= 0 else "ATM"
        )
        return f"{dte_bit} {hint}"
    return "stock"


def build_decision_explanation(
    *,
    ticker: str,
    decision: str,
    reason: str = "",
    instrument_hint: str = "stock",
    action_probs: Optional[Dict[str, Any]] = None,
    lean: str = "WAIT",
    lean_pct: int = 0,
    signal_source: str = "news",
    herd_stage: str = "",
    quadrant: str = "",
    news_score: float | None = None,
    news_headline: str = "",
    news_confidence: str = "",
    options_bias: str | None = None,
    options_score: float | None = None,
    options_reasoning: str = "",
    dte: int | None = None,
    max_oi_strike: float | None = None,
    relative_volume: float | None = None,
    advisor: Optional[Dict[str, Any]] = None,
    exits: Optional[Dict[str, Any]] = None,
    odte_meta: Optional[Dict[str, Any]] = None,
    in_depth_rationale: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Assemble a decision card the dashboard / Telegram / logs can show.

    Always rule-based at minimum; merges Claude advisor text when present.
    """
    probs = action_probs or {}
    decision_u = str(decision).upper().strip()
    source = str(signal_source or "news").lower().strip()
    hint = str(instrument_hint or "stock").lower().strip()
    conf_label, conf_pct = _confidence_from_lean(int(lean_pct or 0), decision_u)
    odte = odte_meta or {}
    if odte.get("confidence_pct") is not None:
        try:
            conf_pct = int(round(float(odte["confidence_pct"])))
            conf_label = str(odte.get("confidence_label") or conf_label)
        except Exception:
            pass
    if news_confidence and source in {"news", "both"}:
        news_c = str(news_confidence).lower().strip()
        if news_c in {"high", "medium", "low"} and decision_u in {"BUY", "SELL"}:
            # Blend: news label floors low if Claude is unsure.
            order = {"low": 0, "medium": 1, "high": 2}
            if order.get(news_c, 0) < order.get(conf_label, 1):
                conf_label = news_c

    instrument = _instrument_label(hint, dte, decision_u)
    buy_pct = _pct(probs, "BUY")
    sell_pct = _pct(probs, "SELL")
    wait_pct = _pct(probs, "WAIT")

    why_parts: list[str] = []
    if source in {"expiry", "both"} or (dte is not None and int(dte) == 0):
        why_parts.append(
            f"Path B options positioning on {ticker}"
            + (f" with nearest expiry in {int(dte)} day(s)" if dte is not None else "")
            + "."
        )
    if source in {"news", "both"} and news_headline:
        why_parts.append(f"News catalyst: {news_headline[:140].rstrip('.')}.")
    if news_score is not None and abs(float(news_score)) >= 0.01 and source != "expiry":
        why_parts.append(f"Claude news score {float(news_score):+.2f} ({news_confidence or 'n/a'} confidence).")
    if options_bias:
        score_txt = f"{float(options_score):.0f}" if options_score is not None else "n/a"
        why_parts.append(f"Options confirmation is {options_bias} (score {score_txt}/100).")
    if options_reasoning:
        why_parts.append(str(options_reasoning)[:160].rstrip(".") + ".")
    if herd_stage:
        why_parts.append(f"Herd stage: {herd_stage}" + (f" · quadrant {quadrant}" if quadrant else "") + ".")
    if relative_volume is not None:
        why_parts.append(f"Relative volume {float(relative_volume):.1f}x.")
    if max_oi_strike is not None:
        why_parts.append(f"Heavy open interest clustered near strike {float(max_oi_strike):.2f}.")
    # Near-expiry / through-Friday factor card fields
    if odte.get("gex_regime"):
        why_parts.append(f"GEX regime: {odte['gex_regime']}.")
    snap = odte.get("factor_snapshot") or {}
    if snap.get("max_pain_distance_pct") is not None:
        why_parts.append(f"Max-pain distance {float(snap['max_pain_distance_pct']):+.2f}% from spot.")
    if snap.get("iv_rank") is not None:
        why_parts.append(f"IV rank {float(snap['iv_rank']):.2f}.")
    if snap.get("flow_trend_score") is not None:
        why_parts.append(f"Flow-trend score {float(snap['flow_trend_score']):.2f}.")
    if odte.get("liquidity_ok") is False:
        why_parts.append("Liquidity floor failed.")
    elif odte.get("liquidity_ok") is True:
        why_parts.append("Liquidity floor passed.")
    if odte.get("setup_quality_score") is not None:
        why_parts.append(f"Setup quality {float(odte['setup_quality_score']):.0f}/100.")
    if odte.get("conflict"):
        why_parts.append("Signal conflict: " + "; ".join(odte.get("conflict_reasons") or []) + ".")
    if reason and reason not in " ".join(why_parts):
        why_parts.append(str(reason)[:200].rstrip(".") + ".")
    why = " ".join(why_parts) if why_parts else (reason or "Signal rules fired.")
    if in_depth_rationale and in_depth_rationale.get("reasoning"):
        why = str(in_depth_rationale["reasoning"])

    exits_cfg = exits or {}
    tp = float(exits_cfg.get("take_profit_pct", 0.40))
    sl = float(exits_cfg.get("stop_loss_pct", 0.30))
    eod = str(exits_cfg.get("eod_flatten_et", "15:45"))
    is_option = hint in {"call", "put"} or str(instrument).lower().find("call") >= 0 or str(instrument).lower().find("put") >= 0

    if decision_u == "BUY" and is_option:
        what = (
            f"Paper-buy a {instrument} betting upside into expiry. "
            f"Expect premium to expand if spot rises / vol spikes; decay accelerates as the clock runs out."
        )
        exit_plan = (
            f"Auto-exit: take-profit +{tp:.0%}, stop-loss −{sl:.0%}, "
            f"or flatten by {eod} ET / Friday deadline if still open (near-expiry risk)."
        )
    elif decision_u == "SELL" and is_option:
        what = (
            f"Paper-buy a {instrument} betting downside (or close a long call first). "
            f"Expect premium to expand if spot falls; still subject to near-expiry theta/gamma."
        )
        exit_plan = (
            f"Auto-exit: take-profit +{tp:.0%}, stop-loss −{sl:.0%}, "
            f"or flatten by {eod} ET if still open."
        )
    elif decision_u == "BUY":
        what = "Bias is long. Expect continuation higher if news/options stay aligned."
        exit_plan = "Hold until reverse SELL/flip signal or manual close."
    elif decision_u == "SELL":
        what = "Bias is short / exit longs. Expect weakness if bearish options/news hold."
        exit_plan = "Hold short or stay flat until BUY flips the bias."
    elif decision_u == "REVIEW":
        what = (
            f"Setup is mixed — lean {lean} at {int(lean_pct)}% "
            f"(BUY {buy_pct}% / SELL {sell_pct}% / WAIT {wait_pct}%). Waiting for clearer confirmation."
        )
        exit_plan = "No auto-trade until approved or the lean clears a BUY/SELL threshold."
    else:
        what = "No actionable trade — logged for research only."
        exit_plan = "No position opened."

    advisor = advisor or {}
    advisor_step = str(advisor.get("next_step") or "").strip()
    advisor_rationale = str(advisor.get("rationale") or "").strip()
    advisor_conf = advisor.get("confidence")
    if advisor_conf is not None:
        try:
            ac = float(advisor_conf)
            if ac <= 1.0:
                ac = ac * 100.0
            # Prefer rule lean_pct for the displayed %, but raise label if advisor is strong.
            if ac >= 70 and conf_label == "medium":
                conf_label = "high"
            elif ac < 40 and conf_label == "high":
                conf_label = "medium"
        except Exception:
            pass
    if advisor_rationale:
        why = f"{why} Advisor: {advisor_rationale}".strip()
    if advisor_step:
        what = f"{what} Next: {advisor_step}".strip()

    if in_depth_rationale:
        if in_depth_rationale.get("expected_outcome_if_right"):
            what = (
                f"If right: {in_depth_rationale['expected_outcome_if_right']} "
                f"If wrong: {in_depth_rationale.get('expected_outcome_if_wrong', '')}"
            ).strip()
        if in_depth_rationale.get("confidence_pct") is not None:
            conf_pct = int(round(float(in_depth_rationale["confidence_pct"])))
            conf_label = str(in_depth_rationale.get("confidence_label") or conf_label)

    summary = (
        f"{decision_u} {ticker} via {instrument} · confidence {conf_label} ({conf_pct}%) · "
        f"lean {lean} {int(lean_pct)}%"
    )
    agree_conf = odte.get("agreement_confidence")
    if agree_conf is None:
        agree_conf = odte.get("confidence_pct")
    n_dir = odte.get("n_dir")
    if n_dir is None:
        n_dir = odte.get("n_directional")
    lean_gate = odte.get("lean_gate") or {}
    gate_bits = []
    if agree_conf is not None:
        gate_bits.append(f"agreement_conf={agree_conf}")
    if n_dir is not None:
        gate_bits.append(f"n_dir={n_dir}")
    gate_bits.append(f"lean={lean} {int(lean_pct)}%")
    if lean_gate:
        need = lean_gate.get("min_lean_pct")
        if need is not None:
            gate_bits.append(f"lean_gate={'pass' if lean_gate.get('passed') else 'fail'}(need≥{need})")
    if gate_bits:
        why = f"{why} [{'; '.join(gate_bits)}]".strip()

    return {
        "summary": summary,
        "why": why,
        "what_to_expect": what,
        "confidence_label": conf_label,
        "confidence_pct": conf_pct,
        "agreement_confidence": agree_conf,
        "n_dir": n_dir,
        "instrument": instrument,
        "exit_plan": exit_plan,
        "next_step": advisor_step or what,
        "rationale": advisor_rationale or why,
        "action_probs_text": f"BUY {buy_pct}% · SELL {sell_pct}% · WAIT {wait_pct}%",
        "in_depth_rationale": in_depth_rationale or {},
        "odte_factors": {
            "gex_regime": odte.get("gex_regime"),
            "agreement": odte.get("agreement"),
            "agreement_confidence": agree_conf,
            "n_dir": n_dir,
            "lean_gate": lean_gate or None,
            "conflict": odte.get("conflict"),
            "liquidity_ok": odte.get("liquidity_ok"),
            "setup_quality_score": odte.get("setup_quality_score"),
            "factor_snapshot": snap,
        },
    }


def format_explanation_text(card: Dict[str, Any]) -> str:
    """Multi-line text for Telegram / console."""
    return (
        f"{card.get('summary', '')}\n"
        f"Why: {card.get('why', '')}\n"
        f"Expect: {card.get('what_to_expect', '')}\n"
        f"Exit: {card.get('exit_plan', '')}\n"
        f"Probs: {card.get('action_probs_text', '')}"
    )
