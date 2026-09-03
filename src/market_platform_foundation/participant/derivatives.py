"""PI12 large derivatives participant research — consumes O5 signed flow only."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ..contracts.options_quality import OptionQualityFlag
from ..contracts.participant import (
    DerivativeFlowRegime,
    DerivativeParticipantEvidence,
    IdentityConfidence,
    MetaorderEvidence,
    MetaorderLifecycleState,
    ParticipantActionType,
    ParticipantHorizon,
    ParticipantMechanism,
    ParticipantQualityFlag,
    ParticipantResearchClassification,
    ParticipantType,
    derivative_participant_evidence_to_dict,
)
from ..cross_lane.evidence import EvidenceSignal
from ..normalization.equity_bars import iso_to_epoch_ns
from ..options.flow import aggregate_signed_flow, classify_signed_flow

PRODUCER_VERSION = "participant_derivatives_v1"
SCORING_METHOD = "derivatives_participant_v1"
ANONYMOUS_OPTIONS_PARTICIPANT_ID = "participant:anonymous:large_options"

DEFAULT_DERIVATIVES_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "participant"
    / "nvda_derivatives_participant_slice.json"
)

DEFAULT_SIGNED_FLOW_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "providers"
    / "options"
    / "nvda_signed_flow_slice.json"
)


def load_derivatives_slice(path: Path | str | None = None) -> dict[str, Any]:
    fixture_path = Path(path) if path is not None else DEFAULT_DERIVATIVES_FIXTURE
    with fixture_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _parse_time_ns(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    return iso_to_epoch_ns(text)


def _activity_available_time(activity: dict[str, Any]) -> str:
    available = activity.get("available_time")
    if available:
        return str(available)
    return str(activity.get("event_time", ""))


def _filter_pit_activities(
    activities: list[dict[str, Any]],
    *,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for row in activities:
        if not isinstance(row, dict):
            continue
        available_ns = _parse_time_ns(_activity_available_time(row))
        if available_ns <= 0 or available_ns > prediction_cutoff:
            continue
        eligible.append(row)
    return eligible


def _load_options_activities(
    *,
    instrument_id: str,
    prediction_cutoff: int,
    fixture_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    if fixture_path is not None:
        payload = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        symbol = str(payload.get("symbol", instrument_id)).upper()
        if symbol != instrument_id.upper():
            return []
        activities = payload.get("activities", [])
        if not isinstance(activities, list):
            return []
        return _filter_pit_activities(
            [row for row in activities if isinstance(row, dict)],
            prediction_cutoff=prediction_cutoff,
        )

    from ..features.institutional import get_institutional_ledger

    ledger = get_institutional_ledger()
    if ledger is None:
        return []
    summaries = ledger.query_options_summaries(
        instrument_id=instrument_id.upper(),
        prediction_cutoff=prediction_cutoff,
    )
    if not isinstance(summaries, list):
        return []
    return _filter_pit_activities(
        [row for row in summaries if isinstance(row, dict)],
        prediction_cutoff=prediction_cutoff,
    )


def _summarize_open_close(activities: list[dict[str, Any]]) -> str:
    open_count = 0
    close_count = 0
    unknown_count = 0
    for row in activities:
        classification = classify_signed_flow(row)
        open_close = str(classification.get("open_close", "unknown")).lower()
        if open_close == "open":
            open_count += 1
        elif open_close == "close":
            close_count += 1
        else:
            unknown_count += 1
    if open_count > close_count and open_count > unknown_count:
        return "open_heavy"
    if close_count > open_count and close_count > unknown_count:
        return "close_heavy"
    if unknown_count >= open_count and unknown_count >= close_count and unknown_count > 0:
        return "unknown"
    if open_count > 0 and close_count > 0:
        return "mixed"
    return "unknown"


def _collect_quality_flags(activities: list[dict[str, Any]], aggregate: dict[str, Any]) -> tuple[str, ...]:
    flags: set[str] = set()
    for row in activities:
        classification = classify_signed_flow(row)
        for flag in classification.get("quality_flags", []):
            flags.add(str(flag))
    for flag in aggregate.get("quality_flags", []):
        flags.add(str(flag))
    if aggregate.get("uncertain_trade_count", 0) > 0:
        flags.add(OptionQualityFlag.FLOW_DIRECTION_UNCERTAIN.value)
    return tuple(sorted(flags))


def _map_mechanism(open_close_summary: str) -> ParticipantMechanism:
    if open_close_summary == "close_heavy":
        return ParticipantMechanism.HEDGING
    if open_close_summary == "open_heavy":
        return ParticipantMechanism.FLOW_DRIVEN
    return ParticipantMechanism.UNKNOWN


def _map_research_classification(
    flow_regime: DerivativeFlowRegime,
    *,
    open_close_summary: str,
    metaorder_corroborated: bool,
) -> ParticipantResearchClassification:
    if flow_regime == DerivativeFlowRegime.INSUFFICIENT_DATA:
        return ParticipantResearchClassification.INSUFFICIENT_INFORMATION
    if flow_regime == DerivativeFlowRegime.SCALE_ELEVATED_AMBIGUOUS:
        if open_close_summary == "close_heavy":
            return ParticipantResearchClassification.HEDGING_LIKELY
        return ParticipantResearchClassification.INSUFFICIENT_INFORMATION
    if metaorder_corroborated:
        return ParticipantResearchClassification.FLOW_CONTINUATION_CANDIDATE
    if open_close_summary == "open_heavy":
        return ParticipantResearchClassification.FLOW_CONTINUATION_CANDIDATE
    if open_close_summary == "close_heavy":
        return ParticipantResearchClassification.HEDGING_LIKELY
    return ParticipantResearchClassification.INFORMATIONAL_CONTEXT_ONLY


def _scale_config(scale_config: dict[str, Any] | None) -> dict[str, Any]:
    config = scale_config if isinstance(scale_config, dict) else {}
    return {
        "min_confirmed_trade_count": int(config.get("min_confirmed_trade_count", 2)),
        "min_buy_initiated_volume": int(config.get("min_buy_initiated_volume", 500)),
        "min_total_volume": int(config.get("min_total_volume", 0)),
        "min_uncertain_trade_count": int(config.get("min_uncertain_trade_count", 1)),
    }


def _meets_scale_threshold(aggregate: dict[str, Any], thresholds: dict[str, Any]) -> bool:
    confirmed = int(aggregate.get("confirmed_trade_count", 0))
    if confirmed < thresholds["min_confirmed_trade_count"]:
        return False
    buy_volume = int(aggregate.get("buy_initiated_volume", 0))
    sell_volume = int(aggregate.get("sell_initiated_volume", 0))
    total_volume = buy_volume + sell_volume
    if thresholds["min_total_volume"] > 0 and total_volume < thresholds["min_total_volume"]:
        return False
    dominant_volume = max(buy_volume, sell_volume)
    if dominant_volume < thresholds["min_buy_initiated_volume"]:
        return False
    return True


def _classify_flow_regime(
    aggregate: dict[str, Any],
    *,
    thresholds: dict[str, Any],
) -> DerivativeFlowRegime:
    confirmed = int(aggregate.get("confirmed_trade_count", 0))
    uncertain = int(aggregate.get("uncertain_trade_count", 0))
    if confirmed == 0 and uncertain == 0:
        return DerivativeFlowRegime.INSUFFICIENT_DATA
    buy_volume = int(aggregate.get("buy_initiated_volume", 0))
    sell_volume = int(aggregate.get("sell_initiated_volume", 0))
    if confirmed > 0 and buy_volume == sell_volume:
        if uncertain >= thresholds["min_uncertain_trade_count"]:
            return DerivativeFlowRegime.SCALE_ELEVATED_AMBIGUOUS
        return DerivativeFlowRegime.INSUFFICIENT_DATA
    if not _meets_scale_threshold(aggregate, thresholds):
        if uncertain >= thresholds["min_uncertain_trade_count"] or confirmed > 0:
            return DerivativeFlowRegime.SCALE_ELEVATED_AMBIGUOUS
        return DerivativeFlowRegime.INSUFFICIENT_DATA
    if confirmed > 0 and buy_volume != sell_volume:
        return DerivativeFlowRegime.CONFIRMED_DIRECTIONAL
    return DerivativeFlowRegime.SCALE_ELEVATED_AMBIGUOUS


def _dominant_signed_direction(aggregate: dict[str, Any]) -> str | None:
    buy_volume = int(aggregate.get("buy_initiated_volume", 0))
    sell_volume = int(aggregate.get("sell_initiated_volume", 0))
    if buy_volume > sell_volume:
        return "buy_initiated"
    if sell_volume > buy_volume:
        return "sell_initiated"
    return None


def _cross_lane_signal_for_regime(flow_regime: DerivativeFlowRegime) -> str | None:
    if flow_regime == DerivativeFlowRegime.CONFIRMED_DIRECTIONAL:
        return EvidenceSignal.LARGE_DERIVATIVE_FLOW_CONFIRMED.value
    if flow_regime == DerivativeFlowRegime.SCALE_ELEVATED_AMBIGUOUS:
        return EvidenceSignal.LARGE_DERIVATIVE_FLOW_AMBIGUOUS.value
    return None


def _metaorder_corroborated(
    metaorder_evidence: list[MetaorderEvidence] | None,
    *,
    dominant_direction: str | None,
) -> bool:
    if not metaorder_evidence or dominant_direction is None:
        return False
    for item in metaorder_evidence:
        if item.lifecycle_state != MetaorderLifecycleState.ACTIVE:
            continue
        side = str(item.aggressor_side).upper()
        if dominant_direction == "buy_initiated" and side == "BUY":
            return True
        if dominant_direction == "sell_initiated" and side == "SELL":
            return True
    return False


def _latest_times(activities: list[dict[str, Any]]) -> tuple[str, str]:
    event_time = ""
    available_time = ""
    latest_ns = -1
    for row in activities:
        available = _activity_available_time(row)
        available_ns = _parse_time_ns(available)
        if available_ns >= latest_ns:
            latest_ns = available_ns
            available_time = available
            event_time = str(row.get("event_time", available))
    return event_time, available_time


def interpret_derivatives_flow(
    activities: list[dict[str, Any]],
    *,
    instrument_id: str,
    prediction_cutoff: int,
    scale_config: dict[str, Any] | None = None,
    metaorder_evidence: list[MetaorderEvidence] | None = None,
) -> list[DerivativeParticipantEvidence]:
    """Interpret O5-classified options flow into PI12 participant evidence."""
    eligible = _filter_pit_activities(activities, prediction_cutoff=prediction_cutoff)
    if not eligible:
        return []

    aggregate = aggregate_signed_flow(eligible)
    thresholds = _scale_config(scale_config)
    open_close_summary = _summarize_open_close(eligible)
    quality_flags = _collect_quality_flags(eligible, aggregate)
    flow_regime = _classify_flow_regime(aggregate, thresholds=thresholds)
    dominant_direction = _dominant_signed_direction(aggregate)
    if flow_regime != DerivativeFlowRegime.CONFIRMED_DIRECTIONAL:
        dominant_direction = None if flow_regime == DerivativeFlowRegime.INSUFFICIENT_DATA else dominant_direction

    metaorder_flag = _metaorder_corroborated(
        metaorder_evidence,
        dominant_direction=dominant_direction,
    )
    mechanism = _map_mechanism(open_close_summary)
    if mechanism == ParticipantMechanism.UNKNOWN:
        quality_flags = tuple(
            sorted(set(quality_flags) | {ParticipantQualityFlag.INTENT_UNKNOWN.value})
        )

    research_classification = _map_research_classification(
        flow_regime,
        open_close_summary=open_close_summary,
        metaorder_corroborated=metaorder_flag,
    )
    cross_lane_signal = _cross_lane_signal_for_regime(flow_regime)
    event_time, available_time = _latest_times(eligible)
    if _parse_time_ns(available_time) > prediction_cutoff:
        cross_lane_signal = None
        flow_regime = DerivativeFlowRegime.INSUFFICIENT_DATA

    evidence_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"derivatives:{instrument_id.upper()}:{available_time}:{flow_regime.value}",
        )
    )
    return [
        DerivativeParticipantEvidence(
            evidence_id=evidence_id,
            instrument_id=instrument_id.upper(),
            action_type=ParticipantActionType.DERIVATIVE_POSITION.value,
            flow_regime=flow_regime,
            dominant_signed_direction=dominant_direction,
            open_close_summary=open_close_summary,
            net_delta_flow=aggregate.get("net_delta_flow"),
            confirmed_trade_count=int(aggregate.get("confirmed_trade_count", 0)),
            participant_id=ANONYMOUS_OPTIONS_PARTICIPANT_ID,
            participant_type=ParticipantType.UNKNOWN_LARGE_PARTICIPANT,
            identity_confidence=IdentityConfidence.ANONYMOUS_INSTITUTIONAL_SCALE,
            mechanism=mechanism,
            research_classification=research_classification,
            horizon=ParticipantHorizon.INTRADAY,
            metaorder_corroborated=metaorder_flag,
            event_time=event_time,
            available_time=available_time,
            producer_version=PRODUCER_VERSION,
            quality_flags=quality_flags,
            cross_lane_signal=cross_lane_signal,
        )
    ]


def derivatives_summary_to_dict(item: DerivativeParticipantEvidence) -> dict[str, Any]:
    payload = derivative_participant_evidence_to_dict(item)
    payload["scoring_method"] = SCORING_METHOD
    return payload


def summarize_derivatives_participant(
    items: list[DerivativeParticipantEvidence],
) -> dict[str, Any]:
    if not items:
        return {
            "derivatives_participant_available": False,
            "flow_regime": DerivativeFlowRegime.INSUFFICIENT_DATA.value,
            "cross_lane_signals": [],
            "producer_version": PRODUCER_VERSION,
        }
    item = items[0]
    signals = [item.cross_lane_signal] if item.cross_lane_signal else []
    return {
        "derivatives_participant_available": item.flow_regime
        != DerivativeFlowRegime.INSUFFICIENT_DATA,
        "flow_regime": item.flow_regime.value,
        "dominant_signed_direction": item.dominant_signed_direction,
        "open_close_summary": item.open_close_summary,
        "confirmed_trade_count": item.confirmed_trade_count,
        "metaorder_corroborated": item.metaorder_corroborated,
        "cross_lane_signals": signals,
        "producer_version": PRODUCER_VERSION,
    }


def build_derivatives_participant_bundle(
    *,
    instrument_id: str,
    prediction_cutoff: int,
    derivatives_fixture_path: Path | str | None = None,
    options_fixture_path: Path | str | None = None,
    metaorder_evidence: list[MetaorderEvidence] | None = None,
) -> dict[str, Any]:
    fixture = load_derivatives_slice(derivatives_fixture_path)
    resolved_options_path = options_fixture_path or fixture.get("options_fixture_path")
    if resolved_options_path and not Path(resolved_options_path).is_absolute():
        resolved_options_path = Path(__file__).resolve().parents[3] / resolved_options_path

    cutoff_raw = fixture.get("prediction_cutoff", prediction_cutoff)
    cutoff_ns = _parse_time_ns(cutoff_raw) if cutoff_raw is not None else prediction_cutoff
    if cutoff_ns <= 0:
        cutoff_ns = prediction_cutoff

    symbol = str(fixture.get("instrument_id", instrument_id)).upper()
    activities = _load_options_activities(
        instrument_id=symbol,
        prediction_cutoff=cutoff_ns,
        fixture_path=resolved_options_path,
    )
    scale_config = {
        key: fixture.get(key)
        for key in (
            "min_confirmed_trade_count",
            "min_buy_initiated_volume",
            "min_total_volume",
            "min_uncertain_trade_count",
        )
        if fixture.get(key) is not None
    }
    evidence_items = interpret_derivatives_flow(
        activities,
        instrument_id=symbol,
        prediction_cutoff=cutoff_ns,
        scale_config=scale_config,
        metaorder_evidence=metaorder_evidence,
    )
    envelopes = []
    if evidence_items:
        from .evidence import build_derivative_evidence_envelope

        envelopes = [build_derivative_evidence_envelope(item) for item in evidence_items]
    return {
        "available": bool(evidence_items)
        and evidence_items[0].flow_regime != DerivativeFlowRegime.INSUFFICIENT_DATA,
        "summary": summarize_derivatives_participant(evidence_items),
        "evidence": evidence_items,
        "evidence_payloads": [
            derivatives_summary_to_dict(item) for item in evidence_items
        ],
        "envelopes": envelopes,
    }


__all__ = [
    "ANONYMOUS_OPTIONS_PARTICIPANT_ID",
    "DEFAULT_DERIVATIVES_FIXTURE",
    "DEFAULT_SIGNED_FLOW_FIXTURE",
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "build_derivatives_participant_bundle",
    "derivatives_summary_to_dict",
    "interpret_derivatives_flow",
    "load_derivatives_slice",
    "summarize_derivatives_participant",
]
