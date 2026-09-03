"""Provider-neutral observational market-data boundary (ADR-LIVE-001).

Canonical core never imports vendor SDKs. Live Moomoo bytes enter only as
serialized JSON/JSONL produced by an optional adapter process.
"""

from .allocator import AllocationDecision, SubscriptionAllocator
from .book_features import BookFeatureSnapshot, compute_book_features, diff_book_liquidity
from .capabilities import CapabilityState, MarketCapability, merge_capability
from .capture import ProviderEnvelope, append_envelope, read_envelopes
from .lifecycle import ObservationLifecycle, next_lifecycle_state
from .normalization import (
    canonical_symbol,
    classified_trade_from_ticker,
    l1_from_quote,
    levels_from_order_book,
    live_envelope_from_capture,
    replay_envelope_from_capture,
)
from .quality import assess_book, assess_quote, assess_ticker
from .timestamps import TimestampSet, clocks_from_capture

__all__ = [
    "AllocationDecision",
    "BookFeatureSnapshot",
    "CapabilityState",
    "MarketCapability",
    "ObservationLifecycle",
    "ProviderEnvelope",
    "SubscriptionAllocator",
    "TimestampSet",
    "append_envelope",
    "assess_book",
    "assess_quote",
    "assess_ticker",
    "canonical_symbol",
    "classified_trade_from_ticker",
    "clocks_from_capture",
    "compute_book_features",
    "diff_book_liquidity",
    "l1_from_quote",
    "levels_from_order_book",
    "live_envelope_from_capture",
    "merge_capability",
    "next_lifecycle_state",
    "read_envelopes",
    "replay_envelope_from_capture",
]
