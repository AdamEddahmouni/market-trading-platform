"""Project donor squeeze screener rows into IMP explore DTOs."""

from __future__ import annotations

from typing import Any

from ..clock import monotonic_wall_ns
from . import internship_client
from .historical_cohort import build_historical_squeeze_context
from .institutional_ignition import (
    _OPTIONS_FROZEN_UNAVAILABLE,
    build_supplemental_ignition_evidence,
    merge_institutional_ignition_cards,
)
from .squeeze_client import (
    DEFAULT_BASE_URL,
    evaluate_causal_intelligence,
    fetch_current_candidate_detail,
    fetch_current_candidates,
    fetch_donor_deployment_mode,
    fetch_frozen_candidate_detail,
    fetch_frozen_candidates,
    fetch_manifest,
    is_available,
    post_cross_lane_snapshot,
)

ADMITTED_REPLAY_INSTRUMENT_ID = "BIYA"
FROZEN_DEMO_REFERENCE_SYMBOL = "AVTX"
_DONOR_UNAVAILABLE_REASON = (
    "Short squeeze FROZEN_DEMO server not reachable. "
    "Start: SQUEEZE_APP_MODE=FROZEN_DEMO python -m apps.research_screener --no-browser"
)
_SCANNER_UNAVAILABLE_REASON = (
    "Short squeeze donor server not reachable for live scanner bridge. "
    "Start the research screener with provider mode enabled."
)
_SCANNER_DISCLAIMER = (
    "Ephemeral provider scanner snapshot. Not the frozen research cohort "
    "(n=35 calibration cohort). Research-only. No trade recommendation."
)


def _outcome_label(row: dict[str, Any]) -> str:
    outcome = row.get("outcome", {})
    if isinstance(outcome, dict):
        status = str(outcome.get("status", "UNKNOWN"))
        reasons = outcome.get("reasons", [])
        if isinstance(reasons, list) and reasons:
            return f"{status}: {reasons[0]}"
        return status
    return "UNKNOWN"


def _research_detection_label(detail: dict[str, Any]) -> str:
    research = detail.get("research_detection", {})
    if isinstance(research, dict):
        return str(research.get("status", "UNKNOWN"))
    return "UNKNOWN"


def _resolve_ignition_state(detail: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    """D-01: ignition_state is causal lifecycle only — never research_detection / phase3a."""
    causal = detail.get("causal_intelligence")
    if isinstance(causal, dict) and causal.get("state"):
        return str(causal["state"]), ()
    flags: list[str] = []
    if isinstance(causal, dict):
        flags.append("CAUSAL_STATE_MISSING")
    else:
        flags.append("CAUSAL_INTELLIGENCE_UNAVAILABLE")
    return "UNKNOWN", tuple(flags)


def _ignition_state(detail: dict[str, Any]) -> str:
    state, _ = _resolve_ignition_state(detail)
    return state


def _phase3a_summary(detail: dict[str, Any]) -> str:
    phase3a = detail.get("phase3a", {})
    if isinstance(phase3a, dict) and phase3a.get("summary"):
        return str(phase3a["summary"])
    counts = phase3a.get("counts", {}) if isinstance(phase3a, dict) else {}
    if isinstance(counts, dict) and counts:
        return (
            f"{counts.get('PASS', 0)} PASS / {counts.get('FAIL', 0)} FAIL / "
            f"{counts.get('UNKNOWN', 0)} UNKNOWN"
        )
    return "coverage unknown"


def _project_rules(detail: dict[str, Any]) -> list[dict[str, Any]]:
    rules_raw = detail.get("rules", [])
    if not isinstance(rules_raw, list):
        return []
    projected: list[dict[str, Any]] = []
    for rule in rules_raw:
        if not isinstance(rule, dict):
            continue
        projected.append(
            {
                "rule_id": str(rule.get("rule_id", "")),
                "category": str(rule.get("category", "")),
                "outcome": str(rule.get("outcome", "UNKNOWN")),
                "reason": str(rule.get("reason", "")),
            }
        )
    return projected


def _outcome_counts(rules: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    for rule in rules:
        outcome = str(rule.get("outcome", "UNKNOWN"))
        if outcome not in counts:
            counts["UNKNOWN"] += 1
        else:
            counts[outcome] += 1
    return counts


def _format_rule_counts(counts: dict[str, int]) -> str:
    return f"{counts['PASS']} PASS / {counts['FAIL']} FAIL / {counts['UNKNOWN']} UNKNOWN"


def _build_readiness(detail: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any]:
    from ..donor_patterns.provenance_gates import (
        evaluate_freshness,
        provenance_gate,
        readiness_summary,
    )

    provenance = detail.get("provenance", {})
    provenance_row = {
        "symbol": str(detail.get("identity", {}).get("symbol", "") if isinstance(detail.get("identity"), dict) else ""),
        "data_mode": str(detail.get("identity", {}).get("mode_label", "FROZEN_RESEARCH") if isinstance(detail.get("identity"), dict) else "FROZEN_RESEARCH"),
        "source_kind": provenance.get("source_kind") if isinstance(provenance, dict) else None,
        "observed_at": provenance.get("observed_at") if isinstance(provenance, dict) else None,
    }
    admissible, reason_codes = provenance_gate(
        provenance_row,
        required_fields=("symbol",),
        frozen_mode=True,
    )
    freshness_state = evaluate_freshness(
        observed_at=provenance_row.get("observed_at"),
        max_age_seconds=86400 * 14,
        now_epoch=0,
        frozen_mode=True,
    )
    rule_rows = [
        {"outcome": {"status": rule.get("outcome", "UNKNOWN")}}
        for rule in rules
    ]
    return {
        "freshness_state": freshness_state.value,
        "provenance_admissible": admissible,
        "provenance_reason_codes": reason_codes,
        "rule_outcome_totals": readiness_summary(rule_rows),
    }


def _build_state_machine(detail: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any]:
    ignition_state = _ignition_state(detail)
    freshness = str(detail.get("freshness", "FROZEN"))
    causal = detail.get("causal_intelligence") if isinstance(detail.get("causal_intelligence"), dict) else {}
    transition_meta = causal.get("transition") if isinstance(causal.get("transition"), dict) else {}
    changed = [
        {
            "rule_id": rule["rule_id"],
            "category": rule["category"],
            "outcome": rule["outcome"],
            "reason": rule.get("reason", ""),
        }
        for rule in rules
        if str(rule.get("outcome", "")).upper() == "FAIL"
    ]
    unchanged = [
        {
            "rule_id": rule["rule_id"],
            "category": rule["category"],
            "outcome": rule["outcome"],
            "reason": rule.get("reason", ""),
        }
        for rule in rules
        if str(rule.get("outcome", "")).upper() == "PASS"
    ]
    unknown = [
        {
            "rule_id": rule["rule_id"],
            "category": rule["category"],
            "outcome": rule["outcome"],
            "reason": rule.get("reason", ""),
        }
        for rule in rules
        if str(rule.get("outcome", "")).upper() not in {"PASS", "FAIL"}
    ]
    state_transitions = _causal_state_transitions(detail)
    last_delta = str(transition_meta.get("trigger") or "frozen aggregate snapshot")
    if state_transitions:
        latest = state_transitions[0]
        if latest.get("changed_at"):
            last_delta = str(latest["changed_at"])
        elif latest.get("trigger"):
            last_delta = str(latest["trigger"])
    elif freshness.upper() == "FROZEN" and not transition_meta:
        last_delta = "frozen — no live transition stream"
    elif freshness and not transition_meta:
        last_delta = f"freshness {freshness}"
    from_state = transition_meta.get("from_state") or "INITIAL"
    trigger = transition_meta.get("trigger") or "FROZEN_DEMO aggregate load"
    return {
        "changed_criteria": changed,
        "failed_thresholds": changed,
        "current_state": ignition_state,
        "last_transition_label": last_delta,
        "transitions": [
            {
                "at_label": freshness,
                "from_state": from_state,
                "kind": "causal_snapshot" if causal else "frozen_snapshot",
                "to_state": ignition_state,
                "trigger": trigger,
            }
        ],
        "state_transitions": state_transitions,
        "transition_count": len(state_transitions),
        "latest_transition_at": (
            state_transitions[0].get("changed_at") if state_transitions else None
        ),
        "unchanged_criteria": unchanged,
        "unknown_criteria": unknown,
        "causal_model_version": causal.get("model_version"),
        "overall_confidence": causal.get("overall_confidence"),
        "mechanism_labels": causal.get("mechanism_labels"),
    }


def _causal_state_transitions(detail: dict[str, Any]) -> list[dict[str, Any]]:
    raw = detail.get("causal_state_transitions")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    causal = detail.get("causal_intelligence")
    if isinstance(causal, dict):
        transition = causal.get("transition")
        if isinstance(transition, dict) and transition.get("from_state"):
            return [
                {
                    **transition,
                    "kind": "causal_state",
                }
            ]
    return []


def _ignition_evidence_cards(
    detail: dict[str, Any],
    *,
    symbol: str,
    prediction_cutoff: int | None = None,
    as_of_context: dict[str, Any] | None = None,
    frozen_aggregate_only: bool = True,
) -> list[dict[str, Any]]:
    rules = _project_rules(detail)
    short_pressure = [rule for rule in rules if rule.get("category") == "SHORT_PRESSURE_CONFIRMATION"]
    borrow = [rule for rule in rules if "BORROW" in str(rule.get("rule_id", ""))]
    catalyst = [rule for rule in rules if rule.get("category") == "CATALYST_EVIDENCE"]

    def card(label: str, matched: list[dict[str, Any]], *, unavailable_reason: str | None = None) -> dict[str, Any]:
        if unavailable_reason:
            return {
                "label": label,
                "state": "UNAVAILABLE",
                "detail": unavailable_reason,
                "epistemic_class": "OBSERVED",
            }
        if not matched:
            return {
                "label": label,
                "state": "UNAVAILABLE",
                "detail": "No matching rules in frozen aggregate",
                "epistemic_class": "OBSERVED",
            }
        counts = _outcome_counts(matched)
        freshness = str(detail.get("freshness", "FROZEN"))
        return {
            "label": label,
            "state": freshness if freshness else "FROZEN",
            "detail": _format_rule_counts(counts),
            "epistemic_class": "OBSERVED",
        }

    cards = [
        card("SI / Float", [rule for rule in short_pressure if "BORROW" not in rule.get("rule_id", "")]),
        card("Borrow", borrow),
    ]
    if frozen_aggregate_only:
        cards.append(
            card(
                "Options",
                catalyst,
                unavailable_reason=_OPTIONS_FROZEN_UNAVAILABLE,
            )
        )
    else:
        cards.append(card("Options", catalyst))
    return merge_institutional_ignition_cards(
        cards,
        symbol=symbol,
        prediction_cutoff=prediction_cutoff,
        as_of_context=as_of_context,
        frozen_aggregate_only=frozen_aggregate_only and prediction_cutoff is None,
        donor_detail=detail,
    )


def _coverage_label(row: dict[str, Any]) -> str:
    coverage = row.get("evidence_coverage", {})
    if isinstance(coverage, dict) and coverage.get("label"):
        return str(coverage["label"])
    phase3a = row.get("phase3a", {})
    if isinstance(phase3a, dict) and phase3a.get("summary"):
        return str(phase3a["summary"])
    return "coverage unknown"


def _effective_prediction_cutoff(
    *,
    mode_normalized: str,
    prediction_cutoff: int | None,
    as_of_context: dict[str, Any] | None,
) -> int | None:
    if prediction_cutoff is not None:
        return prediction_cutoff
    ctx = as_of_context or {}
    as_of_ns = ctx.get("as_of_time_ns")
    if as_of_ns is not None:
        return int(as_of_ns)
    if mode_normalized == "current":
        return monotonic_wall_ns()
    return None


def _merge_cross_lane_causal(
    detail: dict[str, Any],
    *,
    symbol: str,
    base_url: str,
    mode_normalized: str,
    prediction_cutoff: int | None,
    as_of_context: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Fuse IMP whale lane evidence into donor causal intelligence when available."""
    effective_cutoff = _effective_prediction_cutoff(
        mode_normalized=mode_normalized,
        prediction_cutoff=prediction_cutoff,
        as_of_context=as_of_context,
    )
    if effective_cutoff is None:
        return detail, []

    from ..providers.projections import (
        build_workspace_catalyst_payload,
        build_workspace_distribution_payload,
        build_workspace_futures_payload,
        build_workspace_options_payload,
        build_workspace_order_book_payload,
        build_workspace_order_flow_payload,
    )
    from .participant_adapter import build_participant_cross_lane_bundle
    from .market_context_adapter import (
        build_cross_lane_snapshot_from_catalyst,
        build_ss_p2_structures_from_catalyst,
    )
    from .cross_lane_adapter import (
        build_cross_lane_evidence_from_risk_neutral,
        build_cross_lane_snapshot_from_distribution,
        build_cross_lane_snapshot_from_futures,
        build_cross_lane_snapshot_from_options,
        build_cross_lane_snapshot_from_order_book,
        build_cross_lane_snapshot_from_order_flow,
        build_cross_lane_snapshot_from_squeeze,
        merge_cross_lane_evidence,
        merge_cross_lane_snapshots,
    )
    from .horizon_model_bridge import build_horizon_model_snapshot
    from .lending_adapter import build_lending_cross_lane_fields, build_lending_cross_lane_snapshot
    from .transition_stream import (
        extract_fuel_history,
        extract_prior_cross_lane,
        replay_transition_stream,
    )
    from ..options.risk_neutral import infer_risk_neutral_distribution
    from ..options.surface import build_volatility_surface

    order_flow = build_workspace_order_flow_payload(
        symbol,
        as_of_context=as_of_context or {},
        prediction_cutoff=effective_cutoff,
    )
    options = build_workspace_options_payload(
        symbol,
        as_of_context=as_of_context or {},
        prediction_cutoff=effective_cutoff,
    )
    order_book = build_workspace_order_book_payload(
        symbol,
        as_of_context=as_of_context or {},
        prediction_cutoff=effective_cutoff,
    )
    futures = build_workspace_futures_payload(
        symbol,
        as_of_context=as_of_context or {},
        prediction_cutoff=effective_cutoff,
    )
    distribution = build_workspace_distribution_payload(
        symbol,
        as_of_context=as_of_context or {},
        prediction_cutoff=effective_cutoff,
    )
    catalyst = build_workspace_catalyst_payload(
        symbol,
        as_of_context=as_of_context or {},
        prediction_cutoff=effective_cutoff,
    )

    of_snapshot, of_evidence = build_cross_lane_snapshot_from_order_flow(order_flow)
    transitions = replay_transition_stream(as_of_time_ns=effective_cutoff)
    prior_cross_lane = extract_prior_cross_lane(transitions)
    fuel_history = extract_fuel_history(transitions)
    opt_snapshot, opt_evidence = build_cross_lane_snapshot_from_options(
        options,
        prior_cross_lane=prior_cross_lane or None,
    )
    ob_snapshot, ob_evidence = build_cross_lane_snapshot_from_order_book(order_book)
    fut_snapshot, fut_evidence = build_cross_lane_snapshot_from_futures(futures)
    dist_snapshot, dist_evidence = build_cross_lane_snapshot_from_distribution(distribution)
    mc_snapshot, mc_evidence = build_cross_lane_snapshot_from_catalyst(catalyst)
    ss_p2_fields = build_ss_p2_structures_from_catalyst(catalyst)
    risk_neutral = None
    if options.get("available") and isinstance(options.get("activities"), list):
        surface = build_volatility_surface(options.get("activities", []))
        risk_neutral = infer_risk_neutral_distribution(
            surface,
            symbol=symbol.upper(),
            as_of_time=str(options.get("activities", [{}])[0].get("event_time", ""))
            if options.get("activities")
            else "",
        )
    rn_evidence = build_cross_lane_evidence_from_risk_neutral(risk_neutral)
    participant_snapshot, participant_evidence = build_participant_cross_lane_bundle(
        instrument_id=symbol.upper(),
        prediction_cutoff=effective_cutoff,
    )
    snapshot = merge_cross_lane_snapshots(
        of_snapshot,
        opt_snapshot,
        ob_snapshot,
        fut_snapshot,
        dist_snapshot,
        mc_snapshot,
        build_lending_cross_lane_fields(),
        build_lending_cross_lane_snapshot(detail if isinstance(detail, dict) else None),
        participant_snapshot,
    )
    evidence = merge_cross_lane_evidence(
        of_evidence,
        opt_evidence,
        ob_evidence,
        fut_evidence,
        dist_evidence,
        mc_evidence,
        rn_evidence,
        participant_evidence,
    )

    from ..cross_lane.evidence import (
        EvidenceProvenanceClass,
        EvidenceSignal,
        LaneId,
        NormalizedLaneEvidence,
        validate_evidence_dag,
    )

    parsed_evidence = [
        NormalizedLaneEvidence(
            lane=LaneId(str(item.get("lane", LaneId.ORDER_FLOW.value))),
            signal=EvidenceSignal(str(item.get("signal", EvidenceSignal.CVD_POSITIVE_SLOPE.value))),
            strength=str(item.get("strength", "LOW")),
            available=bool(item.get("available", False)),
            source_ref=str(item.get("source_ref", "")),
            detail=str(item.get("detail", "")),
            provenance_class=EvidenceProvenanceClass(
                str(item.get("provenance_class", EvidenceProvenanceClass.DERIVED.value))
            ),
        )
        for item in evidence
        if isinstance(item, dict)
    ]
    dag_violations = validate_evidence_dag(parsed_evidence)
    if dag_violations:
        snapshot["evidence_dag_violations"] = dag_violations

    if not any(
        [
            snapshot.get("order_flow_available"),
            snapshot.get("options_available"),
            snapshot.get("order_book_available"),
            snapshot.get("futures_available"),
            snapshot.get("distribution_available"),
            snapshot.get("catalyst_available"),
            snapshot.get("attention_available"),
            snapshot.get("lending_available"),
        ]
    ):
        merged_detail = dict(detail)
        merged_detail["_ss_p2_fields"] = ss_p2_fields
        return merged_detail, evidence

    merged_detail = dict(detail)
    try:
        if mode_normalized == "current":
            post_cross_lane_snapshot(symbol, snapshot, base_url=base_url)
            merged_detail = fetch_current_candidate_detail(symbol, base_url=base_url)
        else:
            eval_row = {
                **merged_detail,
                "rules": merged_detail.get("rules") or [],
                "pressure": merged_detail.get("pressure"),
                "ignition": merged_detail.get("ignition"),
                "adam_classification": merged_detail.get("adam_classification"),
                "freshness": merged_detail.get("freshness", "FROZEN"),
            }
            horizon_model = build_horizon_model_snapshot(
                symbol=symbol,
                row=eval_row,
                prediction_cutoff=effective_cutoff,
            )
            causal = evaluate_causal_intelligence(
                row=eval_row,
                cross_lane=snapshot,
                fuel_history=fuel_history or None,
                horizon_model=horizon_model,
                base_url=base_url,
            )
            merged_detail["causal_intelligence"] = causal
            if isinstance(merged_detail.get("research_detection"), dict):
                merged_detail["research_detection"] = {
                    **merged_detail["research_detection"],
                    "ignition_state": causal.get("state"),
                }
    except (ConnectionError, ValueError):
        return detail, evidence

    sq_snapshot, sq_evidence = build_cross_lane_snapshot_from_squeeze(merged_detail)
    evidence = merge_cross_lane_evidence(evidence, sq_evidence)
    if sq_snapshot:
        snapshot = merge_cross_lane_snapshots(snapshot, sq_snapshot)

    merged_detail["_ss_p2_fields"] = ss_p2_fields
    return merged_detail, evidence


def build_explore_squeeze_payload(
    *,
    base_url: str = DEFAULT_BASE_URL,
    as_of_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    available = is_available(base_url=base_url)
    if not available:
        return {
            "source": "short-squeeze-project",
            "bridge_mode": "READ_ONLY",
            "donor_base_url": base_url,
            "available": False,
            "reason": _DONOR_UNAVAILABLE_REASON,
            "as_of_context": as_of_context,
            "manifest": None,
            "rows": [],
            "row_count": 0,
            "outcome_summary": [],
            "data_mode": "frozen",
        }

    manifest = fetch_manifest(base_url=base_url)
    frozen = fetch_frozen_candidates(base_url=base_url)
    rows_raw = frozen.get("rows", [])
    if not isinstance(rows_raw, list):
        rows_raw = []

    projected_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows_raw):
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol", ""))
        projected_rows.append(
            {
                "screener_id": f"squeeze:frozen:{symbol or index}",
                "symbol": symbol,
                "headline": f"{symbol} — frozen research aggregate",
                "outcome_status": _outcome_label(row),
                "evidence_coverage": _coverage_label(row),
                "freshness": str(row.get("freshness", "FROZEN")),
                "research_detection": (
                    row.get("research_detection", {}).get("status", "UNKNOWN")
                    if isinstance(row.get("research_detection"), dict)
                    else "UNKNOWN"
                ),
                "mode_label": str(row.get("mode_label", "FROZEN_RESEARCH")),
                "explanation_ref": f"explain:squeeze:{symbol}",
                "capability_state": "AVAILABLE",
                "epistemic_class": "OBSERVED",
            }
        )

    return {
        "source": "short-squeeze-project",
        "bridge_mode": "READ_ONLY",
        "donor_base_url": base_url,
        "available": True,
        "as_of_context": as_of_context,
        "manifest": {
            "api_version": manifest.get("api_version"),
            "schema_version": manifest.get("schema_version"),
            "prohibited_capabilities": manifest.get("prohibited_capabilities"),
        },
        "header": frozen.get("header"),
        "row_count": len(projected_rows),
        "rows": projected_rows,
        "outcome_summary": _outcome_summary(projected_rows),
        "disclaimer": "Donor screener rows are read-only research aggregates. No trade recommendation.",
        "data_mode": "frozen",
    }


def _scanner_rank(row: dict[str, Any], fallback_index: int) -> int | None:
    for key in ("provider_scanner_order", "scanner_order", "discovery_rank"):
        value = row.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    fields = row.get("fields")
    if isinstance(fields, dict):
        nested = fields.get("provider_scanner_order")
        if isinstance(nested, dict) and nested.get("value") is not None:
            try:
                return int(nested["value"])
            except (TypeError, ValueError):
                pass
    return fallback_index + 1


def _project_scanner_explore_row(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    symbol = str(row.get("symbol", ""))
    rank = _scanner_rank(row, index)
    return {
        "screener_id": f"squeeze:scanner:{symbol or index}",
        "symbol": symbol,
        "headline": f"{symbol} — current scanner candidate",
        "outcome_status": "EPHEMERAL — no forward outcome label",
        "evidence_coverage": _coverage_label(row),
        "freshness": str(row.get("freshness", "CURRENT")),
        "research_detection": (
            row.get("research_detection", {}).get("status", "UNKNOWN")
            if isinstance(row.get("research_detection"), dict)
            else "UNKNOWN"
        ),
        "mode_label": str(row.get("mode_label", "CURRENT")),
        "scanner_rank": rank,
        "explanation_ref": f"explain:squeeze:scanner:{symbol}",
        "capability_state": "AVAILABLE",
        "epistemic_class": "OBSERVED",
    }


def _detection_summary(rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get("research_detection", "UNKNOWN"))
        counts[label] = counts.get(label, 0) + 1
    return [{"label": label, "count": count} for label, count in sorted(counts.items())]


def build_explore_squeeze_scanner_payload(
    *,
    base_url: str = DEFAULT_BASE_URL,
    as_of_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    unavailable = {
        "source": "short-squeeze-project",
        "bridge_mode": "READ_ONLY",
        "donor_base_url": base_url,
        "available": False,
        "reason": _SCANNER_UNAVAILABLE_REASON,
        "as_of_context": as_of_context,
        "manifest": None,
        "rows": [],
        "row_count": 0,
        "detection_summary": [],
        "data_mode": "current",
        "donor_deployment_mode": None,
        "empty_reason": None,
    }
    if not is_available(base_url=base_url):
        return {**unavailable, "disclaimer": _SCANNER_DISCLAIMER}

    deployment_mode = fetch_donor_deployment_mode(base_url=base_url)
    manifest = fetch_manifest(base_url=base_url)
    current = fetch_current_candidates(base_url=base_url)
    rows_raw = current.get("rows", [])
    if not isinstance(rows_raw, list):
        rows_raw = []

    projected_rows = [
        _project_scanner_explore_row(row, index=index)
        for index, row in enumerate(rows_raw)
        if isinstance(row, dict)
    ]

    return {
        "source": "short-squeeze-project",
        "bridge_mode": "READ_ONLY",
        "donor_base_url": base_url,
        "available": True,
        "as_of_context": as_of_context,
        "manifest": {
            "api_version": manifest.get("api_version"),
            "schema_version": manifest.get("schema_version"),
            "prohibited_capabilities": manifest.get("prohibited_capabilities"),
        },
        "header": current.get("header"),
        "row_count": len(projected_rows),
        "rows": projected_rows,
        "detection_summary": _detection_summary(projected_rows),
        "data_mode": "current",
        "donor_deployment_mode": deployment_mode,
        "empty_reason": current.get("reason") if not projected_rows else None,
        "disclaimer": _SCANNER_DISCLAIMER,
    }


def _outcome_summary(rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get("outcome_status", "UNKNOWN"))
        counts[label] = counts.get(label, 0) + 1
    return [{"label": label, "count": count} for label, count in sorted(counts.items())]


def build_workspace_squeeze_payload(
    symbol: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    as_of_context: dict[str, Any] | None = None,
    prediction_cutoff: int | None = None,
    data_mode: str = "frozen",
    replay_instrument_id: str = ADMITTED_REPLAY_INSTRUMENT_ID,
) -> dict[str, Any]:
    symbol_upper = symbol.strip().upper()
    if not symbol_upper:
        raise ValueError("symbol is required")

    mode_normalized = "current" if data_mode == "current" else "frozen"
    replay_chart_available = symbol_upper == replay_instrument_id.upper()
    historical_context = build_historical_squeeze_context(symbol_upper)
    base_payload: dict[str, Any] = {
        "symbol": symbol_upper,
        "source": "short-squeeze-project",
        "bridge_mode": "READ_ONLY",
        "donor_base_url": base_url,
        "data_mode": mode_normalized,
        "donor_deployment_mode": None,
        "replay_chart_available": replay_chart_available,
        "as_of_context": as_of_context,
        "epistemic_class": "OBSERVED",
        "explanation_ref": (
            f"explain:squeeze:scanner:{symbol_upper}"
            if mode_normalized == "current"
            else f"explain:squeeze:{symbol_upper}"
        ),
        "disclaimer": (
            _SCANNER_DISCLAIMER
            if mode_normalized == "current"
            else "Donor squeeze evidence is read-only research. No trade recommendation."
        ),
        "rules": [],
        "ignition_evidence": [],
        "historical_context": historical_context,
    }

    supplemental_ignition = build_supplemental_ignition_evidence(
        symbol_upper,
        prediction_cutoff=prediction_cutoff,
        as_of_context=as_of_context,
    )
    unavailable_detail_fields = {
        "outcome_status": None,
        "evidence_coverage": None,
        "research_detection": None,
        "ignition_state": None,
        "freshness": None,
        "phase3a_summary": None,
        "mode_label": None,
        "provenance": None,
        "rules": [],
        "ignition_evidence": supplemental_ignition,
    }

    donor_down_reason = (
        _SCANNER_UNAVAILABLE_REASON if mode_normalized == "current" else _DONOR_UNAVAILABLE_REASON
    )

    if not is_available(base_url=base_url):
        return {
            **base_payload,
            "available": False,
            "reason": donor_down_reason,
            **unavailable_detail_fields,
        }

    base_payload["donor_deployment_mode"] = fetch_donor_deployment_mode(base_url=base_url)

    try:
        if mode_normalized == "current":
            detail = fetch_current_candidate_detail(symbol_upper, base_url=base_url)
        else:
            detail = fetch_frozen_candidate_detail(symbol_upper, base_url=base_url)
    except (ConnectionError, ValueError):
        return {
            **base_payload,
            "available": False,
            "reason": donor_down_reason,
            **unavailable_detail_fields,
        }

    if detail.get("error"):
        return {
            **base_payload,
            "available": False,
            "reason": str(detail.get("error")),
            **unavailable_detail_fields,
        }

    if mode_normalized == "frozen" and (detail.get("available") is False):
        return {
            **base_payload,
            "available": False,
            "reason": str(detail.get("error", f"{symbol_upper} is not in frozen research cases.")),
            **unavailable_detail_fields,
        }

    detail, cross_lane_evidence = _merge_cross_lane_causal(
        detail,
        symbol=symbol_upper,
        base_url=base_url,
        mode_normalized=mode_normalized,
        prediction_cutoff=prediction_cutoff,
        as_of_context=as_of_context,
    )

    identity = detail.get("identity", {})
    mode_label = identity.get("mode_label") if isinstance(identity, dict) else None
    coverage = detail.get("evidence_coverage", {})
    coverage_label = _coverage_label(detail) if not isinstance(coverage, dict) else str(
        coverage.get("label", _coverage_label(detail))
    )
    provenance = detail.get("provenance", {})
    rules = _project_rules(detail)
    readiness = _build_readiness(detail, rules)
    state_machine = _build_state_machine(detail, rules)
    default_freshness = "CURRENT" if mode_normalized == "current" else "FROZEN"
    default_mode_label = "CURRENT" if mode_normalized == "current" else "FROZEN_RESEARCH"
    outcome_status = (
        "EPHEMERAL — no forward outcome label"
        if mode_normalized == "current"
        else _outcome_label(detail)
    )
    opportunity_payload: dict[str, Any] = {}
    if as_of_context is not None and prediction_cutoff is not None:
        from ..providers.projections import build_workspace_opportunity_payload

        opportunity_payload = build_workspace_opportunity_payload(
            symbol_upper,
            as_of_context=as_of_context,
            prediction_cutoff=prediction_cutoff,
            squeeze_causal=detail.get("causal_intelligence")
            if isinstance(detail.get("causal_intelligence"), dict)
            else None,
        )
    return {
        **base_payload,
        "available": True,
        "outcome_status": outcome_status,
        "evidence_coverage": coverage_label,
        "research_detection": _research_detection_label(detail),
        "ignition_state": _ignition_state(detail),
        "ignition_state_quality_flags": list(_resolve_ignition_state(detail)[1]),
        "freshness": str(detail.get("freshness", default_freshness)),
        "phase3a_summary": _phase3a_summary(detail),
        "mode_label": str(mode_label or default_mode_label),
        "provenance": provenance if isinstance(provenance, dict) else None,
        "readiness": readiness,
        "rules": rules,
        "state_machine": state_machine,
        "causal_intelligence": detail.get("causal_intelligence")
        if isinstance(detail.get("causal_intelligence"), dict)
        else None,
        "cross_lane_evidence": cross_lane_evidence,
        "opportunity_snapshot": opportunity_payload.get("opportunity_snapshot"),
        "catalyst_strength": (
            (detail.get("_ss_p2_fields") or {}).get("catalyst_strength")
            if isinstance(detail.get("_ss_p2_fields"), dict)
            else None
        ),
        "attention_feature": (
            (detail.get("_ss_p2_fields") or {}).get("attention_feature")
            if isinstance(detail.get("_ss_p2_fields"), dict)
            else None
        ),
        "thesis_invalidation": (
            (detail.get("_ss_p2_fields") or {}).get("thesis_invalidation")
            if isinstance(detail.get("_ss_p2_fields"), dict)
            else None
        ),
        "information_value": (
            (detail.get("_ss_p2_fields") or {}).get("information_value")
            if isinstance(detail.get("_ss_p2_fields"), dict)
            else None
        ),
        "reflexive_impact": (
            (detail.get("_ss_p2_fields") or {}).get("reflexive_impact")
            if isinstance(detail.get("_ss_p2_fields"), dict)
            else None
        ),
        "author_influence_score": (
            (detail.get("_ss_p2_fields") or {}).get("author_influence_score")
            if isinstance(detail.get("_ss_p2_fields"), dict)
            else None
        ),
        "author_accuracy_score": (
            (detail.get("_ss_p2_fields") or {}).get("author_accuracy_score")
            if isinstance(detail.get("_ss_p2_fields"), dict)
            else None
        ),
        "author_handle": (
            (detail.get("_ss_p2_fields") or {}).get("author_handle")
            if isinstance(detail.get("_ss_p2_fields"), dict)
            else None
        ),
        "author_intelligence_available": (
            (detail.get("_ss_p2_fields") or {}).get("author_intelligence_available")
            if isinstance(detail.get("_ss_p2_fields"), dict)
            else False
        ),
        "securities_lending_snapshot": detail.get("securities_lending_snapshot")
        if isinstance(detail.get("securities_lending_snapshot"), dict)
        else None,
        "ignition_evidence": _ignition_evidence_cards(
            detail,
            symbol=symbol_upper,
            prediction_cutoff=prediction_cutoff,
            as_of_context=as_of_context,
            frozen_aggregate_only=mode_normalized == "frozen",
        ),
        "capability_state": "AVAILABLE",
    }


def build_squeeze_attention_items(
    *,
    base_url: str = DEFAULT_BASE_URL,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Project donor screener rows into NOW attention items (read-only, no rank score)."""
    payload = build_explore_squeeze_payload(base_url=base_url)
    if not payload.get("available"):
        return []
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return []
    items: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:limit]):
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol", ""))
        if not symbol:
            continue
        items.append(
            {
                "attention_id": f"att-squeeze-{symbol.lower()}",
                "explanation_ref": f"explain:squeeze:{symbol}",
                "headline": f"{symbol} — squeeze research aggregate",
                "instrument_id": symbol,
                "priority_rank": 10 + index,
                "reasons": [
                    {"code": "SQUEEZE_BRIDGE", "label": "Donor screener FROZEN_DEMO (read-only)"},
                    {
                        "code": str(row.get("research_detection", "UNKNOWN")),
                        "label": str(row.get("outcome_status", "Research outcome")),
                    },
                ],
                "tier": 2,
            }
        )
    return items


def build_squeeze_scanner_attention_items(
    *,
    base_url: str = DEFAULT_BASE_URL,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Project ephemeral scanner rows into NOW attention items (read-only)."""
    payload = build_explore_squeeze_scanner_payload(base_url=base_url)
    if not payload.get("available"):
        return []
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return []
    items: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:limit]):
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol", ""))
        if not symbol:
            continue
        rank = row.get("scanner_rank")
        rank_label = f"scanner rank {rank}" if rank is not None else "current scanner"
        items.append(
            {
                "attention_id": f"att-squeeze-scanner-{symbol.lower()}",
                "explanation_ref": f"explain:squeeze:scanner:{symbol}",
                "headline": str(row.get("headline", f"{symbol} — current scanner candidate")),
                "instrument_id": symbol,
                "priority_rank": 15 + index,
                "reasons": [
                    {"code": "SQUEEZE_SCANNER", "label": "Ephemeral provider scanner (read-only)"},
                    {
                        "code": str(row.get("research_detection", "UNKNOWN")),
                        "label": rank_label,
                    },
                ],
                "tier": 2,
            }
        )
    return items


_CATALYST_UNAVAILABLE_REASON = (
    "Internship demo state not found. "
    "Run: python scripts/seed_demo_state.py in news_momentum_agent/"
)


def _catalyst_decision_label(row: dict[str, Any]) -> str:
    decision = str(row.get("decision", "UNKNOWN")).upper()
    lean = str(row.get("lean", "")).upper()
    if lean and lean != decision:
        return f"{decision} (lean {lean})"
    return decision


def _catalyst_confidence_pct(row: dict[str, Any]) -> float | None:
    meta = row.get("decision_meta") or row.get("in_depth_rationale") or {}
    if isinstance(meta, dict) and meta.get("confidence_pct") is not None:
        try:
            return float(meta["confidence_pct"])
        except (TypeError, ValueError):
            pass
    lean_pct = row.get("lean_pct")
    if lean_pct is not None:
        try:
            return float(lean_pct)
        except (TypeError, ValueError):
            return None
    return None


def _project_catalyst_row(row: dict[str, Any], *, source: str) -> dict[str, Any]:
    symbol = str(row.get("ticker", "")).upper()
    headline = str(
        row.get("news_headline")
        or row.get("reasoning")
        or row.get("headline")
        or f"{symbol} catalyst signal"
    )
    confidence_pct = _catalyst_confidence_pct(row)
    return {
        "catalyst_id": f"catalyst:{source}:{symbol}:{row.get('timestamp', '')}",
        "symbol": symbol,
        "headline": headline,
        "decision": _catalyst_decision_label(row),
        "confidence_pct": confidence_pct,
        "options_score": row.get("options_score"),
        "options_bias": row.get("options_bias"),
        "instrument_hint": row.get("instrument_hint") or row.get("instrument"),
        "signal_source": row.get("signal_source"),
        "timestamp": row.get("timestamp"),
        "executed": bool(row.get("executed")),
        "explanation_ref": f"explain:catalyst:{symbol}",
        "epistemic_class": "INFERRED",
        "research_only": True,
    }


def build_explore_catalyst_payload(
    *,
    state_dir: Any | None = None,
    as_of_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = state_dir or internship_client.default_state_dir()
    available = internship_client.is_available(state_dir=root)
    if not available:
        return {
            "source": "internship-project-main",
            "bridge_mode": "READ_ONLY",
            "state_dir": str(root),
            "available": False,
            "reason": _CATALYST_UNAVAILABLE_REASON,
            "as_of_context": as_of_context,
            "rows": [],
            "row_count": 0,
            "decision_summary": [],
        }

    trade_log = internship_client.load_trade_log(state_dir=root)
    watchlist = internship_client.load_watchlist(state_dir=root)
    health = internship_client.load_health(state_dir=root) or {}

    seen: set[str] = set()
    projected_rows: list[dict[str, Any]] = []
    for row in trade_log:
        symbol = str(row.get("ticker", "")).upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        projected_rows.append(_project_catalyst_row(row, source="trade_log"))

    for row in watchlist:
        symbol = str(row.get("ticker", "")).upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        projected_rows.append(
            {
                "catalyst_id": f"catalyst:watchlist:{symbol}",
                "symbol": symbol,
                "headline": f"{symbol} on watchlist ({row.get('source', 'discovery')})",
                "decision": "WATCH",
                "confidence_pct": None,
                "options_score": None,
                "options_bias": None,
                "instrument_hint": None,
                "signal_source": row.get("source"),
                "timestamp": row.get("added_at"),
                "executed": False,
                "explanation_ref": f"explain:catalyst:{symbol}",
                "epistemic_class": "INFERRED",
                "research_only": True,
            }
        )

    decision_counts: dict[str, int] = {}
    for row in projected_rows:
        label = str(row.get("decision", "UNKNOWN"))
        decision_counts[label] = decision_counts.get(label, 0) + 1

    return {
        "source": "internship-project-main",
        "bridge_mode": "READ_ONLY",
        "state_dir": str(root),
        "available": True,
        "as_of_context": as_of_context,
        "demo_mode": bool(health.get("demo_mode")),
        "health": {
            "watchlist_count": health.get("watchlist_count"),
            "high_alert_count": health.get("high_alert_count"),
            "updated_at": health.get("updated_at"),
        },
        "row_count": len(projected_rows),
        "rows": projected_rows,
        "decision_summary": [
            {"label": label, "count": count} for label, count in sorted(decision_counts.items())
        ],
        "disclaimer": "Donor catalyst rows are demo paper-research state. No trade recommendation.",
    }


def _latest_trade_for_symbol(trade_log: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    matches = [
        row
        for row in trade_log
        if str(row.get("ticker", "")).upper() == symbol.upper()
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda row: str(row.get("timestamp", "")), reverse=True)[0]


def _watchlist_entry_for_symbol(watchlist: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    for row in watchlist:
        if str(row.get("ticker", "")).upper() == symbol.upper():
            return row
    return None


def build_workspace_catalyst_payload(
    symbol: str,
    *,
    state_dir: Any | None = None,
    as_of_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    symbol_upper = symbol.strip().upper()
    if not symbol_upper:
        raise ValueError("symbol is required")

    root = state_dir or internship_client.default_state_dir()
    base_payload: dict[str, Any] = {
        "symbol": symbol_upper,
        "source": "internship-project-main",
        "bridge_mode": "READ_ONLY",
        "state_dir": str(root),
        "as_of_context": as_of_context,
        "explanation_ref": f"explain:catalyst:{symbol_upper}",
        "disclaimer": "Donor catalyst evidence is demo paper-research state. No trade recommendation.",
        "epistemic_class": "INFERRED",
    }

    if not internship_client.is_available(state_dir=root):
        return {
            **base_payload,
            "available": False,
            "reason": _CATALYST_UNAVAILABLE_REASON,
            "trade_signal": None,
            "watchlist_entry": None,
            "evidence_cards": [],
        }

    trade_log = internship_client.load_trade_log(state_dir=root)
    watchlist = internship_client.load_watchlist(state_dir=root)
    latest = _latest_trade_for_symbol(trade_log, symbol_upper)
    watch_entry = _watchlist_entry_for_symbol(watchlist, symbol_upper)

    if latest is None and watch_entry is None:
        return {
            **base_payload,
            "available": False,
            "reason": f"{symbol_upper} is not in demo trade log or watchlist.",
            "trade_signal": None,
            "watchlist_entry": None,
            "evidence_cards": [],
        }

    from ..donor_patterns.catalyst_lane import gate_catalyst, lean_direction, project_catalyst_evidence

    evidence_cards: list[dict[str, Any]] = []
    if latest:
        score = float(latest.get("score", 0.0) or 0.0)
        lean = lean_direction(signed_score=score)
        liquidity_ok = not bool(
            (latest.get("decision_meta") or {}).get("equity_fallback_liquidity")
            if isinstance(latest.get("decision_meta"), dict)
            else False
        )
        confidence = abs(score)
        gate_ok, gate_reasons = gate_catalyst(
            confidence=confidence,
            min_confidence=0.5,
            lean=lean,
            liquidity_ok=liquidity_ok,
        )
        evidence_cards.append(
            project_catalyst_evidence(
                symbol=symbol_upper,
                headline=str(latest.get("news_headline") or latest.get("reasoning") or ""),
                confidence=confidence,
                lean=lean,
                source="internship trade_log",
            )
        )
        evidence_cards.append(
            {
                "label": "Options confirmation",
                "state": "PASS" if latest.get("options_score") else "UNAVAILABLE",
                "detail": (
                    f"score={latest.get('options_score')} bias={latest.get('options_bias')}"
                    if latest.get("options_score") is not None
                    else "No options score on latest signal"
                ),
                "epistemic_class": "INFERRED",
            }
        )
        evidence_cards.append(
            {
                "label": "Catalyst gate",
                "state": "PASS" if gate_ok else "FAIL",
                "detail": ", ".join(gate_reasons) if gate_reasons else "gates satisfied",
                "epistemic_class": "DERIVED",
            }
        )

    return {
        **base_payload,
        "available": True,
        "trade_signal": latest,
        "watchlist_entry": watch_entry,
        "evidence_cards": evidence_cards,
        "capability_state": "AVAILABLE",
    }


def build_catalyst_attention_items(
    *,
    state_dir: Any | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    from ..normalization.equity_bars import iso_to_epoch_ns
    from ..providers.projections import (
        build_workspace_market_context_payload,
        market_context_available,
    )

    if market_context_available(instrument_id="BOXL", prediction_cutoff=iso_to_epoch_ns("2099-01-01T00:00:00.000000000Z")):
        mc_payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_mode": "fixture"},
            prediction_cutoff=iso_to_epoch_ns("2026-07-23T00:00:00.000000000Z"),
        )
        summaries = mc_payload.get("attention_summaries") or []
        if isinstance(summaries, list) and summaries:
            items: list[dict[str, Any]] = []
            ranked = sorted(
                [row for row in summaries if isinstance(row, dict)],
                key=lambda row: (
                    -(row.get("attention_acceleration") or 0.0),
                    -(row.get("diffusion_score") or 0.0),
                ),
            )
            for index, row in enumerate(ranked[:limit]):
                symbol = str(row.get("entity_id", "BOXL"))
                accel = row.get("attention_acceleration")
                info_value = row.get("information_value")
                reflexive = row.get("reflexive_impact")
                tier = 1 if accel is not None and accel >= 0.05 else 2
                item: dict[str, Any] = {
                    "attention_id": f"att-mc9-{row.get('event_id', index)}",
                    "explanation_ref": f"explain:attention:{symbol}:{row.get('event_id', index)}",
                    "headline": str(row.get("headline", f"{symbol} attention diffusion")),
                    "instrument_id": symbol,
                    "priority_rank": 10 + index,
                    "reasons": [
                        {"code": "MC9_ATTENTION", "label": "MC9 attention diffusion (fixture)"},
                        {
                            "code": "INFORMATION_VALUE",
                            "label": f"information value {info_value:.2f}" if info_value is not None else "information value UNAVAILABLE",
                        },
                        {
                            "code": "REFLEXIVE_IMPACT",
                            "label": f"reflexive impact {reflexive:.2f}" if reflexive is not None else "reflexive impact UNAVAILABLE",
                        },
                    ],
                    "tier": tier,
                }
                available_time = row.get("available_time")
                if available_time:
                    try:
                        item["surfaced_time"] = iso_to_epoch_ns(str(available_time))
                    except (TypeError, ValueError):
                        pass
                items.append(item)
            return items

    payload = build_explore_catalyst_payload(state_dir=state_dir)
    if not payload.get("available"):
        return []
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        return []
    items: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:limit]):
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol", ""))
        if not symbol:
            continue
        items.append(
            {
                "attention_id": f"att-catalyst-{symbol.lower()}",
                "explanation_ref": f"explain:catalyst:{symbol}",
                "headline": str(row.get("headline", f"{symbol} catalyst signal")),
                "instrument_id": symbol,
                "priority_rank": 20 + index,
                "reasons": [
                    {"code": "CATALYST_BRIDGE", "label": "Internship demo state (read-only)"},
                    {"code": str(row.get("decision", "UNKNOWN")), "label": "Donor paper decision"},
                ],
                "tier": 2,
            }
        )
    return items
