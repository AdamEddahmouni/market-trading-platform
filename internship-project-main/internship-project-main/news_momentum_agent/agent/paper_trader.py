"""Paper-trading audit log for every pipeline decision (BUY/SELL/REVIEW/LOG).

Pipeline role
-------------
Called immediately after ``decision_engine.decide_trade_action`` (and Path B
variants). Records the full decision context — news, options, lean, herd,
explanation card — before ``portfolio.execute_decision`` runs. LOG rows capture
*why* a signal did not trade (reason codes align with ``LOG_REASON_TEMPLATES``).

State files
-----------
  - ``state/trade_log.json`` — structured JSON array (primary audit trail).
  - ``state/trade_log.txt`` — compact one-line-per-decision mirror.

Also provides ``fetch_price_at_signal`` (yfinance spot) used by portfolio and
near-miss shadow pricing. Reusable in a stocks/futures fork; options-specific
fields (``dte``, ``options_bias``, instrument hints) can stay as optional metadata.

Merge notes
-----------
  - Keep ``append_paper_trade_entry`` as the single write path for decisions.
  - ``templated_log_why`` maps machine reason codes to human LOG explanations.
  - Telegram alerts are triggered from here for BUY/SELL/REVIEW when enabled.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yfinance as yf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
TRADE_JSON_PATH = STATE_DIR / "trade_log.json"
TRADE_TXT_PATH = STATE_DIR / "trade_log.txt"

LOG_REASON_TEMPLATES = {
    "liquidity_reject": "LOG — failed options liquidity floor",
    "low_confidence": "LOG — confidence below action threshold",
    "weak_lean": "LOG — lean too weak / coin-flip vs WAIT (Path B lean gate)",
    "options_not_clear": "LOG — options bias unclear / not directional",
    "no_lean": "LOG — no actionable lean",
    "outside_rth": "LOG — options market closed (outside RTH)",
    "past_eod": "LOG — past 15:45 ET; no new options opens",
    "stale_quote": "LOG — entry quote rejected as stale / missing NBBO",
    "identical_quote_pause": "LOG — identical quote circuit paused this ticker",
    "risk_blocked": "LOG — risk manager blocked new entry",
    "flip_reentry_cooldown": "LOG — flip re-entry cooldown active",
    "flip_suppressed_min_hold": "LOG — flip suppressed (min hold)",
    "flip_suppressed_hysteresis": "LOG — flip suppressed (confidence hysteresis)",
    "flip_suppressed_flip_disabled": "LOG — reverse signal ignored (flip exits off)",
    "no_contract": "LOG — no liquid ATM contract for max_dte",
    "size_zero": "LOG — position sizing produced zero contracts",
    "not_reconciled": "LOG — portfolio not reconciled after startup",
    "options_conflict": "LOG — news/options conflict below REVIEW bar",
    "path_b_research_only": "LOG — Path B research-only (auto execute off)",
    "path_a2_research_only": "LOG — Path A.2 research-only (auto execute off)",
}


def templated_log_why(reason_code: str, fallback: str = "", detail: str = "") -> str:
    """Map a decision reason code to a short human-readable LOG explanation string."""
    code = str(reason_code or "").strip()
    base = ""
    if code in LOG_REASON_TEMPLATES:
        base = LOG_REASON_TEMPLATES[code]
    elif code.startswith("flip_suppressed_"):
        base = f"LOG — flip suppressed ({code.replace('flip_suppressed_', '')})"
    else:
        base = fallback or (f"LOG — {code}" if code else "LOG — no trade")
    extra = str(detail or "").strip()
    if extra and code == "liquidity_reject":
        return f"{base}: {extra}"
    return base


def load_trade_log() -> List[Dict[str, Any]]:
    """Load existing paper-trade JSON log entries."""
    try:
        if not TRADE_JSON_PATH.exists():
            return []
        data = json.loads(TRADE_JSON_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return []
    except Exception as error:
        print(f"[paper_trader] Could not load trade log: {error}")
        return []


def save_trade_log(entries: List[Dict[str, Any]]) -> None:
    """Save the full paper-trade log back to JSON."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = TRADE_JSON_PATH.with_suffix(TRADE_JSON_PATH.suffix + ".tmp")
        temp_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        temp_path.replace(TRADE_JSON_PATH)
    except Exception as error:
        print(f"[paper_trader] Could not save trade JSON log: {error}")


def fetch_price_at_signal(ticker: str) -> float:
    """Fetch a best-effort current price for the ticker via yfinance."""
    try:
        symbol = ticker.upper().strip()
        history = yf.Ticker(symbol).history(period="1d", interval="1m")
        if not history.empty:
            return float(history["Close"].iloc[-1])
    except Exception as error:
        print(f"[paper_trader] Could not fetch yfinance history for {ticker}: {error}")

    try:
        fast_info = yf.Ticker(ticker.upper().strip()).fast_info
        value = fast_info.get("lastPrice")
        return float(value) if value is not None else 0.0
    except Exception:
        return 0.0


def append_paper_trade_entry(
    ticker: str,
    decision: str,
    claude_response: Dict[str, Any],
    news_headline: str,
    news_source: str,
    social_signal_level: str,
    social_signal_posts: List[Dict[str, Any]],
    options_score: float | None = None,
    options_bias: str | None = None,
    options_reasoning: str = "",
    settings: Optional[Dict[str, Any]] = None,
    price_hint: float | None = None,
    decision_meta: Optional[Dict[str, Any]] = None,
    next_action: str = "",
    signal_source: str = "news",
    herd_stage: str = "",
    quadrant: str = "",
    relative_volume: float | None = None,
    dte: int | None = None,
    max_oi_strike: float | None = None,
    advisor: Optional[Dict[str, Any]] = None,
    decision_reason: str = "",
) -> Dict[str, Any]:
    """Append one paper-trade decision to JSON and text logs."""
    timestamp = datetime.now(timezone.utc).isoformat()
    price_at_signal = float(price_hint) if price_hint and price_hint > 0 else fetch_price_at_signal(ticker)
    if price_at_signal <= 0 and price_hint:
        price_at_signal = float(price_hint)

    meta = decision_meta or {}
    instrument_hint = str(meta.get("instrument_hint", "stock")).lower().strip()
    action_probs = meta.get("action_probs") or {}
    lean = str(meta.get("lean", "WAIT"))
    lean_pct = int(meta.get("lean_pct", 0))
    source = str(meta.get("signal_source") or signal_source or "news")

    instrument = instrument_hint
    if settings:
        configured = str(settings.get("trading", {}).get("instrument", "auto")).lower()
        if configured != "auto":
            instrument = configured

    from agent.decision_explainer import build_decision_explanation

    decision_u_pre = str(decision).upper().strip()
    reason_code = str(
        meta.get("decision_reason_code")
        or meta.get("review_reason_code")
        or meta.get("review_reason_code_odte")
        or ""
    ).strip()
    in_depth: Dict[str, Any] = {}
    # In-depth Claude only for BUY/SELL/REVIEW — LOG gets a cheap templated why.
    if decision_u_pre in {"BUY", "SELL", "REVIEW"} and settings:
        try:
            from sentiment.claude_trade_rationale import generate_trade_rationale

            factor_snap = dict(meta.get("factor_snapshot") or {})
            factor_snap["setup_quality_score"] = meta.get("setup_quality_score")
            factor_snap["agreement_confidence"] = meta.get("agreement_confidence")
            factor_snap["n_dir"] = meta.get("n_dir") if meta.get("n_dir") is not None else meta.get("n_directional")
            factor_snap["lean_pct"] = lean_pct
            factor_snap["lean"] = lean
            if meta.get("lean_gate"):
                factor_snap["lean_gate"] = meta.get("lean_gate")
            theta_be = None
            feats = meta.get("options_features") or {}
            # Rough theta-adjusted breakeven (% underlying) without importing options_engine.
            try:
                theta_left = float(feats.get("tod_theta_remaining_frac", 0.5) or 0.5)
                burn = max(0.0, 1.0 - theta_left)
                # Assume ~1% of spot as ATM premium proxy and ~0.5 delta.
                if price_at_signal and price_at_signal > 0:
                    prem_est = float(price_at_signal) * 0.01
                    theta_be = (prem_est * burn) / (float(price_at_signal) * 0.5) * 100.0
            except Exception:
                theta_be = None
            in_depth = generate_trade_rationale(
                ticker=ticker,
                decision=decision_u_pre,
                confidence_pct=float(meta.get("confidence_pct") or lean_pct or 50),
                confidence_label=str(meta.get("confidence_label") or "medium"),
                agreement=float(meta.get("agreement") or 0.0),
                conflict_reasons=list(meta.get("conflict_reasons") or []),
                factor_snapshot=factor_snap,
                lean=lean,
                lean_pct=lean_pct,
                instrument_hint=instrument_hint,
                news_headline=news_headline,
                news_score=float(claude_response.get("score", 0.0)),
                options_score=options_score,
                options_bias=options_bias,
                spot=price_at_signal,
                theta_breakeven_pct=theta_be,
                settings=settings,
            )
        except Exception as error:
            print(f"[paper_trader] In-depth rationale failed: {error}")

    explanation = build_decision_explanation(
        ticker=ticker,
        decision=decision,
        reason=decision_reason or str(claude_response.get("reasoning", "")),
        instrument_hint=instrument_hint,
        action_probs=action_probs if isinstance(action_probs, dict) else {},
        lean=lean,
        lean_pct=lean_pct,
        signal_source=source,
        herd_stage=herd_stage or str(meta.get("herd_stage", "")),
        quadrant=quadrant,
        news_score=float(claude_response.get("score", 0.0)),
        news_headline=news_headline,
        news_confidence=str(claude_response.get("confidence", "")),
        options_bias=options_bias,
        options_score=options_score,
        options_reasoning=options_reasoning,
        dte=dte if dte is not None else meta.get("dte"),
        max_oi_strike=max_oi_strike,
        relative_volume=relative_volume if relative_volume is not None else meta.get("relative_volume"),
        advisor=advisor,
        exits=(settings or {}).get("trading", {}).get("options_exits") or {},
        odte_meta=meta,
        in_depth_rationale=in_depth,
    )
    if not next_action:
        next_action = str(explanation.get("next_step") or "")

    if decision_u_pre == "LOG":
        liq_detail = str(meta.get("liquidity_reject_detail") or "").strip()
        why_line = templated_log_why(
            reason_code,
            decision_reason or str(claude_response.get("reasoning", "")),
            detail=liq_detail,
        )
        explanation["why"] = why_line
        explanation["what_to_expect"] = "No trade — logged for audit / EOD rejection breakdown."
        explanation["next_step"] = "Wait for a clearer setup or next scan cycle."

    entry = {
        "ticker": ticker.upper().strip(),
        "timestamp": timestamp,
        "decision": decision,
        "score": float(claude_response.get("score", 0.0)),
        "label": str(claude_response.get("label", "neutral")),
        "confidence": str(explanation.get("confidence_label") or claude_response.get("confidence", "low")),
        "confidence_pct": int(explanation.get("confidence_pct") or lean_pct),
        "reasoning": str(claude_response.get("reasoning", "")),
        "catalyst_type": str(claude_response.get("catalyst_type", "other")),
        "news_headline": news_headline,
        "news_source": news_source,
        "social_signal_level": social_signal_level,
        "social_signal_posts": social_signal_posts,
        "price_at_signal": price_at_signal,
        "paper_trade": True,
        "options_score": options_score,
        "options_bias": options_bias,
        "options_reasoning": options_reasoning,
        "executed": False,
        "execution_fills": [],
        "instrument": instrument,
        "instrument_hint": instrument_hint,
        "action_probs": action_probs,
        "lean": lean,
        "lean_pct": lean_pct,
        "agreement_confidence": meta.get("agreement_confidence"),
        "n_dir": meta.get("n_dir") if meta.get("n_dir") is not None else meta.get("n_directional"),
        "signal_source": source,
        "herd_stage": herd_stage or meta.get("herd_stage", ""),
        "quadrant": quadrant,
        "relative_volume": relative_volume if relative_volume is not None else meta.get("relative_volume"),
        "dte": dte if dte is not None else meta.get("dte"),
        "max_oi_strike": max_oi_strike,
        "next_action": next_action,
        "review_reason_code": meta.get("review_reason_code", ""),
        "decision_reason_code": reason_code,
        "decision_explanation": explanation,
        "why": explanation.get("why", ""),
        "what_to_expect": explanation.get("what_to_expect", ""),
        "exit_plan": explanation.get("exit_plan", ""),
        "in_depth_rationale": in_depth,
        "decision_meta": {
            "agreement": meta.get("agreement"),
            "confidence_pct": meta.get("confidence_pct"),
            "agreement_confidence": meta.get("agreement_confidence"),
            "n_dir": meta.get("n_dir") if meta.get("n_dir") is not None else meta.get("n_directional"),
            "n_directional": meta.get("n_directional") if meta.get("n_directional") is not None else meta.get("n_dir"),
            "confidence_label": meta.get("confidence_label"),
            "gex_regime": meta.get("gex_regime"),
            "conflict": meta.get("conflict"),
            "conflict_reasons": meta.get("conflict_reasons"),
            "factor_snapshot": meta.get("factor_snapshot"),
            "setup_quality_score": meta.get("setup_quality_score"),
            "lean_gate": meta.get("lean_gate"),
            "decision_reason_code": reason_code,
            "liquidity_ok": meta.get("liquidity_ok"),
            "liquidity_reject_primary": meta.get("liquidity_reject_primary"),
            "liquidity_reject_detail": meta.get("liquidity_reject_detail"),
            "liquidity_fail_counts": meta.get("liquidity_fail_counts"),
            "options_features": {
                k: (meta.get("options_features") or {}).get(k)
                for k in (
                    "atm_median_spread_pct",
                    "atm_min_oi",
                    "atm_max_oi",
                    "atm_contract_count",
                    "atm_max_volume",
                    "liquidity_ok",
                    "liquidity_reject",
                    "liquidity_reject_primary",
                    "liquidity_reject_detail",
                    "liquidity_fail_counts",
                    "liquidity_max_spread_pct",
                    "liquidity_min_oi_required",
                    "liquidity_nearest_dte",
                    "nearest_dte",
                )
                if (meta.get("options_features") or {}).get(k) is not None
            },
        },
    }

    trading = (settings or {}).get("trading", {})
    execution_cfg = (settings or {}).get("execution") or {}
    review_requires_approval = bool(trading.get("review_requires_approval", True))
    decision_u = str(decision).upper()
    autonomous = bool(execution_cfg.get("autonomous_buy_sell", trading.get("auto_execute", True)))

    # Kill switch: force everything to REVIEW (no auto execute).
    if bool(execution_cfg.get("force_review_all", False)) and decision_u in {"BUY", "SELL"}:
        decision_u = "REVIEW"
        entry["decision"] = "REVIEW"
        entry["why"] = (entry.get("why") or "") + " | kill-switch force_review_all"

    should_execute = decision_u in {"BUY", "SELL"} and autonomous
    signal_src = str(entry.get("signal_source") or signal_source or "").lower().strip()
    if signal_src == "news_catalyst" and not bool(execution_cfg.get("path_a2_auto_execute", False)):
        should_execute = False
        if decision_u in {"BUY", "SELL"}:
            entry["decision_reason_code"] = entry.get("decision_reason_code") or "path_a2_research_only"
    if review_requires_approval and decision_u == "REVIEW":
        should_execute = False

    if settings and should_execute:
        if price_at_signal <= 0:
            print(f"[paper_trader] No price for {ticker} — logged signal but skipped execution")
        else:
            try:
                from agent.portfolio import execute_decision

                execution = execute_decision(
                    ticker=ticker,
                    decision=decision_u,
                    price=price_at_signal,
                    reason=f"{decision_u} signal: {news_headline[:80]}",
                    settings=settings,
                    instrument_hint=instrument_hint,
                    signal_confidence=float(entry.get("confidence_pct") or lean_pct or 50),
                )
                exec_action = str((execution or {}).get("action") or "")
                entry["execution_action"] = exec_action
                if execution and execution.get("fills"):
                    entry["executed"] = True
                    entry["execution_fills"] = execution.get("fills", [])
                    entry["instrument"] = execution.get("instrument_type", instrument)
                    if execution.get("contract_symbol"):
                        entry["contract_symbol"] = execution.get("contract_symbol")
                    if execution.get("option_side"):
                        entry["option_side"] = execution.get("option_side")
                    if execution.get("premium") is not None:
                        entry["premium"] = execution.get("premium")
                    label = execution.get("contract_symbol") or ticker
                    print(
                        f"[paper_trader] Executed {decision_u} {label} @ ${price_at_signal:.2f} "
                        f"({len(entry['execution_fills'])} fill(s), instrument={entry['instrument']})"
                    )
                    expl = entry.get("decision_explanation") or {}
                    if expl:
                        print(f"[paper_trader] Why: {expl.get('why', '')}")
                        print(f"[paper_trader] Expect: {expl.get('what_to_expect', '')}")
                        print(
                            f"[paper_trader] Confidence: {expl.get('confidence_label')} "
                            f"({expl.get('confidence_pct')}%) | Exit: {expl.get('exit_plan', '')}"
                        )
                elif execution is None:
                    print(f"[paper_trader] Execution skipped for {ticker} {decision_u} (auto_execute off or invalid)")
                elif exec_action in {
                    "hold",
                    "outside_rth",
                    "past_eod",
                    "risk_blocked",
                    "size_zero",
                    "quote_rejected",
                    "flip_reentry_blocked",
                    "no_contract",
                    "not_reconciled",
                }:
                    # Persist blocked opens as auditable skips (no Telegram spam).
                    code = str(
                        (execution or {}).get("decision_reason_code")
                        or (execution or {}).get("reason")
                        or exec_action
                    )
                    entry["decision_reason_code"] = code
                    entry["execution_blocked"] = True
                    if decision_u in {"BUY", "SELL"} and exec_action != "hold":
                        entry["decision"] = "LOG"
                        entry["why"] = templated_log_why(code)
                        decision_u = "LOG"
                    print(f"[paper_trader] {ticker} → {exec_action} logged as {entry['decision']} ({code})")
                else:
                    if execution and execution.get("decision_reason_code"):
                        entry["decision_reason_code"] = execution["decision_reason_code"]
                    print(f"[paper_trader] {decision_u} {ticker} — decision logged, no new position opened (hold/flat)")
            except Exception as error:
                print(f"[paper_trader] Portfolio execution failed for {ticker}: {error}")

    entries = load_trade_log()
    entries.append(entry)
    save_trade_log(entries)
    append_trade_log_text_line(entry)

    if decision_u == "LOG" and settings:
        try:
            from agent.near_miss_tracker import maybe_record_near_miss

            maybe_record_near_miss(entry, settings)
        except Exception as error:
            print(f"[near_miss] record failed: {error}")

    # Confidence calibration log (predicted confidence; outcome filled on exit later).
    if decision_u in {"BUY", "SELL", "REVIEW"}:
        try:
            from agent.risk_manager import append_calibration_record, calibration_entry_from_trade

            append_calibration_record(calibration_entry_from_trade(trade_entry=entry, outcome=None))
        except Exception as error:
            print(f"[paper_trader] Calibration log failed: {error}")

    # Notify phone for actionable decisions (not LOG / blocked skips).
    if settings and decision_u in {"BUY", "SELL", "REVIEW"} and not entry.get("execution_blocked"):
        try:
            from agent.telegram_notifier import send_signal_alert

            send_signal_alert(entry, settings)
        except Exception as error:
            print(f"[paper_trader] Telegram notify failed: {error}")

    return entry


def append_trade_log_text_line(entry: Dict[str, Any]) -> None:
    """Append a compact human-readable trade log line to text file."""
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        options_part = ""
        if entry.get("options_bias") is not None:
            options_part = f" | options={entry.get('options_bias')}({entry.get('options_score')})"
        lean_part = ""
        if entry.get("lean"):
            lean_part = f" | lean={entry.get('lean')} {entry.get('lean_pct', 0)}%"
        why = str(entry.get("why") or "")[:120]
        why_part = f" | why={why}" if why else ""
        conf = entry.get("confidence_pct") or entry.get("confidence")
        conf_part = f" | conf={conf}"
        line = (
            f"{entry['timestamp']} | {entry['ticker']} | {entry['decision']} | "
            f"score={entry['score']:+.2f}{options_part}{lean_part}{conf_part} | "
            f"instr={entry.get('instrument_hint') or entry.get('instrument')} | "
            f"source={entry['news_source']} | headline={entry['news_headline']}{why_part}\n"
        )
        with TRADE_TXT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except Exception as error:
        print(f"[paper_trader] Could not append trade_log.txt line: {error}")
