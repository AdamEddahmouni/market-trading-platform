"""Prospective Paper lineage reconstruction helpers (read-only honesty).

Maps the governed Paper lifecycle chain. Missing links stay NOT_OBSERVED.
Does not rewrite strategy/runtime.py. Does not start a Paper session.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ...intelligence.execution.order_ready_correlation import (
    opportunity_id_from_order_ready,
    order_ready_correlation_snapshot,
)
from ...intelligence.execution.types import OrderReadyV1
from .item9_validation_readiness_contract import (
    FIELD_NOT_APPLICABLE,
    FIELD_NOT_OBSERVED,
    PROSPECTIVE_PAPER_RUN_PACKAGE_SCHEMA_ID,
)

LINEAGE_STEPS: tuple[str, ...] = (
    "raw_observation",
    "EventV1",
    "analysis",
    "strategy_candidate",
    "OpportunityV1",
    "thesis",
    "operator_decision",
    "risk",
    "order_ready",
    "paper_order",
    "fill",
    "position",
    "monitoring",
    "outcome",
    "settlement",
    "attribution",
)

# Canonical backend strategy Paper path from PAPER_DECISION_LIFECYCLE.md.
# Names differ from LINEAGE_STEPS; gaps stay NOT_OBSERVED rather than invented.
PAPER_DECISION_LIFECYCLE_CANONICAL: tuple[str, ...] = (
    "StrategyDefinition",
    "StrategyMatch",
    "ForecastV1",
    "OpportunityV1",
    "capital_allocation",
    "TradeProposalV1",
    "RiskDecisionV1",
    "OrderReadyV1",
    "paper_order",
    "fill",
    "portfolio_settlement",
    "attribution",
)

LINEAGE_RECONSTRUCTION_HELPERS: dict[str, str] = {
    "OpportunityV1": "order_ready_lineage_from_record",
    "order_ready": "order_ready_lineage_from_record",
    "risk": "order_ready_lineage_from_record",
}

LINEAGE_TO_LIFECYCLE: dict[str, str] = {
    "OpportunityV1": "OpportunityV1",
    "risk": "RiskDecisionV1",
    "order_ready": "OrderReadyV1",
    "paper_order": "paper_order",
    "fill": "fill",
    "position": "portfolio_settlement",
    "attribution": "attribution",
}

RUN_PACKAGE_REL = Path("manifests/paper/item9_prospective_paper_run_package_v1.json")


def load_prospective_paper_run_package(*, imp_root: Path) -> dict[str, Any]:
    path = imp_root / RUN_PACKAGE_REL
    if not path.is_file():
        return {
            "loaded": False,
            "schema_id": PROSPECTIVE_PAPER_RUN_PACKAGE_SCHEMA_ID,
            "path": str(path),
            "session_started": False,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"loaded": False, "invalid": True, "path": str(path)}
    return {"loaded": True, "path": str(path.resolve()), **payload}


def paper_lifecycle_gap_report() -> dict[str, Any]:
    """Compare Item 9 lineage steps to PAPER_DECISION_LIFECYCLE without inventing links."""

    mapped = {step: LINEAGE_TO_LIFECYCLE[step] for step in LINEAGE_STEPS if step in LINEAGE_TO_LIFECYCLE}
    unmapped_lineage = [step for step in LINEAGE_STEPS if step not in LINEAGE_TO_LIFECYCLE]
    missing_canonical = [
        node
        for node in PAPER_DECISION_LIFECYCLE_CANONICAL
        if node not in mapped.values()
    ]
    helper_coverage = {
        step: LINEAGE_RECONSTRUCTION_HELPERS.get(step, FIELD_NOT_OBSERVED)
        for step in LINEAGE_STEPS
    }
    return {
        "schema_id": PROSPECTIVE_PAPER_RUN_PACKAGE_SCHEMA_ID,
        "source_doc": "docs/architecture/PAPER_DECISION_LIFECYCLE.md",
        "mapped": mapped,
        "unmapped_lineage_steps": unmapped_lineage,
        "missing_canonical_nodes": missing_canonical,
        "reconstruction_helpers": helper_coverage,
        "missing_link_token": FIELD_NOT_OBSERVED,
        "session_started": False,
    }


def reconstruct_lineage_map(
    present: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return id→status for each lineage step. Absent → NOT_OBSERVED."""

    present = dict(present or {})
    links: dict[str, Any] = {}
    for step in LINEAGE_STEPS:
        if step in present and present[step] not in (None, "", FIELD_NOT_OBSERVED):
            links[step] = {
                "status": "PRESENT",
                "value": present[step],
            }
        else:
            links[step] = {
                "status": FIELD_NOT_OBSERVED,
                "value": None,
            }
    return {
        "schema_id": PROSPECTIVE_PAPER_RUN_PACKAGE_SCHEMA_ID,
        "session_started": False,
        "links": links,
        "missing_link_token": FIELD_NOT_OBSERVED,
        "mode_b_strategy_fields": FIELD_NOT_APPLICABLE,
    }


def order_ready_lineage_from_record(order_ready: OrderReadyV1) -> dict[str, Any]:
    """Extract OrderReady opportunity lineage without inventing ids."""

    snapshot = order_ready_correlation_snapshot(order_ready)
    opportunity_id = opportunity_id_from_order_ready(order_ready)
    return {
        "order_ready": {
            "status": "PRESENT",
            "value": snapshot.get("order_ready_id"),
        },
        "OpportunityV1": (
            {"status": "PRESENT", "value": opportunity_id}
            if opportunity_id
            else {"status": FIELD_NOT_OBSERVED, "value": None}
        ),
        "risk": (
            {"status": "PRESENT", "value": snapshot.get("risk_decision_id")}
            if snapshot.get("risk_decision_id")
            else {"status": FIELD_NOT_OBSERVED, "value": None}
        ),
        "correlation_id": snapshot.get("correlation_id"),
    }


__all__ = [
    "LINEAGE_STEPS",
    "PAPER_DECISION_LIFECYCLE_CANONICAL",
    "RUN_PACKAGE_REL",
    "load_prospective_paper_run_package",
    "order_ready_lineage_from_record",
    "paper_lifecycle_gap_report",
    "reconstruct_lineage_map",
]
