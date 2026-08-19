"""Participant Intelligence cross-lane adapter (PI3 + PI5 + PI6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..features.institutional import get_institutional_ledger
from ..order_flow.evidence import metaorder_primitive_cross_lane_evidence
from ..order_flow.metaorder import classified_trades_from_bars, detect_metaorder_primitives
from ..participant.bridge import query_participant_actions_from_ledger
from ..participant.evidence import (
    build_evidence_payloads_from_actions,
    build_metaorder_evidence_envelope,
    participant_cross_lane_evidence_from_actions,
    participant_skill_cross_lane_evidence,
    publish_metaorder_signals,
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
    metaorder_bundle = build_metaorder_bundle(
        instrument_id=instrument_id,
        prediction_cutoff=str(prediction_cutoff),
        fixture_path=metaorder_fixture_path,
    )
    summary = summarize_participant_actions(actions)
    if skill_bundle.get("available"):
        skill_summary = skill_bundle.get("summary", {})
        if isinstance(skill_summary, dict):
            summary["participant_skill"] = skill_summary
    if metaorder_bundle.get("available"):
        summary["metaorder"] = metaorder_bundle.get("summary", {})
    return {
        "available": True,
        "actions": actions,
        "summary": summary,
        "typed_evidence": typed,
        "envelopes": envelopes,
        "skill": skill_bundle,
        "metaorder": metaorder_bundle,
    }


def participant_evidence_from_actions(
    actions: list[dict[str, Any]],
    *,
    skill_summary: dict[str, Any] | None = None,
    metaorder_evidence: list | None = None,
    metaorder_primitives: list | None = None,
) -> list[dict[str, Any]]:
    evidence = participant_cross_lane_evidence_from_actions(actions)
    if skill_summary:
        evidence.extend(participant_skill_cross_lane_evidence(skill_summary))
    if metaorder_evidence:
        evidence.extend(publish_metaorder_signals(metaorder_evidence))
    if metaorder_primitives:
        evidence.extend(metaorder_primitive_cross_lane_evidence(metaorder_primitives))
    return evidence


def build_participant_cross_lane_bundle(
    *,
    instrument_id: str,
    prediction_cutoff: int,
    price_fixture_path: Path | str | None = None,
    metaorder_fixture_path: Path | str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    bundle = build_participant_actions_bundle(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
        price_fixture_path=price_fixture_path,
        metaorder_fixture_path=metaorder_fixture_path,
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
    snapshot = {
        "participant_available": True,
        "participant_summary": bundle.get("summary", {}),
        "participant_action_count": len(actions),
        "participant_evidence_count": len(bundle.get("typed_evidence", [])),
        "participant_skill_summary": skill_summary,
        "participant_skill_available": bool(skill_summary.get("skill_available")),
        "participant_metaorder_summary": metaorder_summary,
        "participant_metaorder_available": bool(metaorder_summary.get("metaorder_available")),
    }
    evidence = participant_evidence_from_actions(
        actions,
        skill_summary=skill_summary,
        metaorder_evidence=metaorder_bundle.get("evidence", []) if isinstance(metaorder_bundle, dict) else [],
        metaorder_primitives=metaorder_bundle.get("primitives", []) if isinstance(metaorder_bundle, dict) else [],
    )
    return snapshot, evidence
