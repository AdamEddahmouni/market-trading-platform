"""Sanitized deterministic aggregates over the 13 frozen cases.

Every aggregate is a *descriptive count with an explicit denominator*. No aggregate is a
score, rank, recommendation, accuracy, or predictive-performance measure, and no raw OHLCV
or derived price/return value can reach this module: it reads only ``CaseFreezeRecord``,
which has no price field.
"""

from __future__ import annotations

from ..operation_readiness.models import CaseOperationReadiness
from .models import (
    BlockingReasonCode,
    CaseFreezeRecord,
    FreezeReport,
    FreezeStatus,
    OutcomeCount,
    PublicationReadinessPreview,
    ReceiptModelingPolicy,
    RuleOutcomeMatrixRow,
    SensitivitySummary,
)

_PASSED = "LEAKAGE_AUDIT_PASSED"


def _counts(values: list[str]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return tuple(sorted(counts.items(), key=lambda item: item[0]))


def rule_matrix(
    cases: tuple[CaseFreezeRecord, ...]
) -> tuple[RuleOutcomeMatrixRow, ...]:
    """One row per rule: outcome per case, outcome counts, and evidence-use flags."""
    if not cases:
        return ()
    rule_ids = tuple(sorted({item.rule_id for case in cases for item in case.rule_outcomes}))
    rows: list[RuleOutcomeMatrixRow] = []
    for rule_id in rule_ids:
        per_case = tuple(
            (case.case_id, item.outcome)
            for case in cases
            for item in case.rule_outcomes
            if item.rule_id == rule_id
        )
        entries = [
            item for case in cases for item in case.rule_outcomes if item.rule_id == rule_id
        ]
        first = entries[0]
        blockers: set[BlockingReasonCode] = set()
        for item in entries:
            blockers.update(item.blocking_reason_codes)
        rows.append(
            RuleOutcomeMatrixRow(
                rule_id=rule_id,
                category=first.category,
                batch07_admissibility_status=first.batch07_admissibility_status,
                outcomes_by_case=per_case,
                outcome_counts=_counts([outcome for _, outcome in per_case]),
                evidence_used=any(item.supporting_observation_ids for item in entries),
                metric_used=any(item.supporting_metric_ids for item in entries),
                readiness_used=any(item.supporting_readiness_ids for item in entries),
                blocking_reason_codes=tuple(blockers),
            )
        )
    return tuple(rows)


def summaries(
    cases: tuple[CaseFreezeRecord, ...], matrix: tuple[RuleOutcomeMatrixRow, ...]
) -> tuple[OutcomeCount, ...]:
    """The sanitized aggregate counts, each with an explicit denominator."""
    pairs = [item.outcome for case in cases for item in case.rule_outcomes]
    return (
        OutcomeCount(
            label="rule_outcome_over_case_rule_pairs",
            denominator=len(pairs),
            counts=_counts(pairs),
        ),
        OutcomeCount(
            label="rule_outcome_over_categories",
            denominator=len(pairs),
            counts=_counts(
                [
                    f"{item.category}:{item.outcome}"
                    for case in cases
                    for item in case.rule_outcomes
                ]
            ),
        ),
        OutcomeCount(
            label="batch07_admissibility_over_25_rules",
            denominator=len(matrix),
            counts=_counts([row.batch07_admissibility_status for row in matrix]),
        ),
        OutcomeCount(
            label="freeze_status_over_cases",
            denominator=len(cases),
            counts=_counts([case.freeze_status.value for case in cases]),
        ),
        OutcomeCount(
            label="leakage_audit_over_cases",
            denominator=len(cases),
            counts=_counts([case.leakage_audit_status for case in cases]),
        ),
        OutcomeCount(
            label="evidence_use_over_25_rules",
            denominator=len(matrix),
            counts=_counts(
                [
                    "OBSERVATIONS_USED"
                    if row.evidence_used
                    else "METRIC_USED"
                    if row.metric_used
                    else "READINESS_ONLY"
                    if row.readiness_used
                    else "NO_EVIDENCE_SUPPLIED"
                    for row in matrix
                ]
            ),
        ),
        OutcomeCount(
            label="missingness_blocking_reason_over_rule_case_pairs",
            denominator=sum(
                len(item.blocking_reason_codes)
                for case in cases
                for item in case.rule_outcomes
            ),
            counts=_counts(
                [
                    code.value
                    for case in cases
                    for item in case.rule_outcomes
                    for code in item.blocking_reason_codes
                ]
            ),
        ),
    )


def publication_readiness_preview(
    cases: tuple[CaseFreezeRecord, ...]
) -> tuple[PublicationReadinessPreview, ...]:
    """Preview only. Publishes nothing and computes no outcome classification."""
    return tuple(
        PublicationReadinessPreview(
            case_id=case.case_id,
            has_frozen_phase3a_request=bool(case.phase3a_request_id),
            has_frozen_phase3a_result=bool(case.phase3a_result_id),
            leakage_audit_passed=case.leakage_audit_status == _PASSED,
            outcome_complete=False,
            phase3b_publication_performed=False,
            referenceable_by_future_phase3b_revision=(
                case.freeze_status is FreezeStatus.REQUEST_AND_RESULT_FROZEN
                and case.leakage_audit_status == _PASSED
            ),
        )
        for case in cases
    )


def sensitivity_summary(
    primary: tuple[CaseFreezeRecord, ...],
    alternative: tuple[CaseFreezeRecord, ...],
    policy: ReceiptModelingPolicy,
) -> SensitivitySummary:
    """Rule-outcome counts under an alternative receipt-modeling policy."""
    pairs = [item.outcome for case in alternative for item in case.rule_outcomes]
    primary_by_key = {
        (case.case_id, item.rule_id): item.outcome
        for case in primary
        for item in case.rule_outcomes
    }
    diverging = {
        item.rule_id
        for case in alternative
        for item in case.rule_outcomes
        if primary_by_key.get((case.case_id, item.rule_id)) != item.outcome
    }
    return SensitivitySummary(
        receipt_modeling_policy=policy,
        case_count=len(alternative),
        outcome_counts_over_case_rule_pairs=OutcomeCount(
            label="rule_outcome_over_case_rule_pairs",
            denominator=len(pairs),
            counts=_counts(pairs),
        ),
        rules_diverging_from_primary=tuple(sorted(diverging)),
    )


def build_freeze_report(
    cases: tuple[CaseFreezeRecord, ...],
    *,
    receipt_policy: ReceiptModelingPolicy,
    boundary_time,
    sensitivity: SensitivitySummary | None = None,
) -> FreezeReport:
    matrix = rule_matrix(cases)
    return FreezeReport(
        receipt_modeling_policy=receipt_policy,
        boundary_time=boundary_time,
        requests_frozen=sum(1 for case in cases if case.phase3a_request_id),
        results_frozen=sum(1 for case in cases if case.phase3a_result_id),
        leakage_audits_passed=sum(
            1 for case in cases if case.leakage_audit_status == _PASSED
        ),
        cases=cases,
        rule_matrix=matrix,
        summaries=summaries(cases, matrix),
        publication_readiness_preview=publication_readiness_preview(cases),
        sensitivity=sensitivity,
    )


def render_markdown(report: FreezeReport) -> str:
    """Deterministic sanitized Markdown. Contains no OHLCV and no derived price."""
    lines: list[str] = [
        "# Batch 08 — Phase 3A Request and Result Freeze (sanitized)",
        "",
        f"- Freeze policy: `{report.freeze_policy_version}`",
        f"- Phase 3A policy: `{report.phase3a_policy_version}`",
        f"- Phase 3A evaluation: `{report.phase3a_evaluation_version}`",
        f"- Receipt modeling: `{report.receipt_modeling_policy.value}`",
        f"- Global preflight: `{report.global_preflight_verdict}` "
        f"(unchanged: {str(report.global_preflight_unchanged).lower()})",
        f"- Frozen boundary: `{report.boundary_time.isoformat()}`",
        f"- Requests frozen: {report.requests_frozen}",
        f"- Results frozen: {report.results_frozen}",
        f"- Leakage audits passed: {report.leakage_audits_passed}",
        f"- Report id: `{report.deterministic_id}`",
        "",
        "## Rule-outcome matrix (25 rules × 13 cases)",
        "",
        "| Rule | Category | Batch 07 admissibility | Outcome counts | Evidence | Metric | Readiness |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rule_matrix:
        counts = ", ".join(f"{name}={count}" for name, count in row.outcome_counts)
        lines.append(
            f"| `{row.rule_id}` | {row.category} | {row.batch07_admissibility_status} | "
            f"{counts} | {str(row.evidence_used).lower()} | {str(row.metric_used).lower()} | "
            f"{str(row.readiness_used).lower()} |"
        )
    lines += ["", "## Aggregate counts", ""]
    for summary in report.summaries:
        lines.append(f"### {summary.label} (denominator {summary.denominator})")
        lines.append("")
        for name, count in summary.counts:
            lines.append(f"- `{name}`: {count}")
        lines.append("")
    lines += [
        "## Per-case freeze",
        "",
        "| Case | Freeze status | Request id | Result id | Bars used | Leakage |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in report.cases:
        lines.append(
            f"| `{case.case_id}` | {case.freeze_status.value} | "
            f"`{case.phase3a_request_id}` | `{case.phase3a_result_id}` | "
            f"{case.temporal_selection.included_bar_count} | {case.leakage_audit_status} |"
        )
    lines += [
        "",
        "## Phase 3B publication-readiness preview (publishes nothing)",
        "",
        "| Case | Frozen request | Frozen result | Leakage passed | Outcome complete | Referenceable |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for preview in report.publication_readiness_preview:
        lines.append(
            f"| `{preview.case_id}` | {str(preview.has_frozen_phase3a_request).lower()} | "
            f"{str(preview.has_frozen_phase3a_result).lower()} | "
            f"{str(preview.leakage_audit_passed).lower()} | "
            f"{str(preview.outcome_complete).lower()} | "
            f"{str(preview.referenceable_by_future_phase3b_revision).lower()} |"
        )
    if report.sensitivity is not None:
        counts = ", ".join(
            f"{name}={count}"
            for name, count in report.sensitivity.outcome_counts_over_case_rule_pairs.counts
        )
        lines += [
            "",
            "## Disclosed receipt-modeling sensitivity",
            "",
            f"- Alternative policy: `{report.sensitivity.receipt_modeling_policy.value}`",
            f"- Cases: {report.sensitivity.case_count}",
            f"- Outcome counts: {counts}",
            "- Rules diverging from the primary policy: "
            + (
                ", ".join(f"`{item}`" for item in report.sensitivity.rules_diverging_from_primary)
                or "none"
            ),
        ]
    lines.append("")
    return "\n".join(lines)


def case_ids_in_order(readiness: dict[str, CaseOperationReadiness]) -> tuple[str, ...]:
    """Helper kept for callers that need the Batch 07 case-id set."""
    return tuple(readiness)


__all__ = [
    "build_freeze_report",
    "case_ids_in_order",
    "publication_readiness_preview",
    "render_markdown",
    "rule_matrix",
    "sensitivity_summary",
    "summaries",
]
