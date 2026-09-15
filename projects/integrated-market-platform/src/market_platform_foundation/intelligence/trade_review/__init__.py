"""Trade review foundation — post-event learning without execution authority."""

from .construct import (
    build_live_trade_review,
    build_paper_trade_review,
    build_rejected_opportunity_review,
    build_watched_opportunity_review,
)
from .contracts import (
    TRADE_REVIEW_DURABLE_LOOP_READY,
    TRADE_REVIEW_FOUNDATION_READY,
    TRADE_REVIEW_IMPLEMENTATION_VERSION,
    TRADE_REVIEW_SCHEMA_VERSION,
    TradeExecutionAttribution,
    TradeReviewMode,
    TradeReviewV1,
)
from .identity import derive_trade_review_id
from .materialize import materialize_trade_review_for_operator_ack
from .repository import InMemoryTradeReviewRepository, TradeReviewRepository
from .sqlite_repository import SqliteTradeReviewRepository
from .store import open_trade_review_repository, reset_trade_review_repository_for_tests
from .serialization import trade_review_v1_from_dict, trade_review_v1_to_dict

__all__ = [
    "TRADE_REVIEW_DURABLE_LOOP_READY",
    "TRADE_REVIEW_FOUNDATION_READY",
    "TRADE_REVIEW_IMPLEMENTATION_VERSION",
    "TRADE_REVIEW_SCHEMA_VERSION",
    "InMemoryTradeReviewRepository",
    "SqliteTradeReviewRepository",
    "materialize_trade_review_for_operator_ack",
    "open_trade_review_repository",
    "reset_trade_review_repository_for_tests",
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
