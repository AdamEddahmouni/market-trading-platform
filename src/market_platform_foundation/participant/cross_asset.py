"""PI11 cross-asset participant context — fuse PI10 equity crowding with F4 COT."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..contracts.futures_quality import quality_blocks_positioning_interpretation
from ..contracts.participant import (
    CrossAssetAlignmentRegime,
    CrossAssetParticipantContextEvidence,
    ParticipantAlignmentRegime,
    ParticipantCrowdingEvidence,
    ParticipantStanceDirection,
    cross_asset_participant_context_evidence_to_dict,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..futures.positioning import CrowdingRegime, positioning_payload
from ..normalization.equity_bars import iso_to_epoch_ns
from ..providers.adapters.fixture_futures_positioning import (
    DEFAULT_COT_FIXTURE,
    FixtureFuturesPositioningProvider,
)
from ..providers.contracts import ProviderResult
from .crowding import (
    PRODUCER_VERSION as CROWDING_PRODUCER_VERSION,
    compute_crowding_evidence,
)

PRODUCER_VERSION = "participant_cross_asset_v1"
SCORING_METHOD = "cross_asset_v1"

DEFAULT_CROSS_ASSET_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "participant"
    / "biya_cross_asset_slice.json"
)

_EMPTY_CHAIN_RESULT = ProviderResult(
    status="unavailable",
    reason_code="CHAIN_NOT_REQUIRED_FOR_PI11",
    provider_id="pi11.stub",
    capability="futures_chain",
)


def load_cross_asset_slice(path: Path | str | None = None) -> dict[str, Any]:
    fixture_path = Path(path) if path is not None else DEFAULT_CROSS_ASSET_FIXTURE
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


def _equity_direction_from_crowding(
    equity_crowding: ParticipantCrowdingEvidence | None,
) -> str | None:
    if equity_crowding is None:
        return None
    return equity_crowding.institutional_direction


def _equity_crowding_regime_label(
    equity_crowding: ParticipantCrowdingEvidence | None,
) -> str | None:
    if equity_crowding is None:
        return None
    if equity_crowding.alignment_regime == ParticipantAlignmentRegime.INSUFFICIENT_DATA:
        return None
    return equity_crowding.alignment_regime.value


def _fetch_cot_payload(
    *,
    futures_symbol: str,
    decision_time: int | str,
    cot_fixture_path: Path | str | None = None,
) -> dict[str, Any]:
    provider = FixtureFuturesPositioningProvider(
        fixture_path=Path(cot_fixture_path) if cot_fixture_path is not None else None,
    )
    as_of_ns = _parse_time_ns(decision_time) if not isinstance(decision_time, int) else decision_time
    positioning_result = provider.fetch_positioning(
        futures_symbol.upper(),
        as_of_time_ns=as_of_ns if as_of_ns > 0 else None,
    )
    return positioning_payload(
        positioning_result,
        _EMPTY_CHAIN_RESULT,
        decision_time=decision_time,
    )


def _classify_alignment(
    *,
    equity_direction: str | None,
    cot_regime: str | None,
) -> CrossAssetAlignmentRegime:
    if equity_direction is None or cot_regime is None:
        return CrossAssetAlignmentRegime.INSUFFICIENT_DATA

    equity_bullish = equity_direction == ParticipantStanceDirection.BULLISH.value
    equity_bearish = equity_direction == ParticipantStanceDirection.BEARISH.value
    cot_long = cot_regime == CrowdingRegime.CROWDED_LONG.value
    cot_short = cot_regime == CrowdingRegime.CROWDED_SHORT.value
    cot_neutral = cot_regime == CrowdingRegime.NEUTRAL.value

    if equity_bullish and cot_long:
        return CrossAssetAlignmentRegime.ALIGNED_BULLISH
    if equity_bearish and cot_short:
        return CrossAssetAlignmentRegime.ALIGNED_BEARISH
    if (equity_bullish and cot_short) or (equity_bearish and cot_long):
        return CrossAssetAlignmentRegime.DIVERGENT
    if (equity_bullish or equity_bearish) and cot_neutral:
        return CrossAssetAlignmentRegime.MIXED
    if cot_long or cot_short:
        return CrossAssetAlignmentRegime.MIXED
    return CrossAssetAlignmentRegime.INSUFFICIENT_DATA


def _alignment_score(regime: CrossAssetAlignmentRegime) -> float | None:
    if regime in {
        CrossAssetAlignmentRegime.ALIGNED_BULLISH,
        CrossAssetAlignmentRegime.ALIGNED_BEARISH,
    }:
        return 1.0
    if regime == CrossAssetAlignmentRegime.DIVERGENT:
        return 0.0
    if regime == CrossAssetAlignmentRegime.MIXED:
        return 0.5
    return None


def _select_cross_lane_signal(regime: CrossAssetAlignmentRegime) -> str | None:
    if regime in {
        CrossAssetAlignmentRegime.ALIGNED_BULLISH,
        CrossAssetAlignmentRegime.ALIGNED_BEARISH,
    }:
        return EvidenceSignal.PARTICIPANT_CROSS_ASSET_ALIGNED.value
    if regime == CrossAssetAlignmentRegime.DIVERGENT:
        return EvidenceSignal.PARTICIPANT_CROSS_ASSET_DIVERGENT.value
    return None


def _collect_quality_flags(
    *,
    equity_crowding: ParticipantCrowdingEvidence | None,
    cot_payload: dict[str, Any],
) -> tuple[str, ...]:
    flags: set[str] = set()
    if equity_crowding is not None:
        flags.update(equity_crowding.quality_flags)
    for flag in cot_payload.get("quality_flags", []):
        flags.add(str(flag))
    snapshot = cot_payload.get("positioning_snapshot")
    if isinstance(snapshot, dict):
        for flag in snapshot.get("quality_flags", []):
            flags.add(str(flag))
    return tuple(sorted(flags))


def _cot_unavailable(cot_payload: dict[str, Any]) -> bool:
    if not cot_payload.get("futures_positioning_available"):
        return True
    quality_flags = tuple(cot_payload.get("quality_flags", []))
    if quality_blocks_positioning_interpretation(quality_flags):
        return True
    snapshot = cot_payload.get("positioning_snapshot")
    if not isinstance(snapshot, dict):
        return True
    snapshot_flags = tuple(snapshot.get("quality_flags", []))
    return quality_blocks_positioning_interpretation(snapshot_flags)


def compute_cross_asset_context(
    equity_crowding: ParticipantCrowdingEvidence | None,
    cot_payload: dict[str, Any],
    *,
    equity_symbol: str,
    futures_symbol: str,
    prediction_cutoff: int,
) -> CrossAssetParticipantContextEvidence | None:
    if equity_crowding is None:
        return None

    equity_direction = _equity_direction_from_crowding(equity_crowding)
    if _cot_unavailable(cot_payload):
        quality_flags = _collect_quality_flags(
            equity_crowding=equity_crowding,
            cot_payload=cot_payload,
        )
        return CrossAssetParticipantContextEvidence(
            equity_symbol=equity_symbol.upper(),
            futures_symbol=futures_symbol.upper(),
            equity_crowding_regime=_equity_crowding_regime_label(equity_crowding),
            futures_cot_regime=None,
            alignment_regime=CrossAssetAlignmentRegime.INSUFFICIENT_DATA,
            alignment_score=None,
            equity_institutional_direction=equity_direction,
            futures_cot_net_percentile=None,
            event_time=equity_crowding.event_time,
            available_time=equity_crowding.available_time,
            producer_version=PRODUCER_VERSION,
            quality_flags=quality_flags,
            cross_lane_signal=None,
        )

    cot_regime = str(cot_payload.get("crowding_regime", CrowdingRegime.NEUTRAL.value))
    snapshot = cot_payload.get("positioning_snapshot", {})
    net_percentile = (
        snapshot.get("net_percentile") if isinstance(snapshot, dict) else None
    )
    quality_flags = _collect_quality_flags(
        equity_crowding=equity_crowding,
        cot_payload=cot_payload,
    )

    if equity_direction is None:
        regime = CrossAssetAlignmentRegime.INSUFFICIENT_DATA
    else:
        regime = _classify_alignment(
            equity_direction=equity_direction,
            cot_regime=cot_regime,
        )

    cross_lane_signal = _select_cross_lane_signal(regime)
    available_time = equity_crowding.available_time
    available_ns = _parse_time_ns(available_time)
    if available_ns > 0 and available_ns > prediction_cutoff:
        cross_lane_signal = None
        regime = CrossAssetAlignmentRegime.INSUFFICIENT_DATA

    event_time = equity_crowding.event_time
    if isinstance(snapshot, dict) and snapshot.get("observation_time"):
        event_time = str(snapshot.get("observation_time"))

    return CrossAssetParticipantContextEvidence(
        equity_symbol=equity_symbol.upper(),
        futures_symbol=futures_symbol.upper(),
        equity_crowding_regime=_equity_crowding_regime_label(equity_crowding),
        futures_cot_regime=cot_regime,
        alignment_regime=regime,
        alignment_score=_alignment_score(regime),
        equity_institutional_direction=equity_direction,
        futures_cot_net_percentile=net_percentile,
        event_time=event_time,
        available_time=available_time,
        producer_version=PRODUCER_VERSION,
        quality_flags=quality_flags,
        cross_lane_signal=cross_lane_signal,
    )


def cross_asset_summary_to_dict(item: CrossAssetParticipantContextEvidence) -> dict[str, Any]:
    payload = cross_asset_participant_context_evidence_to_dict(item)
    payload["scoring_method"] = SCORING_METHOD
    return payload


def summarize_cross_asset_context(
    item: CrossAssetParticipantContextEvidence | None,
) -> dict[str, Any]:
    if item is None:
        return {
            "cross_asset_available": False,
            "alignment_regime": CrossAssetAlignmentRegime.INSUFFICIENT_DATA.value,
            "cross_lane_signals": [],
            "producer_version": PRODUCER_VERSION,
        }
    signals = [item.cross_lane_signal] if item.cross_lane_signal else []
    return {
        "cross_asset_available": item.alignment_regime
        != CrossAssetAlignmentRegime.INSUFFICIENT_DATA,
        "alignment_regime": item.alignment_regime.value,
        "alignment_score": item.alignment_score,
        "equity_symbol": item.equity_symbol,
        "futures_symbol": item.futures_symbol,
        "equity_institutional_direction": item.equity_institutional_direction,
        "futures_cot_regime": item.futures_cot_regime,
        "futures_cot_net_percentile": item.futures_cot_net_percentile,
        "cross_lane_signals": signals,
        "producer_version": PRODUCER_VERSION,
    }


def publish_cross_asset_signals(
    item: CrossAssetParticipantContextEvidence | None,
    *,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    if item is None or item.cross_lane_signal is None:
        return []
    if _parse_time_ns(item.available_time) > prediction_cutoff:
        return []
    if item.alignment_regime == CrossAssetAlignmentRegime.INSUFFICIENT_DATA:
        return []

    detail = (
        f"{item.equity_symbol}/{item.futures_symbol} cross-asset={item.alignment_regime.value} "
        f"equity={item.equity_institutional_direction} cot={item.futures_cot_regime}; research only"
    )
    return [
        lane_evidence_to_dict(
            NormalizedLaneEvidence(
                lane=LaneId.PARTICIPANT_INTELLIGENCE,
                signal=EvidenceSignal(item.cross_lane_signal),
                strength="MODERATE",
                available=True,
                source_ref=f"participant:cross_asset:{item.equity_symbol}:{item.futures_symbol}",
                detail=detail,
                observed_at=item.available_time,
                quality_flags=item.quality_flags,
                provenance_class=EvidenceProvenanceClass.DERIVED,
            )
        )
    ]


def build_cross_asset_participant_context_bundle(
    actions: list[dict[str, Any]],
    *,
    instrument_id: str,
    prediction_cutoff: int,
    cross_asset_fixture_path: Path | str | None = None,
    crowding_fixture_path: Path | str | None = None,
    cot_fixture_path: Path | str | None = None,
) -> dict[str, Any]:
    if not actions:
        return {
            "available": False,
            "reason": "NO_PARTICIPANT_ACTIONS",
            "summary": summarize_cross_asset_context(None),
            "evidence": None,
        }

    fixture = load_cross_asset_slice(cross_asset_fixture_path)
    equity_symbol = str(fixture.get("equity_symbol", instrument_id)).upper()
    futures_symbol = str(fixture.get("futures_symbol", "ES")).upper()
    futures_decision_time = fixture.get("futures_decision_time")
    if futures_decision_time is None:
        futures_decision_time = prediction_cutoff
    cot_path = cot_fixture_path or fixture.get("cot_fixture_path")
    crowding_path = crowding_fixture_path or fixture.get("crowding_fixture_path")

    equity_crowding = compute_crowding_evidence(
        actions,
        instrument_id=equity_symbol,
        prediction_cutoff=prediction_cutoff,
        crowding_fixture_path=crowding_path,
    )
    if equity_crowding is None:
        return {
            "available": False,
            "reason": "EQUITY_CROWDING_UNAVAILABLE",
            "summary": summarize_cross_asset_context(None),
            "evidence": None,
        }

    resolved_cot_path = Path(cot_path) if cot_path else DEFAULT_COT_FIXTURE
    if not resolved_cot_path.is_absolute():
        resolved_cot_path = Path(__file__).resolve().parents[3] / resolved_cot_path

    cot_payload = _fetch_cot_payload(
        futures_symbol=futures_symbol,
        decision_time=futures_decision_time,
        cot_fixture_path=resolved_cot_path,
    )
    evidence = compute_cross_asset_context(
        equity_crowding,
        cot_payload,
        equity_symbol=equity_symbol,
        futures_symbol=futures_symbol,
        prediction_cutoff=prediction_cutoff,
    )
    return {
        "available": evidence is not None
        and evidence.alignment_regime != CrossAssetAlignmentRegime.INSUFFICIENT_DATA,
        "summary": summarize_cross_asset_context(evidence),
        "evidence": cross_asset_summary_to_dict(evidence) if evidence is not None else None,
        "evidence_object": evidence,
        "equity_crowding_producer": CROWDING_PRODUCER_VERSION,
    }


__all__ = [
    "DEFAULT_CROSS_ASSET_FIXTURE",
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "build_cross_asset_participant_context_bundle",
    "compute_cross_asset_context",
    "cross_asset_summary_to_dict",
    "load_cross_asset_slice",
    "publish_cross_asset_signals",
    "summarize_cross_asset_context",
]
