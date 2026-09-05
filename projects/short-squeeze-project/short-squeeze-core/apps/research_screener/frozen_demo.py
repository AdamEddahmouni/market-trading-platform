from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DEMO_PATH = Path(__file__).resolve().parent / "demo_data" / "frozen_research_v1.json"
SHORT_PRESSURE_RULES = {
    "BORROW_AVAILABILITY_CHANGE_MAXIMUM", "BORROW_AVAILABILITY_MAXIMUM",
    "BORROW_FEE_CHANGE_MINIMUM", "BORROW_FEE_MINIMUM", "DAYS_TO_COVER_MINIMUM",
    "PUBLISHED_SHORT_INTEREST_AVAILABLE", "SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM",
}
CATALYST_RULES = {
    "CORPORATE_ACTION_CONTEXT_AVAILABLE", "NEWS_AVAILABLE",
    "NEWS_AVAILABLE_BEFORE_AS_OF", "NEWS_TIMESTAMP_KNOWN", "SEC_FILING_AVAILABLE",
}
EVIDENCE_VALIDITY_RULES = {
    "NO_DEFAULT_SUBSTITUTION", "NO_MATERIAL_CONFLICTS", "POINT_IN_TIME_ELIGIBLE",
    "PROVIDER_SCOPE_EXPLICIT", "REQUIRED_DOMAINS_PRESENT",
    "REQUIRED_HISTORY_SUFFICIENT", "REQUIRED_UNITS_COMPATIBLE",
}


def _category(rule_id: str) -> str:
    if rule_id in SHORT_PRESSURE_RULES:
        return "SHORT_PRESSURE_CONFIRMATION"
    if rule_id in CATALYST_RULES:
        return "CATALYST_EVIDENCE"
    if rule_id in EVIDENCE_VALIDITY_RULES:
        return "EVIDENCE_VALIDITY"
    return "MOMENTUM_DISCOVERY"


@lru_cache(maxsize=1)
def load_frozen_demo() -> dict[str, Any]:
    raw = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    pass_symbols = set(raw["percentage_change_pass_symbols"])
    rows = []
    totals = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    for symbol in raw["symbols"]:
        outcomes = (
            raw["outcomes_percentage_pass"]
            if symbol in pass_symbols
            else raw["outcomes_percentage_fail"]
        )
        rules = [
            {
                "rule_id": rule_id,
                "category": _category(rule_id),
                "outcome": outcome,
                "observed_value": None,
                "observed_unit": None,
                "observed_display": "—",
                "threshold": "—",
                "evidence_ids": [],
                "evidence_display": "—",
                "explanation_code": "SANITIZED_FROZEN_AGGREGATE",
                "blocking_reason_codes": [],
                "reason": (
                    "Sanitized frozen aggregate preserves the canonical recorded outcome; "
                    "private evidence identifiers and raw bars are intentionally omitted."
                ),
            }
            for rule_id, outcome in zip(raw["rule_ids"], outcomes, strict=True)
        ]
        counts = {key: outcomes.count(key) for key in totals}
        for key in totals:
            totals[key] += counts[key]
        rows.append({
            "symbol": symbol,
            "phase3a": {"counts": counts, "total_rules": 25},
            "rules": rules,
            "research_detection": raw["research_detection"],
            "outcome_status": raw["outcome_status"],
        })
    if totals != raw["totals"]:
        raise ValueError(f"frozen demo totals mismatch: {totals!r}")
    return {
        "schema_version": raw["schema_version"],
        "mode": raw["mode"],
        "label": raw["label"],
        "boundary_time": raw["boundary_time"],
        "rows": rows,
        "totals": totals,
        "phase3e_started": raw["phase3e_started"],
    }


def frozen_demo_research_summary() -> dict[str, Any]:
    """Historical research panel derived from the sanitized aggregate.

    Mirrors the shape of ``FrozenResearchSource.research_summary`` using only the
    recorded, sanitized outcome aggregates in ``frozen_research_v1.json``. Used when
    the private canonical tree is absent so the research-summary panel degrades like
    every other frozen surface instead of raising.
    """
    demo = load_frozen_demo()
    rows = demo["rows"]
    case_count = len(rows)
    rule_ids_per_row = len(rows[0]["rules"]) if rows else 0
    by_category: dict[str, dict[str, int]] = {}
    pct_change: dict[str, list[str]] = {}
    detection_counts: dict[str, int] = {}
    evaluable: set[str] = set()
    for row in rows:
        status = row["research_detection"]
        detection_counts[status] = detection_counts.get(status, 0) + 1
        for rule in row["rules"]:
            evaluable.add(rule["rule_id"])
            bucket = by_category.setdefault(
                rule["category"], {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
            )
            outcome = rule["outcome"]
            bucket[outcome] = bucket.get(outcome, 0) + 1
            if rule["rule_id"] == "PERCENTAGE_CHANGE_MINIMUM":
                pct_change.setdefault(outcome, []).append(row["symbol"])
            if outcome in {"UNKNOWN", "CONFLICTED", "INSUFFICIENT_DATA"}:
                evaluable.discard(rule["rule_id"])
    return {
        "boundary_time": demo["boundary_time"],
        "mode_label": demo["label"],
        "source_kind": "SANITIZED_AGGREGATE",
        "case_count": case_count,
        "evaluation_count": case_count,
        "rule_case_pairs": case_count * rule_ids_per_row,
        "outcome_totals": demo["totals"],
        "by_category": by_category,
        "evaluable_rules_across_all_cases": sorted(evaluable),
        "percentage_change_split": {
            key: sorted(value) for key, value in pct_change.items() if value
        },
        "research_detection_counts": detection_counts,
        "outcome_counts": {"INCOMPLETE": case_count},
        "global_preflight_verdict": "PREFLIGHT_REJECTED",
        "leakage_audits_passed": True,
        "phase3b_published": False,
        "phase3e_started": demo["phase3e_started"],
        "notes": [
            "SANITIZED AGGREGATE: recorded outcomes are preserved; private evidence "
            "identifiers, raw bars and the Batch 09 registry-revision preview are not "
            "included in the deployment image.",
            "UNKNOWN means insufficient admissible evidence, not failure.",
            "No forward outcome window has been acquired, so no case can be scored as "
            "a successful or failed prediction.",
        ],
    }


def frozen_demo_snapshot() -> dict[str, Any]:
    demo = load_frozen_demo()
    rows = []
    for item in demo["rows"]:
        counts = item["phase3a"]["counts"]
        rows.append({
            "symbol": item["symbol"],
            "case_id": None,
            "candidate_id": None,
            "data_mode": "FROZEN_RESEARCH",
            "mode_label": demo["label"],
            "fields": {},
            "phase3a": {
                **item["phase3a"],
                "summary": (
                    f"{counts['PASS']} PASS / {counts['FAIL']} FAIL / "
                    f"{counts['UNKNOWN']} UNKNOWN"
                ),
            },
            "research_detection": {
                "status": item["research_detection"],
                "reasons": ["Insufficient admissible evidence in the frozen evaluation."],
            },
            "outcome": {
                "status": item["outcome_status"],
                "reasons": ["No forward outcome is included in the sanitized demo."],
            },
            "evidence_coverage": {
                "supported": counts["PASS"] + counts["FAIL"],
                "total": 25,
                "label": f"{counts['PASS'] + counts['FAIL']} / 25 rules supported",
            },
            "freshness": "FROZEN",
            "last_updated": demo["boundary_time"],
        })
    return {
        "header": {
            "mode": "FROZEN_RESEARCH",
            "mode_label": demo["label"],
            "disclaimer": "Sanitized descriptive research aggregate.",
            "generated_at": demo["boundary_time"],
            "banners": [
                "FROZEN DEMO — sanitized aggregate, not the private canonical tree.",
                "No raw OHLCV, forward outcome, or private evidence identifier is included.",
            ],
        },
        "available": True,
        "row_count": len(rows),
        "rows": rows,
        "outcome_totals": demo["totals"],
        "global_preflight_verdict": "PREFLIGHT_REJECTED",
        "source_kind": "SANITIZED_AGGREGATE",
        "phase3e_started": False,
    }


def frozen_demo_detail(symbol: str) -> dict[str, Any] | None:
    demo = load_frozen_demo()
    item = next((row for row in demo["rows"] if row["symbol"] == symbol.upper()), None)
    if item is None:
        return None
    snapshot_row = next(
        row for row in frozen_demo_snapshot()["rows"] if row["symbol"] == symbol.upper()
    )
    from .causal_intelligence import build_causal_intelligence

    detail: dict[str, Any] = {
        "identity": {
            "symbol": symbol.upper(),
            "boundary_time": demo["boundary_time"],
            "mode_label": demo["label"],
            "data_mode": "FROZEN_RESEARCH",
        },
        "available": True,
        "rules": item["rules"],
        "phase3a": snapshot_row["phase3a"],
        "research_detection": snapshot_row["research_detection"],
        "outcome": snapshot_row["outcome"],
        "evidence_coverage": snapshot_row["evidence_coverage"],
        "chart": {
            "available": False,
            "points": [],
            "reason": "Raw OHLCV is intentionally excluded from the sanitized frozen demo.",
            "forward_window_shown": False,
        },
        "provenance": {
            "source_kind": "SANITIZED_AGGREGATE",
            "private_canonical_tree": False,
            "phase3e_started": False,
        },
        "freshness": "FROZEN",
    }
    detail["causal_intelligence"] = build_causal_intelligence(
        {
            **snapshot_row,
            "rules": item["rules"],
            "freshness": "FROZEN",
        }
    )
    if isinstance(detail["research_detection"], dict):
        detail["research_detection"] = {
            **detail["research_detection"],
            "ignition_state": detail["causal_intelligence"]["state"],
        }
    return detail
