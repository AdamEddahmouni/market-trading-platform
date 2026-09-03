"""MC13 information decay / priced-in — post-MC12 enrichment (experimental)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ..contracts.market_context import ContextQualityFlag, InformationDecayClass
from ..normalization.equity_bars import iso_to_epoch_ns
from .attention import AttentionSummary
from .catalyst import CatalystSummary
from .expectations import SurpriseSummary
from .reaction import (
    ReactionSummary,
    build_market_reaction_evidence,
)

PRODUCER_VERSION = "market_context_information_decay_v1"
SCORING_METHOD = "information_decay_v1"

PRE_EVENT_RETURN_SCALE = 0.03
SURPRISE_SCORE_SCALE = 3.0

_PRICED_IN_WEIGHTS = (
    ("pre_event", 0.40),
    ("diffusion", 0.35),
    ("surprise", 0.25),
)

_EVENT_TYPE_DECAY_CLASS: dict[str, InformationDecayClass] = {
    "offering_risk": InformationDecayClass.MINUTES,
    "earnings_beat": InformationDecayClass.HOURS,
    "earnings_miss": InformationDecayClass.HOURS,
    "fda_clearance": InformationDecayClass.DAYS,
    "analyst_upgrade": InformationDecayClass.WEEKS,
    "analyst_downgrade": InformationDecayClass.WEEKS,
}


@dataclass(frozen=True, slots=True)
class DecayFixtureRow:
    event_id: str
    pre_event_abnormal_return: float | None = None
    decay_class_override: str | None = None
    priced_in_override: float | None = None


@dataclass(frozen=True, slots=True)
class InformationDecaySummary:
    event_id: str
    entity_id: str
    canonical_event_type: str
    information_decay_class: str | None
    priced_in_probability: float | None
    remaining_information_edge: float | None
    event_time: str
    available_time: str
    publication_state: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    headline: str = ""


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def load_decay_fixture(path: Path) -> dict[str, DecayFixtureRow]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("decay_rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return {}
    result: dict[str, DecayFixtureRow] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        event_id = str(row.get("event_id", ""))
        if not event_id:
            continue
        pre_event_raw = row.get("pre_event_abnormal_return")
        pre_event = float(pre_event_raw) if pre_event_raw is not None else None
        override_raw = row.get("priced_in_override")
        priced_in_override = float(override_raw) if override_raw is not None else None
        decay_override = row.get("decay_class_override")
        result[event_id] = DecayFixtureRow(
            event_id=event_id,
            pre_event_abnormal_return=pre_event,
            decay_class_override=str(decay_override) if decay_override else None,
            priced_in_override=priced_in_override,
        )
    return result


def compute_decay_class(
    canonical_event_type: str,
    *,
    decay_class_override: str | None = None,
) -> tuple[InformationDecayClass, bool]:
    if decay_class_override:
        return InformationDecayClass(decay_class_override), False
    mapped = _EVENT_TYPE_DECAY_CLASS.get(canonical_event_type)
    if mapped is not None:
        return mapped, False
    return InformationDecayClass.DAYS, True


def _surprise_magnitude(
    catalyst: CatalystSummary | None,
    surprise: SurpriseSummary | None,
) -> float | None:
    if catalyst is not None and catalyst.surprise_score is not None:
        return abs(float(catalyst.surprise_score))
    if surprise is not None and surprise.standardized_surprise is not None:
        try:
            return abs(float(Decimal(str(surprise.standardized_surprise))))
        except (InvalidOperation, ValueError):
            return None
    return None


def compute_priced_in_probability(
    *,
    pre_event_abnormal_return: float | None,
    diffusion_score: float | None,
    surprise_magnitude: float | None,
    priced_in_override: float | None = None,
) -> tuple[float | None, bool]:
    if priced_in_override is not None:
        return round(_clamp01(priced_in_override), 6), False

    components: list[tuple[float, float]] = []
    if pre_event_abnormal_return is not None:
        components.append(
            (
                _PRICED_IN_WEIGHTS[0][1],
                _clamp01(abs(pre_event_abnormal_return) / PRE_EVENT_RETURN_SCALE),
            )
        )
    if diffusion_score is not None:
        components.append((_PRICED_IN_WEIGHTS[1][1], _clamp01(diffusion_score)))
    if surprise_magnitude is not None:
        components.append(
            (
                _PRICED_IN_WEIGHTS[2][1],
                1.0 - _clamp01(surprise_magnitude / SURPRISE_SCORE_SCALE),
            )
        )

    if not components:
        return None, True

    total_weight = sum(weight for weight, _ in components)
    if total_weight <= 0:
        return None, True

    weighted_sum = sum(weight * value for weight, value in components)
    partial = len(components) < len(_PRICED_IN_WEIGHTS)
    return round(weighted_sum / total_weight, 6), partial


def compute_remaining_information_edge(
    *,
    expected_impact: float | None,
    abnormal_return: float | None,
    priced_in_probability: float | None,
    diffusion_score: float | None,
) -> tuple[float | None, bool]:
    if expected_impact is None or abnormal_return is None:
        return None, True

    realized = abs(abnormal_return) / PRE_EVENT_RETURN_SCALE
    raw_edge = max(0.0, expected_impact - realized)
    priced_in = priced_in_probability if priced_in_probability is not None else 0.0
    diffusion = diffusion_score if diffusion_score is not None else 0.0
    remaining = raw_edge * (1.0 - priced_in) * (1.0 - 0.5 * diffusion)
    return round(min(1.0, remaining), 6), False


def _expected_impact(catalyst: CatalystSummary | None) -> float | None:
    if catalyst is None:
        return None
    if catalyst.materiality_score is not None:
        return catalyst.materiality_score
    return catalyst.catalyst_strength


def enrich_reaction_summary(
    summary: ReactionSummary,
    *,
    catalyst: CatalystSummary | None,
    attention: AttentionSummary | None,
    surprise: SurpriseSummary | None,
    decay_row: DecayFixtureRow | None,
    prediction_cutoff: int,
) -> ReactionSummary:
    if iso_to_epoch_ns(summary.available_time) > prediction_cutoff:
        return summary

    quality_flags = list(summary.quality_flags)
    decay_override = decay_row.decay_class_override if decay_row else None
    decay_class, decay_defaulted = compute_decay_class(
        summary.canonical_event_type,
        decay_class_override=decay_override,
    )
    if decay_defaulted:
        quality_flags.append(ContextQualityFlag.DECAY_CLASS_DEFAULTED.value)

    pre_event = decay_row.pre_event_abnormal_return if decay_row else None
    diffusion = attention.diffusion_score if attention is not None else None
    surprise_mag = _surprise_magnitude(catalyst, surprise)
    priced_in_override = decay_row.priced_in_override if decay_row else None

    priced_in, priced_in_partial = compute_priced_in_probability(
        pre_event_abnormal_return=pre_event,
        diffusion_score=diffusion,
        surprise_magnitude=surprise_mag,
        priced_in_override=priced_in_override,
    )
    if priced_in_partial:
        quality_flags.append(ContextQualityFlag.PRICED_IN_DATA_PARTIAL.value)

    expected = _expected_impact(catalyst)
    remaining, remaining_partial = compute_remaining_information_edge(
        expected_impact=expected,
        abnormal_return=summary.abnormal_return,
        priced_in_probability=priced_in,
        diffusion_score=diffusion,
    )
    if remaining_partial:
        quality_flags.append(ContextQualityFlag.REMAINING_EDGE_DATA_PARTIAL.value)

    quality_flags.append(ContextQualityFlag.INFORMATION_DECAY_EXPERIMENTAL.value)

    return replace(
        summary,
        information_decay_class=decay_class.value,
        priced_in_probability=priced_in,
        remaining_information_edge=remaining,
        quality_flags=tuple(dict.fromkeys(quality_flags)),
    )


def enrich_reaction_summaries(
    reaction_summaries: list[ReactionSummary],
    *,
    catalyst_by_event: dict[str, CatalystSummary],
    attention_by_event: dict[str, AttentionSummary],
    surprise_by_event: dict[str, SurpriseSummary],
    decay_fixture: dict[str, DecayFixtureRow],
    prediction_cutoff: int,
) -> list[ReactionSummary]:
    enriched: list[ReactionSummary] = []
    for summary in reaction_summaries:
        enriched.append(
            enrich_reaction_summary(
                summary,
                catalyst=catalyst_by_event.get(summary.event_id),
                attention=attention_by_event.get(summary.event_id),
                surprise=surprise_by_event.get(summary.event_id),
                decay_row=decay_fixture.get(summary.event_id),
                prediction_cutoff=prediction_cutoff,
            )
        )
    return enriched


def build_fixture_information_decay_pipeline(
    reaction_summaries: list[ReactionSummary],
    *,
    catalyst_summaries: list[CatalystSummary],
    attention_summaries: list[AttentionSummary],
    surprise_summaries: list[SurpriseSummary],
    decay_fixture: dict[str, DecayFixtureRow],
    prediction_cutoff: int,
) -> tuple[list[ReactionSummary], list[Any], list[InformationDecaySummary]]:
    catalyst_by_event = {item.event_id: item for item in catalyst_summaries}
    attention_by_event = {item.event_id: item for item in attention_summaries}
    surprise_by_event = {
        item.event_id: item for item in surprise_summaries if item.event_id is not None
    }

    enriched = enrich_reaction_summaries(
        reaction_summaries,
        catalyst_by_event=catalyst_by_event,
        attention_by_event=attention_by_event,
        surprise_by_event=surprise_by_event,
        decay_fixture=decay_fixture,
        prediction_cutoff=prediction_cutoff,
    )

    evidence = [build_market_reaction_evidence(item) for item in enriched]
    decay_summaries = [
        InformationDecaySummary(
            event_id=item.event_id,
            entity_id=item.entity_id,
            canonical_event_type=item.canonical_event_type,
            information_decay_class=item.information_decay_class,
            priced_in_probability=item.priced_in_probability,
            remaining_information_edge=item.remaining_information_edge,
            event_time=item.event_time,
            available_time=item.available_time,
            publication_state=item.publication_state,
            quality_flags=item.quality_flags,
            headline=item.headline,
        )
        for item in enriched
        if iso_to_epoch_ns(item.available_time) <= prediction_cutoff
    ]
    return enriched, evidence, decay_summaries


def information_decay_summary_to_dict(item: InformationDecaySummary) -> dict[str, Any]:
    return {
        "event_id": item.event_id,
        "entity_id": item.entity_id,
        "canonical_event_type": item.canonical_event_type,
        "information_decay_class": item.information_decay_class,
        "priced_in_probability": item.priced_in_probability,
        "remaining_information_edge": item.remaining_information_edge,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state,
        "quality_flags": list(item.quality_flags),
        "headline": item.headline,
        "scoring_method": SCORING_METHOD,
    }


__all__ = [
    "DecayFixtureRow",
    "InformationDecaySummary",
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "build_fixture_information_decay_pipeline",
    "compute_decay_class",
    "compute_priced_in_probability",
    "compute_remaining_information_edge",
    "enrich_reaction_summaries",
    "enrich_reaction_summary",
    "information_decay_summary_to_dict",
    "load_decay_fixture",
]
