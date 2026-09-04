"""MC6 expectations / surprise — PIT consensus store and fail-closed surprise evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ..contracts.market_context import (
    ContextQualityFlag,
    ExpectationSnapshot,
    PublicationState,
    SurpriseEvidence,
    expectation_snapshot_to_dict,
    surprise_evidence_to_dict,
    surprise_unavailable_when_expectation_missing,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns

PRODUCER_VERSION = "market_context_expectations_v1"
SURPRISE_METHOD = "expectations_v1"


@dataclass(frozen=True, slots=True)
class ExpectationFixtureRow:
    """One consensus row with optional actual for surprise computation."""

    expectation_id: str
    metric_name: str
    entity_id: str | None
    expected_value: str | None
    median: str | None
    high: str | None
    low: str | None
    dispersion: str | None
    sample_size: int | None
    source: str
    event_time: str
    available_time: str
    actual_value: str | None = None
    actual_available_time: str | None = None
    actual_document_id: str | None = None
    event_id: str | None = None
    revision_of: str | None = None
    units: str | None = None
    currency: str | None = None
    period: str | None = None
    provenance_ref: str = ""


@dataclass(frozen=True, slots=True)
class SurpriseSummary:
    """Workspace-friendly surprise rollup."""

    expectation_id: str
    metric_name: str
    entity_id: str | None
    event_id: str | None
    expected_value: str | None
    actual_value: str | None
    surprise: str | None
    surprise_percent: str | None
    standardized_surprise: str | None
    event_time: str
    available_time: str
    publication_state: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    surprise_available: bool = False


def _decimal_or_none(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _parse_expectation_row(row: dict[str, Any]) -> ExpectationFixtureRow | None:
    if not isinstance(row, dict):
        return None
    expectation_id = str(row.get("expectation_id", ""))
    metric_name = str(row.get("metric_name", ""))
    if not expectation_id or not metric_name:
        return None
    sample_size_raw = row.get("sample_size")
    sample_size = int(sample_size_raw) if isinstance(sample_size_raw, int) else None
    return ExpectationFixtureRow(
        expectation_id=expectation_id,
        metric_name=metric_name,
        entity_id=str(row.get("entity_id")) if row.get("entity_id") else None,
        expected_value=str(row.get("expected_value")) if row.get("expected_value") is not None else None,
        median=str(row.get("median")) if row.get("median") is not None else None,
        high=str(row.get("high")) if row.get("high") is not None else None,
        low=str(row.get("low")) if row.get("low") is not None else None,
        dispersion=str(row.get("dispersion")) if row.get("dispersion") is not None else None,
        sample_size=sample_size,
        source=str(row.get("source", "fixture.expectations")),
        event_time=str(row.get("event_time", "")),
        available_time=str(row.get("available_time", "")),
        actual_value=str(row.get("actual_value")) if row.get("actual_value") is not None else None,
        actual_available_time=(
            str(row.get("actual_available_time")) if row.get("actual_available_time") else None
        ),
        actual_document_id=(
            str(row.get("actual_document_id")) if row.get("actual_document_id") else None
        ),
        event_id=str(row.get("event_id")) if row.get("event_id") else None,
        revision_of=str(row.get("revision_of")) if row.get("revision_of") else None,
        units=str(row.get("units")) if row.get("units") else None,
        currency=str(row.get("currency")) if row.get("currency") else None,
        period=str(row.get("period")) if row.get("period") else None,
        provenance_ref=str(row.get("provenance_ref", "")),
    )


def load_expectations_fixture(path: Path) -> list[ExpectationFixtureRow]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("expectations", [])
    if not isinstance(rows, list):
        return []
    parsed: list[ExpectationFixtureRow] = []
    for row in rows:
        item = _parse_expectation_row(row)
        if item is not None:
            parsed.append(item)
    return parsed


def load_es_macro_expectations_fixture(path: Path) -> list[ExpectationFixtureRow]:
    """Map ES macro event fixture rows into expectation rows when consensus present."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    events = payload.get("events", [])
    if not isinstance(events, list):
        return []
    parsed: list[ExpectationFixtureRow] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = str(event.get("event_id", ""))
        event_type = str(event.get("event_type", ""))
        consensus = event.get("consensus")
        if consensus is None:
            continue
        release_time = str(event.get("release_time") or event.get("scheduled_time", ""))
        scheduled = str(event.get("scheduled_time", release_time))
        actual_raw = event.get("actual")
        parsed.append(
            ExpectationFixtureRow(
                expectation_id=f"macro-{event_id}",
                metric_name=event_type.lower(),
                entity_id="ES",
                expected_value=str(consensus),
                median=str(consensus),
                high=None,
                low=None,
                dispersion=str(event.get("dispersion", "1")) if event.get("dispersion") else None,
                sample_size=None,
                source="macro.fixture.consensus",
                event_time=scheduled,
                available_time=scheduled,
                actual_value=str(actual_raw) if actual_raw is not None else None,
                actual_available_time=release_time if actual_raw is not None else None,
                event_id=event_id,
                provenance_ref=str(event.get("provenance_ref", "")),
            )
        )
    return parsed


def build_expectation_snapshot(row: ExpectationFixtureRow) -> ExpectationSnapshot | None:
    if not row.available_time or not row.event_time:
        return None
    flags: list[str] = []
    if row.revision_of:
        flags.append("EXPECTATION_REVISION")
    return ExpectationSnapshot(
        metric_name=row.metric_name,
        entity_id=row.entity_id,
        expected_value=_decimal_or_none(row.expected_value),
        median=_decimal_or_none(row.median),
        high=_decimal_or_none(row.high),
        low=_decimal_or_none(row.low),
        dispersion=_decimal_or_none(row.dispersion),
        sample_size=row.sample_size,
        source=row.source,
        event_time=row.event_time,
        available_time=row.available_time,
        publication_state=PublicationState.PUBLISHED,
        provenance_ref=row.provenance_ref or f"expectation:{row.expectation_id}",
        quality_flags=tuple(flags),
    )


def compute_surprise_evidence(
    expectation: ExpectationSnapshot,
    actual_value: Decimal,
    *,
    expectation_id: str,
    event_time: str,
    available_time: str,
) -> SurpriseEvidence | None:
    baseline = expectation.median if expectation.median is not None else expectation.expected_value
    if baseline is None:
        return None
    surprise = actual_value - baseline
    surprise_percent: Decimal | None = None
    if baseline != 0:
        surprise_percent = (surprise / baseline) * Decimal("100")
    standardized: Decimal | None = None
    if expectation.dispersion is not None and expectation.dispersion > 0:
        standardized = surprise / expectation.dispersion
    return SurpriseEvidence(
        metric_name=expectation.metric_name,
        entity_id=expectation.entity_id,
        actual_value=actual_value,
        expectation_snapshot_id=expectation_id,
        surprise=surprise,
        surprise_percent=surprise_percent,
        standardized_surprise=standardized,
        event_time=event_time,
        available_time=available_time,
        publication_state=PublicationState.PUBLISHED,
        provenance_ref=expectation.provenance_ref,
        quality_flags=(),
    )


def _pit_visible(available_time: str, prediction_cutoff: int) -> bool:
    if not available_time:
        return False
    return iso_to_epoch_ns(available_time) <= prediction_cutoff


def _select_revision_rows(
    rows: list[ExpectationFixtureRow],
    prediction_cutoff: int,
) -> list[ExpectationFixtureRow]:
    """Keep latest PIT-visible revision per expectation lineage."""
    visible = [row for row in rows if _pit_visible(row.available_time, prediction_cutoff)]
    by_lineage: dict[str, ExpectationFixtureRow] = {}
    for row in visible:
        key = row.revision_of or row.expectation_id
        existing = by_lineage.get(key)
        if existing is None or iso_to_epoch_ns(row.available_time) >= iso_to_epoch_ns(
            existing.available_time
        ):
            by_lineage[key] = row
    return list(by_lineage.values())


def build_fixture_surprise_pipeline(
    rows: list[ExpectationFixtureRow],
    *,
    prediction_cutoff: int,
) -> tuple[
    list[ExpectationSnapshot],
    list[SurpriseEvidence],
    list[SurpriseSummary],
    list[tuple[str, ...]],
]:
    expectations: list[ExpectationSnapshot] = []
    surprises: list[SurpriseEvidence] = []
    summaries: list[SurpriseSummary] = []
    unavailable_flags: list[tuple[str, ...]] = []

    selected = _select_revision_rows(rows, prediction_cutoff)
    for row in selected:
        if not _pit_visible(row.available_time, prediction_cutoff):
            continue
        snapshot = build_expectation_snapshot(row)
        if snapshot is None:
            continue
        expectations.append(snapshot)

        actual_present = (
            row.actual_value is not None
            and row.actual_available_time is not None
            and _pit_visible(row.actual_available_time, prediction_cutoff)
        )
        unavailable, flags = surprise_unavailable_when_expectation_missing(
            snapshot,
            actual_present=actual_present,
        )
        if unavailable is not None or flags:
            unavailable_flags.append(flags)

        if not actual_present:
            summaries.append(
                SurpriseSummary(
                    expectation_id=row.expectation_id,
                    metric_name=row.metric_name,
                    entity_id=row.entity_id,
                    event_id=row.event_id,
                    expected_value=row.median or row.expected_value,
                    actual_value=None,
                    surprise=None,
                    surprise_percent=None,
                    standardized_surprise=None,
                    event_time=row.event_time,
                    available_time=row.available_time,
                    publication_state=PublicationState.UNAVAILABLE.value,
                    quality_flags=flags,
                    surprise_available=False,
                )
            )
            continue

        actual_decimal = _decimal_or_none(row.actual_value)
        if actual_decimal is None:
            continue
        if snapshot.median is None and snapshot.expected_value is None:
            flags = list(flags) + [
                ContextQualityFlag.EXPECTATION_MISSING.value,
                ContextQualityFlag.SURPRISE_UNAVAILABLE.value,
            ]
            summaries.append(
                SurpriseSummary(
                    expectation_id=row.expectation_id,
                    metric_name=row.metric_name,
                    entity_id=row.entity_id,
                    event_id=row.event_id,
                    expected_value=None,
                    actual_value=row.actual_value,
                    surprise=None,
                    surprise_percent=None,
                    standardized_surprise=None,
                    event_time=row.event_time,
                    available_time=row.actual_available_time or row.event_time,
                    publication_state=PublicationState.UNAVAILABLE.value,
                    quality_flags=tuple(flags),
                    surprise_available=False,
                )
            )
            continue
        evidence = compute_surprise_evidence(
            snapshot,
            actual_decimal,
            expectation_id=row.expectation_id,
            event_time=row.event_time,
            available_time=row.actual_available_time or row.event_time,
        )
        if evidence is None:
            continue
        surprises.append(evidence)
        summaries.append(
            SurpriseSummary(
                expectation_id=row.expectation_id,
                metric_name=row.metric_name,
                entity_id=row.entity_id,
                event_id=row.event_id,
                expected_value=row.median or row.expected_value,
                actual_value=row.actual_value,
                surprise=str(evidence.surprise) if evidence.surprise is not None else None,
                surprise_percent=(
                    str(evidence.surprise_percent) if evidence.surprise_percent is not None else None
                ),
                standardized_surprise=(
                    str(evidence.standardized_surprise)
                    if evidence.standardized_surprise is not None
                    else None
                ),
                event_time=evidence.event_time,
                available_time=evidence.available_time,
                publication_state=evidence.publication_state.value,
                quality_flags=evidence.quality_flags,
                surprise_available=True,
            )
        )

    return expectations, surprises, summaries, unavailable_flags


def surprise_summary_to_dict(item: SurpriseSummary) -> dict[str, Any]:
    return {
        "expectation_id": item.expectation_id,
        "metric_name": item.metric_name,
        "entity_id": item.entity_id,
        "event_id": item.event_id,
        "expected_value": item.expected_value,
        "actual_value": item.actual_value,
        "surprise": item.surprise,
        "surprise_percent": item.surprise_percent,
        "standardized_surprise": item.standardized_surprise,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state,
        "quality_flags": list(item.quality_flags),
        "surprise_available": item.surprise_available,
    }


def build_surprise_cross_lane_evidence(
    surprises: list[SurpriseEvidence],
    *,
    symbol: str,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in surprises:
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        if item.surprise is None:
            continue
        signal = (
            EvidenceSignal.EVENT_SURPRISE_POSITIVE
            if item.surprise > 0
            else EvidenceSignal.EVENT_SURPRISE_NEGATIVE
        )
        strength = "LOW"
        if item.standardized_surprise is not None:
            z = abs(float(item.standardized_surprise))
            if z >= 2.0:
                strength = "HIGH"
            elif z >= 1.0:
                strength = "MODERATE"
        row = lane_evidence_to_dict(
            NormalizedLaneEvidence(
                lane=LaneId.MARKET_CONTEXT,
                signal=signal,
                strength=strength,
                available=True,
                source_ref=item.provenance_ref,
                detail=(
                    f"SurpriseEvidence {item.metric_name}: surprise={item.surprise} "
                    f"(display-only, not trade signal)"
                ),
                observed_at=item.available_time,
                quality_flags=item.quality_flags,
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            )
        )
        row["metadata"] = {
            "metric_name": item.metric_name,
            "entity_id": item.entity_id,
            "surprise": str(item.surprise),
            "surprise_percent": (
                str(item.surprise_percent) if item.surprise_percent is not None else None
            ),
            "standardized_surprise": (
                str(item.standardized_surprise)
                if item.standardized_surprise is not None
                else None
            ),
            "instrument_id": symbol.upper(),
            "producer_id": "market_context.expectations",
            "producer_version": PRODUCER_VERSION,
            "display_only": True,
        }
        evidence.append(row)
    return evidence


__all__ = [
    "PRODUCER_VERSION",
    "SURPRISE_METHOD",
    "ExpectationFixtureRow",
    "SurpriseSummary",
    "build_expectation_snapshot",
    "build_fixture_surprise_pipeline",
    "build_surprise_cross_lane_evidence",
    "compute_surprise_evidence",
    "load_es_macro_expectations_fixture",
    "load_expectations_fixture",
    "surprise_summary_to_dict",
]
