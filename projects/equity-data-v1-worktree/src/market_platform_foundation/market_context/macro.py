"""MC11 macro context — shared event ontology and multi-dimensional regime evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contracts.market_context import (
    ContextQualityFlag,
    MacroContextEvidence,
    PublicationState,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..futures.macro_events import (
    DEFAULT_EVENT_WINDOW_HOURS,
    compute_surprise_zscore,
    event_window_active,
    filter_pit_events,
)
from ..normalization.equity_bars import iso_to_epoch_ns

PRODUCER_VERSION = "market_context_macro_v1"
SCORING_METHOD = "macro_context_v1"

GROWTH_EVENT_TYPES = frozenset({"NFP", "GDP", "RETAIL_SALES"})
INFLATION_EVENT_TYPES = frozenset({"CPI", "PPI", "PCE"})
POLICY_EVENT_TYPES = frozenset({"FOMC", "FED_SPEECH"})
SURPRISE_ELEVATED_THRESHOLD = 1.5
POLICY_WINDOW_HOURS = 48


@dataclass(frozen=True, slots=True)
class MacroContextSummary:
    growth_regime: str | None
    inflation_regime: str | None
    monetary_policy_regime: str | None
    risk_regime: str | None
    volatility_regime: str | None
    liquidity_regime: str | None
    event_time: str
    available_time: str
    publication_state: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    macro_context_available: bool = False
    upcoming_event_id: str | None = None
    upcoming_event_type: str | None = None
    max_surprise_zscore: float | None = None


def load_macro_context_fixture(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    events = payload.get("events", [])
    if not isinstance(events, list):
        return []
    return [row for row in events if isinstance(row, dict)]


def _surprise_direction(consensus: float | None, actual: float | None) -> str | None:
    if consensus is None or actual is None:
        return None
    if actual > consensus:
        return "ABOVE"
    if actual < consensus:
        return "BELOW"
    return "INLINE"


def _latest_past_event(
    events: list[dict[str, Any]],
    *,
    event_types: frozenset[str],
    prediction_cutoff: int,
    require_surprise: bool = False,
) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    latest_ns = -1
    latest_with_surprise: dict[str, Any] | None = None
    latest_with_surprise_ns = -1
    for event in events:
        if str(event.get("event_type", "")) not in event_types:
            continue
        anchor = str(event.get("release_time") or event.get("scheduled_time") or "")
        anchor_ns = iso_to_epoch_ns(anchor) if anchor else -1
        if anchor_ns > prediction_cutoff:
            continue
        has_surprise = event.get("consensus") is not None and event.get("actual") is not None
        if has_surprise and anchor_ns > latest_with_surprise_ns:
            latest_with_surprise = event
            latest_with_surprise_ns = anchor_ns
        if anchor_ns > latest_ns:
            latest = event
            latest_ns = anchor_ns
    if require_surprise:
        return latest_with_surprise
    return latest_with_surprise or latest


def _growth_regime(event: dict[str, Any] | None) -> str | None:
    if event is None:
        return None
    direction = _surprise_direction(
        float(event["consensus"]) if event.get("consensus") is not None else None,
        float(event["actual"]) if event.get("actual") is not None else None,
    )
    if direction == "ABOVE":
        return "EXPANDING"
    if direction == "BELOW":
        return "CONTRACTING"
    if direction == "INLINE":
        return "STABLE"
    return None


def _inflation_regime(event: dict[str, Any] | None) -> str | None:
    if event is None:
        return None
    direction = _surprise_direction(
        float(event["consensus"]) if event.get("consensus") is not None else None,
        float(event["actual"]) if event.get("actual") is not None else None,
    )
    if direction == "ABOVE":
        return "ELEVATED"
    if direction == "BELOW":
        return "DISINFLATIONARY"
    if direction == "INLINE":
        return "STABLE"
    return None


def _monetary_policy_regime(
    events: list[dict[str, Any]],
    *,
    prediction_cutoff: int,
) -> str:
    cutoff_iso = _decision_time_from_ns(prediction_cutoff)
    for event in events:
        if str(event.get("event_type", "")) not in POLICY_EVENT_TYPES:
            continue
        scheduled = str(event.get("scheduled_time", ""))
        if not scheduled:
            continue
        if event_window_active(
            cutoff_iso,
            scheduled,
            window_hours=POLICY_WINDOW_HOURS,
        ):
            return "POLICY_EVENT_IMMINENT"
        scheduled_ns = iso_to_epoch_ns(scheduled)
        if scheduled_ns <= prediction_cutoff:
            hours_ago = (prediction_cutoff - scheduled_ns) / 3_600_000_000_000
            if 0 <= hours_ago <= POLICY_WINDOW_HOURS:
                return "POLICY_EVENT_IMMINENT"
    return "NEUTRAL"


def _decision_time_from_ns(prediction_cutoff: int) -> str:
    from datetime import datetime, timezone

    secs = prediction_cutoff // 1_000_000_000
    dt = datetime.fromtimestamp(secs, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")


def _max_surprise(events: list[dict[str, Any]]) -> float | None:
    best: float | None = None
    for event in events:
        consensus = event.get("consensus")
        actual = event.get("actual")
        if consensus is None or actual is None:
            continue
        z = compute_surprise_zscore(float(consensus), float(actual))
        if z is not None and (best is None or z > best):
            best = z
    return best


def _risk_regime(
    *,
    growth: str | None,
    inflation: str | None,
    monetary: str,
    max_surprise: float | None,
    event_window: bool,
) -> str:
    if event_window:
        return "ELEVATED"
    if max_surprise is not None and max_surprise >= SURPRISE_ELEVATED_THRESHOLD:
        return "ELEVATED"
    if monetary == "POLICY_EVENT_IMMINENT":
        return "ELEVATED"
    if growth in {"EXPANDING", "CONTRACTING"} and inflation == "ELEVATED":
        return "ELEVATED"
    if growth is None and inflation is None:
        return "NORMAL"
    return "NORMAL"


def build_macro_context_summary(
    events: list[dict[str, Any]],
    *,
    prediction_cutoff: int,
) -> MacroContextSummary:
    pit_events, pit_flags = filter_pit_events(events, prediction_cutoff)
    quality_flags = list(pit_flags)

    if not pit_events:
        quality_flags.append(ContextQualityFlag.MACRO_CONSENSUS_MISSING.value)
        return MacroContextSummary(
            growth_regime=None,
            inflation_regime=None,
            monetary_policy_regime=None,
            risk_regime=None,
            volatility_regime=None,
            liquidity_regime=None,
            event_time=_decision_time_from_ns(prediction_cutoff),
            available_time=_decision_time_from_ns(prediction_cutoff),
            publication_state=PublicationState.UNAVAILABLE.value,
            quality_flags=tuple(dict.fromkeys(quality_flags)),
            macro_context_available=False,
        )

    growth_event = _latest_past_event(
        pit_events,
        event_types=GROWTH_EVENT_TYPES,
        prediction_cutoff=prediction_cutoff,
    )
    inflation_event = _latest_past_event(
        pit_events,
        event_types=INFLATION_EVENT_TYPES,
        prediction_cutoff=prediction_cutoff,
    )
    growth = _growth_regime(growth_event)
    inflation = _inflation_regime(inflation_event)
    monetary = _monetary_policy_regime(pit_events, prediction_cutoff=prediction_cutoff)
    max_surprise = _max_surprise(pit_events)

    upcoming_event: dict[str, Any] | None = None
    event_window = False
    cutoff_iso = _decision_time_from_ns(prediction_cutoff)
    for event in pit_events:
        scheduled = str(event.get("scheduled_time", ""))
        if not scheduled:
            continue
        if iso_to_epoch_ns(scheduled) > prediction_cutoff:
            if upcoming_event is None or iso_to_epoch_ns(scheduled) < iso_to_epoch_ns(
                str(upcoming_event.get("scheduled_time", ""))
            ):
                upcoming_event = event
        if event_window_active(cutoff_iso, scheduled, window_hours=DEFAULT_EVENT_WINDOW_HOURS):
            event_window = True

    if max_surprise is None:
        quality_flags.append(ContextQualityFlag.MACRO_SURPRISE_UNAVAILABLE.value)

    risk = _risk_regime(
        growth=growth,
        inflation=inflation,
        monetary=monetary,
        max_surprise=max_surprise,
        event_window=event_window,
    )
    volatility = "ELEVATED" if risk == "ELEVATED" else "NORMAL"
    liquidity = "STRESSED" if risk == "ELEVATED" and inflation == "ELEVATED" else "NORMAL"

    resolved = sum(1 for value in (growth, inflation, monetary, risk, volatility, liquidity) if value)
    if resolved < 3:
        quality_flags.append(ContextQualityFlag.MACRO_REGIME_PARTIAL.value)

    anchor_event = inflation_event or growth_event or (pit_events[-1] if pit_events else None)
    anchor_candidates = [event for event in (growth_event, inflation_event, anchor_event) if event]
    policy_events = [
        event
        for event in pit_events
        if str(event.get("event_type", "")) in POLICY_EVENT_TYPES
        and iso_to_epoch_ns(str(event.get("scheduled_time", ""))) <= prediction_cutoff
    ]
    if policy_events:
        anchor_candidates.append(
            max(
                policy_events,
                key=lambda row: iso_to_epoch_ns(str(row.get("scheduled_time", ""))),
            )
        )
    if anchor_candidates:
        anchor_event = max(
            anchor_candidates,
            key=lambda row: iso_to_epoch_ns(
                str(row.get("release_time") or row.get("scheduled_time") or "")
            ),
        )
    event_time = str(
        anchor_event.get("release_time") or anchor_event.get("scheduled_time") or cutoff_iso
    ) if anchor_event else cutoff_iso
    available_time = event_time

    return MacroContextSummary(
        growth_regime=growth,
        inflation_regime=inflation,
        monetary_policy_regime=monetary,
        risk_regime=risk,
        volatility_regime=volatility,
        liquidity_regime=liquidity,
        event_time=event_time,
        available_time=available_time,
        publication_state=PublicationState.PUBLISHED.value,
        quality_flags=tuple(dict.fromkeys(quality_flags)),
        macro_context_available=True,
        upcoming_event_id=str(upcoming_event.get("event_id")) if upcoming_event else None,
        upcoming_event_type=str(upcoming_event.get("event_type")) if upcoming_event else None,
        max_surprise_zscore=max_surprise,
    )


def build_macro_context_evidence(summary: MacroContextSummary) -> MacroContextEvidence:
    return MacroContextEvidence(
        growth_regime=summary.growth_regime,
        inflation_regime=summary.inflation_regime,
        monetary_policy_regime=summary.monetary_policy_regime,
        risk_regime=summary.risk_regime,
        volatility_regime=summary.volatility_regime,
        liquidity_regime=summary.liquidity_regime,
        event_time=summary.event_time,
        available_time=summary.available_time,
        publication_state=(
            PublicationState.PUBLISHED
            if summary.macro_context_available
            else PublicationState.UNAVAILABLE
        ),
        provenance_ref="macro.fixture:ADMITTED-MC-MACRO-BOXL-001",
        quality_flags=summary.quality_flags,
    )


def build_fixture_macro_pipeline(
    events: list[dict[str, Any]],
    *,
    prediction_cutoff: int,
) -> tuple[MacroContextEvidence, MacroContextSummary, dict[str, Any]]:
    summary = build_macro_context_summary(events, prediction_cutoff=prediction_cutoff)
    evidence = build_macro_context_evidence(summary)
    adapter_row = macro_summary_to_adapter_row(summary)
    return evidence, summary, adapter_row


def macro_summary_to_dict(item: MacroContextSummary) -> dict[str, Any]:
    return {
        "growth_regime": item.growth_regime,
        "inflation_regime": item.inflation_regime,
        "monetary_policy_regime": item.monetary_policy_regime,
        "risk_regime": item.risk_regime,
        "volatility_regime": item.volatility_regime,
        "liquidity_regime": item.liquidity_regime,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state,
        "quality_flags": list(item.quality_flags),
        "macro_context_available": item.macro_context_available,
        "upcoming_event_id": item.upcoming_event_id,
        "upcoming_event_type": item.upcoming_event_type,
        "max_surprise_zscore": item.max_surprise_zscore,
        "scoring_method": SCORING_METHOD,
    }


def macro_summary_to_adapter_row(item: MacroContextSummary) -> dict[str, Any]:
    return {
        "growth_regime": item.growth_regime,
        "inflation_regime": item.inflation_regime,
        "risk_regime": item.risk_regime,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "scoring_method": SCORING_METHOD,
    }


def build_macro_cross_lane_evidence(
    summary: MacroContextSummary,
    *,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    if iso_to_epoch_ns(summary.available_time) > prediction_cutoff:
        return []
    if not summary.macro_context_available:
        return []
    publish = (
        summary.risk_regime == "ELEVATED"
        or summary.inflation_regime not in {None, "STABLE"}
        or summary.growth_regime not in {None, "STABLE"}
    )
    if not publish:
        return []
    detail = (
        f"MC11 macro context growth={summary.growth_regime} "
        f"inflation={summary.inflation_regime} risk={summary.risk_regime}"
    )
    return [
        lane_evidence_to_dict(
            NormalizedLaneEvidence(
                lane=LaneId.MARKET_CONTEXT,
                signal=EvidenceSignal.MACRO_REGIME_CONTEXT,
                strength="HIGH" if summary.risk_regime == "ELEVATED" else "MODERATE",
                available=True,
                source_ref="market_context:macro_context",
                detail=detail,
                observed_at=summary.available_time,
                quality_flags=summary.quality_flags,
                provenance_class=EvidenceProvenanceClass.DERIVED,
            )
        )
    ]


__all__ = [
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "MacroContextSummary",
    "build_fixture_macro_pipeline",
    "build_macro_context_evidence",
    "build_macro_context_summary",
    "build_macro_cross_lane_evidence",
    "load_macro_context_fixture",
    "macro_summary_to_adapter_row",
    "macro_summary_to_dict",
]
