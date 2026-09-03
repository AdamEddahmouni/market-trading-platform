"""LLM advisor for plain-English next action (Path B / combined).

Purpose
-------
Produce a JSON action card (BUY/SELL/WAIT/AVOID, instrument_hint, next_step,
rationale) for REVIEW rows and Path B expiry decisions.

Pipeline role
-------------
Invoked from Path B / unified decision flow when human-readable guidance is
needed beyond numeric lean probabilities.

Key outputs
-----------
``{action, instrument_hint, next_step, confidence, rationale}`` with rule-based
fallback when LLM unavailable.

Handoff notes
-------------
**Reusable** for equity/futures — adjust prompt rules that mention DTE/0DTE
when not trading options.

**Options-only:** ``instrument_hint`` call/put/spread and same-day expiry language.
"""

from __future__ import annotations

from typing import Any, Dict

from dotenv import load_dotenv
from pathlib import Path

try:
    from sentiment.llm_client import chat_json, load_llm_settings
except ImportError:
    from llm_client import chat_json, load_llm_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fallback(reason: str, lean: str = "WAIT", instrument_hint: str = "stock") -> Dict[str, Any]:
    return {
        "action": lean if lean in {"BUY", "SELL", "WAIT", "AVOID"} else "WAIT",
        "instrument_hint": instrument_hint,
        "next_step": reason,
        "confidence": 0.3,
        "rationale": reason,
    }


def advise_next_action(
    ticker: str,
    quadrant: str,
    herd_stage: str,
    action_probs: Dict[str, float],
    lean: str,
    instrument_hint: str,
    options_score: float | None = None,
    options_bias: str | None = None,
    news_score: float | None = None,
    dte: int | None = None,
    max_oi_strike: float | None = None,
    relative_volume: float | None = None,
    headline: str = "",
    reason: str = "",
) -> Dict[str, Any]:
    """
    Ask the configured LLM for an explicit next action card.

    Falls back to rule-based text when the API key is missing or the call fails.
    """
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    probs_text = ", ".join(f"{k} {v*100:.0f}%" for k, v in (action_probs or {}).items())
    dte_note = "same-day expiry (0DTE)" if dte is not None and int(dte) == 0 else f"DTE={dte}"
    fallback_step = (
        f"If setup holds, bias is {lean} ({probs_text}). "
        f"Instrument hint: {instrument_hint} ({dte_note}). Monitor {ticker}."
    )

    settings = load_llm_settings()
    llm = settings.get("llm") or {}
    max_tokens = int(llm.get("max_tokens", 400))

    system = "You are a trading research assistant explaining a paper-trading decision. Return ONLY valid JSON."
    prompt = f"""Return ONLY valid JSON:
{{
  "action": "BUY" | "SELL" | "WAIT" | "AVOID",
  "instrument_hint": "stock" | "call" | "put" | "spread",
  "next_step": "one plain-English sentence: what to do / watch next",
  "confidence": 0.0-1.0,
  "rationale": "2 short sentences: WHY this decision, and WHAT to expect if it works vs if it fails"
}}

Rules:
- If DTE is 0, treat this as a same-day options scalp (gamma/theta risk); say so.
- Be concrete (price/strike/expiry condition if possible), not generic.
- Do not invent fills — this is research / paper trading.

Ticker: {ticker}
Quadrant: {quadrant}
Herd stage: {herd_stage}
Lean: {lean}
Action probs: {probs_text}
Suggested instrument: {instrument_hint}
News score: {news_score}
Options bias/score: {options_bias} / {options_score}
DTE: {dte} ({dte_note})
Max OI strike: {max_oi_strike}
Relative volume: {relative_volume}
Headline: {headline}
Decision reason: {reason}
"""
    try:
        payload, _provider = chat_json(
            system=system,
            user=prompt,
            max_tokens=max_tokens,
            settings=settings,
            purpose="action_advisor",
        )
        action = str(payload.get("action", lean)).upper().strip()
        if action not in {"BUY", "SELL", "WAIT", "AVOID"}:
            action = lean if lean in {"BUY", "SELL", "WAIT", "AVOID"} else "WAIT"
        hint = str(payload.get("instrument_hint", instrument_hint)).lower().strip()
        if hint not in {"stock", "call", "put", "spread"}:
            hint = instrument_hint
        return {
            "action": action,
            "instrument_hint": "stock" if hint == "spread" else hint,
            "next_step": str(payload.get("next_step", fallback_step)),
            "confidence": float(payload.get("confidence", 0.5)),
            "rationale": str(payload.get("rationale", "")),
        }
    except Exception:
        return _fallback(fallback_step, lean=lean, instrument_hint=instrument_hint)
