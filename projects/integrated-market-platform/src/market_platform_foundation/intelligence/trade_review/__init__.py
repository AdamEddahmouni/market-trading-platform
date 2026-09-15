"""Trade review foundation — post-event learning without execution authority."""

from .construct import (
    build_live_trade_review,
    build_paper_trade_review,
    build_rejected_opportunity_review,
    build_watched_opportunity_review,
)
from .contracts import (
    TRADE_REVIEW_FOUNDATION_READY,
    TRADE_REVIEW_IMPLEMENTATION_VERSION,
    TRADE_REVIEW_SCHEMA_VERSION,
    TradeExecutionAttribution,
    TradeReviewMode,
    TradeReviewV1,
)
from .identity import derive_trade_review_id
from .repository import InMemoryTradeReviewRepository, TradeReviewRepository
from .serialization import trade_review_v1_from_dict, trade_review_v1_to_dict

__all__ = [
    "TRADE_REVIEW_FOUNDATION_READY",
    "TRADE_REVIEW_IMPLEMENTATION_VERSION",
    "TRADE_REVIEW_SCHEMA_VERSION",
    "InMemoryTradeReviewRepository",
    "TradeExecutionAttribution",
    "TradeReviewMode",
    "TradeReviewRepository",
    "TradeReviewV1",
    "build_live_trade_review",
    "build_paper_trade_review",
    "build_rejected_opportunity_review",
    "build_watched_opportunity_review",
    "derive_trade_review_id",
    "trade_review_v1_from_dict",
    "trade_review_v1_to_dict",
]
