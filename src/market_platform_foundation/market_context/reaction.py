"""MC12 market reaction engine — consumer-only confirmation/contradiction classification."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ..contracts.market_context import (
    ContextQualityFlag,
    InformationDecayClass,
    MarketReactionEvidence,
    PublicationState,
    ReactionConfirmationState,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns
from .catalyst import CatalystSummary
from .expectations import SurpriseSummary

PRODUCER_VERSION = "market_context_reaction_v1"
SCORING_METHOD = "market_reaction_v1"

ABNORMAL_RETURN_BULLISH_THRESHOLD = 0.005
ABNORMAL_RETURN_BEARISH_THRESHOLD = -0.005

_BULLISH_CROSS_LANE_SIGNALS = frozenset(
    {
        EvidenceSignal.CVD_POSITIVE_SLOPE.value,
        EvidenceSignal.AGGRESSIVE_BUY_PRESSURE.value,
        EvidenceSignal.MICROSTRUCTURE_CONTINUATION_UP.value,
        EvidenceSignal.PERSISTENT_AGGRESSIVE_BUY_FLOW.value,
        EvidenceSignal.OPTION_FLOW_DIRECTION.value,
        EvidenceSignal.FUTURES_ORDER_FLOW_CONFIRMING.value,
        EvidenceSignal.FUTURES_TREND_UP.value,
        EvidenceSignal.EVENT_SURPRISE_POSITIVE.value,
        EvidenceSignal.SEMANTIC_SENTIMENT_POSITIVE.value,
    }
)
_BEARISH_CROSS_LANE_SIGNALS = frozenset(
    {
        EvidenceSignal.CVD_NEGATIVE_SLOPE.value,
        EvidenceSignal.AGGRESSIVE_SELL_PRESSURE.value,
        EvidenceSignal.MICROSTRUCTURE_CONTINUATION_DOWN.value,
        EvidenceSignal.PERSISTENT_AGGRESSIVE_SELL_FLOW.value,
        EvidenceSignal.OPTIONS_FLOW_REVERSAL.value,
        EvidenceSignal.FUTURES_TREND_DOWN.value,
        EvidenceSignal.EVENT_SURPRISE_NEGATIVE.value,
        EvidenceSignal.SEMANTIC_SENTIMENT_NEGATIVE.value,
    }
)


@dataclass(frozen=True, slots=True)
class ReactionFixtureRow:
    event_id: str
    abnormal_return: float | None
    volume_multiple: float | None
    horizon: str | None
    cross_lane_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReactionSummary:
    entity_id: str
    event_id: str
    canonical_event_type: str
    semantic_direction: str | None
    predicted_economic_direction: str | None
    observed_market_direction: str | None
    reaction_mismatch: bool
    confirmation_state: str
    abnormal_return: float | None
    volume_multiple: float | None
    priced_in_probability: float | None
    remaining_information_edge: float | None
    information_decay_class: str | None
    horizon: str | None
    cross_lane_refs: tuple[str, ...]
    event_time: str
    available_time: str
    publication_state: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    reaction_available: bool = False
    headline: str = ""


def load_reaction_fixture(path: Path) -> dict[str, ReactionFixtureRow]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("reactions") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return {}
    result: dict[str, ReactionFixtureRow] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        event_id = str(row.get("event_id", ""))
        if not event_id:
            continue
        abnormal_raw = row.get("abnormal_return")
        volume_raw = row.get("volume_multiple")
        abnormal_return = float(abnormal_raw) if abnormal_raw is not None else None
        volume_multiple = float(volume_raw) if volume_raw is not None else None
        refs = row.get("cross_lane_refs") or []
        cross_lane_refs = tuple(str(item) for item in refs if item)
        result[event_id] = ReactionFixtureRow(
            event_id=event_id,
            abnormal_return=abnormal_return,
            volume_multiple=volume_multiple,
            horizon=str(row.get("horizon")) if row.get("horizon") else None,
            cross_lane_refs=cross_lane_refs,
        )
    return result


def _direction_from_return(abnormal_return: float | None) -> str | None:
    if abnormal_return is None:
        return None
    if abnormal_return >= ABNORMAL_RETURN_BULLISH_THRESHOLD:
        return "BULLISH"
    if abnormal_return <= ABNORMAL_RETURN_BEARISH_THRESHOLD:
        return "BEARISH"
    return "NEUTRAL"


def _predicted_direction(
    catalyst: CatalystSummary,
    surprise_by_event: dict[str, SurpriseSummary],
) -> str | None:
    surprise = surprise_by_event.get(catalyst.event_id)
    if surprise is not None and surprise.standardized_surprise is not None:
        try:
            value = Decimal(str(surprise.standardized_surprise))
        except (InvalidOperation, ValueError):
            value = None
        if value is not None:
            if value > 0:
                return "BULLISH"
            if value < 0:
                return "BEARISH"
            return "NEUTRAL"
    return catalyst.lean if catalyst.lean != "NEUTRAL" else None


def _cross_lane_vote(cross_lane_refs: tuple[str, ...]) -> str | None:
    bullish = sum(1 for signal in cross_lane_refs if signal in _BULLISH_CROSS_LANE_SIGNALS)
    bearish = sum(1 for signal in cross_lane_refs if signal in _BEARISH_CROSS_LANE_SIGNALS)
    if bullish > 0 and bearish > 0:
        return "MIXED"
    if bullish > bearish:
        return "BULLISH"
    if bearish > bullish:
        return "BEARISH"
    return None


def compute_confirmation_state(
    *,
    semantic_direction: str | None,
    observed_direction: str | None,
    abnormal_return: float | None,
    cross_lane_refs: tuple[str, ...],
    fixture_present: bool,
) -> tuple[ReactionConfirmationState, bool]:
    if not fixture_present:
        return ReactionConfirmationState.INSUFFICIENT_DATA, False

    semantic = semantic_direction or "NEUTRAL"
    observed = observed_direction or "NEUTRAL"
    vote = _cross_lane_vote(cross_lane_refs)

    if semantic != "NEUTRAL" and observed != "NEUTRAL":
        if semantic == observed:
            return ReactionConfirmationState.CONFIRMED, False
        return ReactionConfirmationState.CONTRADICTED, True

    if vote == "MIXED":
        return ReactionConfirmationState.MIXED, False

    if semantic != "NEUTRAL" and observed == "NEUTRAL":
        if vote == semantic:
            return ReactionConfirmationState.PARTIALLY_CONFIRMED, False

    if abnormal_return is not None and abs(abnormal_return) < ABNORMAL_RETURN_BULLISH_THRESHOLD:
        if vote != semantic:
            return ReactionConfirmationState.NO_MEANINGFUL_REACTION, False

    if vote == semantic and semantic != "NEUTRAL":
        return ReactionConfirmationState.CONFIRMED, False

    return ReactionConfirmationState.NO_MEANINGFUL_REACTION, False


def build_market_reaction_evidence(summary: ReactionSummary) -> MarketReactionEvidence:
    publication = (
        PublicationState.PUBLISHED
        if summary.confirmation_state != ReactionConfirmationState.INSUFFICIENT_DATA.value
        else PublicationState.UNAVAILABLE
    )
    return MarketReactionEvidence(
        entity_id=summary.entity_id,
        event_id=summary.event_id,
        semantic_direction=summary.semantic_direction,
        predicted_economic_direction=summary.predicted_economic_direction,
        observed_market_direction=summary.observed_market_direction,
        reaction_mismatch=summary.reaction_mismatch,
        confirmation_state=ReactionConfirmationState(summary.confirmation_state),
        abnormal_return=summary.abnormal_return,
        volume_multiple=summary.volume_multiple,
        priced_in_probability=summary.priced_in_probability,
        remaining_information_edge=summary.remaining_information_edge,
        information_decay_class=(
            InformationDecayClass(summary.information_decay_class)
            if summary.information_decay_class
            else None
        ),
        horizon=summary.horizon,
        event_time=summary.event_time,
        available_time=summary.available_time,
        publication_state=publication,
        provenance_ref=f"{PRODUCER_VERSION}:{SCORING_METHOD}",
        quality_flags=summary.quality_flags,
    )


def build_fixture_reaction_pipeline(
    catalyst_summaries: list[CatalystSummary],
    surprise_summaries: list[SurpriseSummary],
    reaction_fixture: dict[str, ReactionFixtureRow],
    *,
    prediction_cutoff: int,
    entity_id: str,
) -> tuple[
    list[MarketReactionEvidence],
    list[ReactionSummary],
    list[dict[str, Any]],
]:
    surprise_by_event = {
        item.event_id: item for item in surprise_summaries if item.event_id is not None
    }
    gated = [
        item
        for item in catalyst_summaries
        if item.gate_ok and iso_to_epoch_ns(item.available_time) <= prediction_cutoff
    ]
    gated = sorted(gated, key=lambda item: (item.available_time, item.event_id))

    evidence_rows: list[MarketReactionEvidence] = []
    summary_rows: list[ReactionSummary] = []
    adapter_rows: list[dict[str, Any]] = []

    for catalyst in gated:
        fixture_row = reaction_fixture.get(catalyst.event_id)
        quality_flags: list[str] = []
        if fixture_row is None:
            quality_flags.append(ContextQualityFlag.MARKET_REACTION_DATA_MISSING.value)

        abnormal_return = fixture_row.abnormal_return if fixture_row else None
        volume_multiple = fixture_row.volume_multiple if fixture_row else None
        horizon = fixture_row.horizon if fixture_row else None
        cross_lane_refs = fixture_row.cross_lane_refs if fixture_row else tuple()

        semantic_direction = catalyst.lean if catalyst.lean != "NEUTRAL" else None
        predicted_direction = _predicted_direction(catalyst, surprise_by_event)
        observed_direction = _direction_from_return(abnormal_return)
        confirmation_state, reaction_mismatch = compute_confirmation_state(
            semantic_direction=semantic_direction,
            observed_direction=observed_direction,
            abnormal_return=abnormal_return,
            cross_lane_refs=cross_lane_refs,
            fixture_present=fixture_row is not None,
        )

        summary = ReactionSummary(
            entity_id=entity_id,
            event_id=catalyst.event_id,
            canonical_event_type=catalyst.canonical_event_type,
            semantic_direction=semantic_direction,
            predicted_economic_direction=predicted_direction,
            observed_market_direction=observed_direction,
            reaction_mismatch=reaction_mismatch,
            confirmation_state=confirmation_state.value,
            abnormal_return=abnormal_return,
            volume_multiple=volume_multiple,
            priced_in_probability=None,
            remaining_information_edge=None,
            information_decay_class=None,
            horizon=horizon,
            cross_lane_refs=cross_lane_refs,
            event_time=catalyst.event_time,
            available_time=catalyst.available_time,
            publication_state=(
                PublicationState.PUBLISHED.value
                if fixture_row is not None
                else PublicationState.UNAVAILABLE.value
            ),
            quality_flags=tuple(dict.fromkeys(quality_flags)),
            reaction_available=fixture_row is not None,
            headline=catalyst.headline,
        )
        evidence = build_market_reaction_evidence(summary)
        evidence_rows.append(evidence)
        summary_rows.append(summary)
        adapter_rows.append(reaction_summary_to_adapter_row(summary))

    return evidence_rows, summary_rows, adapter_rows


def reaction_summary_to_dict(item: ReactionSummary) -> dict[str, Any]:
    return {
        "entity_id": item.entity_id,
        "event_id": item.event_id,
        "canonical_event_type": item.canonical_event_type,
        "semantic_direction": item.semantic_direction,
        "predicted_economic_direction": item.predicted_economic_direction,
        "observed_market_direction": item.observed_market_direction,
        "reaction_mismatch": item.reaction_mismatch,
        "confirmation_state": item.confirmation_state,
        "abnormal_return": item.abnormal_return,
        "volume_multiple": item.volume_multiple,
        "priced_in_probability": item.priced_in_probability,
        "remaining_information_edge": item.remaining_information_edge,
        "information_decay_class": item.information_decay_class,
        "horizon": item.horizon,
        "cross_lane_refs": list(item.cross_lane_refs),
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state,
        "quality_flags": list(item.quality_flags),
        "reaction_available": item.reaction_available,
        "headline": item.headline,
        "scoring_method": SCORING_METHOD,
    }


def reaction_summary_to_adapter_row(item: ReactionSummary) -> dict[str, Any]:
    return {
        "event_id": item.event_id,
        "entity_id": item.entity_id,
        "canonical_event_type": item.canonical_event_type,
        "semantic_direction": item.semantic_direction,
        "observed_market_direction": item.observed_market_direction,
        "reaction_mismatch": item.reaction_mismatch,
        "confirmation_state": item.confirmation_state,
        "abnormal_return": item.abnormal_return,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "scoring_method": SCORING_METHOD,
    }


def build_reaction_cross_lane_evidence(
    summaries: list[ReactionSummary],
    *,
    symbol: str,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in summaries:
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        if item.confirmation_state == ReactionConfirmationState.INSUFFICIENT_DATA.value:
            continue
        if item.confirmation_state == ReactionConfirmationState.CONTRADICTED.value:
            signal = EvidenceSignal.REACTION_CONTRADICTED
            strength = "HIGH"
        elif item.confirmation_state in {
            ReactionConfirmationState.CONFIRMED.value,
            ReactionConfirmationState.PARTIALLY_CONFIRMED.value,
        }:
            signal = EvidenceSignal.REACTION_CONFIRMED
            strength = (
                "MODERATE"
                if item.confirmation_state == ReactionConfirmationState.PARTIALLY_CONFIRMED.value
                else "HIGH"
            )
        else:
            continue

        row = lane_evidence_to_dict(
            NormalizedLaneEvidence(
                lane=LaneId.MARKET_CONTEXT,
                signal=signal,
                strength=strength,
                available=True,
                source_ref=item.event_id,
                detail=(
                    f"MC12 market reaction {item.confirmation_state.lower()} on "
                    f"{item.canonical_event_type}"
                ),
                observed_at=item.available_time,
                quality_flags=item.quality_flags,
                provenance_class=EvidenceProvenanceClass.DERIVED,
            )
        )
        row["metadata"] = {
            "symbol": symbol,
            "event_id": item.event_id,
            "semantic_direction": item.semantic_direction,
            "observed_market_direction": item.observed_market_direction,
            "reaction_mismatch": item.reaction_mismatch,
            "confirmation_state": item.confirmation_state,
            "abnormal_return": item.abnormal_return,
            "cross_lane_refs": list(item.cross_lane_refs),
            "scoring_method": SCORING_METHOD,
        }
        evidence.append(row)
    return evidence


__all__ = [
    "ABNORMAL_RETURN_BEARISH_THRESHOLD",
    "ABNORMAL_RETURN_BULLISH_THRESHOLD",
    "PRODUCER_VERSION",
    "ReactionFixtureRow",
    "ReactionSummary",
    "SCORING_METHOD",
    "build_fixture_reaction_pipeline",
    "build_market_reaction_evidence",
    "build_reaction_cross_lane_evidence",
    "compute_confirmation_state",
    "load_reaction_fixture",
    "reaction_summary_to_adapter_row",
    "reaction_summary_to_dict",
]
