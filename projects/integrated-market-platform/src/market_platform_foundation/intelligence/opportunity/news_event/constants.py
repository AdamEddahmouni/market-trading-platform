"""BUILD 09 NEWS_EVENT detector — stable identifiers (provider-agnostic)."""

from __future__ import annotations

DETECTOR_ID = "canonical-news-event"
DETECTOR_VERSION = "1"
DETECTOR_POLICY_ID = "canonical-news-event-policy-v1"
NORMALIZATION_VERSION = "intelligence/news-event/normalize/1.0.0"

# Canonical EventV1 type produced by news_article_to_event_v1 (and admit path).
CANONICAL_NEWS_ARTICLE_EVENT_TYPE = "NEWS_ARTICLE"

# Tempting but non-canonical event types — never activate NEWS_EVENT from these.
NON_CANONICAL_NEWS_EVENT_TYPES = frozenset(
    {
        "NEWS",
        "NEWS_EVENT",
        "HEADLINE",
        "STORY",
        "PRESS_RELEASE",
        "ARTICLE",
    }
)
