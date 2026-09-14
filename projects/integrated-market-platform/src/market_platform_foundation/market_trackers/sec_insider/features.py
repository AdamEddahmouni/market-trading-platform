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
        feature_id="insider.txn_code_raw",
        description="Raw SEC transaction code (P, S, M, F, …) preserved without bullish/bearish mapping.",
        source_fields=("code",),
        defensibility="high_when_present",
        pitfalls=("null_on_form3_holdings", "code_alone_not_discretionary_signal"),
    ),
    CandidateFeature(
        feature_id="insider.acquired_disposed",
        description="Reported A/D flag when present; not equivalent to open-market buy/sell.",
        source_fields=("acquiredDisposed", "code"),
        defensibility="medium",
        pitfalls=("grants_and_tax_withholdings", "derivative_rows"),
    ),
    CandidateFeature(
        feature_id="insider.reporting_person_role",
        description="Director/officer/10% owner booleans from filing.",
        source_fields=("insider.isDirector", "insider.isOfficer", "insider.isTenPctOwner", "insider.title"),
        defensibility="high",
        pitfalls=("title_text_unnormalized"),
    ),
    CandidateFeature(
        feature_id="insider.filing_timing_delta_days",
        description="Days between transactedAt and filedAt when both exist (reporting lag proxy).",
        source_fields=("transactedAt", "filedAt"),
        defensibility="medium",
        pitfalls=("do_not_use_transactedAt_as_public_time", "amendments_shift_filedAt"),
    ),
    CandidateFeature(
        feature_id="insider.clustering_by_insider_cik",
        description="Count/window of rows per insider CIK (requires external snapshot store).",
        source_fields=("insider.cik", "transactedAt", "filedAt"),
        defensibility="low_without_full_history",
        pitfalls=("ingestion_day_deltas_not_event_complete"),
    ),
    CandidateFeature(
        feature_id="insider.size_shares",
        description="Reported share count on row when numeric.",
        source_fields=("shares",),
        defensibility="medium",
        pitfalls=("null_values", "split_adjustment_not_applied"),
    ),
    CandidateFeature(
        feature_id="insider.size_notional",
        description="shares * pricePerShare when both present.",
        source_fields=("shares", "pricePerShare"),
        defensibility="low_to_medium",
        pitfalls=("missing_price", "derivative_vs_common"),
    ),
    CandidateFeature(
        feature_id="insider.holdings_after",
        description="sharesOwnedFollowing when reported on row.",
        source_fields=("sharesOwnedAfter",),
        defensibility="medium_when_sourced_from_filing",
        pitfalls=("not_all_rows_populated", "indirect_ownership"),
    ),
)


def candidate_feature_catalog() -> tuple[dict[str, Any], ...]:
    return tuple(feature.to_dict() for feature in CANDIDATE_FEATURES)
