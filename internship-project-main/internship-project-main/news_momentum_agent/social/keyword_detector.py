"""Tiered keyword scoring for StockTwits catalyst hints.

Purpose
-------
Deterministic keyword dictionary (tier1/2/3 weights) to detect social chatter
about imminent catalysts before formal news wires publish.

Pipeline role
-------------
``score_post_for_catalyst`` ← ``stocktwits_scanner``; escalation thresholds
configurable via ``settings.social`` (high_alert_threshold, watch_threshold).

Key outputs
-----------
Per-post: ``{keywords_found, total_score, escalation_level}``.

Handoff notes
-------------
**Fully reusable** for equity/futures/crypto social feeds — replace ``TIER_KEYWORDS``
and ``KEYWORD_ALIASES`` for domain-specific catalyst language.

**Options-only coupling:** Tier2 includes options-flow phrases; safe to keep or
trim for pure equity momentum.

**No API calls** — unit-test friendly; ``run_demo_tests`` exercises scoring offline.
"""

from __future__ import annotations

import re
from typing import Dict, List


TIER_KEYWORDS: Dict[str, Dict[str, int]] = {
    "tier1": {
        "FDA decision": 3,
        "FDA approval": 3,
        "FDA ruling": 3,
        "PDUFA": 3,
        "earnings today": 3,
        "earnings release": 3,
        "data readout": 3,
        "phase 3 results": 3,
        "phase 2 results": 3,
        "clinical trial results": 3,
        "merger announcement": 3,
        "acquisition news": 3,
        "binary event": 3,
        "partnership announcement": 3,
        "contract awarded": 3,
        "government contract": 3,
        "DOD contract": 3,
        "buyout announced": 3,
        "takeover bid": 3,
        "strategic review": 3,
    },
    "tier2": {
        "catalyst today": 2,
        "big news today": 2,
        "news dropping": 2,
        "news coming": 2,
        "watch $": 2,
        "keep an eye on": 2,
        "major announcement": 2,
        "press release today": 2,
        "announcement today": 2,
        "someone knows something": 2,
        "unusual options activity": 2,
        "options flow": 2,
        "dark pool": 2,
        "loading up": 2,
        "8-K filed": 2,
        "10-K today": 2,
        "SEC filing today": 2,
        "short squeeze": 2,
        "short interest": 2,
        "heavily shorted": 2,
    },
    "tier3": {
        "watch this": 1,
        "interesting today": 1,
        "eyes on": 1,
        "don't sleep on": 1,
        "here we go": 1,
        "it's happening": 1,
        "breaking": 1,
        "volume spike": 1,
        "premarket": 1,
        "pre market": 1,
        "gap up incoming": 1,
        "whale alert": 1,
        "smart money": 1,
        "accumulating": 1,
        "something is coming": 1,
        "set an alert": 1,
        "don't miss this": 1,
        "this is the one": 1,
        "paying attention to": 1,
        "loading shares": 1,
        "big move coming": 1,
        "catalyst watch": 1,
        "news watch": 1,
        "PR coming": 1,
        "halt incoming": 1,
    },
}

KEYWORD_ALIASES: Dict[str, List[str]] = {
    "fda approval": ["fda ok", "fda cleared", "fda greenlight"],
    "earnings release": ["er today", "earnings tonight", "eps release"],
    "contract awarded": ["won contract", "contract win", "award notice"],
    "short squeeze": ["squeeze setup", "squeeze candidate"],
    "premarket": ["pre market", "pre-market"],
}


def normalize_post_text(post_text: str) -> str:
    """
    Normalize social text so keyword checks are less brittle.

    Inputs:
    - post_text: raw StockTwits body text.

    Output:
    - Lowercased, whitespace-normalized text with most punctuation removed.

    Why this exists:
    - StockTwits posts include noisy punctuation and spacing, which can
      hide valid catalysts from exact substring checks.
    """
    lowered = (post_text or "").lower()
    # Keep '$' and '-' because they are meaningful in cashtags/phrases.
    cleaned = re.sub(r"[^a-z0-9$\-\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def get_escalation_level(total_score: int, high_alert_threshold: int = 3, watch_threshold: int = 1) -> str:
    """
    Convert a numeric keyword score into an alert level.

    Inputs:
    - total_score: integer score accumulated from matched keywords.

    Output:
    - 'HIGH_ALERT', 'WATCH', or 'IGNORE'.

    Why this exists:
    - We need one clear level so downstream code can decide polling
      speed and whether the ticker deserves immediate attention.
    """
    safe_watch = max(0, int(watch_threshold))
    safe_high_alert = max(safe_watch, int(high_alert_threshold))
    if total_score >= safe_high_alert:
        return "HIGH_ALERT"
    if total_score >= safe_watch:
        return "WATCH"
    return "IGNORE"


def score_post_for_catalyst(
    post_text: str,
    high_alert_threshold: int = 3,
    watch_threshold: int = 1,
    enable_aliases: bool = True,
) -> Dict[str, object]:
    """
    Score one StockTwits post using the three-tier keyword dictionary.

    Inputs:
    - post_text: one social post as a string.

    Output:
    - Dictionary with:
      - keywords_found: list of matching keyword strings
      - total_score: integer summed score
      - escalation_level: HIGH_ALERT / WATCH / IGNORE

    Why this exists:
    - We only need keyword presence (not full sentiment analysis) to
      detect potential catalyst chatter before formal news drops.
    """
    normalized = normalize_post_text(post_text)
    keywords_found: List[str] = []
    total_score = 0
    matched_keywords = set()

    for tier_keywords in TIER_KEYWORDS.values():
        for keyword, weight in tier_keywords.items():
            normalized_keyword = normalize_post_text(keyword)
            alias_candidates = [normalized_keyword]
            if enable_aliases:
                alias_candidates.extend([normalize_post_text(item) for item in KEYWORD_ALIASES.get(keyword.lower(), [])])
            if any(candidate and candidate in normalized for candidate in alias_candidates):
                keyword_key = keyword.lower()
                if keyword_key in matched_keywords:
                    continue
                matched_keywords.add(keyword_key)
                keywords_found.append(keyword)
                total_score += int(weight)

    return {
        "keywords_found": keywords_found,
        "total_score": total_score,
        "escalation_level": get_escalation_level(
            total_score,
            high_alert_threshold=high_alert_threshold,
            watch_threshold=watch_threshold,
        ),
    }


def run_demo_tests() -> None:
    """
    Run five example posts to demonstrate how scoring behaves.

    Inputs:
    - None.

    Output:
    - None. Prints test-case results in the terminal.

    Why this exists:
    - A simple direct test gives beginners confidence that keyword
      rules are working before integrating API calls.
    """
    test_posts = [
        "Keep an eye on $ASTC, big news today and PR coming.",
        "Company has FDA approval and phase 3 results this morning.",
        "Premarket volume spike, watch this one.",
        "No catalyst here, just regular chatter.",
        "Short squeeze + unusual options activity + someone knows something.",
    ]

    print("Keyword Detector Test Cases")
    print("=" * 80)
    for index, post in enumerate(test_posts, start=1):
        result = score_post_for_catalyst(post)
        print(f"\nTest {index}: {post}")
        print(f"  Keywords: {result['keywords_found']}")
        print(f"  Total score: {result['total_score']}")
        print(f"  Escalation: {result['escalation_level']}")


if __name__ == "__main__":
    run_demo_tests()
