"""Candidate feature catalog (research metadata; not admitted signals)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CandidateFeature:
    feature_id: str
    description: str
    source_fields: tuple[str, ...]
    defensibility: str
    pitfalls: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "defensibility": self.defensibility,
            "description": self.description,
            "feature_id": self.feature_id,
            "pitfalls": list(self.pitfalls),
            "source_fields": list(self.source_fields),
        }


CANDIDATE_FEATURES: tuple[CandidateFeature, ...] = (
    CandidateFeature(
        feature_id="congress.disclosed_side_raw",
        description="Filing side label (buy/sell/exchange) without LONG/SHORT mapping.",
        source_fields=("side",),
        defensibility="high_when_present",
        pitfalls=("exchange_rows", "not_execution_side"),
    ),
    CandidateFeature(
        feature_id="congress.amount_range_bounds",
        description="Statutory min/max bounds; max null when open-ended.",
        source_fields=("amountRange.min", "amountRange.max", "amountRange.text"),
        defensibility="high",
        pitfalls=("no_midpoint_inference", "wide_buckets"),
    ),
    CandidateFeature(
        feature_id="congress.filing_lag_days",
        description="Calendar days between transactedAt and filedAt (reporting delay proxy).",
        source_fields=("transactedAt", "filedAt"),
        defensibility="medium",
        pitfalls=("not_public_knowledge_lag", "amendments_not_modeled_in_prep"),
    ),
    CandidateFeature(
        feature_id="congress.owner_scope",
        description="Whether transaction attributed to self/spouse/joint/dependent when disclosed.",
        source_fields=("owner",),
        defensibility="medium_when_present",
        pitfalls=("nullable_on_some_filings",),
    ),
    CandidateFeature(
        feature_id="congress.asset_type",
        description="Normalized asset class from filing (stock, option, fund, …).",
        source_fields=("assetType", "assetDescription"),
        defensibility="medium",
        pitfalls=("parser_heuristics", "ticker_null"),
    ),
)


def candidate_feature_catalog() -> tuple[dict[str, Any], ...]:
    return tuple(feature.to_dict() for feature in CANDIDATE_FEATURES)
