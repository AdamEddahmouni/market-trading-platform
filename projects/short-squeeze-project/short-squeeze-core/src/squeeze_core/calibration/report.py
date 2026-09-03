"""Render calibration reports as JSON and Markdown."""

from __future__ import annotations

import json
from pathlib import Path

from squeeze_core.serialization import canonical_json_bytes

from .models import CalibrationReport, VariantResult


def render_markdown(report: CalibrationReport) -> str:
    lines = [
        "# Phase 3D Calibration Report",
        "",
        f"- Experiment: `{report.experiment_version}`",
        f"- Type: `{report.experiment_type.value}`",
        f"- Cohort: `{report.cohort_type.value}`",
        f"- Analysis unit: `{report.analysis_unit.value}`",
        f"- Baseline: `{report.baseline_variant_id}`",
        "",
        "## Limitations",
        "",
    ]
    for item in report.limitations:
        lines.append(f"- **{item.code}** — {item.statement}")
    lines.extend(["", "## Variant summary", ""])
    for variant in report.variant_results:
        lines.extend(_variant_section(variant, report.baseline_variant_id))
    return "\n".join(lines) + "\n"


def _variant_section(variant: VariantResult, baseline_id: str) -> list[str]:
    matrix = variant.analysis.confusion_matrix
    counts = ""
    if matrix is not None:
        counts = (
            f"TP={matrix.true_positive_count} FP={matrix.false_positive_count} "
            f"TN={matrix.true_negative_count} FN={matrix.false_negative_count} "
            f"unevaluable={matrix.unevaluable_count}"
        )
    lines = [
        f"### {variant.variant_id}",
        "",
        variant.description,
        "",
        f"- Cases: {variant.case_count}",
        f"- Confusion matrix: {counts or 'n/a'}",
    ]
    if variant.flips_from_baseline:
        lines.append(f"- Classification flips from baseline: {len(variant.flips_from_baseline)}")
        for flip in variant.flips_from_baseline:
            lines.append(
                f"  - `{flip.case_id}` ({flip.symbol}): "
                f"{flip.baseline.value} → {flip.variant.value}"
            )
    elif variant.variant_id != baseline_id:
        lines.append("- Classification flips from baseline: 0")
    lines.append("")
    return lines


def write_report(report: CalibrationReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(canonical_json_bytes(report).decode("utf-8"))
    output_path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path = output_path.with_suffix(".md")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")


__all__ = ["render_markdown", "write_report"]
