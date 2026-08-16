"""Project donor squeeze screener rows into IMP explore DTOs."""

from __future__ import annotations

from typing import Any

from . import internship_client
from .squeeze_client import (
    DEFAULT_BASE_URL,
    fetch_frozen_candidate_detail,
    fetch_frozen_candidates,
    fetch_manifest,
    is_available,
)

ADMITTED_REPLAY_INSTRUMENT_ID = "BIYA"
FROZEN_DEMO_REFERENCE_SYMBOL = "AVTX"
_DONOR_UNAVAILABLE_REASON = (
    "Short squeeze FROZEN_DEMO server not reachable. "
    "Start: SQUEEZE_APP_MODE=FROZEN_DEMO python -m apps.research_screener --no-browser"
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


def _ignition_state(detail: dict[str, Any]) -> str:
    research = detail.get("research_detection", {})
    if isinstance(research, dict):
        for key in ("ignition_state", "state", "status"):
            value = research.get(key)
            if value:
                return str(value)
    phase3a = detail.get("phase3a", {})
    if isinstance(phase3a, dict) and phase3a.get("status"):
        return str(phase3a["status"])
    return "UNKNOWN"


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
    last_delta = "frozen aggregate snapshot"
    if freshness.upper() == "FROZEN":
        last_delta = "frozen — no live transition stream"
    elif freshness:
        last_delta = f"freshness {freshness}"
    return {
        "changed_criteria": changed,
        "current_state": ignition_state,
        "last_transition_label": last_delta,
        "transitions": [
            {
                "at_label": freshness,
                "from_state": "INITIAL",
                "kind": "frozen_snapshot",
                "to_state": ignition_state,
                "trigger": "FROZEN_DEMO aggregate load",
            }
        ],
        "unchanged_criteria": unchanged,
        "unknown_criteria": unknown,
    }


def _ignition_evidence_cards(detail: dict[str, Any]) -> list[dict[str, Any]]:
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

    return [
        card("SI / Float", [rule for rule in short_pressure if "BORROW" not in rule.get("rule_id", "")]),
        card("Borrow", borrow),
        card(
            "Options",
            catalyst,
            unavailable_reason="Options flow not included in sanitized frozen aggregate",
        ),
    ]


def _coverage_label(row: dict[str, Any]) -> str:
    coverage = row.get("evidence_coverage", {})
    if isinstance(coverage, dict) and coverage.get("label"):
        return str(coverage["label"])
    phase3a = row.get("phase3a", {})
    if isinstance(phase3a, dict) and phase3a.get("summary"):
        return str(phase3a["summary"])
    return "coverage unknown"


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
    replay_instrument_id: str = ADMITTED_REPLAY_INSTRUMENT_ID,
) -> dict[str, Any]:
    symbol_upper = symbol.strip().upper()
    if not symbol_upper:
        raise ValueError("symbol is required")

    replay_chart_available = symbol_upper == replay_instrument_id.upper()
    base_payload: dict[str, Any] = {
        "symbol": symbol_upper,
        "source": "short-squeeze-project",
        "bridge_mode": "READ_ONLY",
        "donor_base_url": base_url,
        "replay_chart_available": replay_chart_available,
        "as_of_context": as_of_context,
        "epistemic_class": "OBSERVED",
        "explanation_ref": f"explain:squeeze:{symbol_upper}",
        "disclaimer": "Donor squeeze evidence is read-only research. No trade recommendation.",
        "rules": [],
        "ignition_evidence": [],
    }

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
        "ignition_evidence": [],
    }

    if not is_available(base_url=base_url):
        return {
            **base_payload,
            "available": False,
            "reason": _DONOR_UNAVAILABLE_REASON,
            **unavailable_detail_fields,
        }

    try:
        detail = fetch_frozen_candidate_detail(symbol_upper, base_url=base_url)
    except (ConnectionError, ValueError):
        return {
            **base_payload,
            "available": False,
            "reason": _DONOR_UNAVAILABLE_REASON,
            **unavailable_detail_fields,
        }

    if detail.get("available") is False or detail.get("error"):
        return {
            **base_payload,
            "available": False,
            "reason": str(detail.get("error", f"{symbol_upper} is not in frozen research cases.")),
            **unavailable_detail_fields,
        }

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
    return {
        **base_payload,
        "available": True,
        "outcome_status": _outcome_label(detail),
        "evidence_coverage": coverage_label,
        "research_detection": _research_detection_label(detail),
        "ignition_state": _ignition_state(detail),
        "freshness": str(detail.get("freshness", "FROZEN")),
        "phase3a_summary": _phase3a_summary(detail),
        "mode_label": str(mode_label or "FROZEN_RESEARCH"),
        "provenance": provenance if isinstance(provenance, dict) else None,
        "readiness": readiness,
        "rules": rules,
        "state_machine": state_machine,
        "ignition_evidence": _ignition_evidence_cards(detail),
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
