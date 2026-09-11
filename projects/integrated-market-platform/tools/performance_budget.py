"""Performance budget loading, compatibility checks, and classification.

P7 establishes observational performance budgets. Classifications never gate
validation exit codes unless a future increment explicitly enables gating.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


CLASSIFICATION_NO_BASELINE = "NO_BASELINE"
CLASSIFICATION_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
CLASSIFICATION_NORMAL = "NORMAL"
CLASSIFICATION_WARNING = "WARNING"
CLASSIFICATION_REGRESSION = "REGRESSION"
CLASSIFICATION_SEVERE_REGRESSION = "SEVERE_REGRESSION"
CLASSIFICATION_INCOMPATIBLE = "INCOMPATIBLE_BASELINE"

DEFAULT_BUDGET_PATH = Path("manifests/performance_budget.json")


@dataclass(frozen=True, slots=True)
class BudgetWorkload:
    workload_id: str
    validation_mode: str
    reference_workers: int
    baseline_median_seconds: float
    baseline_sample_count: int
    reference_test_count: int | None
    workload_identity_required: bool
    warning_ratio: float
    regression_ratio: float
    severe_regression_ratio: float
    changed_test_count_tolerance: float
    domain_target: str | None = None
    reference_skipped: int | None = None


@dataclass(frozen=True, slots=True)
class PerformanceBudget:
    schema_version: str
    telemetry_schema_version: str
    budget_version: str
    parent_scheduler_version: str
    parent_selector_version: str
    gating_policy: str
    maturity_status: str
    compatibility: dict[str, Any]
    workloads: dict[str, BudgetWorkload]
    raw: dict[str, Any]


def load_performance_budget(path: Path | None = None) -> PerformanceBudget:
    target = Path(path) if path is not None else DEFAULT_BUDGET_PATH
    payload = json.loads(target.read_text(encoding="utf-8"))
    threshold = payload.get("threshold_policy", {})
    warning_ratio = float(threshold.get("warning_ratio", 1.15))
    regression_ratio = float(threshold.get("regression_ratio", 1.30))
    severe_ratio = float(threshold.get("severe_regression_ratio", 1.50))
    changed_tolerance = float(
        threshold.get("changed_workload_test_count_tolerance", 0.02)
    )
    workloads: dict[str, BudgetWorkload] = {}
    for workload_id, row in payload.get("workloads", {}).items():
        workloads[workload_id] = BudgetWorkload(
            workload_id=workload_id,
            validation_mode=str(row.get("validation_mode", "")),
            reference_workers=int(row.get("reference_workers", 1)),
            baseline_median_seconds=float(
                row.get("baseline_median_seconds", row.get("baseline_wall_seconds", 0.0))
            ),
            baseline_sample_count=int(row.get("baseline_sample_count", 0)),
            reference_test_count=(
                int(row["reference_test_count"])
                if row.get("reference_test_count") is not None
                else None
            ),
            workload_identity_required=bool(row.get("workload_identity_required", False)),
            warning_ratio=warning_ratio,
            regression_ratio=regression_ratio,
            severe_regression_ratio=severe_ratio,
            changed_test_count_tolerance=changed_tolerance,
            domain_target=row.get("domain_target"),
            reference_skipped=(
                int(row["reference_skipped"])
                if row.get("reference_skipped") is not None
                else None
            ),
        )
    return PerformanceBudget(
        schema_version=str(payload.get("schema_version", "")),
        telemetry_schema_version=str(payload.get("telemetry_schema_version", "")),
        budget_version=str(payload.get("budget_version", "")),
        parent_scheduler_version=str(payload.get("parent_scheduler_version", "")),
        parent_selector_version=str(payload.get("parent_selector_version", "")),
        gating_policy=str(payload.get("gating_policy", "OBSERVE_ONLY")),
        maturity_status=str(payload.get("maturity_status", "PROVISIONAL")),
        compatibility=dict(payload.get("environment_compatibility", {})),
        workloads=workloads,
        raw=payload,
    )


def validate_budget_schema(payload: Mapping[str, Any]) -> list[str]:
    """Return schema validation errors; empty list means valid."""

    errors: list[str] = []
    required = (
        "schema_version",
        "budget_version",
        "gating_policy",
        "threshold_policy",
        "workloads",
    )
    for key in required:
        if key not in payload:
            errors.append(f"missing required field: {key}")
    for workload_id, row in payload.get("workloads", {}).items():
        if not isinstance(row, dict):
            errors.append(f"workload {workload_id} must be an object")
            continue
        for field in ("validation_mode", "reference_workers", "baseline_wall_seconds"):
            if field not in row:
                errors.append(f"workload {workload_id} missing {field}")
    return errors


def _workload_key_for_receipt(receipt: Mapping[str, Any]) -> str | None:
    mode = str(receipt.get("mode", ""))
    if mode == "fast":
        return "fast"
    if mode == "full":
        return "full"
    if mode == "domain":
        domain = str(receipt.get("domain_target", receipt.get("target", "")))
        if domain == "macro":
            return "domain_macro"
        return None
    if mode == "changed":
        return "changed_product_paths"
    return None


def environments_compatible(
    observed: Mapping[str, Any],
    baseline_environment_class: str,
    compatibility: Mapping[str, Any],
    *,
    baseline_python_version: str | None = None,
) -> tuple[bool, list[str]]:
    """Determine whether observed environment may be compared to a baseline."""

    reasons: list[str] = []
    observed_class = str(observed.get("environment_class", ""))
    if observed_class and baseline_environment_class:
        if compatibility.get("allow_local_vs_ci_comparison") is False:
            observed_ci = bool(observed.get("ci", False))
            baseline_ci = baseline_environment_class.startswith("ci_")
            if observed_ci != baseline_ci:
                reasons.append("local and ci environments are not comparable")
    if compatibility.get("require_matching_os_family", True):
        observed_os = str(observed.get("os_family", ""))
        baseline_os = "windows" if "windows" in baseline_environment_class.lower() else ""
        if baseline_os and observed_os and observed_os != baseline_os:
            reasons.append(f"os family mismatch: {observed_os} vs {baseline_os}")
    if compatibility.get("require_matching_python_minor", True) and baseline_python_version:
        observed_py = str(observed.get("python_version", ""))
        baseline_minor = ".".join(baseline_python_version.split(".")[:2])
        observed_minor = ".".join(observed_py.split(".")[:2]) if observed_py else ""
        if observed_minor and observed_minor != baseline_minor:
            reasons.append(
                f"python minor mismatch: {observed_minor} vs baseline {baseline_minor}"
            )
    cpu_tolerance = float(compatibility.get("cpu_count_tolerance_ratio", 0.5))
    observed_cpu = int(observed.get("logical_cpu_count", 0) or 0)
    baseline_cpu = int(observed.get("baseline_logical_cpu_count", 8) or 8)
    if observed_cpu and baseline_cpu:
        ratio = observed_cpu / baseline_cpu
        if ratio < (1.0 - cpu_tolerance) or ratio > (1.0 + cpu_tolerance):
            reasons.append(
                f"cpu count outside tolerance: {observed_cpu} vs baseline {baseline_cpu}"
            )
    return (len(reasons) == 0, reasons)


def workload_identity_matches(
    workload: BudgetWorkload,
    receipt: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    """Check whether receipt workload is comparable to the configured baseline."""

    reasons: list[str] = []
    if workload.reference_test_count is not None:
        observed_tests = int(receipt.get("tests_run", 0))
        reference = workload.reference_test_count
        if reference > 0:
            delta_ratio = abs(observed_tests - reference) / reference
            if delta_ratio > workload.changed_test_count_tolerance:
                reasons.append(
                    f"test count mismatch: {observed_tests} vs reference {reference} "
                    f"(delta {delta_ratio:.3f} > tolerance {workload.changed_test_count_tolerance})"
                )
    if workload.reference_skipped is not None:
        observed_skipped = int(receipt.get("skips", 0))
        if observed_skipped != workload.reference_skipped:
            reasons.append(
                f"skipped count mismatch: {observed_skipped} vs reference {workload.reference_skipped}"
            )
    return (len(reasons) == 0, reasons)


def classify_performance(
    receipt: Mapping[str, Any],
    *,
    budget: PerformanceBudget,
    environment: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify a validation receipt against the performance budget."""

    workload_key = _workload_key_for_receipt(receipt)
    if workload_key is None:
        return _classification_payload(
            classification=CLASSIFICATION_NO_BASELINE,
            workload_id=None,
            explain=["no canonical workload mapping for mode"],
            budget=budget,
            environment=environment,
        )
    workload = budget.workloads.get(workload_key)
    if workload is None:
        return _classification_payload(
            classification=CLASSIFICATION_NO_BASELINE,
            workload_id=workload_key,
            explain=[f"no budget entry for workload {workload_key}"],
            budget=budget,
            environment=environment,
        )
    baseline_row = budget.raw.get("workloads", {}).get(workload_key, {})
    baseline_env_class = str(baseline_row.get("environment_class", ""))
    provenance_env = budget.raw.get("provenance", {}).get("environment", {})
    baseline_python = provenance_env.get("python_version")
    if baseline_python is None:
        p2_source = budget.raw.get("provenance", {}).get("p2_baseline_source", "")
        if "p2" in p2_source.lower():
            baseline_python = "3.11.15"
    compatible, compat_reasons = environments_compatible(
        environment,
        baseline_env_class,
        budget.compatibility,
        baseline_python_version=str(baseline_python) if baseline_python else None,
    )
    if not compatible:
        return _classification_payload(
            classification=CLASSIFICATION_INCOMPATIBLE,
            workload_id=workload_key,
            explain=compat_reasons,
            budget=budget,
            environment=environment,
            workload=workload,
        )
    observed_workers = int(
        receipt.get("effective_workers", receipt.get("workers", 0)) or 0
    )
    if observed_workers != workload.reference_workers:
        return _classification_payload(
            classification=CLASSIFICATION_INCOMPATIBLE,
            workload_id=workload_key,
            explain=[
                f"worker count mismatch: {observed_workers} vs reference {workload.reference_workers}"
            ],
            budget=budget,
            environment=environment,
            workload=workload,
        )
    scheduler_version = str(receipt.get("scheduler_version", ""))
    if (
        budget.compatibility.get("require_matching_scheduler_version", True)
        and scheduler_version
        and scheduler_version != budget.parent_scheduler_version
    ):
        return _classification_payload(
            classification=CLASSIFICATION_INCOMPATIBLE,
            workload_id=workload_key,
            explain=[
                f"scheduler version mismatch: {scheduler_version} vs {budget.parent_scheduler_version}"
            ],
            budget=budget,
            environment=environment,
            workload=workload,
        )
    if workload.baseline_sample_count < 1:
        return _classification_payload(
            classification=CLASSIFICATION_INSUFFICIENT_DATA,
            workload_id=workload_key,
            explain=["baseline sample count is zero"],
            budget=budget,
            environment=environment,
            workload=workload,
        )
    min_samples = int(
        budget.raw.get("minimum_sample_requirements", {}).get(
            workload_key.split("_")[0], 1
        )
    )
    if workload.baseline_sample_count < min_samples:
        return _classification_payload(
            classification=CLASSIFICATION_INSUFFICIENT_DATA,
            workload_id=workload_key,
            explain=[
                f"baseline samples {workload.baseline_sample_count} < required {min_samples}"
            ],
            budget=budget,
            environment=environment,
            workload=workload,
        )
    if workload.workload_identity_required:
        identity_ok, identity_reasons = workload_identity_matches(workload, receipt)
        if not identity_ok:
            return _classification_payload(
                classification=CLASSIFICATION_INSUFFICIENT_DATA,
                workload_id=workload_key,
                explain=identity_reasons,
                budget=budget,
                environment=environment,
                workload=workload,
            )
    wall_seconds = float(receipt.get("wall_seconds", 0.0))
    baseline = workload.baseline_median_seconds
    if baseline <= 0 or wall_seconds <= 0:
        return _classification_payload(
            classification=CLASSIFICATION_INSUFFICIENT_DATA,
            workload_id=workload_key,
            explain=["non-positive timing values"],
            budget=budget,
            environment=environment,
            workload=workload,
            wall_seconds=wall_seconds,
            baseline_seconds=baseline,
        )
    classification, threshold_crossed, ratio, absolute_delta = _classify_ratio(
        wall_seconds,
        baseline,
        workload,
    )
    payload = _classification_payload(
        classification=classification,
        workload_id=workload_key,
        explain=[],
        budget=budget,
        environment=environment,
        workload=workload,
        wall_seconds=wall_seconds,
        baseline_seconds=baseline,
        ratio=ratio,
        absolute_delta=absolute_delta,
        threshold_crossed=threshold_crossed,
    )
    inherited_seconds = baseline_row.get("p2_inherited_seconds")
    inherited_status = str(baseline_row.get("inherited_baseline_status", "INHERITED"))
    if inherited_seconds and float(inherited_seconds) > 0:
        inherited_classification, inherited_threshold, inherited_ratio, inherited_delta = (
            _classify_ratio(
                wall_seconds,
                float(inherited_seconds),
                workload,
            )
        )
        payload["inherited_baseline_comparison"] = {
            "baseline_seconds": round(float(inherited_seconds), 6),
            "baseline_status": inherited_status,
            "classification": inherited_classification,
            "ratio": round(inherited_ratio, 6),
            "absolute_delta_seconds": round(inherited_delta, 6),
            "threshold_crossed": inherited_threshold,
        }
        payload["regression_masking_risk"] = (
            classification == CLASSIFICATION_NORMAL
            and inherited_classification
            in {CLASSIFICATION_REGRESSION, CLASSIFICATION_SEVERE_REGRESSION}
        )
    return payload


def _classify_ratio(
    wall_seconds: float,
    baseline_seconds: float,
    workload: BudgetWorkload,
) -> tuple[str, str | None, float, float]:
    ratio = wall_seconds / baseline_seconds
    absolute_delta = wall_seconds - baseline_seconds
    if ratio >= workload.severe_regression_ratio:
        classification = CLASSIFICATION_SEVERE_REGRESSION
        threshold_crossed = "severe_regression_ratio"
    elif ratio >= workload.regression_ratio:
        classification = CLASSIFICATION_REGRESSION
        threshold_crossed = "regression_ratio"
    elif ratio >= workload.warning_ratio:
        classification = CLASSIFICATION_WARNING
        threshold_crossed = "warning_ratio"
    else:
        classification = CLASSIFICATION_NORMAL
        threshold_crossed = None
    return classification, threshold_crossed, ratio, absolute_delta


def _classification_payload(
    *,
    classification: str,
    workload_id: str | None,
    explain: list[str],
    budget: PerformanceBudget,
    environment: Mapping[str, Any],
    workload: BudgetWorkload | None = None,
    wall_seconds: float | None = None,
    baseline_seconds: float | None = None,
    ratio: float | None = None,
    absolute_delta: float | None = None,
    threshold_crossed: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "telemetry_schema_version": budget.telemetry_schema_version,
        "budget_version": budget.budget_version,
        "classification": classification,
        "gating_policy": budget.gating_policy,
        "maturity_status": budget.maturity_status,
        "workload_id": workload_id,
        "trustworthy_for_action": classification in {
            CLASSIFICATION_NORMAL,
            CLASSIFICATION_WARNING,
            CLASSIFICATION_REGRESSION,
            CLASSIFICATION_SEVERE_REGRESSION,
        },
        "explain": explain,
        "environment_comparison": {
            "observed": dict(environment),
            "compatible": classification
            not in {CLASSIFICATION_INCOMPATIBLE, CLASSIFICATION_NO_BASELINE},
        },
    }
    if workload is not None:
        payload["baseline_identity"] = {
            "workload_id": workload.workload_id,
            "baseline_median_seconds": workload.baseline_median_seconds,
            "baseline_sample_count": workload.baseline_sample_count,
            "reference_workers": workload.reference_workers,
            "reference_test_count": workload.reference_test_count,
        }
        payload["thresholds"] = {
            "warning_ratio": workload.warning_ratio,
            "regression_ratio": workload.regression_ratio,
            "severe_regression_ratio": workload.severe_regression_ratio,
        }
    if wall_seconds is not None:
        payload["observed_wall_seconds"] = round(wall_seconds, 6)
    if baseline_seconds is not None:
        payload["baseline_median_seconds"] = round(baseline_seconds, 6)
    if ratio is not None:
        payload["ratio"] = round(ratio, 6)
        payload["percentage_delta"] = round((ratio - 1.0) * 100.0, 3)
    if absolute_delta is not None:
        payload["absolute_delta_seconds"] = round(absolute_delta, 6)
    if threshold_crossed:
        payload["threshold_crossed"] = threshold_crossed
    return payload


def summarize_variance(samples: list[float]) -> dict[str, float]:
    """Compute variance statistics for benchmark series."""

    if not samples:
        return {}
    ordered = sorted(samples)
    mean = sum(samples) / len(samples)
    median = ordered[len(ordered) // 2]
    if len(ordered) % 2 == 0:
        median = (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2
    if len(samples) > 1:
        variance = sum((value - mean) ** 2 for value in samples) / (len(samples) - 1)
        stdev = math.sqrt(variance)
    else:
        stdev = 0.0
    cv = (stdev / mean) if mean > 0 else 0.0
    return {
        "sample_count": float(len(samples)),
        "min_seconds": min(samples),
        "max_seconds": max(samples),
        "mean_seconds": mean,
        "median_seconds": median,
        "stdev_seconds": stdev,
        "coefficient_of_variation": cv,
    }
