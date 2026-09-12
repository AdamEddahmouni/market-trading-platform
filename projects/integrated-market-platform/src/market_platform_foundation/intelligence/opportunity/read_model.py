"""Canonical opportunity read model with provisional deterministic ranking.

Ranking weights are engineering placeholders — not FTEP-tuned campaign numerics.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Protocol

from market_platform_foundation.news.contracts import PipelineEventResult

READ_MODEL_SCHEMA_VERSION = "opportunity/read_model/1.0.0"

# Provisional stub weights (documented; replace when campaign calibration lands).
PROVISIONAL_RANKING_WEIGHTS: dict[str, float] = {
    "catalyst_match_count": 0.40,
    "instrument_explicit_link": 0.25,
    "headline_length_norm": 0.15,
    "accepted_pipeline": 0.20,
}


@dataclass(frozen=True, slots=True)
class OpportunitySummary:
    """Operator-facing opportunity projection — not an order or lock."""

    summary_id: str
    instrument_id: str
    headline: str
    catalyst_ids: tuple[str, ...] = ()
    source_event_id: str = ""
    campaign_slug: str | None = None
    accepted: bool = True
    rank_score: float | None = None
    rank_order: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": READ_MODEL_SCHEMA_VERSION,
            "summary_id": self.summary_id,
            "instrument_id": self.instrument_id,
            "headline": self.headline,
            "catalyst_ids": list(self.catalyst_ids),
            "source_event_id": self.source_event_id,
            "campaign_slug": self.campaign_slug,
            "accepted": self.accepted,
            "rank_score": self.rank_score,
            "rank_order": self.rank_order,
            "metadata": dict(self.metadata),
        }


class OpportunitySummaryStore(Protocol):
    def upsert(self, summary: OpportunitySummary) -> None: ...

    def list_summaries(self) -> tuple[OpportunitySummary, ...]: ...

    def clear(self) -> None: ...


class InMemoryOpportunitySummaryStore:
    """Process-local read-model cache (non-authoritative)."""

    def __init__(self) -> None:
        self._by_id: dict[str, OpportunitySummary] = {}

    def upsert(self, summary: OpportunitySummary) -> None:
        self._by_id[summary.summary_id] = summary

    def list_summaries(self) -> tuple[OpportunitySummary, ...]:
        return tuple(self._by_id[key] for key in sorted(self._by_id))

    def clear(self) -> None:
        self._by_id.clear()


def provisional_rank_score(summary: OpportunitySummary) -> float:
    weights = PROVISIONAL_RANKING_WEIGHTS
    catalyst_component = min(len(summary.catalyst_ids), 5) / 5.0
    link_component = 1.0 if summary.instrument_id else 0.0
    headline_component = min(len(summary.headline), 120) / 120.0
    accepted_component = 1.0 if summary.accepted else 0.0
    return (
        weights["catalyst_match_count"] * catalyst_component
        + weights["instrument_explicit_link"] * link_component
        + weights["headline_length_norm"] * headline_component
        + weights["accepted_pipeline"] * accepted_component
    )


def rank_opportunity_summaries(
    summaries: tuple[OpportunitySummary, ...] | list[OpportunitySummary],
) -> tuple[OpportunitySummary, ...]:
    """Deterministic descending rank; ties broken by ``summary_id``."""

    scored = sorted(
        ((summary, provisional_rank_score(summary), summary.summary_id) for summary in summaries),
        key=lambda row: (-row[1], row[2]),
    )
    ranked: list[OpportunitySummary] = []
    for order, (summary, score, _) in enumerate(scored, start=1):
        ranked.append(replace(summary, rank_score=score, rank_order=order))
    return tuple(ranked)


def ftep_pipeline_result_to_summary(
    result: PipelineEventResult,
    *,
    campaign_slug: str = "FTEP-V1-002",
) -> OpportunitySummary:
    """Map governed news pipeline output to an opportunity read-model row."""

    event = result.event
    instrument_id = ""
    if event.instrument_linkages:
        instrument_id = event.instrument_linkages[0].instrument_id
    catalyst_ids: tuple[str, ...] = ()
    for decision in result.decisions:
        if decision.matched_catalyst_ids:
            catalyst_ids = decision.matched_catalyst_ids
            break
    return OpportunitySummary(
        summary_id=f"ftep-opp-{event.event_id}",
        instrument_id=instrument_id,
        headline=event.headline,
        catalyst_ids=catalyst_ids,
        source_event_id=event.event_id,
        campaign_slug=campaign_slug,
        accepted=result.accepted,
        metadata={"adapter": "ftep_pipeline_result"},
    )


def ftep_attention_candidate_to_summary(
    row: Mapping[str, Any],
    *,
    campaign_slug: str = "FTEP-V1-002",
) -> OpportunitySummary:
    """Map donor-bridge / explore catalyst rows into ``OpportunitySummary``."""

    symbol = str(row.get("instrument_id") or row.get("symbol") or "")
    attention_id = str(row.get("attention_id") or f"ftep-attn-{symbol.lower()}")
    headline = str(row.get("headline") or f"{symbol} catalyst signal")
    return OpportunitySummary(
        summary_id=attention_id,
        instrument_id=symbol,
        headline=headline,
        catalyst_ids=tuple(str(item) for item in row.get("catalyst_ids", ()) if item),
        campaign_slug=campaign_slug,
        accepted=True,
        metadata={"adapter": "ftep_attention_candidate", "tier": row.get("tier")},
    )


__all__ = [
    "InMemoryOpportunitySummaryStore",
    "OpportunitySummary",
    "OpportunitySummaryStore",
    "PROVISIONAL_RANKING_WEIGHTS",
    "READ_MODEL_SCHEMA_VERSION",
    "ftep_attention_candidate_to_summary",
    "ftep_pipeline_result_to_summary",
    "provisional_rank_score",
    "rank_opportunity_summaries",
]
