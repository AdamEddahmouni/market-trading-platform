"""Backend-owned operator truth tokens for Control / Command.

Lane E owns this contract. Presentation (labels, tones) stays in Lane B.
Partial Item 9 corpus admission (e.g. 2/3) is calendar IDLE, never DEGRADED.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

OPERATOR_TRUTH_CLASSES = (
    "HEALTHY",
    "DEGRADED",
    "BLOCKED",
    "IDLE",
    "UNKNOWN",
    "UNAVAILABLE",
    "NOT_OBSERVED",
)

_FRACTION_RE = re.compile(r"^(\d+)\s*/\s*(\d+)$")

_TRUTH_SCHEMA_VERSION = "operator-truth/1.0.0"


def map_lifecycle_truth(status: str | None) -> str:
    token = str(status or "UNKNOWN").upper()
    if token in {"HEALTHY", "READY", "RUNNING", "OK"}:
        return "HEALTHY"
    if token == "STOPPED":
        return "BLOCKED"
    if token in {"PARTIAL", "DEGRADED"}:
        return "DEGRADED"
    return "UNKNOWN"


def map_readiness_truth(status: str | None) -> str:
    token = str(status or "UNKNOWN").upper()
    if token == "READY":
        return "HEALTHY"
    if token == "ACTION_REQUIRED":
        return "DEGRADED"
    return "UNKNOWN"


def map_item9_disposition_truth(disposition: str | None) -> str:
    token = str(disposition or "UNKNOWN").upper()
    if token == "READY_TO_COLLECT":
        return "HEALTHY"
    if token == "NOT_RTH":
        return "IDLE"
    if token in {"WRONG_RUNTIME", "OUTPUT_PATH_INVALID"}:
        return "BLOCKED"
    if token == "PROVIDER_UNAVAILABLE":
        return "UNAVAILABLE"
    if token == "ACTIVE_COLLECTOR_EXISTS":
        return "DEGRADED"
    return "UNKNOWN"


def parse_item9_sample_gate_fraction(distinct_rth_dates: str) -> tuple[int, int] | None:
    match = _FRACTION_RE.match(distinct_rth_dates.strip())
    if match is None:
        return None
    admitted = int(match.group(1))
    required = int(match.group(2))
    if required <= 0:
        return None
    return admitted, required


def map_item9_corpus_progress_truth(
    corpus_section: Mapping[str, Any] | None,
    *,
    distinct_rth_dates: str | None = None,
) -> str:
    """Calendar/methodology progress — not platform degradation."""

    section = corpus_section if isinstance(corpus_section, Mapping) else {}
    availability = str(section.get("availability") or "NOT_OBSERVED").upper()
    if availability != "AVAILABLE":
        return "UNAVAILABLE" if availability == "UNAVAILABLE" else "NOT_OBSERVED"

    token = str(
        distinct_rth_dates
        if distinct_rth_dates is not None
        else _distinct_rth_dates_from_corpus(section)
    ).strip().upper()
    if token in {"NOT_OBSERVED", "UNKNOWN"}:
        return "NOT_OBSERVED"
    if token == "UNAVAILABLE":
        return "UNAVAILABLE"

    fraction = parse_item9_sample_gate_fraction(token)
    if fraction is None:
        return "UNKNOWN"
    admitted, required = fraction
    if admitted == 0:
        return "NOT_OBSERVED"
    if admitted < required:
        return "IDLE"
    if admitted == required:
        return "HEALTHY"
    return "UNKNOWN"


def item9_corpus_progress_detail(
    corpus_section: Mapping[str, Any] | None,
    corpus_truth: str,
) -> str:
    """Keep UNAVAILABLE/NOT_OBSERVED/UNKNOWN as themselves — never mint 2/3."""

    dates = _distinct_rth_dates_from_corpus(
        corpus_section if isinstance(corpus_section, Mapping) else {}
    )
    token = str(dates).strip()
    if parse_item9_sample_gate_fraction(token) is not None:
        return token
    if corpus_truth in {"UNAVAILABLE", "NOT_OBSERVED", "UNKNOWN"}:
        return corpus_truth
    return token or corpus_truth


def next_safe_action_for_operator_row(row_id: str, truth: str) -> str:
    """Operator next-safe-action copy. Never calibrate, collect, or enable Live."""

    if row_id == "item9-corpus":
        if truth == "IDLE":
            return (
                "Wait for more distinct regular-trading-hours dates. "
                "Do not calibrate, do not treat IDLE as a workstation repair, and do not enable Live."
            )
        if truth == "HEALTHY":
            return (
                "Date-gate coverage is complete. Still NOT CALIBRATED; calibration remains forbidden. "
                "Do not enable Live or run Full30."
            )
        if truth in {"UNAVAILABLE", "NOT_OBSERVED", "UNKNOWN"}:
            return (
                f"Retry GET /operator/diagnostics. Keep Item 9 as {truth}; "
                "do not mint 2/3, calibrate, or enable Live."
            )
        return "Do not calibrate, enable Live, or run Full30."
    if row_id == "item9-preflight" and truth == "IDLE":
        return "Wait for the next US cash session. Do not start collection from this UI."
    if row_id == "live-execution":
        if truth in {"BLOCKED", "POLICY"}:
            return "Leave Live OFF. Observational data is not a go-live."
        return "Live execution remains governed. This is not authorization to place broker orders."
    return "Do not enable Live, fit calibration, or run Full30."


def _distinct_rth_dates_from_corpus(section: Mapping[str, Any]) -> str:
    progress = section.get("sample_gate_progress")
    if isinstance(progress, Mapping) and progress.get("distinct_rth_dates"):
        return str(progress["distinct_rth_dates"])
    report = section.get("report")
    if isinstance(report, Mapping):
        nested = report.get("sample_gate_progress")
        if isinstance(nested, Mapping) and nested.get("distinct_rth_dates"):
            return str(nested["distinct_rth_dates"])
    return "NOT_OBSERVED"


def map_collector_truth(*, detected: bool, item9_disposition: str | None) -> str:
    if detected:
        return "HEALTHY"
    if str(item9_disposition or "").upper() == "NOT_RTH":
        return "IDLE"
    return "NOT_OBSERVED"


def map_live_execution_truth(live_execution_env: bool) -> str:
    return "DEGRADED" if live_execution_env else "BLOCKED"


def map_cycle_failure_truth(expected_cycle_failure: str | None) -> str:
    token = str(expected_cycle_failure or "NOT_OBSERVED").upper()
    if token == "OBSERVED":
        return "DEGRADED"
    if token == "NOT_OBSERVED":
        return "NOT_OBSERVED"
    return "UNKNOWN"


def map_evidence_gaps_truth(evidence_gaps: list[Any] | None) -> str:
    return "DEGRADED" if evidence_gaps else "NOT_OBSERVED"


def build_operator_truth_section(
    *,
    as_of_utc: str,
    lifecycle_status: str | None,
    readiness_status: str | None,
    runtime_git_sha: str | None,
    item9_disposition: str | None,
    item9_corpus_status: Mapping[str, Any] | None,
    collector_detected: bool,
    collector_probe_status: str | None,
    live_execution_env: bool,
    expected_cycle_failure: str | None,
    cycle_gap_note: str | None,
    evidence_gaps: list[Any] | None,
) -> dict[str, Any]:
    corpus_truth = map_item9_corpus_progress_truth(item9_corpus_status)
    corpus_dates = item9_corpus_progress_detail(item9_corpus_status, corpus_truth)
    rows = [
        {
            "id": "imp-lifecycle",
            "truth": map_lifecycle_truth(lifecycle_status),
            "detail": f"Lifecycle status {str(lifecycle_status or 'UNKNOWN').upper()}.",
            "source_field": "sections.lifecycle.status",
        },
        {
            "id": "operator-readiness",
            "truth": map_readiness_truth(readiness_status),
            "detail": f"Readiness status {str(readiness_status or 'UNKNOWN').upper()}.",
            "source_field": "sections.readiness.status",
        },
        {
            "id": "runtime-sha",
            "truth": "HEALTHY" if runtime_git_sha else "UNAVAILABLE",
            "detail": str(runtime_git_sha or "Diagnostics did not include runtime SHA."),
            "source_field": "sections.runtime.git_sha",
        },
        {
            "id": "item9-preflight",
            "truth": map_item9_disposition_truth(item9_disposition),
            "detail": str(item9_disposition or "UNKNOWN"),
            "source_field": "sections.runtime.item9_preflight.disposition",
            "next_safe_action": next_safe_action_for_operator_row(
                "item9-preflight",
                map_item9_disposition_truth(item9_disposition),
            ),
        },
        {
            "id": "item9-corpus",
            "truth": corpus_truth,
            "detail": corpus_dates,
            "source_field": "sections.runtime.item9_corpus_status.sample_gate_progress.distinct_rth_dates",
            "next_safe_action": next_safe_action_for_operator_row("item9-corpus", corpus_truth),
        },
        {
            "id": "collector",
            "truth": map_collector_truth(
                detected=collector_detected,
                item9_disposition=item9_disposition,
            ),
            "detail": (
                "Active collector process detected (summarized)."
                if collector_detected
                else f"Probe {collector_probe_status or item9_disposition or 'NOT_OBSERVED'}."
            ),
            "source_field": "sections.runtime.runtime_resilience.collector_process.active_collector_detected",
        },
        {
            "id": "live-execution",
            "truth": map_live_execution_truth(live_execution_env),
            "detail": "Live execution env flag is on — still governed." if live_execution_env else "Live OFF",
            "source_field": "sections.governance.live_execution_env",
            "next_safe_action": next_safe_action_for_operator_row(
                "live-execution",
                map_live_execution_truth(live_execution_env),
            ),
        },
        {
            "id": "expected-cycle",
            "truth": map_cycle_failure_truth(expected_cycle_failure),
            "detail": cycle_gap_note or "Cycle ledger not observed.",
            "source_field": "sections.cycle_recovery.expected_cycle_failure",
        },
        {
            "id": "evidence-gaps",
            "truth": map_evidence_gaps_truth(evidence_gaps),
            "detail": (
                "; ".join(
                    f"{gap.get('domain', 'gap')}:{gap.get('gap_class', 'UNKNOWN')}"
                    for gap in evidence_gaps
                    if isinstance(gap, Mapping)
                )
                if evidence_gaps
                else "No composed evidence gaps."
            ),
            "source_field": "sections.evidence_gaps",
        },
    ]
    return {
        "schema_version": _TRUTH_SCHEMA_VERSION,
        "clock": {
            "as_of_utc": as_of_utc,
            "kind": "wall_utc",
            "note": "ISO-8601 UTC wall clock. Not a monotonic probe clock.",
        },
        "rows": rows,
        "by_id": {str(row["id"]): str(row["truth"]) for row in rows},
    }


__all__ = [
    "OPERATOR_TRUTH_CLASSES",
    "build_operator_truth_section",
    "item9_corpus_progress_detail",
    "map_collector_truth",
    "map_cycle_failure_truth",
    "map_evidence_gaps_truth",
    "map_item9_corpus_progress_truth",
    "map_item9_disposition_truth",
    "map_lifecycle_truth",
    "map_live_execution_truth",
    "map_readiness_truth",
    "next_safe_action_for_operator_row",
    "parse_item9_sample_gate_fraction",
]
