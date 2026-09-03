from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .comparison import compare_candidate
from .evidence import EvidenceInput


def _cell(row: dict[str, Any], name: str, key: str | None = None) -> EvidenceInput:
    cell = row.get("fields", {}).get(name) or {}
    status = cell.get("status")
    admissibility = cell.get("research_admissibility") == "RESEARCH_ADMISSIBLE"
    return EvidenceInput(
        key=key or name,
        value=cell.get("value"),
        unit=cell.get("unit"),
        provider=cell.get("provider"),
        provider_field=cell.get("provider_field"),
        event_time=cell.get("event_time"),
        received_time=cell.get("received_time"),
        display_available=status == "KNOWN",
        research_admissible=admissibility,
        point_in_time_eligible=status == "KNOWN",
        fresh=cell.get("freshness") in ("CURRENT", "DELAYED"),
        conflict=bool(cell.get("conflict")),
        missing_reason=cell.get("missing_reason"),
        evidence_id=cell.get("evidence_id"),
        selection_reason=cell.get("selection_reason"),
    )


def evidence_from_row(row: dict[str, Any]) -> dict[str, EvidenceInput]:
    inputs = {
        "price": _cell(row, "last", "price"),
        # Intentionally no today_percentage_change: current canonical return is not
        # silently relabelled as the Legacy daily field.
        "relative_volume": _cell(row, "relative_volume"),
        "published_short_interest_pct": _cell(
            row, "published_short_interest", "published_short_interest_pct"
        ),
        "days_to_cover": _cell(row, "days_to_cover"),
        "cost_to_borrow": _cell(row, "borrow_fee", "cost_to_borrow"),
        "float_shares": _cell(row, "float_shares"),
        "current_percentage_change": _cell(
            row, "percentage_change", "current_percentage_change"
        ),
        "completed_bar_acceleration": _cell(
            row, "completed_bar_acceleration", "completed_bar_acceleration"
        ),
        "catalyst_age_hours": _cell(row, "catalyst_age_hours"),
    }
    borrow = _cell(row, "borrow_availability")
    float_item = inputs["float_shares"]
    if borrow.value is not None and float_item.value not in (None, 0):
        inputs["borrow_availability_pct_float"] = EvidenceInput(
            **{
                **borrow.__dict__,
                "key": "borrow_availability_pct_float",
                "value": 100.0 * float(borrow.value) / float(float_item.value),
                "unit": "PERCENT_OF_FLOAT",
                "research_admissible": (
                    borrow.research_admissible and float_item.research_admissible
                ),
            }
        )
    return inputs


def project_candidate(row: dict[str, Any]) -> dict[str, Any]:
    methods = compare_candidate(evidence_from_row(row), as_of=row.get("last_updated"))
    adam = methods[2]
    why = [row.get("discovery_source") or "session history"]
    if not row.get("in_current_scan", True):
        why.append("no longer in scanner")
    classification = adam["classification"]
    if classification in ("PRIME", "SUBPRIME", "WATCH"):
        why.append(f"Evidence-Gated {classification.title()}")
    elif classification == "UNEVALUABLE":
        why.append("incomplete evidence")
    return {
        **row,
        "why_listed": why,
        "methodologies": methods,
        "legacy_classification": methods[0]["classification"],
        "peer_classification": methods[1]["classification"],
        "adam_classification": classification,
        "pressure": adam["pressure"],
        "ignition": adam["ignition"],
        "methodology_coverage": adam["evidence_coverage"],
    }


def project_candidates(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [project_candidate(row) for row in rows]


def filter_projections(
    rows: Iterable[dict[str, Any]], *, classifications: set[str] | None = None
) -> list[dict[str, Any]]:
    copied = list(rows)
    if not classifications:
        return copied
    return [row for row in copied if row.get("adam_classification") in classifications]


def sort_projections(
    rows: Iterable[dict[str, Any]], key: str, descending: bool
) -> list[dict[str, Any]]:
    copied = list(rows)
    known = [row for row in copied if row.get(key) is not None]
    missing = [row for row in copied if row.get(key) is None]
    known.sort(key=lambda row: (row.get(key), row.get("symbol", "")), reverse=descending)
    missing.sort(key=lambda row: row.get("symbol", ""))
    return [*known, *missing]
