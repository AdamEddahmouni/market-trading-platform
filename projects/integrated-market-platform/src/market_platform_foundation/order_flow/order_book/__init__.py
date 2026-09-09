"""Canonical provider-neutral incremental L2 order-book engine (G5 / ARCH-003).

This package is the single authoritative incremental market-by-price book
engine. Provider depth feeds are adapted into :class:`DepthUpdate` canonical
events at the boundary; snapshot replacement survives only as an explicit
ingestion compatibility mode (:meth:`IncrementalOrderBook.replace_from_snapshot`
/ :func:`ingest_snapshot_dict`).
"""

from .contracts import (
    ApplyOutcome,
    ApplyResult,
    BOOK_MODEL_VERSION,
    BookLevel,
    BookStatusReason,
    BookValidity,
    DEPTH_EVENT_SCHEMA_VERSION,
    DepthOperation,
    DepthSide,
    DepthUpdate,
    FreshnessStatus,
    SequenceState,
    build_depth_update,
    exact_decimal,
    price_key,
    size_value,
)
from .engine import IncrementalOrderBook
from .freshness import (
    FreshnessEvaluation,
    FreshnessPolicy,
    evaluate_book_freshness,
)
from .projection import ingest_snapshot_dict, project_book_snapshot
from .replay import (
    measure_replay_throughput,
    replay,
    replay_state_hash,
    replay_with_results,
)

__all__ = [
    "ApplyOutcome",
    "ApplyResult",
    "BOOK_MODEL_VERSION",
    "BookLevel",
    "BookStatusReason",
    "BookValidity",
    "DEPTH_EVENT_SCHEMA_VERSION",
    "DepthOperation",
    "DepthSide",
    "DepthUpdate",
    "FreshnessEvaluation",
    "FreshnessPolicy",
    "FreshnessStatus",
    "IncrementalOrderBook",
    "SequenceState",
    "build_depth_update",
    "evaluate_book_freshness",
    "exact_decimal",
    "ingest_snapshot_dict",
    "measure_replay_throughput",
    "price_key",
    "project_book_snapshot",
    "replay",
    "replay_state_hash",
    "replay_with_results",
    "size_value",
]
