"""Load deterministic evaluation fixture packs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from market_platform_foundation.intelligence.inference.contracts import (
    ConfidenceKind,
    ImpactHorizon,
    InferenceRecord,
    InferenceStatus,
    IntelligenceInputPacket,
    IntelligenceResult,
    IntelligenceTaskType,
    MarketImpactLevel,
    ParsingStatus,
    SentimentLabel,
    StructuredIntelligenceOutput,
)
from market_platform_foundation.news.contracts import InstrumentLinkage, NewsArticleEvent, PublicationTimeQuality
from market_platform_foundation.news.normalize import normalize_raw_item


DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "news_strategy_evaluation"
    / "evaluation_replay_pack.json"
)


@dataclass(frozen=True, slots=True)
class EvaluationFixtureSample:
    sample_id: str
    scenario: str
    as_of: str
    instrument_id: str
    asset_class: str
    events: tuple[NewsArticleEvent, ...]
    inference_record: InferenceRecord | None
    expect_excluded: bool
    exclusion_reason: str
    overlap_with: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationFixturePack:
    schema_version: str
    lane_id: str
    market_data_ref: str
    bar_interval: str
    raw_payload: dict[str, Any]
    samples: tuple[EvaluationFixtureSample, ...]

    @property
    def instrument_universe(self) -> tuple[str, ...]:
        market = self.raw_payload.get("market_bars", {})
        if isinstance(market, dict):
            return tuple(sorted(str(k) for k in market.keys()))
        return ()


def _build_inference_record(row: dict[str, Any], as_of: str) -> InferenceRecord:
    intel = row.get("intelligence", {})
    if not isinstance(intel, dict):
        raise ValueError("INVALID_INFERENCE_FIXTURE")
    output_data = intel.get("output", {})
    sentiment_raw = output_data.get("sentiment_label")
    impact_raw = output_data.get("market_impact_level")
    horizon_raw = output_data.get("impact_horizon")
    output = StructuredIntelligenceOutput(
        sentiment_label=SentimentLabel(sentiment_raw) if sentiment_raw else None,
        sentiment_score=output_data.get("sentiment_score"),
        catalyst_interpretation=str(output_data.get("catalyst_interpretation", "")),
        catalyst_strength=str(output_data.get("catalyst_strength", "")),
        market_impact_level=MarketImpactLevel(impact_raw) if impact_raw else None,
        impact_horizon=ImpactHorizon(horizon_raw) if horizon_raw else None,
        rationale=str(output_data.get("rationale", "")),
        model_confidence=output_data.get("model_confidence"),
        confidence_kind=ConfidenceKind.MODEL_REPORTED_CONFIDENCE,
        warnings=tuple(output_data.get("warnings", [])),
    )
    input_packet = IntelligenceInputPacket(
        input_id=str(intel.get("input_id", f"fix-input-{row.get('sample_id')}")),
        task_type=IntelligenceTaskType(intel.get("task_type", "NEWS_MARKET_IMPACT")),
        as_of=as_of,
        articles=(),
        instrument_ids=(str(row.get("instrument_id", "")),),
        prompt_id=str(intel.get("prompt_id", "news.market_impact.v1")),
        prompt_version=str(intel.get("prompt_version", "1.0.0")),
        prompt_hash=str(intel.get("prompt_hash", "FIXTURE")),
        output_schema_version="intelligence/inference/output/1.0.0",
        model_policy_id="fixture",
        input_hash=str(intel.get("input_hash", "FIXTURE")),
    )
    result = IntelligenceResult(
        result_id=str(intel.get("result_id", f"fix-result-{row.get('sample_id')}")),
        input_id=input_packet.input_id,
        status=InferenceStatus.SUCCESS,
        task_type=input_packet.task_type,
        as_of=as_of,
        output=output,
        parsing_status=ParsingStatus.VALID,
        provider_id="inference.fixture",
        model_id="fixture.news-intelligence.v1",
        prompt_id=input_packet.prompt_id,
        prompt_version=input_packet.prompt_version,
        prompt_hash=input_packet.prompt_hash,
        input_hash=input_packet.input_hash,
        completed_time=str(intel.get("completed_time", as_of)),
        source_event_ids=tuple(intel.get("source_event_ids", [])),
        instrument_ids=input_packet.instrument_ids,
        read_only=True,
        execution_authority=False,
    )
    return InferenceRecord(
        record_id=str(intel.get("record_id", f"fix-record-{row.get('sample_id')}")),
        input_packet=input_packet,
        result=result,
    )


def _event_from_row(row: dict[str, Any]) -> NewsArticleEvent:
    return normalize_raw_item(
        row,
        provider_id=str(row.get("provider_id", "news.fixture")),
        source_id=str(row.get("source_id", "fixture_wire")),
        retrieved_time=str(row.get("retrieved_time", "")),
    )


def load_fixture_pack(path: Path | None = None) -> EvaluationFixturePack:
    fixture_path = path or DEFAULT_FIXTURE_PATH
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("EVALUATION_FIXTURE_INVALID")
    samples: list[EvaluationFixtureSample] = []
    for row in payload.get("samples", []):
        if not isinstance(row, dict):
            continue
        events = tuple(_event_from_row(e) for e in row.get("events", []) if isinstance(e, dict))
        as_of = str(row.get("as_of", ""))
        inference = None
        if row.get("intelligence"):
            inference = _build_inference_record(row, as_of)
        samples.append(
            EvaluationFixtureSample(
                sample_id=str(row.get("sample_id", "")),
                scenario=str(row.get("scenario", "")),
                as_of=as_of,
                instrument_id=str(row.get("instrument_id", "")),
                asset_class=str(row.get("asset_class", "FUTURES")),
                events=events,
                inference_record=inference,
                expect_excluded=bool(row.get("expect_excluded", False)),
                exclusion_reason=str(row.get("exclusion_reason", "")),
                overlap_with=tuple(str(x) for x in row.get("overlap_with", [])),
            )
        )
    return EvaluationFixturePack(
        schema_version=str(payload.get("schema_version", "")),
        lane_id=str(payload.get("lane_id", "")),
        market_data_ref=str(payload.get("market_data_ref", "fixture/evaluation")),
        bar_interval=str(payload.get("bar_interval", "1m")),
        raw_payload=payload,
        samples=tuple(samples),
    )


__all__ = [
    "DEFAULT_FIXTURE_PATH",
    "EvaluationFixturePack",
    "EvaluationFixtureSample",
    "load_fixture_pack",
]
