"""MC16 → MC7/MC8 optional synthesis enrichment — metadata-only, PIT-safe, fail-closed."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..contracts.market_context import (
    ContextQualityFlag,
    SynthesisEnrichmentMetadata,
    synthesis_enrichment_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns
from .synthesis import MultiDocumentSynthesisSummary

PRODUCER_VERSION = "market_context_synthesis_enrichment_v1"
SCORING_METHOD = "synthesis_enrichment_v1"
THEME_CORROBORATION_THRESHOLD = 0.75

DEFAULT_ENRICHMENT_EXPECTED = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "boxl_synthesis_enrichment_expected.json"
)


def _metadata_from_synthesis(
    synthesis: MultiDocumentSynthesisSummary,
) -> SynthesisEnrichmentMetadata:
    return SynthesisEnrichmentMetadata(
        synthesis_id=synthesis.synthesis_id,
        theme_agreement_score=synthesis.theme_agreement_score,
        contradiction_detected=synthesis.contradiction_detected,
        consolidated_channels=synthesis.consolidated_channels,
        synthesis_confidence=synthesis.synthesis_confidence,
    )


def _enrichment_quality_flags(
    synthesis: MultiDocumentSynthesisSummary,
) -> tuple[str, ...]:
    flags: list[str] = [
        ContextQualityFlag.MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL.value,
    ]
    if synthesis.contradiction_detected:
        flags.append(ContextQualityFlag.CATALYST_SYNTHESIS_CONTRADICTION.value)
    elif (
        synthesis.theme_agreement_score is not None
        and synthesis.theme_agreement_score >= THEME_CORROBORATION_THRESHOLD
    ):
        flags.append(ContextQualityFlag.SYNTHESIS_THEME_CORROBORATED.value)
    return tuple(dict.fromkeys(flags))


def _merge_quality_flags(
    existing: tuple[str, ...],
    enrichment_flags: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(dict.fromkeys(list(existing) + list(enrichment_flags)))


def index_synthesis_by_cluster_id(
    summaries: list[MultiDocumentSynthesisSummary],
) -> dict[str, MultiDocumentSynthesisSummary]:
    return {item.cluster_id: item for item in summaries}


def _pit_visible(
    synthesis: MultiDocumentSynthesisSummary,
    prediction_cutoff: int,
) -> bool:
    return iso_to_epoch_ns(synthesis.available_time) <= prediction_cutoff


def apply_synthesis_enrichment_to_impact(
    summaries: list[Any],
    synthesis_index: dict[str, MultiDocumentSynthesisSummary],
    prediction_cutoff: int,
) -> list[Any]:
    enriched: list[Any] = []
    for item in summaries:
        synthesis = synthesis_index.get(item.event_id)
        if synthesis is None or not _pit_visible(synthesis, prediction_cutoff):
            enriched.append(item)
            continue
        enrichment_flags = _enrichment_quality_flags(synthesis)
        enriched.append(
            replace(
                item,
                synthesis_enrichment=_metadata_from_synthesis(synthesis),
                quality_flags=_merge_quality_flags(item.quality_flags, enrichment_flags),
            )
        )
    return enriched


def apply_synthesis_enrichment_to_catalyst(
    summaries: list[Any],
    synthesis_index: dict[str, MultiDocumentSynthesisSummary],
    prediction_cutoff: int,
) -> list[Any]:
    enriched: list[Any] = []
    for item in summaries:
        synthesis = synthesis_index.get(item.event_id)
        if synthesis is None or not _pit_visible(synthesis, prediction_cutoff):
            enriched.append(item)
            continue
        enrichment_flags = _enrichment_quality_flags(synthesis)
        enriched.append(
            replace(
                item,
                synthesis_enrichment=_metadata_from_synthesis(synthesis),
                quality_flags=_merge_quality_flags(item.quality_flags, enrichment_flags),
            )
        )
    return enriched


def run_mc16_mc78_enrichment_gate_validation(
    *,
    expected_path: Path | None = None,
    prediction_cutoff: int | None = None,
) -> dict[str, Any]:
    """Validate MC16→MC7/MC8 enrichment gates on admitted BOXL fixtures."""
    from ..providers.projections import build_workspace_market_context_payload
    from .synthesis import GATE_PREDICTION_CUTOFF

    expected_file = expected_path or DEFAULT_ENRICHMENT_EXPECTED
    expected = json.loads(expected_file.read_text(encoding="utf-8"))
    cutoff_ns = (
        prediction_cutoff
        if prediction_cutoff is not None
        else iso_to_epoch_ns(GATE_PREDICTION_CUTOFF)
    )
    early_cutoff_ns = iso_to_epoch_ns("2026-07-16T00:00:00.000000000Z")

    payload = build_workspace_market_context_payload(
        "BOXL",
        as_of_context={"replay_session_id": "mc78-gate"},
        prediction_cutoff=cutoff_ns,
    )
    early_payload = build_workspace_market_context_payload(
        "BOXL",
        as_of_context={"replay_session_id": "mc78-gate-early"},
        prediction_cutoff=early_cutoff_ns,
    )

    impact_by_event = {
        item["event_id"]: item
        for item in payload.get("impact_component_summaries") or []
    }
    catalyst_by_event = {
        item["event_id"]: item for item in payload.get("catalyst_summaries") or []
    }

    enrichment_gate = "PASS"
    score_gate = "PASS"
    pit_gate = "PASS"
    doctrine_gate = "PASS"

    for row in expected.get("enriched_events", []):
        event_id = row["event_id"]
        impact = impact_by_event.get(event_id)
        catalyst = catalyst_by_event.get(event_id)
        if impact is None or catalyst is None:
            enrichment_gate = "FAIL"
            continue
        expected_enrichment = row["synthesis_enrichment"]
        if impact.get("synthesis_enrichment") != expected_enrichment:
            enrichment_gate = "FAIL"
        if catalyst.get("synthesis_enrichment") != expected_enrichment:
            enrichment_gate = "FAIL"
        for flag in row.get("quality_flags_append", []):
            if flag not in impact.get("quality_flags", []):
                enrichment_gate = "FAIL"
            if flag not in catalyst.get("quality_flags", []):
                enrichment_gate = "FAIL"

    for event_id in expected.get("non_enriched_event_ids", []):
        impact = impact_by_event.get(event_id) or {}
        catalyst = catalyst_by_event.get(event_id) or {}
        if impact.get("synthesis_enrichment") is not None:
            enrichment_gate = "FAIL"
        if catalyst.get("synthesis_enrichment") is not None:
            enrichment_gate = "FAIL"

    pre_enrichment_impact = {
        item["event_id"]: {
            key: item[key]
            for key in (
                "novelty_score",
                "materiality_score",
                "source_credibility",
                "surprise_score",
            )
        }
        for item in expected.get("score_invariance_impact", [])
    }
    for event_id, scores in pre_enrichment_impact.items():
        actual = impact_by_event.get(event_id) or {}
        for key, value in scores.items():
            if actual.get(key) != value:
                score_gate = "FAIL"

    pre_enrichment_catalyst = {
        item["event_id"]: {
            key: item[key]
            for key in (
                "catalyst_strength",
                "novelty_score",
                "materiality_score",
                "credibility_score",
                "gate_ok",
            )
        }
        for item in expected.get("score_invariance_catalyst", [])
    }
    for event_id, scores in pre_enrichment_catalyst.items():
        actual = catalyst_by_event.get(event_id) or {}
        for key, value in scores.items():
            if actual.get(key) != value:
                score_gate = "FAIL"

    early_enriched = [
        item
        for item in early_payload.get("impact_component_summaries") or []
        if item.get("synthesis_enrichment") is not None
    ]
    if len(early_enriched) != expected.get("early_cutoff_enriched_count", 0):
        pit_gate = "FAIL"

    forbidden_top_level = ("universal_news_score", "context_score", "fused_news_score")
    if any(key in payload for key in forbidden_top_level):
        doctrine_gate = "FAIL"

    gates = [
        {"gate_milestone": "MC16-MC78-ENRICHMENT", "gate_status": enrichment_gate},
        {"gate_milestone": "MC16-MC78-SCORE-INVARIANCE", "gate_status": score_gate},
        {"gate_milestone": "MC16-MC78-PIT", "gate_status": pit_gate},
        {"gate_milestone": "MC16-MC78-DOCTRINE", "gate_status": doctrine_gate},
    ]
    aggregate = "PASS" if all(item["gate_status"] == "PASS" for item in gates) else "FAIL"

    enriched_count = sum(
        1
        for item in payload.get("impact_component_summaries") or []
        if item.get("synthesis_enrichment") is not None
    )

    return {
        "aggregate_status": aggregate,
        "artifact_type": "MC16_MC78_SYNTHESIS_ENRICHMENT_GATE_VALIDATION_REPORT",
        "enriched_impact_count": enriched_count,
        "enriched_catalyst_count": sum(
            1
            for item in payload.get("catalyst_summaries") or []
            if item.get("synthesis_enrichment") is not None
        ),
        "fixture_refs": [
            {
                "repository_relative_path": str(
                    expected_file.relative_to(expected_file.parents[3])
                ),
                "role": "golden_expected",
            }
        ],
        "gate_summary": gates,
        "not_trade_signal": True,
        "research_only": True,
        "scope": "fixture",
    }


__all__ = [
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "apply_synthesis_enrichment_to_catalyst",
    "apply_synthesis_enrichment_to_impact",
    "index_synthesis_by_cluster_id",
    "run_mc16_mc78_enrichment_gate_validation",
    "synthesis_enrichment_to_dict",
]
