"""Participant Intelligence cross-lane adapter (PI3 + PI5 + PI6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..features.institutional import get_institutional_ledger
from ..order_flow.evidence import metaorder_primitive_cross_lane_evidence
from ..order_flow.metaorder import classified_trades_from_bars, detect_metaorder_primitives
from ..participant.bridge import query_participant_actions_from_ledger
from ..participant.contextual_intent import (
    build_contextual_intent_evidence,
    contextual_intent_summary_to_dict,
    publish_contextual_intent_signals,
)
from ..participant.copyability import (
    build_participant_copyability_bundle,
    publish_copyability_signals,
)
from ..participant.crowding import (
    build_participant_crowding_bundle,
    compute_crowding_evidence,
    publish_crowding_signals,
)
from ..participant.cross_asset import (
    build_cross_asset_participant_context_bundle,
    publish_cross_asset_signals,
)
from ..participant.derivatives import build_derivatives_participant_bundle
from ..participant.forced_flow import build_forced_flow_bundle
from ..participant.evidence import (
    build_evidence_payloads_from_actions,
    build_metaorder_evidence_envelope,
    participant_cross_lane_evidence_from_actions,
    participant_skill_cross_lane_evidence,
    publish_metaorder_signals,
    publish_derivatives_signals,
    publish_forced_flow_signals,
    summarize_participant_actions,
)
from ..participant.metaorder import interpret_metaorder_primitives
from ..participant.skill import build_participant_skill_bundle, DEFAULT_PRICE_OUTCOME_FIXTURE

DEFAULT_METAORDER_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "providers"
    / "order_flow"
    / "nvda_metaorder_slice.json"
)

DEFAULT_DERIVATIVES_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "participant"
    / "nvda_derivatives_participant_slice.json"
)

DEFAULT_FORCED_FLOW_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "participant"
    / "nvda_forced_flow_slice.json"
)


def _load_order_flow_bars(
    *,
    instrument_id: str,
    prediction_cutoff: int,
    fixture_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    if fixture_path is not None:
        payload = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
        bars = payload.get("bars", [])
        return [bar for bar in bars if isinstance(bar, dict)] if isinstance(bars, list) else []
    ledger = get_institutional_ledger()
    if ledger is None:
        return []
    return ledger.query_order_flow_summaries(
        instrument_id=instrument_id.upper(),
        prediction_cutoff=prediction_cutoff,
    )


def build_metaorder_bundle(
    *,
    instrument_id: str,
    prediction_cutoff: str,
    fixture_path: Path | str | None = None,
) -> dict[str, Any]:
    bars = _load_order_flow_bars(
        instrument_id=instrument_id,
        prediction_cutoff=int(prediction_cutoff),
        fixture_path=fixture_path,
    )
    if not bars:
        return {
            "available": False,
            "primitives": [],
            "evidence": [],
            "envelopes": [],
            "summary": {"metaorder_available": False, "primitive_count": 0},
        }
    trades = classified_trades_from_bars(bars, instrument=instrument_id.upper())
    primitives = detect_metaorder_primitives(
        trades,
        instrument=instrument_id.upper(),
        min_signed_volume=500.0,
        min_trade_count=3,
        min_duration_seconds=2.0,
    )
    evidence_items = interpret_metaorder_primitives(
        primitives,
        prediction_cutoff=int(prediction_cutoff),
    )
    envelopes = [build_metaorder_evidence_envelope(item) for item in evidence_items]
    return {
        "available": bool(primitives),
        "primitives": primitives,
        "evidence": evidence_items,
        "envelopes": envelopes,
        "summary": {
            "metaorder_available": bool(primitives),
            "primitive_count": len(primitives),
            "active_count": sum(1 for item in evidence_items if item.lifecycle_state.value == "ACTIVE"),
            "likely_complete_count": sum(
                1 for item in evidence_items if item.lifecycle_state.value == "LIKELY_COMPLETE"
            ),
        },
    }


def build_participant_actions_bundle(
    *,
    instrument_id: str,
    prediction_cutoff: int,
    price_fixture_path: Path | str | None = None,
    metaorder_fixture_path: Path | str | None = None,
    copyability_fixture_path: Path | str | None = None,
    crowding_fixture_path: Path | str | None = None,
    cross_asset_fixture_path: Path | str | None = None,
    cot_fixture_path: Path | str | None = None,
    derivatives_fixture_path: Path | str | None = None,
    forced_flow_fixture_path: Path | str | None = None,
) -> dict[str, Any]:
    ledger = get_institutional_ledger()
    if ledger is None:
        return {
            "available": False,
            "reason": "WHALE_NO_ENTITLED_SOURCE",
            "actions": [],
            "summary": {"direction": "unavailable", "action_count": 0},
            "typed_evidence": [],
            "envelopes": [],
            "skill": {"available": False, "summary": {"skill_available": False}},
            "metaorder": {"available": False, "summary": {"metaorder_available": False}},
            "copyability": {"available": False, "summary": {"copyability_available": False}},
            "crowding": {"available": False, "summary": {"crowding_available": False}},
            "cross_asset": {"available": False, "summary": {"cross_asset_available": False}},
            "derivatives": {"available": False, "summary": {"derivatives_participant_available": False}},
            "forced_flow": {"available": False, "summary": {"forced_flow_available": False}},
        }
    events = ledger.query_events(
        family="regulatory_disclosure",
        instrument_id=instrument_id.upper(),
        prediction_cutoff=prediction_cutoff,
    )
    if not events:
        return {
            "available": False,
            "reason": "WHALE_NO_PIT_ELIGIBLE_DISCLOSURE",
            "actions": [],
            "summary": {"direction": "unavailable", "action_count": 0},
            "typed_evidence": [],
            "envelopes": [],
            "skill": {"available": False, "summary": {"skill_available": False}},
            "metaorder": {"available": False, "summary": {"metaorder_available": False}},
            "copyability": {"available": False, "summary": {"copyability_available": False}},
            "crowding": {"available": False, "summary": {"crowding_available": False}},
            "cross_asset": {"available": False, "summary": {"cross_asset_available": False}},
            "derivatives": {"available": False, "summary": {"derivatives_participant_available": False}},
            "forced_flow": {"available": False, "summary": {"forced_flow_available": False}},
        }
    actions = query_participant_actions_from_ledger(
        events,
        instrument_id=instrument_id.upper(),
        prediction_cutoff=prediction_cutoff,
    )
    typed, envelopes = build_evidence_payloads_from_actions(actions)
    skill_bundle = build_participant_skill_bundle(
        actions,
        prediction_cutoff=prediction_cutoff,
        price_fixture_path=price_fixture_path or DEFAULT_PRICE_OUTCOME_FIXTURE,
    )
    copyability_bundle = build_participant_copyability_bundle(
        actions,
        prediction_cutoff=prediction_cutoff,
        price_fixture_path=price_fixture_path or DEFAULT_PRICE_OUTCOME_FIXTURE,
        copyability_fixture_path=copyability_fixture_path,
    )
    crowding_bundle = build_participant_crowding_bundle(
        actions,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
        crowding_fixture_path=crowding_fixture_path,
    )
    cross_asset_bundle = build_cross_asset_participant_context_bundle(
        actions,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
        cross_asset_fixture_path=cross_asset_fixture_path,
        crowding_fixture_path=crowding_fixture_path,
        cot_fixture_path=cot_fixture_path,
    )
    metaorder_bundle = build_metaorder_bundle(
        instrument_id=instrument_id,
        prediction_cutoff=str(prediction_cutoff),
        fixture_path=metaorder_fixture_path,
    )
    derivatives_bundle = build_derivatives_participant_bundle(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
        derivatives_fixture_path=derivatives_fixture_path or DEFAULT_DERIVATIVES_FIXTURE,
        metaorder_evidence=metaorder_bundle.get("evidence", [])
        if isinstance(metaorder_bundle, dict)
        else None,
    )
    forced_flow_bundle = build_forced_flow_bundle(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
        forced_flow_fixture_path=forced_flow_fixture_path or DEFAULT_FORCED_FLOW_FIXTURE,
        metaorder_evidence=metaorder_bundle.get("evidence", [])
        if isinstance(metaorder_bundle, dict)
        else None,
    )
    summary = summarize_participant_actions(actions)
    if skill_bundle.get("available"):
        skill_summary = skill_bundle.get("summary", {})
        if isinstance(skill_summary, dict):
            summary["participant_skill"] = skill_summary
    if metaorder_bundle.get("available"):
        summary["metaorder"] = metaorder_bundle.get("summary", {})
    if copyability_bundle.get("available"):
        summary["copyability"] = copyability_bundle.get("summary", {})
    if crowding_bundle.get("available"):
        summary["crowding"] = crowding_bundle.get("summary", {})
    if cross_asset_bundle.get("available"):
        summary["cross_asset"] = cross_asset_bundle.get("summary", {})
    if derivatives_bundle.get("available"):
        summary["derivatives"] = derivatives_bundle.get("summary", {})
    if forced_flow_bundle.get("available"):
        summary["forced_flow"] = forced_flow_bundle.get("summary", {})
    return {
        "available": True,
        "actions": actions,
        "summary": summary,
        "typed_evidence": typed,
        "envelopes": envelopes,
        "skill": skill_bundle,
        "metaorder": metaorder_bundle,
        "copyability": copyability_bundle,
        "crowding": crowding_bundle,
        "cross_asset": cross_asset_bundle,
        "derivatives": derivatives_bundle,
        "forced_flow": forced_flow_bundle,
    }


def participant_evidence_from_actions(
    actions: list[dict[str, Any]],
    *,
    skill_summary: dict[str, Any] | None = None,
    metaorder_evidence: list | None = None,
    metaorder_primitives: list | None = None,
    catalyst_summaries: list | None = None,
    prediction_cutoff: int | None = None,
    copyability_summaries: list | None = None,
    crowding_evidence: Any | None = None,
    cross_asset_evidence: Any | None = None,
    derivatives_evidence: list | None = None,
    forced_flow_evidence: list | None = None,
) -> list[dict[str, Any]]:
    evidence = participant_cross_lane_evidence_from_actions(actions)
    if skill_summary:
        evidence.extend(participant_skill_cross_lane_evidence(skill_summary))
    if metaorder_evidence:
        evidence.extend(publish_metaorder_signals(metaorder_evidence))
    if metaorder_primitives:
        evidence.extend(metaorder_primitive_cross_lane_evidence(metaorder_primitives))
    if catalyst_summaries is not None and prediction_cutoff is not None:
        _, intent_summaries = build_contextual_intent_evidence(
            actions,
            catalyst_summaries,
            prediction_cutoff=prediction_cutoff,
        )
        evidence.extend(
            publish_contextual_intent_signals(
                intent_summaries,
                prediction_cutoff=prediction_cutoff,
            )
        )
    if copyability_summaries is not None and prediction_cutoff is not None:
        evidence.extend(
            publish_copyability_signals(
                copyability_summaries,
                prediction_cutoff=prediction_cutoff,
            )
        )
    if crowding_evidence is not None and prediction_cutoff is not None:
        evidence.extend(
            publish_crowding_signals(
                crowding_evidence,
                prediction_cutoff=prediction_cutoff,
            )
        )
    if cross_asset_evidence is not None and prediction_cutoff is not None:
        evidence.extend(
            publish_cross_asset_signals(
                cross_asset_evidence,
                prediction_cutoff=prediction_cutoff,
            )
        )
    if derivatives_evidence is not None and prediction_cutoff is not None:
        evidence.extend(
            publish_derivatives_signals(
                derivatives_evidence,
                prediction_cutoff=prediction_cutoff,
            )
        )
    if forced_flow_evidence is not None and prediction_cutoff is not None:
        evidence.extend(
            publish_forced_flow_signals(
                forced_flow_evidence,
                prediction_cutoff=prediction_cutoff,
            )
        )
    return evidence


def build_participant_cross_lane_bundle(
    *,
    instrument_id: str,
    prediction_cutoff: int,
    price_fixture_path: Path | str | None = None,
    metaorder_fixture_path: Path | str | None = None,
    catalyst_summaries: list | None = None,
    copyability_fixture_path: Path | str | None = None,
    crowding_fixture_path: Path | str | None = None,
    cross_asset_fixture_path: Path | str | None = None,
    cot_fixture_path: Path | str | None = None,
    derivatives_fixture_path: Path | str | None = None,
    forced_flow_fixture_path: Path | str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    bundle = build_participant_actions_bundle(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
        price_fixture_path=price_fixture_path,
        metaorder_fixture_path=metaorder_fixture_path,
        copyability_fixture_path=copyability_fixture_path,
        crowding_fixture_path=crowding_fixture_path,
        cross_asset_fixture_path=cross_asset_fixture_path,
        cot_fixture_path=cot_fixture_path,
        derivatives_fixture_path=derivatives_fixture_path,
        forced_flow_fixture_path=forced_flow_fixture_path,
    )
    if not bundle.get("available"):
        return {}, []
    actions = bundle.get("actions", [])
    if not isinstance(actions, list):
        actions = []
    skill_bundle = bundle.get("skill", {})
    skill_summary = skill_bundle.get("summary", {}) if isinstance(skill_bundle, dict) else {}
    metaorder_bundle = bundle.get("metaorder", {})
    metaorder_summary = metaorder_bundle.get("summary", {}) if isinstance(metaorder_bundle, dict) else {}
    copyability_bundle = bundle.get("copyability", {})
    copyability_summary = (
        copyability_bundle.get("summary", {}) if isinstance(copyability_bundle, dict) else {}
    )
    copyability_summaries_raw = (
        copyability_bundle.get("summaries", []) if isinstance(copyability_bundle, dict) else []
    )
    crowding_bundle = bundle.get("crowding", {})
    crowding_summary = crowding_bundle.get("summary", {}) if isinstance(crowding_bundle, dict) else {}
    cross_asset_bundle = bundle.get("cross_asset", {})
    cross_asset_summary = (
        cross_asset_bundle.get("summary", {}) if isinstance(cross_asset_bundle, dict) else {}
    )
    derivatives_bundle = bundle.get("derivatives", {})
    derivatives_summary = (
        derivatives_bundle.get("summary", {}) if isinstance(derivatives_bundle, dict) else {}
    )
    forced_flow_bundle = bundle.get("forced_flow", {})
    forced_flow_summary = (
        forced_flow_bundle.get("summary", {}) if isinstance(forced_flow_bundle, dict) else {}
    )
    contextual_intent_summaries: list[dict[str, Any]] = []
    if catalyst_summaries is not None:
        _, contextual_intent_summaries_raw = build_contextual_intent_evidence(
            actions,
            catalyst_summaries,
            prediction_cutoff=prediction_cutoff,
        )
        contextual_intent_summaries = [
            contextual_intent_summary_to_dict(item) for item in contextual_intent_summaries_raw
        ]
    snapshot = {
        "participant_available": True,
        "participant_summary": bundle.get("summary", {}),
        "participant_action_count": len(actions),
        "participant_evidence_count": len(bundle.get("typed_evidence", [])),
        "participant_skill_summary": skill_summary,
        "participant_skill_available": bool(skill_summary.get("skill_available")),
        "participant_metaorder_summary": metaorder_summary,
        "participant_metaorder_available": bool(metaorder_summary.get("metaorder_available")),
        "participant_contextual_intent_available": bool(contextual_intent_summaries),
        "participant_contextual_intent_summaries": contextual_intent_summaries,
        "participant_copyability_summary": copyability_summary,
        "participant_copyability_available": bool(copyability_summary.get("copyability_available")),
        "participant_copyability_summaries": copyability_summaries_raw,
        "participant_crowding_summary": crowding_summary,
        "participant_crowding_available": bool(crowding_summary.get("crowding_available")),
        "participant_cross_asset_summary": cross_asset_summary,
        "participant_cross_asset_available": bool(cross_asset_summary.get("cross_asset_available")),
        "participant_derivatives_summary": derivatives_summary,
        "participant_derivatives_available": bool(
            derivatives_summary.get("derivatives_participant_available")
        ),
        "participant_forced_flow_summary": forced_flow_summary,
        "participant_forced_flow_available": bool(
            forced_flow_summary.get("forced_flow_available")
        ),
    }
    from ..participant.copyability import CopyabilitySummary

    crowding_evidence_item = compute_crowding_evidence(
        actions,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
        crowding_fixture_path=crowding_fixture_path,
    )

    cross_asset_evidence_item = (
        cross_asset_bundle.get("evidence_object")
        if isinstance(cross_asset_bundle, dict)
        else None
    )
    derivatives_evidence_items = (
        derivatives_bundle.get("evidence", [])
        if isinstance(derivatives_bundle, dict)
        else []
    )
    forced_flow_evidence_items = (
        forced_flow_bundle.get("evidence", [])
        if isinstance(forced_flow_bundle, dict)
        else []
    )

    copyability_summary_objects = [
        CopyabilitySummary(
            action_id=str(row.get("action_id", "")),
            participant_id=str(row.get("participant_id", "")),
            display_name=str(row.get("display_name", "")),
            instrument_id=str(row.get("instrument_id", "")),
            mechanism=str(row.get("mechanism", "")),
            copyability_class=str(row.get("copyability_class", "")),
            participant_gross_return=row.get("participant_gross_return"),
            follower_return_at_available=row.get("follower_return_at_available"),
            cost_adjusted_follower_return=row.get("cost_adjusted_follower_return"),
            copyability_score=row.get("copyability_score"),
            event_time=str(row.get("event_time", "")),
            available_time=str(row.get("available_time", "")),
            quality_flags=tuple(row.get("quality_flags", [])),
            cross_lane_signal=row.get("cross_lane_signal"),
        )
        for row in copyability_summaries_raw
        if isinstance(row, dict)
    ]
    evidence = participant_evidence_from_actions(
        actions,
        skill_summary=skill_summary,
        metaorder_evidence=metaorder_bundle.get("evidence", []) if isinstance(metaorder_bundle, dict) else [],
        metaorder_primitives=metaorder_bundle.get("primitives", []) if isinstance(metaorder_bundle, dict) else [],
        catalyst_summaries=catalyst_summaries,
        prediction_cutoff=prediction_cutoff,
        copyability_summaries=copyability_summary_objects,
        crowding_evidence=crowding_evidence_item,
        cross_asset_evidence=cross_asset_evidence_item,
        derivatives_evidence=derivatives_evidence_items,
        forced_flow_evidence=forced_flow_evidence_items,
    )
    return snapshot, evidence
