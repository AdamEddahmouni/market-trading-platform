"""P3.2 unified workstation evidence envelope and lane adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .store import ReplayStore

RESEARCH_CONTEXT_EXECUTION_AUTHORITY = "NONE"

LANE_ORDER_FLOW = "ORDER_FLOW"
LANE_SHORT_INTELLIGENCE = "SHORT_INTELLIGENCE"
LANE_SHORT_SQUEEZE = "SHORT_SQUEEZE"
LANE_MARKET_CONTEXT = "MARKET_CONTEXT"
LANE_CATALYST = "CATALYST"
LANE_WHALE_INSIDER = "WHALE_INSIDER"
LANE_OPTIONS = "OPTIONS"
LANE_FUTURES = "FUTURES"

DIRECTION_POSITIVE = "POSITIVE"
DIRECTION_NEGATIVE = "NEGATIVE"
DIRECTION_NEUTRAL = "NEUTRAL"
DIRECTION_MIXED = "MIXED"
DIRECTION_UNKNOWN = "UNKNOWN"

REPO_ROOT = Path(__file__).resolve().parents[3]
SHORT_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "short_intelligence"


def _lane_base(
    *,
    instrument: str,
    lane: str,
    evidence_type: str,
    quality: str,
    relevance: str,
    summary: str,
    freshness_label: str,
    as_of: str | None = None,
    available_time: str | None = None,
    direction: str | None = None,
    confidence: str | None = None,
    probability: float | None = None,
    expected_value: float | None = None,
    reason_codes: list[str] | None = None,
    sources: list[str] | None = None,
    details: dict[str, Any] | None = None,
    explain_ref: str | None = None,
    missing_evidence: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "instrument": instrument.upper(),
        "lane": lane,
        "evidence_type": evidence_type,
        "as_of": as_of,
        "available_time": available_time,
        "quality": quality,
        "relevance": relevance,
        "direction": direction,
        "confidence": confidence,
        "probability": probability,
        "expected_value": expected_value,
        "summary": summary,
        "freshness_label": freshness_label,
        "reason_codes": reason_codes or [],
        "sources": sources or [],
        "details": details or {},
        "explain_ref": explain_ref,
        "missing_evidence": missing_evidence or [],
        "research_only": True,
    }


def compute_evidence_mix_summary(lanes: list[dict[str, Any]]) -> str:
    """Preserve contradictions — no majority vote."""
    directional: list[str] = []
    for row in lanes:
        direction = str(row.get("direction") or "").upper()
        if direction in {DIRECTION_POSITIVE, DIRECTION_NEGATIVE}:
            directional.append(direction)
    if not directional:
        return DIRECTION_UNKNOWN
    positives = sum(1 for d in directional if d == DIRECTION_POSITIVE)
    negatives = sum(1 for d in directional if d == DIRECTION_NEGATIVE)
    if positives and negatives:
        return DIRECTION_MIXED
    if positives:
        return DIRECTION_POSITIVE
    if negatives:
        return DIRECTION_NEGATIVE
    return DIRECTION_NEUTRAL


def _cvd_direction(cvd: dict[str, Any] | None) -> str:
    if not cvd:
        return DIRECTION_UNKNOWN
    slope = cvd.get("cvd_slope")
    session = cvd.get("session_cvd")
    if isinstance(slope, (int, float)) and slope != 0:
        return DIRECTION_POSITIVE if slope > 0 else DIRECTION_NEGATIVE
    if isinstance(session, (int, float)) and session != 0:
        return DIRECTION_POSITIVE if session > 0 else DIRECTION_NEGATIVE
    return DIRECTION_NEUTRAL


def adapt_order_flow_lane(
    store: ReplayStore,
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument = symbol.upper()
    from .live_projections import build_live_order_flow_payload

    live = build_live_order_flow_payload(instrument)
    if live is not None and live.get("available"):
        cvd = live.get("cvd") if isinstance(live.get("cvd"), dict) else None
        quality = str(live.get("quality") or "PASS")
        direction = _cvd_direction(cvd)
        freshness = "LIVE"
        if quality == "DEGRADED":
            freshness = "LIVE · DEGRADED"
        unknown_agg = int(live.get("unknown_aggressor") or 0)
        inferred = int(live.get("inferred") or 0)
        missing: list[str] = []
        if unknown_agg:
            missing.append(f"{unknown_agg} trades with UNKNOWN aggressor")
        return _lane_base(
            instrument=instrument,
            lane=LANE_ORDER_FLOW,
            evidence_type="LIVE_CVD",
            quality=quality,
            relevance="HIGH",
            summary=f"{direction.lower().replace('_', ' ')} pressure · CVD {cvd.get('session_cvd') if cvd else '—'}",
            freshness_label=freshness,
            as_of=str(as_of_context.get("as_of_time") or ""),
            direction=direction,
            confidence="MEDIUM" if inferred else "HIGH",
            reason_codes=["LIVE_MOOMOO_TRADES"],
            sources=["MOOMOO"],
            details={
                "cvd": cvd,
                "classified_count": live.get("classified_count"),
                "provider_directed": live.get("provider_directed"),
                "inferred": inferred,
                "unknown_aggressor": unknown_agg,
                "bar_count": live.get("bar_count"),
            },
            explain_ref=f"explain:order-flow:{instrument}",
            missing_evidence=missing,
        )

    from ..providers.projections import build_workspace_order_flow_payload

    fixture = build_workspace_order_flow_payload(
        instrument,
        as_of_context=as_of_context,
        prediction_cutoff=prediction_cutoff,
    )
    if not fixture.get("available"):
        return _lane_base(
            instrument=instrument,
            lane=LANE_ORDER_FLOW,
            evidence_type="FIXTURE_CVD",
            quality="UNAVAILABLE",
            relevance="HIGH",
            summary=str(fixture.get("reason") or "No order-flow evidence"),
            freshness_label="—",
            direction=DIRECTION_UNKNOWN,
            reason_codes=[str(fixture.get("reason") or "UNAVAILABLE")],
            sources=[],
            explain_ref=f"explain:order-flow:{instrument}",
        )
    cvd_summary = fixture.get("cvd_summary") if isinstance(fixture.get("cvd_summary"), dict) else {}
    direction = _cvd_direction(
        {
            "session_cvd": cvd_summary.get("session_cvd"),
            "cvd_slope": cvd_summary.get("cvd_slope"),
        }
    )
    return _lane_base(
        instrument=instrument,
        lane=LANE_ORDER_FLOW,
        evidence_type="FIXTURE_CVD",
        quality="PASS",
        relevance="HIGH",
        summary=f"{direction.lower().replace('_', ' ')} pressure · fixture CVD",
        freshness_label="REPLAY",
        as_of=str(as_of_context.get("as_of_time") or ""),
        direction=direction,
        confidence="MEDIUM",
        reason_codes=["FIXTURE_ORDER_FLOW"],
        sources=[str(fixture.get("provider_id") or "cvd.fixture")],
        details={"cvd_summary": cvd_summary, "bar_count": fixture.get("bar_count")},
        explain_ref=f"explain:order-flow:{instrument}",
    )


def _load_short_intelligence_store(symbol: str) -> Any | None:
    from ..short_intelligence.identity import SymbolMap
    from ..short_intelligence.store import ShortIntelligenceStore

    map_path = SHORT_FIXTURES / "symbol_map.json"
    slice_path = SHORT_FIXTURES / "consolidated_short_interest_slice.json"
    if not map_path.is_file() or not slice_path.is_file():
        return None
    try:
        symbol_map = SymbolMap.from_path(map_path)
        from ..finra.short_interest import normalize_short_interest_row

        payload = json.loads(slice_path.read_text(encoding="utf-8"))
        store = ShortIntelligenceStore()
        for row in payload:
            instrument = normalize_short_interest_row(
                row,
                symbol_map=symbol_map,
                observed_time="2026-08-11T20:45:00Z",
                retrieved_time="2026-08-11T20:45:00Z",
            )
            if instrument.instrument_id == symbol.upper():
                store.add_short_interest(instrument)
        return store if store._short_interest else None
    except (OSError, ValueError, KeyError):
        return None


def adapt_short_intelligence_lane(
    store: ReplayStore,
    symbol: str,
    *,
    as_of_context: dict[str, object],
) -> dict[str, Any]:
    instrument = symbol.upper()
    as_of = str(as_of_context.get("as_of_time") or store.as_of_time())
    si_store = _load_short_intelligence_store(instrument)
    if si_store is None:
        return _lane_base(
            instrument=instrument,
            lane=LANE_SHORT_INTELLIGENCE,
            evidence_type="SHORT_PRESSURE",
            quality="UNAVAILABLE",
            relevance="MEDIUM",
            summary="No short intelligence observations for symbol",
            freshness_label="—",
            direction=DIRECTION_UNKNOWN,
            reason_codes=["SHORT_INTELLIGENCE_UNAVAILABLE"],
            sources=[],
            missing_evidence=["SHORT_INTEREST", "SHORT_SALE_FLOW", "THRESHOLD", "FTD"],
        )
    from ..short_intelligence.pressure import pressure_state

    pressure = pressure_state(si_store, instrument, as_of)
    flags = list(pressure.quality_flags)
    quality = "PASS" if pressure.structural_short_crowding == "OBSERVED" else "STALE"
    if any("UNKNOWN" in flag for flag in flags):
        quality = "DEGRADED"
    direction = DIRECTION_NEUTRAL
    if pressure.short_interest_direction == "INCREASING":
        direction = DIRECTION_NEGATIVE
    elif pressure.short_interest_direction == "DECREASING":
        direction = DIRECTION_POSITIVE
    summary_parts = [
        f"SI {pressure.structural_short_crowding}",
        f"flow {pressure.recent_short_sale_flow}",
        f"threshold {pressure.threshold_status}",
    ]
    return _lane_base(
        instrument=instrument,
        lane=LANE_SHORT_INTELLIGENCE,
        evidence_type="SHORT_PRESSURE",
        quality=quality,
        relevance="MEDIUM",
        summary=" · ".join(summary_parts),
        freshness_label="AS OF AUG 11",
        as_of=pressure.as_of,
        direction=direction,
        confidence="MEDIUM",
        reason_codes=list(flags),
        sources=list(pressure.provenance),
        details={
            "days_to_cover": pressure.days_to_cover,
            "ftd_balance_quantity": pressure.ftd_balance_quantity,
            "threshold_duration": pressure.threshold_duration,
            "short_flow_persistence": pressure.short_flow_persistence,
        },
        missing_evidence=[flag for flag in flags if flag.endswith("_UNKNOWN")],
    )


def adapt_short_squeeze_lane(
    store: ReplayStore,
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
    data_mode: str,
) -> dict[str, Any]:
    instrument = symbol.upper()
    from ..donor_bridge.projections import build_workspace_squeeze_payload

    squeeze = build_workspace_squeeze_payload(
        instrument,
        as_of_context=as_of_context,
        prediction_cutoff=prediction_cutoff,
        data_mode=data_mode,
    )
    if not squeeze.get("available"):
        return _lane_base(
            instrument=instrument,
            lane=LANE_SHORT_SQUEEZE,
            evidence_type="SQUEEZE_STATE",
            quality="UNAVAILABLE",
            relevance="LOW",
            summary=str(squeeze.get("reason") or "Not a squeeze research case"),
            freshness_label="—",
            direction=DIRECTION_NEUTRAL,
            reason_codes=[str(squeeze.get("reason") or "UNAVAILABLE")],
            sources=["short-squeeze-project"],
            explain_ref=str(squeeze.get("explanation_ref") or f"explain:squeeze:{instrument}"),
        )
    ignition = str(squeeze.get("ignition_state") or "UNKNOWN")
    relevance = "HIGH" if ignition not in {"NONE", "UNKNOWN", ""} else "LOW"
    direction = DIRECTION_NEUTRAL
    if ignition in {"IGNITION_WATCH", "LIVE_CONFIRMATION", "ACTIVE_SQUEEZE"}:
        direction = DIRECTION_POSITIVE
    return _lane_base(
        instrument=instrument,
        lane=LANE_SHORT_SQUEEZE,
        evidence_type="SQUEEZE_STATE",
        quality="PASS",
        relevance=relevance,
        summary=f"{ignition} · {squeeze.get('evidence_coverage') or 'coverage unknown'}",
        freshness_label=str(squeeze.get("freshness") or "FROZEN"),
        direction=direction,
        confidence="MEDIUM",
        reason_codes=list(squeeze.get("ignition_state_quality_flags") or []),
        sources=["short-squeeze-project"],
        details={
            "research_detection": squeeze.get("research_detection"),
            "readiness": squeeze.get("readiness"),
            "rules": squeeze.get("rules"),
        },
        explain_ref=str(squeeze.get("explanation_ref") or f"explain:squeeze:{instrument}"),
        missing_evidence=[],
    )


def adapt_market_context_lane(
    store: ReplayStore,
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument = symbol.upper()
    from ..providers.projections import build_workspace_market_context_payload

    mc = build_workspace_market_context_payload(
        instrument,
        as_of_context=as_of_context,
        prediction_cutoff=prediction_cutoff,
    )
    if not mc.get("available"):
        return _lane_base(
            instrument=instrument,
            lane=LANE_MARKET_CONTEXT,
            evidence_type="MACRO_REGIME",
            quality="UNAVAILABLE",
            relevance="MEDIUM",
            summary=str(mc.get("reason") or "Market context not entitled"),
            freshness_label="—",
            direction=DIRECTION_UNKNOWN,
            reason_codes=[str(mc.get("reason") or "UNAVAILABLE")],
            sources=[],
            explain_ref=f"explain:market-context:{instrument}",
        )
    synthesis_rows = mc.get("multi_document_synthesis_summaries") or []
    regime_label = None
    if synthesis_rows and isinstance(synthesis_rows[-1], dict):
        regime_label = synthesis_rows[-1].get("regime_label") or synthesis_rows[-1].get("macro_risk_regime")
    direction = DIRECTION_NEUTRAL
    if isinstance(regime_label, str):
        lowered = regime_label.lower()
        if "risk_off" in lowered or "negative" in lowered:
            direction = DIRECTION_NEGATIVE
        elif "risk_on" in lowered or "positive" in lowered:
            direction = DIRECTION_POSITIVE
    return _lane_base(
        instrument=instrument,
        lane=LANE_MARKET_CONTEXT,
        evidence_type="MACRO_REGIME",
        quality="PASS",
        relevance="MEDIUM",
        summary=str(regime_label or "Market context available"),
        freshness_label="REPLAY",
        as_of=str(as_of_context.get("as_of_time") or ""),
        direction=direction,
        confidence="MEDIUM",
        sources=["market_context.fixture"],
        details={"document_count": mc.get("document_count")},
        explain_ref=f"explain:market-context:{instrument}",
    )


def adapt_catalyst_lane(
    store: ReplayStore,
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument = symbol.upper()
    from ..providers.projections import build_workspace_catalyst_payload

    catalyst = build_workspace_catalyst_payload(
        instrument,
        as_of_context=as_of_context,
        prediction_cutoff=prediction_cutoff,
    )
    if not catalyst.get("available"):
        from ..donor_bridge.projections import build_workspace_catalyst_payload as bridge_catalyst

        catalyst = bridge_catalyst(
            instrument,
            as_of_context=as_of_context,
        )
    if not catalyst.get("available"):
        return _lane_base(
            instrument=instrument,
            lane=LANE_CATALYST,
            evidence_type="CATALYST_SENTIMENT",
            quality="UNKNOWN",
            relevance="HIGH",
            summary=str(catalyst.get("reason") or "No catalyst evidence"),
            freshness_label="—",
            direction=DIRECTION_UNKNOWN,
            reason_codes=[str(catalyst.get("reason") or "UNAVAILABLE")],
            sources=[],
            explain_ref=f"explain:catalyst:{instrument}",
        )
    summaries = catalyst.get("catalyst_summaries") or catalyst.get("catalysts") or []
    latest = summaries[-1] if summaries else {}
    lean = None
    if isinstance(latest, dict):
        lean = latest.get("lean_direction") or latest.get("classification")
    direction = DIRECTION_NEUTRAL
    if isinstance(lean, str):
        upper = lean.upper()
        if "POS" in upper or "BULL" in upper:
            direction = DIRECTION_POSITIVE
        elif "NEG" in upper or "BEAR" in upper:
            direction = DIRECTION_NEGATIVE
    headline = ""
    if isinstance(latest, dict):
        headline = str(latest.get("headline") or latest.get("event_type") or "")
    return _lane_base(
        instrument=instrument,
        lane=LANE_CATALYST,
        evidence_type="CATALYST_SENTIMENT",
        quality="PASS",
        relevance="HIGH",
        summary=headline or f"{catalyst.get('catalyst_count', 0)} catalyst(s)",
        freshness_label="REPLAY",
        as_of=str(as_of_context.get("as_of_time") or ""),
        direction=direction,
        confidence=str(latest.get("confidence") or "MEDIUM") if isinstance(latest, dict) else "MEDIUM",
        sources=["catalyst_lane"],
        details={"catalyst_count": catalyst.get("catalyst_count")},
        explain_ref=f"explain:catalyst:{instrument}",
    )


def adapt_whale_insider_lane(
    store: ReplayStore,
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument = symbol.upper()
    from ..providers.projections import build_workspace_disclosure_payload

    disclosure = build_workspace_disclosure_payload(
        instrument,
        as_of_context=as_of_context,
        prediction_cutoff=prediction_cutoff,
    )
    count = int(disclosure.get("event_count") or 0)
    if not disclosure.get("available") or count == 0:
        return _lane_base(
            instrument=instrument,
            lane=LANE_WHALE_INSIDER,
            evidence_type="DISCLOSURE",
            quality="UNAVAILABLE" if not disclosure.get("available") else "PASS",
            relevance="LOW",
            summary="NO CURRENT EVIDENCE",
            freshness_label="—",
            direction=DIRECTION_NEUTRAL,
            reason_codes=[str(disclosure.get("reason") or "NO_DISCLOSURE_EVENTS")],
            sources=[],
            explain_ref=f"explain:disclosure:{instrument}",
        )
    return _lane_base(
        instrument=instrument,
        lane=LANE_WHALE_INSIDER,
        evidence_type="DISCLOSURE",
        quality="PASS",
        relevance="MEDIUM",
        summary=f"{count} disclosure event(s)",
        freshness_label="REPLAY",
        as_of=str(as_of_context.get("as_of_time") or ""),
        direction=DIRECTION_NEUTRAL,
        confidence="HIGH",
        sources=["regulatory_disclosure"],
        details={"event_count": count},
        explain_ref=f"explain:disclosure:{instrument}",
    )


def adapt_options_lane(
    store: ReplayStore,
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument = symbol.upper()
    from ..providers.projections import build_workspace_options_payload

    options = build_workspace_options_payload(
        instrument,
        as_of_context=as_of_context,
        prediction_cutoff=prediction_cutoff,
    )
    if not options.get("available"):
        return _lane_base(
            instrument=instrument,
            lane=LANE_OPTIONS,
            evidence_type="OPTIONS_ACTIVITY",
            quality="NOT_CONFIGURED",
            relevance="—",
            summary="NOT_CONFIGURED",
            freshness_label="—",
            direction=None,
            reason_codes=[str(options.get("reason") or "NOT_CONFIGURED")],
            sources=[],
            explain_ref=f"explain:options:{instrument}",
        )
    return _lane_base(
        instrument=instrument,
        lane=LANE_OPTIONS,
        evidence_type="OPTIONS_ACTIVITY",
        quality="PASS",
        relevance="LOW",
        summary=f"{options.get('activity_count', 0)} activity event(s)",
        freshness_label="REPLAY",
        direction=DIRECTION_NEUTRAL,
        sources=["options_lane"],
        explain_ref=f"explain:options:{instrument}",
    )


def adapt_futures_lane(
    store: ReplayStore,
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument = symbol.upper()
    from ..providers.projections import build_workspace_futures_payload

    futures = build_workspace_futures_payload(
        instrument,
        as_of_context=as_of_context,
        prediction_cutoff=prediction_cutoff,
    )
    if not futures.get("available"):
        return _lane_base(
            instrument=instrument,
            lane=LANE_FUTURES,
            evidence_type="FUTURES_CONTEXT",
            quality="NOT_APPLICABLE",
            relevance="—",
            summary="NOT_APPLICABLE",
            freshness_label="—",
            direction=None,
            reason_codes=[str(futures.get("reason") or "NOT_APPLICABLE")],
            sources=[],
            explain_ref=f"explain:futures:{instrument}",
        )
    return _lane_base(
        instrument=instrument,
        lane=LANE_FUTURES,
        evidence_type="FUTURES_CONTEXT",
        quality="PASS",
        relevance="LOW",
        summary=str(futures.get("depth_imbalance_signal") or "Futures context"),
        freshness_label="REPLAY",
        direction=DIRECTION_NEUTRAL,
        sources=["futures_lane"],
        explain_ref=f"explain:futures:{instrument}",
    )


def build_workspace_evidence_payload(
    store: ReplayStore,
    symbol: str,
    *,
    data_mode: str = "frozen",
    lane_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from . import projections
    from .operator_instrument import resolve_active_operator_instrument

    instrument = symbol.strip().upper()
    if not instrument:
        raise ValueError("symbol is required")

    active, active_source = resolve_active_operator_instrument(store)
    coherence_warning = None
    if active and active != instrument:
        coherence_warning = f"WORKSPACE_INSTRUMENT_COHERENCE: active={active} workspace={instrument}"

    as_of_context = projections.build_as_of_context(store)
    cutoff = store.prediction_cutoff()
    is_live = str(as_of_context.get("data_mode") or "") == "LIVE_OBSERVATIONAL"
    is_replay_capture = str(as_of_context.get("data_mode") or "") == "CAPTURE_REPLAY"

    lanes: list[dict[str, Any]] = [
        adapt_order_flow_lane(store, instrument, as_of_context=as_of_context, prediction_cutoff=cutoff),
        adapt_short_intelligence_lane(store, instrument, as_of_context=as_of_context),
        adapt_short_squeeze_lane(
            store,
            instrument,
            as_of_context=as_of_context,
            prediction_cutoff=cutoff,
            data_mode="current" if is_live else data_mode,
        ),
        adapt_market_context_lane(store, instrument, as_of_context=as_of_context, prediction_cutoff=cutoff),
        adapt_catalyst_lane(store, instrument, as_of_context=as_of_context, prediction_cutoff=cutoff),
        adapt_whale_insider_lane(store, instrument, as_of_context=as_of_context, prediction_cutoff=cutoff),
        adapt_options_lane(store, instrument, as_of_context=as_of_context, prediction_cutoff=cutoff),
        adapt_futures_lane(store, instrument, as_of_context=as_of_context, prediction_cutoff=cutoff),
    ]

    if lane_overrides:
        override_map = {row["lane"]: row for row in lanes}
        for lane_key, patch in lane_overrides.items():
            if lane_key in override_map:
                override_map[lane_key] = {**override_map[lane_key], **patch}
        lanes = list(override_map.values())

    finviz_discovery: dict[str, Any] | None = None
    try:
        from .discovery_projections import enrich_workspace_discovery_evidence

        finviz_discovery = enrich_workspace_discovery_evidence(instrument)
    except Exception:
        finviz_discovery = None

    mix_summary = compute_evidence_mix_summary(lanes)
    what_matters = sorted(
        [row for row in lanes if row.get("relevance") in {"HIGH", "MEDIUM"}],
        key=lambda row: (0 if row.get("relevance") == "HIGH" else 1, row.get("lane", "")),
    )
    if finviz_discovery is not None:
        what_matters.insert(
            0,
            {
                "instrument": instrument,
                **finviz_discovery,
            },
        )

    return {
        "instrument": instrument,
        "active_instrument": active,
        "active_instrument_source": active_source,
        "coherence_warning": coherence_warning,
        "as_of_context": as_of_context,
        "lanes": lanes,
        "what_matters_now": what_matters,
        "evidence_mix_summary": mix_summary,
        "research_context_execution_authority": RESEARCH_CONTEXT_EXECUTION_AUTHORITY,
        "data_provenance": {
            "mode": as_of_context.get("data_mode"),
            "provider": as_of_context.get("data_provider"),
            "replay_label": "MOOMOO CAPTURE" if is_replay_capture else None,
        },
        "finviz_discovery": finviz_discovery,
    }
