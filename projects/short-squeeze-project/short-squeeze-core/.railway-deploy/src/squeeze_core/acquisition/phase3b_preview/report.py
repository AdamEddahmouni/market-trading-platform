"""Deterministic Markdown renderings of the Batch 09 preview.

Reports carry identifiers, hashes, statuses, and policy versions only. No licensed
OHLCV-derived value, no price, no return, no outcome, and no wall clock ever reaches a
report, so the Markdown is safe to commit alongside the sanitized JSON.
"""

from __future__ import annotations

from .models import RegistryRevisionPreview


def _table(header: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> str:
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def render_preview_summary(preview: RegistryRevisionPreview) -> str:
    """One-page Markdown summary of the 13-case preview."""
    candidates = preview.candidates
    lines = [
        "# Batch 09 — Phase 3B Registry Revision Preview (dry run)",
        "",
        f"Preview policy: `{preview.preview_policy_version}`",
        f"Source registry: `{preview.source_registry_version}` "
        f"(`{preview.source_registry_id}`)",
        f"Preview registry: `{preview.preview_registry_version}` "
        f"(`{preview.preview_registry_id}`)",
        f"Frozen boundary: `{preview.boundary_time.isoformat()}`",
        f"Contract audit conclusion: **{preview.contract_audit.conclusion.value}**",
        "",
        "This is a dry run. The canonical Phase 3B registry is unchanged, nothing is "
        "published, and Phase 3E is not started.",
        "",
        "## Candidate previews",
        "",
        _table(
            ("Symbol", "Case ID", "Current candidate ID", "Preview candidate ID", "ID changed"),
            tuple(
                (
                    item.symbol,
                    item.case_id,
                    f"`{item.current_registry_candidate_id}`",
                    f"`{item.preview_registry_candidate_id}`",
                    "yes" if item.candidate_identity_changed else "no",
                )
                for item in candidates
            ),
        ),
        "",
        "## Frozen Phase 3A references",
        "",
        _table(
            ("Symbol", "Request ID", "Result ID", "Request sha256", "Result sha256"),
            tuple(
                (
                    item.symbol,
                    f"`{item.preview_evaluation_request_id}`",
                    f"`{item.preview_evaluation_result_id}`",
                    f"`{item.preview_evaluation_request_sha256[:16]}…`",
                    f"`{item.preview_evaluation_result_sha256[:16]}…`",
                )
                for item in candidates
            ),
        ),
        "",
        "## Research detection (existing policy, executed unchanged)",
        "",
        f"Policy: `{candidates[0].research_detection_policy_version}`",
        "",
        _table(
            ("Symbol", "PRICE_RANGE", "MARKET_DATA_AVAILABLE", "COMPLETED_BAR_AVAILABLE", "Detection"),
            tuple(
                (
                    item.symbol,
                    *(
                        dict(item.required_rule_outcomes).get(rule, "—")
                        for rule in (
                            "PRICE_RANGE",
                            "MARKET_DATA_AVAILABLE",
                            "COMPLETED_BAR_AVAILABLE",
                        )
                    ),
                    item.research_detection_status,
                )
                for item in candidates
            ),
        ),
        "",
        "## Outcome and classification",
        "",
        _table(
            ("Symbol", "Outcome path", "Outcome status", "Research classification"),
            tuple(
                (
                    item.symbol,
                    "null",
                    item.outcome_status.value,
                    item.research_classification_status.value,
                )
                for item in candidates
            ),
        ),
        "",
        "## Field-change frequency",
        "",
        _table(
            ("Field", "Change kind", "Cases"),
            tuple(
                (item.field_name, item.change_kind.value, str(item.case_count))
                for item in preview.field_change_frequency
            ),
        ),
        "",
        "## Status counts",
        "",
        _table(
            ("Dimension", "Status", "Cases"),
            tuple(
                ("research_detection", status, str(count))
                for status, count in preview.detection_status_counts
            )
            + tuple(
                ("outcome", status, str(count))
                for status, count in preview.outcome_status_counts
            )
            + tuple(
                ("research_classification", status, str(count))
                for status, count in preview.classification_status_counts
            )
            + tuple(
                ("preview_compatibility", status, str(count))
                for status, count in preview.compatibility_status_counts
            ),
        ),
        "",
    ]
    return "\n".join(lines) + "\n"


def render_field_diff(preview: RegistryRevisionPreview) -> str:
    """Per-case ADDED / CHANGED / UNCHANGED / FORBIDDEN_TO_CHANGE diff."""
    lines = [
        "# Batch 09 — Canonical Registry Field Diff",
        "",
        "Every field of `CandidateCaseRegistryEntry` is listed for every case, including the "
        "fields that do not move, so the pinned fields are as visible as the changed ones.",
        "",
        "Change kinds: `ADDED` (was null/empty, now set), `CHANGED` (had a value, now "
        "different), `UNCHANGED` (identical, permitted to move in principle), "
        "`FORBIDDEN_TO_CHANGE` (identical, pinned by the preregistered plan).",
        "",
    ]
    for diff in preview.diffs:
        lines.extend([
            f"## {diff.symbol} — `{diff.case_id}`",
            "",
            _table(
                ("Field", "Kind", "Current", "Preview", "Rationale"),
                tuple(
                    (
                        f"`{change.field_name}`",
                        change.change_kind.value,
                        f"`{change.current_value}`",
                        f"`{change.preview_value}`",
                        change.rationale_code,
                    )
                    for change in diff.changes
                ),
            ),
            "",
        ])
    return "\n".join(lines) + "\n"


__all__ = ["render_field_diff", "render_preview_summary"]
