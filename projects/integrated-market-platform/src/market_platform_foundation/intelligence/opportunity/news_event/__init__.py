"""BUILD 09 NEWS_EVENT: NEWS_ARTICLE EventV1 → DetectionV1.

Provider-agnostic. Finviz (and any other provider) must already be EventV1.
OpportunityEngine.assess remains ForecastV1-gated and is not invoked here.
"""

from __future__ import annotations

from .constants import (
    CANONICAL_NEWS_ARTICLE_EVENT_TYPE,
    DETECTOR_ID,
    DETECTOR_POLICY_ID,
    DETECTOR_VERSION,
    NON_CANONICAL_NEWS_EVENT_TYPES,
    NORMALIZATION_VERSION,
)
from .detector import build_news_event_detection
from .facts import CanonicalNewsInput
from .normalize import accepts_canonical_news_article_event, normalize_news_article_event
from .pipeline import NewsEventVerticalResult, run_news_event_vertical
from .validation import NewsEventFailureCode, NewsEventValidation, validate_news_event_inputs

__all__ = [
    "CANONICAL_NEWS_ARTICLE_EVENT_TYPE",
    "CanonicalNewsInput",
    "DETECTOR_ID",
    "DETECTOR_POLICY_ID",
    "DETECTOR_VERSION",
    "NON_CANONICAL_NEWS_EVENT_TYPES",
    "NORMALIZATION_VERSION",
    "NewsEventFailureCode",
    "NewsEventValidation",
    "NewsEventVerticalResult",
    "accepts_canonical_news_article_event",
    "build_news_event_detection",
    "normalize_news_article_event",
    "run_news_event_vertical",
    "validate_news_event_inputs",
]
