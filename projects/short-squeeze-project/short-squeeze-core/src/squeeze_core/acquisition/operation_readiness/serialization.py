"""Deterministic serialization for the Batch 07 operation-readiness report.

Canonical JSON reuses ``squeeze_core.serialization.canonical_json_bytes`` (UTF-8, sorted
keys, explicit nulls, exact Decimal strings, compact separators) plus a single trailing
LF. The Markdown renderer is derived purely from the frozen model -- no wall clock, no
absolute path -- so both artifacts regenerate byte-identically.
"""

from __future__ import annotations

from squeeze_core.serialization import canonical_json_bytes

from .models import CaseOperationReadiness, OperationReadinessReport


def serialize_report(report: OperationReadinessReport) -> bytes:
    return canonical_json_bytes(report) + b"\n"


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _case_status_summary(case: CaseOperationReadiness) -> str:
    counts: dict[str, int] = {}
    for item in case.phase2_metric_readiness:
        counts[item.status.value] = counts.get(item.status.value, 0) + 1
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


def render_markdown(report: OperationReadinessReport) -> str:
    lines: list[str] = []
    lines.append("# Batch 07 — Operation-Specific Readiness Report (generated)")
    lines.append("")
    lines.append(
        "Deterministic output of `operation_readiness`. Descriptive readiness only — "
        "no outcome, score, ranking, recommendation, or Phase 3A PASS/FAIL."
    )
    lines.append("")
    lines.append(f"- operation_readiness_policy_version: `{report.operation_readiness_policy_version}`")
    lines.append(f"- semantic_resolution_policy_version: `{report.semantic_resolution_policy_version}`")
    lines.append(f"- timestamp_uncertainty_policy: `{report.timestamp_uncertainty_policy}`")
    lines.append(f"- frozen_boundary: `{report.frozen_boundary_id}`")
    lines.append(
        f"- global_preflight_verdict: `{report.global_preflight_verdict}` "
        f"(unchanged={report.global_preflight_unchanged})"
    )
    lines.append(f"- report deterministic_id: `{report.deterministic_id}`")
    lines.append("")

    lines.append("## Operation dependency matrix (Phase 2)")
    lines.append("")
    lines.append(_row(["operation", "kind", "required_domains", "required_metrics", "semantic_deps"]))
    lines.append(_row(["---"] * 5))
    for dep in report.operation_dependency_matrix:
        sem = [f for f in (
            "price_adjustment_absolute", "price_adjustment_ratio", "dividend_adjustment",
            "volume_unit", "volume_corporate_action", "volume_filter_stationarity",
            "timestamp_boundary", "session_completeness",
        ) if getattr(dep.semantic_dependency, f)]
        lines.append(_row([
            dep.operation, dep.kind.value,
            ", ".join(dep.required_domains) or "—",
            ", ".join(dep.required_metric_names) or "—",
            ", ".join(sem) or "—",
        ]))
    lines.append("")

    lines.append("## Phase 3A 25-rule dependency-readiness matrix")
    lines.append("")
    lines.append(_row(["rule_id", "category", "touches_bars", "admissibility", "reason_codes"]))
    lines.append(_row(["---"] * 5))
    for rule in report.phase3a_rule_dependency_matrix:
        lines.append(_row([
            rule.rule_id, rule.category, str(rule.touches_detection_context_bars),
            rule.admissibility_status.value,
            ", ".join(c.value for c in rule.reason_codes) or "—",
        ]))
    lines.append("")

    lines.append("## 13-case readiness table")
    lines.append("")
    lines.append(_row([
        "case_id", "symbol", "bars", "final_bar_completed_before_boundary",
        "temporal_alignment", "phase2_metric_status_counts", "phase3a_request",
    ]))
    lines.append(_row(["---"] * 7))
    for case in report.cases:
        lines.append(_row([
            case.case_id, case.symbol, str(case.coverage.bar_count),
            str(case.final_bar_uncertainty.definitely_completed_before_boundary),
            case.temporal_alignment_readiness.status.value,
            _case_status_summary(case),
            case.phase3a_request_readiness.value,
        ]))
    lines.append("")

    lines.append("## Descriptive summaries (explicit denominators)")
    lines.append("")
    for summary in report.summaries:
        rendered = ", ".join(f"{k}={v}" for k, v in summary.counts) or "—"
        lines.append(f"- **{summary.label}** (n={summary.denominator}): {rendered}")
    lines.append("")

    return "\n".join(lines) + "\n"


__all__ = ["serialize_report", "render_markdown"]
