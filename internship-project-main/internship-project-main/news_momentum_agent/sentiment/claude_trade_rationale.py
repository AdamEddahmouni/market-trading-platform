"""In-depth Claude rationale for BUY / SELL / REVIEW actions.

Purpose
-------
Generate structured decision memos (reasoning, expected outcomes, confidence
justification) for executed or REVIEW signals. Uses LLM when available; falls
back to rule-based text from factor snapshots.

Pipeline role
-------------
Called after ``decision_engine`` resolves action/confidence for Path B and
unified decisions. Enriches ``trade_log`` / Telegram cards with human-readable
context — one call per action, not per scanned ticker.

Key outputs
-----------
``{reasoning, expected_outcome_if_right, expected_outcome_if_wrong,
confidence_justification, confidence_pct, source}``.

Handoff notes
-------------
**Reusable pattern** for equity/futures: pass pre-computed confidence + factor
snapshot; prompt forbids inventing numbers.

**Options-only fields:** ``theta_breakeven_pct``, GEX/max-pain/IV in factor
snapshot — omit or replace for delta-1 equity or futures risk metrics.

One structured call per action taken (not per candidate scanned). Confidence
is passed in from code (factor agreement) — Claude justifies and contextualizes
it, and drafts expected-outcome language using the real factor numbers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = PROJECT_ROOT / "settings.json"


def _load_claude_settings() -> Dict[str, Any]:
    defaults = {
        "claude": {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 700,
            "temperature": 0,
        }
    }
    try:
        if SETTINGS_PATH.exists():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update(data)
    except Exception:
        pass
    return defaults


def _rule_based_rationale(
    *,
    ticker: str,
    decision: str,
    confidence_pct: float,
    confidence_label: str,
    factor_snapshot: Dict[str, Any],
    agreement: float,
    conflict_reasons: list,
    lean: str,
    lean_pct: int,
    instrument_hint: str,
    spot: float | None,
    theta_breakeven_pct: float | None,
    exits: Dict[str, Any],
) -> Dict[str, Any]:
    tp = float(exits.get("take_profit_pct", 0.40))
    sl = float(exits.get("stop_loss_pct", 0.30))
    gex = factor_snapshot.get("gex_regime", "n/a")
    mp = factor_snapshot.get("max_pain_distance_pct")
    iv = factor_snapshot.get("iv_rank")
    flow = factor_snapshot.get("flow_trend_score")
    setup = factor_snapshot.get("setup_quality_score")

    reasoning = (
        f"{decision} on {ticker}: factor agreement={agreement:.2f} "
        f"(confidence {confidence_pct:.0f}% / {confidence_label}). "
        f"GEX regime={gex}; max-pain distance={mp}; IV rank={iv}; "
        f"flow trend={flow}; setup quality={setup}. "
    )
    if conflict_reasons:
        reasoning += "Conflicts: " + "; ".join(conflict_reasons) + ". "

    side = "call" if str(instrument_hint).lower() == "call" or decision == "BUY" else "put"
    if decision == "REVIEW":
        side = "call" if lean == "BUY" else ("put" if lean == "SELL" else side)

    right = (
        f"If thesis holds, {side} premium expands toward +{tp:.0%} take-profit; "
        f"lean is {lean} ({lean_pct}%)."
    )
    wrong = f"If thesis fails, expect stop near -{sl:.0%} premium loss or EOD flatten."
    if theta_breakeven_pct is not None:
        right += f" Theta-adjusted breakeven move ≈ {theta_breakeven_pct:.2f}% on the underlying."
    if spot is not None and spot > 0:
        right += f" Spot reference ${spot:.2f}."

    return {
        "reasoning": reasoning.strip(),
        "confidence_pct": float(confidence_pct),
        "confidence_label": confidence_label,
        "expected_outcome_if_right": right,
        "expected_outcome_if_wrong": wrong,
        "theta_breakeven_pct": theta_breakeven_pct,
        "source": "rule_based",
    }


def generate_trade_rationale(
    *,
    ticker: str,
    decision: str,
    confidence_pct: float,
    confidence_label: str,
    agreement: float,
    conflict_reasons: Optional[list] = None,
    factor_snapshot: Optional[Dict[str, Any]] = None,
    lean: str = "WAIT",
    lean_pct: int = 0,
    instrument_hint: str = "call",
    news_headline: str = "",
    news_score: float | None = None,
    options_score: float | None = None,
    options_bias: str | None = None,
    spot: float | None = None,
    theta_breakeven_pct: float | None = None,
    exits: Optional[Dict[str, Any]] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate structured in-depth rationale for BUY, SELL, or REVIEW.

    Confidence numbers are inputs — not invented by the model.
    """
    decision_u = str(decision).upper().strip()
    if decision_u not in {"BUY", "SELL", "REVIEW"}:
        return {}

    exits_cfg = exits or (settings or {}).get("trading", {}).get("options_exits") or {}
    factors = dict(factor_snapshot or {})
    conflicts = list(conflict_reasons or [])

    fallback = _rule_based_rationale(
        ticker=ticker,
        decision=decision_u,
        confidence_pct=confidence_pct,
        confidence_label=confidence_label,
        factor_snapshot=factors,
        agreement=agreement,
        conflict_reasons=conflicts,
        lean=lean,
        lean_pct=lean_pct,
        instrument_hint=instrument_hint,
        spot=spot,
        theta_breakeven_pct=theta_breakeven_pct,
        exits=exits_cfg,
    )

    load_dotenv(PROJECT_ROOT / ".env", override=True)
    try:
        from sentiment.llm_client import chat_json, load_llm_settings
    except ImportError:
        from llm_client import chat_json, load_llm_settings

    cfg = settings or load_llm_settings()
    llm = (cfg.get("llm") or {})
    claude_cfg = (cfg.get("claude") or {})
    max_tokens = int(
        llm.get("rationale_max_tokens")
        or claude_cfg.get("rationale_max_tokens")
        or 700
    )

    system = "You are writing an internship-grade paper-trading decision memo for a 0DTE options system. Return ONLY valid JSON."
    prompt = f"""Return ONLY valid JSON with keys:
{{
  "reasoning": "3-6 sentences referencing the PROVIDED factor numbers (do not invent values)",
  "expected_outcome_if_right": "1-2 sentences: what happens if thesis is right (TP / levels)",
  "expected_outcome_if_wrong": "1-2 sentences: what happens if wrong (stop / flatten)",
  "confidence_justification": "1-2 sentences explaining why the GIVEN confidence fits the factor agreement"
}}

Hard rules:
- Confidence is ALREADY computed as {confidence_pct:.1f}% ({confidence_label}). Do NOT pick a different number.
- Use only the factor values below; if a value is null, say it was unavailable.
- This is paper trading research, not live advice.

Ticker: {ticker}
Decision: {decision_u}
Lean: {lean} ({lean_pct}%)
Agreement score: {agreement:.3f}
Conflict reasons: {conflicts or "none"}
Instrument hint: {instrument_hint}
News headline: {news_headline[:180]}
News score: {news_score}
Options bias/score: {options_bias} / {options_score}
Spot: {spot}
Theta-adjusted breakeven %: {theta_breakeven_pct}
Exits: TP={exits_cfg.get("take_profit_pct")} SL={exits_cfg.get("stop_loss_pct")} EOD={exits_cfg.get("eod_flatten_et")}
Factor snapshot JSON: {json.dumps(factors, default=str)}
"""
    try:
        parsed, provider = chat_json(
            system=system,
            user=prompt,
            max_tokens=max_tokens,
            temperature=0,
            settings=cfg,
            purpose="trade_rationale",
        )
        return {
            "reasoning": str(parsed.get("reasoning") or fallback["reasoning"]),
            "confidence_pct": float(confidence_pct),
            "confidence_label": confidence_label,
            "expected_outcome_if_right": str(
                parsed.get("expected_outcome_if_right") or fallback["expected_outcome_if_right"]
            ),
            "expected_outcome_if_wrong": str(
                parsed.get("expected_outcome_if_wrong") or fallback["expected_outcome_if_wrong"]
            ),
            "confidence_justification": str(parsed.get("confidence_justification") or ""),
            "theta_breakeven_pct": theta_breakeven_pct,
            "source": provider,
        }
    except Exception:
        fallback["source"] = "rule_based_fallback"
        return fallback
