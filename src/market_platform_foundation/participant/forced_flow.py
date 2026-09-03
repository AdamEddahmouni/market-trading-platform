"""PI13 forced-flow / dislocation engine — consumes PI6, OF, F8, MC catalyst gates."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ..contracts.participant import (
    ForcedFlowEvidence,
    ForcedFlowRegime,
    IdentityConfidence,
    MetaorderEvidence,
    MetaorderLifecycleState,
    ParticipantHorizon,
    ParticipantMechanism,
    ParticipantQualityFlag,
    ParticipantResearchClassification,
    ParticipantType,
    forced_flow_evidence_to_dict,
)
from ..cross_lane.evidence import EvidenceSignal
from ..normalization.equity_bars import iso_to_epoch_ns

PRODUCER_VERSION = "participant_forced_flow_v1"
SCORING_METHOD = "forced_flow_v1"
ANONYMOUS_FORCED_FLOW_PARTICIPANT_ID = "participant:anonymous:forced_flow"

DEFAULT_FORCED_FLOW_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "participant"
    / "nvda_forced_flow_slice.json"
)

DEFAULT_METAORDER_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "providers"
    / "order_flow"
    / "nvda_metaorder_slice.json"
)


def load_forced_flow_slice(path: Path | str | None = None) -> dict[str, Any]:
    fixture_path = Path(path) if path is not None else DEFAULT_FORCED_FLOW_FIXTURE
    with fixture_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _parse_time_ns(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    return iso_to_epoch_ns(text)


def _pit_eligible(available_time: str | None, *, prediction_cutoff: int) -> bool:
    if not available_time:
        return False
    available_ns = _parse_time_ns(available_time)
    return 0 < available_ns <= prediction_cutoff


def _threshold_config(fixture: dict[str, Any]) -> dict[str, float]:
    return {
        "min_reversal_probability": float(fixture.get("min_reversal_probability", 0.5)),
        "min_exhaustion_score": float(fixture.get("min_exhaustion_score", 0.5)),
    }


def _resolve_metaorder_state(
    *,
    metaorder_evidence: list[MetaorderEvidence] | None,
    lane_inputs: dict[str, Any],
    prediction_cutoff: int,
) -> tuple[str | None, str | None, str | None]:
    embedded = lane_inputs.get("metaorder")
    if isinstance(embedded, dict):
        available = str(embedded.get("available_time", ""))
        if _pit_eligible(available, prediction_cutoff=prediction_cutoff):
            lifecycle = str(embedded.get("lifecycle_state", ""))
            event_time = str(embedded.get("event_time", available))
            return lifecycle or None, event_time, available

    if metaorder_evidence:
        eligible = [
            item
            for item in metaorder_evidence
            if _pit_eligible(item.available_time, prediction_cutoff=prediction_cutoff)
        ]
        if eligible:
            latest = max(eligible, key=lambda row: _parse_time_ns(row.available_time))
            return (
                latest.lifecycle_state.value,
                latest.event_time,
                latest.available_time,
            )
    return None, None, None


def _resolve_microstructure_inputs(
    lane_inputs: dict[str, Any],
    *,
    prediction_cutoff: int,
) -> dict[str, Any] | None:
    micro = lane_inputs.get("microstructure")
    if not isinstance(micro, dict):
        return None
    available = str(micro.get("available_time", ""))
    if not _pit_eligible(available, prediction_cutoff=prediction_cutoff):
        return None
    return micro


def _resolve_leverage_inputs(
    lane_inputs: dict[str, Any],
    *,
    prediction_cutoff: int,
) -> dict[str, Any] | None:
    leverage = lane_inputs.get("leverage")
    if not isinstance(leverage, dict):
        return None
    available = str(leverage.get("available_time", ""))
    if not _pit_eligible(available, prediction_cutoff=prediction_cutoff):
        return None
    return leverage


def _resolve_catalyst_registry(
    lane_inputs: dict[str, Any],
    *,
    prediction_cutoff: int,
) -> dict[str, Any] | None:
    registry = lane_inputs.get("catalyst_registry")
    if not isinstance(registry, dict):
        return None
    available = str(registry.get("available_time", ""))
    if not _pit_eligible(available, prediction_cutoff=prediction_cutoff):
        return None
    return registry


def _exhaustion_elevated(
    microstructure: dict[str, Any] | None,
    *,
    thresholds: dict[str, float],
) -> bool:
    if microstructure is None:
        return False
    reversal = microstructure.get("reversal_probability")
    exhaustion = microstructure.get("exhaustion_score")
    impact_regime = str(microstructure.get("impact_regime", "")).upper()
    if isinstance(reversal, (int, float)) and float(reversal) >= thresholds["min_reversal_probability"]:
        return True
    if isinstance(exhaustion, (int, float)) and float(exhaustion) >= thresholds["min_exhaustion_score"]:
        return True
    return impact_regime.endswith("EXHAUSTION")


def _liquidation_stress_elevated(leverage: dict[str, Any] | None) -> bool:
    if leverage is None:
        return False
    return bool(leverage.get("long_liquidation_risk")) or bool(leverage.get("short_liquidation_risk"))


def _metaorder_complete(lifecycle_state: str | None) -> bool:
    return lifecycle_state == MetaorderLifecycleState.LIKELY_COMPLETE.value


def _classify_forced_flow_regime(
    *,
    catalyst_registry: dict[str, Any] | None,
    lifecycle_state: str | None,
    microstructure: dict[str, Any] | None,
    leverage: dict[str, Any] | None,
    thresholds: dict[str, float],
) -> tuple[ForcedFlowRegime, tuple[str, ...]]:
    quality_flags: set[str] = set()

    if catalyst_registry is None:
        return ForcedFlowRegime.INSUFFICIENT_DATA, (
            ParticipantQualityFlag.CATALYST_CONTEXT_MISSING.value,
        )

    registry_available = bool(catalyst_registry.get("registry_available"))
    active_catalyst = bool(catalyst_registry.get("active_catalyst_at_cutoff"))
    if not registry_available:
        return ForcedFlowRegime.INSUFFICIENT_DATA, (
            ParticipantQualityFlag.CATALYST_CONTEXT_MISSING.value,
        )
    if active_catalyst:
        return ForcedFlowRegime.INSUFFICIENT_DATA, tuple(sorted(quality_flags))

    metaorder_complete = _metaorder_complete(lifecycle_state)
    exhaustion = _exhaustion_elevated(microstructure, thresholds=thresholds)
    liquidation = _liquidation_stress_elevated(leverage)

    if metaorder_complete and exhaustion and liquidation:
        return ForcedFlowRegime.FORCED_FLOW_LIKELY, tuple(sorted(quality_flags))

    partial_signals = sum([metaorder_complete, exhaustion, liquidation])
    if partial_signals >= 2:
        quality_flags.add(ParticipantQualityFlag.FORCED_FLOW_UNCONFIRMED.value)
        return ForcedFlowRegime.DISLOCATION_AMBIGUOUS, tuple(sorted(quality_flags))

    if partial_signals == 1:
        quality_flags.add(ParticipantQualityFlag.FORCED_FLOW_UNCONFIRMED.value)
        return ForcedFlowRegime.DISLOCATION_AMBIGUOUS, tuple(sorted(quality_flags))

    if lifecycle_state == MetaorderLifecycleState.PAUSED.value and exhaustion and liquidation:
        quality_flags.add(ParticipantQualityFlag.FORCED_FLOW_UNCONFIRMED.value)
        quality_flags.add(ParticipantQualityFlag.METAORDER_INFERENCE_LOW_CONFIDENCE.value)
        return ForcedFlowRegime.DISLOCATION_AMBIGUOUS, tuple(sorted(quality_flags))

    return ForcedFlowRegime.INSUFFICIENT_DATA, tuple(sorted(quality_flags))


def _map_mechanism(leverage: dict[str, Any] | None) -> ParticipantMechanism:
    if leverage is None:
        return ParticipantMechanism.LIQUIDITY_NEED
    if bool(leverage.get("long_liquidation_risk")) or bool(leverage.get("short_liquidation_risk")):
        return ParticipantMechanism.FORCED_LIQUIDATION
    stress = str(leverage.get("stress_regime", "")).upper()
    if stress in {"HIGH", "ELEVATED"}:
        return ParticipantMechanism.MARGIN_DELEVERAGING
    return ParticipantMechanism.LIQUIDITY_NEED


def _map_research_classification(flow_regime: ForcedFlowRegime) -> ParticipantResearchClassification:
    if flow_regime == ForcedFlowRegime.FORCED_FLOW_LIKELY:
        return ParticipantResearchClassification.POST_FLOW_CONTRARIAN_CANDIDATE
    if flow_regime == ForcedFlowRegime.DISLOCATION_AMBIGUOUS:
        return ParticipantResearchClassification.FORCED_FLOW_LIKELY
    return ParticipantResearchClassification.INSUFFICIENT_INFORMATION


def _cross_lane_signal_for_regime(flow_regime: ForcedFlowRegime) -> str | None:
    if flow_regime == ForcedFlowRegime.FORCED_FLOW_LIKELY:
        return EvidenceSignal.FORCED_FLOW_PROBABILITY_ELEVATED.value
    return None


def _latest_available_time(
    *,
    metaorder_available: str | None,
    microstructure: dict[str, Any] | None,
    leverage: dict[str, Any] | None,
    catalyst_registry: dict[str, Any] | None,
) -> tuple[str, str]:
    candidates: list[tuple[int, str, str]] = []
    for available, event in (
        (metaorder_available, metaorder_available),
        (
            str(microstructure.get("available_time", "")) if isinstance(microstructure, dict) else "",
            str(microstructure.get("event_time", "")) if isinstance(microstructure, dict) else "",
        ),
        (
            str(leverage.get("available_time", "")) if isinstance(leverage, dict) else "",
            str(leverage.get("event_time", "")) if isinstance(leverage, dict) else "",
        ),
        (
            str(catalyst_registry.get("available_time", "")) if isinstance(catalyst_registry, dict) else "",
            str(catalyst_registry.get("available_time", "")) if isinstance(catalyst_registry, dict) else "",
        ),
    ):
        available_ns = _parse_time_ns(available)
        if available_ns > 0:
            candidates.append((available_ns, event or available, available))
    if not candidates:
        return "", ""
    latest_ns, event_time, available_time = max(candidates, key=lambda row: row[0])
    del latest_ns
    return event_time, available_time


def interpret_forced_flow(
    *,
    instrument_id: str,
    prediction_cutoff: int,
    lane_inputs: dict[str, Any],
    metaorder_evidence: list[MetaorderEvidence] | None = None,
    thresholds: dict[str, float] | None = None,
) -> list[ForcedFlowEvidence]:
    """Score PI13 forced-flow evidence from cross-lane inputs."""
    threshold_values = thresholds or _threshold_config({})
    lifecycle_state, meta_event_time, meta_available = _resolve_metaorder_state(
        metaorder_evidence=metaorder_evidence,
        lane_inputs=lane_inputs,
        prediction_cutoff=prediction_cutoff,
    )
    microstructure = _resolve_microstructure_inputs(lane_inputs, prediction_cutoff=prediction_cutoff)
    leverage = _resolve_leverage_inputs(lane_inputs, prediction_cutoff=prediction_cutoff)
    catalyst_registry = _resolve_catalyst_registry(lane_inputs, prediction_cutoff=prediction_cutoff)

    flow_regime, quality_flags = _classify_forced_flow_regime(
        catalyst_registry=catalyst_registry,
        lifecycle_state=lifecycle_state,
        microstructure=microstructure,
        leverage=leverage,
        thresholds=threshold_values,
    )
    if (
        lifecycle_state is None
        and microstructure is None
        and leverage is None
        and catalyst_registry is None
    ):
        return []

    event_time, available_time = _latest_available_time(
        metaorder_available=meta_available,
        microstructure=microstructure,
        leverage=leverage,
        catalyst_registry=catalyst_registry,
    )
    if meta_event_time and _parse_time_ns(meta_available or "") >= _parse_time_ns(event_time or ""):
        event_time = meta_event_time
        available_time = meta_available or available_time

    if _parse_time_ns(available_time) > prediction_cutoff:
        flow_regime = ForcedFlowRegime.INSUFFICIENT_DATA
        quality_flags = tuple(
            sorted(set(quality_flags) | {ParticipantQualityFlag.FORCED_FLOW_UNCONFIRMED.value})
        )

    cross_lane_signal = _cross_lane_signal_for_regime(flow_regime)
    mechanism = _map_mechanism(leverage)
    research_classification = _map_research_classification(flow_regime)

    reversal_probability = None
    exhaustion_score = None
    if isinstance(microstructure, dict):
        reversal_raw = microstructure.get("reversal_probability")
        exhaustion_raw = microstructure.get("exhaustion_score")
        reversal_probability = float(reversal_raw) if isinstance(reversal_raw, (int, float)) else None
        exhaustion_score = float(exhaustion_raw) if isinstance(exhaustion_raw, (int, float)) else None

    long_liquidation_risk = bool(leverage.get("long_liquidation_risk")) if isinstance(leverage, dict) else False
    short_liquidation_risk = bool(leverage.get("short_liquidation_risk")) if isinstance(leverage, dict) else False
    registry_available = (
        bool(catalyst_registry.get("registry_available")) if isinstance(catalyst_registry, dict) else False
    )
    active_catalyst = (
        bool(catalyst_registry.get("active_catalyst_at_cutoff")) if isinstance(catalyst_registry, dict) else False
    )

    evidence_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"forced_flow:{instrument_id.upper()}:{available_time}:{flow_regime.value}",
        )
    )
    return [
        ForcedFlowEvidence(
            evidence_id=evidence_id,
            instrument_id=instrument_id.upper(),
            flow_regime=flow_regime,
            metaorder_lifecycle_state=lifecycle_state,
            reversal_probability=reversal_probability,
            exhaustion_score=exhaustion_score,
            long_liquidation_risk=long_liquidation_risk,
            short_liquidation_risk=short_liquidation_risk,
            catalyst_registry_available=registry_available,
            active_catalyst_at_cutoff=active_catalyst,
            participant_id=ANONYMOUS_FORCED_FLOW_PARTICIPANT_ID,
            participant_type=ParticipantType.UNKNOWN_LARGE_PARTICIPANT,
            identity_confidence=IdentityConfidence.ANONYMOUS_INSTITUTIONAL_SCALE,
            mechanism=mechanism,
            research_classification=research_classification,
            horizon=ParticipantHorizon.SECONDS_MINUTES,
            event_time=event_time,
            available_time=available_time,
            producer_version=PRODUCER_VERSION,
            quality_flags=quality_flags,
            cross_lane_signal=cross_lane_signal,
        )
    ]


def forced_flow_summary_to_dict(item: ForcedFlowEvidence) -> dict[str, Any]:
    payload = forced_flow_evidence_to_dict(item)
    payload["scoring_method"] = SCORING_METHOD
    return payload


def summarize_forced_flow(items: list[ForcedFlowEvidence]) -> dict[str, Any]:
    if not items:
        return {
            "forced_flow_available": False,
            "flow_regime": ForcedFlowRegime.INSUFFICIENT_DATA.value,
            "cross_lane_signals": [],
            "producer_version": PRODUCER_VERSION,
        }
    item = items[0]
    signals = [item.cross_lane_signal] if item.cross_lane_signal else []
    return {
        "forced_flow_available": item.flow_regime != ForcedFlowRegime.INSUFFICIENT_DATA,
        "flow_regime": item.flow_regime.value,
        "metaorder_lifecycle_state": item.metaorder_lifecycle_state,
        "reversal_probability": item.reversal_probability,
        "exhaustion_score": item.exhaustion_score,
        "long_liquidation_risk": item.long_liquidation_risk,
        "short_liquidation_risk": item.short_liquidation_risk,
        "active_catalyst_at_cutoff": item.active_catalyst_at_cutoff,
        "cross_lane_signals": signals,
        "producer_version": PRODUCER_VERSION,
    }


def build_forced_flow_bundle(
    *,
    instrument_id: str,
    prediction_cutoff: int,
    forced_flow_fixture_path: Path | str | None = None,
    metaorder_fixture_path: Path | str | None = None,
    metaorder_evidence: list[MetaorderEvidence] | None = None,
) -> dict[str, Any]:
    fixture = load_forced_flow_slice(forced_flow_fixture_path)
    cutoff_raw = fixture.get("prediction_cutoff", prediction_cutoff)
    cutoff_ns = _parse_time_ns(cutoff_raw) if cutoff_raw is not None else prediction_cutoff
    if cutoff_ns <= 0:
        cutoff_ns = prediction_cutoff

    symbol = str(fixture.get("instrument_id", instrument_id)).upper()
    lane_inputs = fixture.get("lane_inputs", {})
    if not isinstance(lane_inputs, dict):
        lane_inputs = {}

    resolved_metaorder_evidence = metaorder_evidence
    if resolved_metaorder_evidence is None:
        metaorder_path = metaorder_fixture_path or fixture.get("metaorder_fixture_path")
        if metaorder_path:
            if not Path(metaorder_path).is_absolute():
                metaorder_path = Path(__file__).resolve().parents[3] / metaorder_path
            from ..donor_bridge.participant_adapter import build_metaorder_bundle

            metaorder_bundle = build_metaorder_bundle(
                instrument_id=symbol,
                prediction_cutoff=str(cutoff_ns),
                fixture_path=metaorder_path,
            )
            bundle_evidence = metaorder_bundle.get("evidence", [])
            if isinstance(bundle_evidence, list):
                resolved_metaorder_evidence = bundle_evidence

    threshold_values = _threshold_config(fixture)
    evidence_items = interpret_forced_flow(
        instrument_id=symbol,
        prediction_cutoff=cutoff_ns,
        lane_inputs=lane_inputs,
        metaorder_evidence=resolved_metaorder_evidence,
        thresholds=threshold_values,
    )
    envelopes = []
    if evidence_items:
        from .evidence import build_forced_flow_evidence_envelope

        envelopes = [build_forced_flow_evidence_envelope(item) for item in evidence_items]
    return {
        "available": bool(evidence_items)
        and evidence_items[0].flow_regime != ForcedFlowRegime.INSUFFICIENT_DATA,
        "summary": summarize_forced_flow(evidence_items),
        "evidence": evidence_items,
        "evidence_payloads": [forced_flow_summary_to_dict(item) for item in evidence_items],
        "envelopes": envelopes,
    }


__all__ = [
    "ANONYMOUS_FORCED_FLOW_PARTICIPANT_ID",
    "DEFAULT_FORCED_FLOW_FIXTURE",
    "DEFAULT_METAORDER_FIXTURE",
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "build_forced_flow_bundle",
    "forced_flow_summary_to_dict",
    "interpret_forced_flow",
    "load_forced_flow_slice",
    "summarize_forced_flow",
]
