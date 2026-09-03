"""Finance slang keyword boosts for adjusted sentiment scoring.

Purpose
-------
Deterministic post-LLM adjustment: scan combined news text for known retail/
momentum phrases and nudge score within [-1, 1].

Pipeline role
-------------
``apply_keyword_boost`` immediately after ``score_news_with_claude`` in Path A.

Key outputs
-----------
Adjusted float score (clamped).

Handoff notes
-------------
**Fully reusable** — edit ``FINANCE_SLANG_BOOSTS`` for futures/crypto lexicon.
No options-specific logic.
"""

from __future__ import annotations

from typing import Dict


FINANCE_SLANG_BOOSTS: Dict[str, float] = {
    "moon": 0.3,
    "to the moon": 0.5,
    "diamond hands": 0.4,
    "tendies": 0.3,
    "bullish": 0.3,
    "bearish": -0.3,
    "dump": -0.4,
    "cooked": -0.3,
    "bag holder": -0.5,
    "paper hands": -0.2,
    "short squeeze": 0.3,
    "rekt": -0.5,
    "going to zero": -0.6,
    "gamma squeeze": 0.4,
    "massive catalyst": 0.4,
    "game changer": 0.3,
    "nothing burger": -0.4,
    "sell the news": -0.3,
    "buy the rumor": 0.2,
}


def clamp_score(value: float, lower: float = -1.0, upper: float = 1.0) -> float:
    """
    Keep a numeric score inside the allowed range.

    Inputs:
    - value: raw score to clamp.
    - lower: minimum allowed value.
    - upper: maximum allowed value.

    Output:
    - A float guaranteed to be between lower and upper.

    Why this exists:
    - Sentiment scores must stay inside the expected interval so
      downstream decision logic remains consistent.
    """
    return max(lower, min(upper, value))


def apply_keyword_boost(base_score: float, news_text: str) -> float:
    """
    Adjust Claude score using finance slang boost keywords.

    Inputs:
    - base_score: model score before slang adjustment.
    - news_text: full combined text to scan for slang.

    Output:
    - Adjusted score clamped to [-1.0, 1.0].

    Why this exists:
    - Some market language carries known momentum context, so a small
      deterministic boost can complement model output.
    """
    adjusted = float(base_score)
    lowered = (news_text or "").lower()

    for phrase, boost in FINANCE_SLANG_BOOSTS.items():
        if phrase in lowered:
            adjusted += boost

    return clamp_score(adjusted)


def main() -> None:
    """
    Run a small demo of score adjustment behavior.

    Inputs:
    - None.

    Output:
    - None. Prints base and adjusted scores.

    Why this exists:
    - Direct-run testing helps verify boost and clamping logic quickly.
    """
    text = "This could moon with a massive catalyst, but some say sell the news."
    base = 0.45
    adjusted = apply_keyword_boost(base_score=base, news_text=text)
    print(f"Base score: {base}")
    print(f"Adjusted score: {adjusted}")


if __name__ == "__main__":
    main()
