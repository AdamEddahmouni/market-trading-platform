"""Filter law-firm / plaintiff-solicitation press releases from news sentiment.

Purpose
-------
Detect plaintiff-firm marketing wires (Kaplan Fox, ClaimsFiler, etc.) that mimic
catalyst headlines but are lead-plaintiff solicitations, not company news.

Pipeline role
-------------
Applied in ``news_aggregator`` and ``catalyst_scanner`` before LLM scoring.
Prevents false-negative sentiment on lawsuit-alert spam.

Key outputs
-----------
``filter_solicitation_articles`` → ``(kept, dropped)`` split;
``is_law_firm_solicitation`` boolean for single headlines.

Handoff notes
-------------
**Reusable (equity/futures):** Fully portable — regex/phrase lists are
asset-class agnostic. Toggle via ``settings.news.exclude_law_firm_solicitations``.

**Options-only coupling:** None.

These wires (Kaplan Fox, ClaimsFiler, Robbins, etc.) are marketing for lead-
plaintiff deadlines — not fresh company catalysts. Feeding them to Claude as
"lawsuit headwinds" produces false-negative scores (e.g. BE on 2026-07-31).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Headline/body patterns typical of plaintiff-solicitation PRs.
_SOLICITATION_PHRASES = (
    "securities class action",
    "class action lawsuit",
    "class-action lawsuit",
    "class action deadline",
    "lead plaintiff deadline",
    "lead plaintiff",
    "shareholder rights",
    "stockholder rights",
    "shareholder alert",
    "stockholder alert",
    "investor alert",
    "investors who purchased",
    "investors with losses",
    "investors with substantial losses",
    "may have legal remedies",
    "opportunity to lead",
    "encourages .* investors",
    "reminds investors",
    "urges .* investors",
    "contact the firm",
    "investigation of",
    "class action investigation",
    "securities class action investigation",
)

# Firm / mill names that commonly headline solicitation wires.
_LAW_FIRM_SUBJECTS = (
    "kaplan fox",
    "kilsheimer",
    "claimsfiler",
    "robbins llp",
    "robbins geller",
    "rosen law",
    "bronstein",
    "gewirtz",
    "hagens berman",
    "block & leviton",
    "block and leviton",
    "kessler topaz",
    "meltzer check",
    "poe & associates",
    "the m&a class action firm",
    "hbss",
    "rgrd law",
    "suewallst",
)

_PHRASE_RE = re.compile(
    "|".join(
        (p if ".*" in p else re.escape(p)) for p in _SOLICITATION_PHRASES
    ),
    re.IGNORECASE,
)
_FIRM_RE = re.compile("|".join(re.escape(n) for n in _LAW_FIRM_SUBJECTS), re.IGNORECASE)

# "Alerts X Investors to a ... Deadline" / "Law Firm Announces ..."
_ALERT_DEADLINE_RE = re.compile(
    r"\b(alerts?|reminds?|urges?|encourages?)\b.{0,80}\b(investors?|shareholders?|stockholders?)\b"
    r".{0,120}\b(deadline|class\s*action|lawsuit|investigation)\b",
    re.IGNORECASE | re.DOTALL,
)
_LLP_ALERTS_RE = re.compile(
    r"\b(llp|law\s+firm|llc)\b.{0,40}\b(alerts?|reminds?|urges?|announces?|encourages?)\b",
    re.IGNORECASE,
)


def is_law_firm_solicitation(
    headline: str = "",
    text: str = "",
    *,
    url: str = "",
) -> bool:
    """
    True when content looks like a plaintiff-solicitation / lead-plaintiff PR.

    Match on headline first; body/url are secondary signals.
    """
    head = str(headline or "").strip()
    body = str(text or "").strip()
    blob = f"{head}\n{body}".lower()
    if not head and not body:
        return False

    if head and (_PHRASE_RE.search(head) or _FIRM_RE.search(head)):
        # Firm-as-subject + class-action language, or solicitation phrase alone.
        if _FIRM_RE.search(head) or _ALERT_DEADLINE_RE.search(head) or _LLP_ALERTS_RE.search(head):
            return True
        if _PHRASE_RE.search(head) and (
            "deadline" in head.lower()
            or "investor" in head.lower()
            or "shareholder" in head.lower()
            or "stockholder" in head.lower()
            or "alert" in head.lower()
        ):
            return True

    if _FIRM_RE.search(blob) and _PHRASE_RE.search(blob):
        return True
    if _ALERT_DEADLINE_RE.search(head or body[:400]):
        return True
    if _LLP_ALERTS_RE.search(head) and (
        "class action" in blob or "lawsuit" in blob or "deadline" in blob
    ):
        return True

    url_l = str(url or "").lower()
    if url_l and any(
        tok in url_l
        for tok in (
            "shareholder-alert",
            "stockholder-alert",
            "investor-alert",
            "class-action",
            "lead-plaintiff",
            "kaplan-fox",
            "claimsfiler",
            "rosen-law",
        )
    ):
        # URL alone is weaker — require a soft headline/body cue.
        if _PHRASE_RE.search(blob) or _FIRM_RE.search(blob) or "deadline" in blob:
            return True

    return False


def filter_solicitation_articles(
    articles: List[Dict[str, Any]],
    *,
    settings: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split articles into (kept, dropped_solicitations).

    Disabled when ``news.exclude_law_firm_solicitations`` is False.
    """
    news_cfg = (settings or {}).get("news") if isinstance(settings, dict) else {}
    news_cfg = news_cfg if isinstance(news_cfg, dict) else {}
    if not bool(news_cfg.get("exclude_law_firm_solicitations", True)):
        return list(articles), []

    kept: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        headline = str(article.get("headline") or article.get("title") or "")
        text = str(article.get("text") or article.get("summary") or "")
        url = str(article.get("url") or "")
        if is_law_firm_solicitation(headline, text, url=url):
            dropped.append(article)
        else:
            kept.append(article)
    return kept, dropped
