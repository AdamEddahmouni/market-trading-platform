"""LLM scorer for catalyst news sentiment and urgency (OpenAI or Anthropic).

Purpose
-------
Prompt LLM with aggregated news text; return structured score, label, confidence,
catalyst_type, and urgency for downstream decision thresholds.

Pipeline role
-------------
``score_news_with_claude`` in Path A / A.2 pipeline after ``news_aggregator``.
Score is keyword-boosted by ``sentiment.keyword_boost`` before ``decision_engine``.

Key outputs
-----------
``{score, label, confidence, reasoning, short_term_outlook, catalyst_type,
urgency, llm_provider}`` — neutral fallback on API failure.

Handoff notes
-------------
**Fully reusable** for equity/futures: swap prompt for asset-class context;
provider via ``settings.llm`` (OpenAI/Anthropic/Gemini through ``llm_client``).

**Options-only coupling:** None at scoring layer; urgency field informs timing
for 0DTE elsewhere.

Function name ``score_news_with_claude`` kept for call-site compatibility.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

try:
    from sentiment.llm_client import chat_json, extract_json_object, load_llm_settings
except ImportError:  # Allows running directly from this folder.
    from llm_client import chat_json, extract_json_object, load_llm_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_settings() -> Dict[str, Any]:
    """Load LLM settings used by the news scorer."""
    return load_llm_settings()


def neutral_response(reason: str) -> Dict[str, Any]:
    """Return a safe neutral score payload when LLM calls fail."""
    return {
        "score": 0.0,
        "label": "neutral",
        "confidence": "low",
        "reasoning": reason,
        "short_term_outlook": "neutral",
        "catalyst_type": "other",
        "urgency": "monitor",
    }


def build_prompts(ticker: str, news_text: str) -> Dict[str, str]:
    """Build system and user prompts for news sentiment JSON scoring."""
    system_prompt = """
You are a financial analyst specializing in momentum trading and
catalyst-driven price movements. You read financial news and press
releases and assess their likely short-term market impact.
Always respond in valid JSON only. No extra text.
""".strip()

    user_prompt = f"""
Analyze this financial news for ticker {ticker}.

News content:
{news_text}

Respond with this exact JSON structure:
{{
  "score": <float from -1.0 to 1.0>,
  "label": "<positive|negative|neutral>",
  "confidence": "<high|medium|low>",
  "reasoning": "<one sentence explaining why>",
  "short_term_outlook": "<bullish|bearish|neutral>",
  "catalyst_type": "<earnings|fda|merger|contract|other>",
  "urgency": "<act_now|monitor|ignore>"
}}

Score guide:
0.7 to 1.0 = strongly positive, clear catalyst, act now
0.3 to 0.7 = moderately positive, worth monitoring
-0.3 to 0.3 = ambiguous or neutral
-0.3 to -0.7 = moderately negative
-0.7 to -1.0 = strongly negative, avoid

Be direct and decisive. A press release is either a catalyst or it
is not. Do not hedge unless genuinely uncertain.
""".strip()

    return {"system_prompt": system_prompt, "user_prompt": user_prompt}


def parse_model_json(text: str) -> Dict[str, Any]:
    """Extract JSON object from raw LLM response text."""


def score_news_with_claude(ticker: str, news_text: str) -> Dict[str, Any]:
    """
    Score news via configured LLM provider (OpenAI by default).

    Function name kept for call-site compatibility.
    """
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    settings = load_settings()
    prompts = build_prompts(ticker=ticker, news_text=news_text)
    llm = settings.get("llm") or {}
    max_tokens = int(llm.get("max_tokens", 300))

    for attempt in range(2):
        try:
            parsed, provider = chat_json(
                system=prompts["system_prompt"],
                user=prompts["user_prompt"],
                max_tokens=max_tokens,
                settings=settings,
                purpose="news_scorer",
            )
            return {
                "score": float(parsed.get("score", 0.0)),
                "label": str(parsed.get("label", "neutral")),
                "confidence": str(parsed.get("confidence", "low")),
                "reasoning": str(parsed.get("reasoning", "No reasoning provided.")),
                "short_term_outlook": str(parsed.get("short_term_outlook", "neutral")),
                "catalyst_type": str(parsed.get("catalyst_type", "other")),
                "urgency": str(parsed.get("urgency", "monitor")),
                "llm_provider": provider,
            }
        except Exception as error:
            print(f"[news_scorer] Attempt {attempt + 1} failed: {error}")
            if attempt == 1:
                return neutral_response(f"LLM scoring failed; defaulting to neutral. ({error})")

    return neutral_response("Unexpected LLM scoring flow fallback.")


def main() -> None:
    """CLI smoke test: score sample press-release text for EXMP."""
    sample_text = (
        "[PR NEWSWIRE]\n"
        "Headline: Example Corp announces major government contract\n"
        "Text: Example Corp said it secured a large multi-year defense contract."
    )
    result = score_news_with_claude(ticker="EXMP", news_text=sample_text)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
