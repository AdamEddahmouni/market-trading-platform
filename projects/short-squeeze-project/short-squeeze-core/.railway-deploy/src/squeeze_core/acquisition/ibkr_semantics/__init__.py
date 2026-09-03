"""Deterministic IBKR historical-bar semantic resolution (Phase 3D Batch 06).

Pure logic that maps official IBKR documented evidence (and the installed official
``ibapi`` contract) onto the existing Batch 03 ``local_bar_intake`` semantic
vocabulary. No network, Gateway, account, or OHLCV access; no case association; no
outcome work. Where official evidence is silent, fields resolve to ``UNKNOWN``.
"""

from .evidence import (
    FILTERED_FEED_DISCLOSURE,
    OFFICIAL_CITATIONS,
    OFFICIAL_TRADES_EVIDENCE,
    EvidenceClass,
    IbkrHistoricalSemanticEvidence,
    SemanticEvidenceCitation,
    TimestampBoundaryDoc,
    VolumeUnitResolution,
)
from .resolver import (
    SUPPORTED_WHAT_TO_SHOW,
    ResolvedIbkrSemantics,
    resolve_ibkr_semantics,
)

__all__ = [
    "FILTERED_FEED_DISCLOSURE",
    "OFFICIAL_CITATIONS",
    "OFFICIAL_TRADES_EVIDENCE",
    "EvidenceClass",
    "IbkrHistoricalSemanticEvidence",
    "SemanticEvidenceCitation",
    "TimestampBoundaryDoc",
    "VolumeUnitResolution",
    "SUPPORTED_WHAT_TO_SHOW",
    "ResolvedIbkrSemantics",
    "resolve_ibkr_semantics",
]
