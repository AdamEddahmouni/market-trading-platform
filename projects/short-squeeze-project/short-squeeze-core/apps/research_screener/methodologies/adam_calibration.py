"""Live-screener calibration for Evidence-Gated Prime v1 (weight-floor sweeps)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .adam_v1 import (
    ADAM_POLICY_ID,
    AdamClassificationThresholds,
    DEFAULT_CLASSIFICATION_THRESHOLDS,
    MIN_DIMENSION_WEIGHT,
    evaluate_adam,
)
from .evidence import EvidenceInput

_PROFILE_UNITS = {
    "published_short_interest_pct": "PERCENT",
    "days_to_cover": "DAYS",
    "cost_to_borrow": "PERCENT_ANNUALIZED",
    "borrow_availability_pct_float": "PERCENT_OF_FLOAT",
    "float_shares": "SHARES",
    "current_percentage_change": "PERCENT",
    "relative_volume": "RATIO",
    "completed_bar_acceleration": "PERCENTAGE_POINTS",
    "catalyst_age_hours": "HOURS",
}

LIMITATIONS = (
    {
        "code": "LIVE_METHODOLOGY_EXPLORATION_ONLY",
        "statement": (
            "Adam calibration explores live methodology behavior on representative "
            "evidence profiles; it is not predictive validation."
        ),
    },
    {
        "code": "NO_THRESHOLD_AUTO_PROMOTION",
        "statement": (
            "No floor variant in this report is authorized for automatic promotion "
            "without human review."
        ),
    },
    {
        "code": "SYNTHETIC_PROFILE_WARNING",
        "statement": (
            "Profiles are synthetic admissible-evidence fixtures, not a labeled "
            "historical outcome cohort."
        ),
    },
    {
        "code": "HISTORICAL_POLICY_SEPARATION",
        "statement": (
            "Adam tuning does not change Phase 3B detection or outcome policies."
        ),
    },
)


@dataclass(frozen=True, slots=True)
class ProfileEvaluation:
    profile_id: str
    provider_profile: str
    classification: str
    evaluable: bool
    pressure: float | None
    ignition: float | None
    pressure_supported_weight: int
    ignition_supported_weight: int
    coverage_category: str


@dataclass(frozen=True, slots=True)
class FloorVariantResult:
    min_dimension_weight: int
    profile_results: tuple[ProfileEvaluation, ...]
    evaluable_count: int
    classification_counts: dict[str, int]
    flips_from_baseline: tuple[dict[str, str], ...]


@dataclass(frozen=True, slots=True)
class AdamCalibrationReport:
    experiment_version: str
    methodology_id: str
    baseline_min_dimension_weight: int
    floor_variants: tuple[int, ...]
    limitations: tuple[dict[str, str], ...]
    variant_results: tuple[FloorVariantResult, ...]
    recommendation: dict[str, Any]

    def public_dict(self) -> dict[str, Any]:
        return {
            "experiment_version": self.experiment_version,
            "methodology_id": self.methodology_id,
            "baseline_min_dimension_weight": self.baseline_min_dimension_weight,
            "floor_variants": list(self.floor_variants),
            "limitations": list(self.limitations),
            "variant_results": [
                {
                    "min_dimension_weight": variant.min_dimension_weight,
                    "evaluable_count": variant.evaluable_count,
                    "classification_counts": variant.classification_counts,
                    "flips_from_baseline": list(variant.flips_from_baseline),
                    "profile_results": [asdict(row) for row in variant.profile_results],
                }
                for variant in self.variant_results
            ],
            "recommendation": self.recommendation,
        }


def _evidence_from_profile_row(row: dict[str, Any]) -> EvidenceInput:
    key = str(row["key"])
    unit = _PROFILE_UNITS.get(key)
    if unit is None:
        raise ValueError(f"unsupported profile key: {key}")
    return EvidenceInput(
        key=key,
        value=float(row["value"]),
        unit=unit,
        provider="CalibrationFixture",
        provider_field=key,
        event_time="2026-08-17T12:00:00Z",
        received_time="2026-08-17T12:00:01Z",
        display_available=True,
        research_admissible=True,
        point_in_time_eligible=True,
        fresh=True,
        conflict=bool(row.get("conflict", False)),
        evidence_id=f"calibration:{key}",
        selection_reason="CALIBRATION_FIXTURE",
    )


def _calibration_evidence(
    key: str,
    value: float,
    *,
    conflict: bool = False,
) -> EvidenceInput:
    unit = _PROFILE_UNITS.get(key)
    if unit is None:
        raise ValueError(f"unsupported profile key: {key}")
    return EvidenceInput(
        key=key,
        value=value,
        unit=unit,
        provider="CalibrationFixture",
        provider_field=key,
        event_time="2026-08-17T12:00:00Z",
        received_time="2026-08-17T12:00:01Z",
        display_available=True,
        research_admissible=True,
        point_in_time_eligible=True,
        fresh=True,
        conflict=conflict,
        evidence_id=f"calibration:{key}",
        selection_reason="CALIBRATION_FIXTURE",
    )


def _full_inputs_at_dimension_scores(
    pressure_pct: float,
    ignition_pct: float,
) -> dict[str, EvidenceInput]:
    pct = pressure_pct
    ign = ignition_pct
    return {
        "published_short_interest_pct": _calibration_evidence(
            "published_short_interest_pct", 5 + 25 * pct / 100
        ),
        "days_to_cover": _calibration_evidence("days_to_cover", 1 + 6 * pct / 100),
        "cost_to_borrow": _calibration_evidence("cost_to_borrow", 2 + 48 * pct / 100),
        "borrow_availability_pct_float": _calibration_evidence(
            "borrow_availability_pct_float", 10 - 9.9 * pct / 100
        ),
        "float_shares": _calibration_evidence(
            "float_shares", 50_000_000 - 40_000_000 * pct / 100
        ),
        "current_percentage_change": _calibration_evidence(
            "current_percentage_change", 20 * ign / 100
        ),
        "relative_volume": _calibration_evidence("relative_volume", 1 + 9 * ign / 100),
        "completed_bar_acceleration": _calibration_evidence(
            "completed_bar_acceleration", 5 * ign / 100
        ),
        "catalyst_age_hours": _calibration_evidence(
            "catalyst_age_hours", 12 if ign >= 75 else 48 if ign >= 50 else 73
        ),
    }


def _profile_inputs(profile: dict[str, Any]) -> dict[str, EvidenceInput]:
    score_targets = profile.get("score_targets")
    if isinstance(score_targets, dict):
        pressure_pct = float(score_targets.get("pressure_pct", 0))
        ignition_pct = float(score_targets.get("ignition_pct", 0))
        return _full_inputs_at_dimension_scores(pressure_pct, ignition_pct)

    inputs: dict[str, EvidenceInput] = {}
    for row in profile.get("inputs", []):
        item = _evidence_from_profile_row(row)
        inputs[item.key] = item
    return inputs


def load_experiment(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("experiment fixture must be an object")
    return payload


def evaluate_profile(
    profile: dict[str, Any],
    *,
    min_dimension_weight: int,
    classification_thresholds: AdamClassificationThresholds = DEFAULT_CLASSIFICATION_THRESHOLDS,
) -> ProfileEvaluation:
    result = evaluate_adam(
        _profile_inputs(profile),
        min_dimension_weight=min_dimension_weight,
        classification_thresholds=classification_thresholds,
    )
    coverage = result.evidence_coverage
    return ProfileEvaluation(
        profile_id=str(profile["profile_id"]),
        provider_profile=str(profile.get("provider_profile", "UNKNOWN")),
        classification=str(result.classification),
        evaluable=bool(result.evaluable),
        pressure=result.pressure,
        ignition=result.ignition,
        pressure_supported_weight=int(result.metadata["pressure_supported_weight"]),
        ignition_supported_weight=int(result.metadata["ignition_supported_weight"]),
        coverage_category=str(coverage.get("category", "UNKNOWN")),
    )


def run_weight_floor_sweep(experiment: dict[str, Any]) -> AdamCalibrationReport:
    profiles = experiment.get("profiles", [])
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("experiment profiles must be a non-empty list")

    baseline = int(experiment.get("baseline_min_dimension_weight", MIN_DIMENSION_WEIGHT))
    floors = tuple(int(value) for value in experiment.get("floor_variants", [baseline]))
    if baseline not in floors:
        floors = (*floors, baseline)

    baseline_by_profile: dict[str, str] = {}
    for profile in profiles:
        evaluation = evaluate_profile(profile, min_dimension_weight=baseline)
        baseline_by_profile[evaluation.profile_id] = evaluation.classification

    variant_results: list[FloorVariantResult] = []

    for floor in sorted(set(floors)):
        profile_results: list[ProfileEvaluation] = []
        for profile in profiles:
            evaluation = evaluate_profile(profile, min_dimension_weight=floor)
            profile_results.append(evaluation)

        classification_counts: dict[str, int] = {}
        evaluable_count = 0
        flips: list[dict[str, str]] = []
        for row in profile_results:
            classification_counts[row.classification] = (
                classification_counts.get(row.classification, 0) + 1
            )
            if row.evaluable:
                evaluable_count += 1
            if floor != baseline:
                baseline_cls = baseline_by_profile.get(row.profile_id)
                if baseline_cls and baseline_cls != row.classification:
                    flips.append(
                        {
                            "profile_id": row.profile_id,
                            "baseline_classification": baseline_cls,
                            "variant_classification": row.classification,
                        }
                    )

        variant_results.append(
            FloorVariantResult(
                min_dimension_weight=floor,
                profile_results=tuple(profile_results),
                evaluable_count=evaluable_count,
                classification_counts=classification_counts,
                flips_from_baseline=tuple(flips),
            )
        )

    recommendation = _recommend_floor(baseline, variant_results)
    return AdamCalibrationReport(
        experiment_version=str(experiment.get("experiment_version", "unknown")),
        methodology_id=str(experiment.get("methodology_id", ADAM_POLICY_ID)),
        baseline_min_dimension_weight=baseline,
        floor_variants=tuple(sorted(set(floors))),
        limitations=LIMITATIONS,
        variant_results=tuple(variant_results),
        recommendation=recommendation,
    )


def _recommend_floor(
    baseline: int,
    variants: tuple[FloorVariantResult, ...],
) -> dict[str, Any]:
    baseline_row = next(v for v in variants if v.min_dimension_weight == baseline)
    lower_variants = [v for v in variants if v.min_dimension_weight < baseline]
    higher_variants = [v for v in variants if v.min_dimension_weight > baseline]

    finviz_core = next(
        (
            row
            for row in baseline_row.profile_results
            if row.profile_id == "finviz_pressure_ignition_core"
        ),
        None,
    )
    si_dtc_only = next(
        (
            row
            for row in baseline_row.profile_results
            if row.profile_id == "pressure_si_dtc_only"
        ),
        None,
    )

    retain = finviz_core is not None and finviz_core.evaluable
    reasons: list[str] = []
    rejected_lower: list[int] = []
    rejected_higher: list[int] = []

    if retain:
        reasons.append(
            "Finviz Elite core profile (SI + DTC + float + change + relvol) stays "
            "evaluable at the 65% floor."
        )
    else:
        reasons.append("Baseline floor does not keep finviz_pressure_ignition_core evaluable.")

    if si_dtc_only is not None and not si_dtc_only.evaluable:
        reasons.append(
            "pressure_si_dtc_only remains UNEVALUABLE at baseline (55% pressure weight "
            "without float)."
        )

    for variant in lower_variants:
        if variant.flips_from_baseline:
            rejected_lower.append(variant.min_dimension_weight)
            reasons.append(
                f"Lowering to {variant.min_dimension_weight}% flips "
                f"{len(variant.flips_from_baseline)} profile classification(s) "
                "(e.g. partial pressure without float becomes SUBPRIME)."
            )

    for variant in higher_variants:
        finviz_at_floor = next(
            (
                row
                for row in variant.profile_results
                if row.profile_id == "finviz_pressure_ignition_core"
            ),
            None,
        )
        if finviz_at_floor is not None and not finviz_at_floor.evaluable:
            rejected_higher.append(variant.min_dimension_weight)
            reasons.append(
                f"Raising to {variant.min_dimension_weight}% blocks the Finviz core "
                "profile (supported weight is exactly 65%)."
            )

    return {
        "action": "RETAIN_BASELINE" if retain else "REVIEW_REQUIRED",
        "baseline_min_dimension_weight": baseline,
        "rationale": reasons,
        "rejected_lower_floors": rejected_lower,
        "rejected_higher_floors": rejected_higher,
        "provisional": True,
    }


def render_markdown(report: AdamCalibrationReport) -> str:
    lines = [
        "# Adam Scoring Calibration Report",
        "",
        f"- Experiment: `{report.experiment_version}`",
        f"- Methodology: `{report.methodology_id}`",
        f"- Baseline floor: `{report.baseline_min_dimension_weight}%`",
        "",
        "## Limitations",
        "",
    ]
    for item in report.limitations:
        lines.append(f"- **{item['code']}** — {item['statement']}")
    lines.extend(["", "## Recommendation", "", f"- Action: **{report.recommendation['action']}**"])
    for reason in report.recommendation.get("rationale", []):
        lines.append(f"- {reason}")
    lines.extend(["", "## Floor variants", ""])
    for variant in report.variant_results:
        lines.append(f"### {variant.min_dimension_weight}% minimum dimension weight")
        lines.append("")
        lines.append(f"- Evaluable profiles: {variant.evaluable_count}")
        lines.append(f"- Classification counts: {variant.classification_counts}")
        if variant.flips_from_baseline:
            lines.append(f"- Flips from baseline: {len(variant.flips_from_baseline)}")
            for flip in variant.flips_from_baseline:
                lines.append(
                    f"  - `{flip['profile_id']}`: "
                    f"{flip['baseline_classification']} → {flip['variant_classification']}"
                )
        else:
            lines.append("- Flips from baseline: 0")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_report(report: AdamCalibrationReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.public_dict()
    output_path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    output_path.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")


@dataclass(frozen=True, slots=True)
class ThresholdVariantResult:
    variant_id: str
    thresholds: AdamClassificationThresholds
    profile_results: tuple[ProfileEvaluation, ...]
    evaluable_count: int
    classification_counts: dict[str, int]
    flips_from_baseline: tuple[dict[str, str], ...]


@dataclass(frozen=True, slots=True)
class AdamThresholdCalibrationReport:
    experiment_version: str
    methodology_id: str
    baseline_variant_id: str
    baseline_thresholds: AdamClassificationThresholds
    threshold_variants: tuple[str, ...]
    limitations: tuple[dict[str, str], ...]
    variant_results: tuple[ThresholdVariantResult, ...]
    recommendation: dict[str, Any]

    def public_dict(self) -> dict[str, Any]:
        return {
            "experiment_version": self.experiment_version,
            "methodology_id": self.methodology_id,
            "baseline_variant_id": self.baseline_variant_id,
            "baseline_thresholds": asdict(self.baseline_thresholds),
            "threshold_variants": list(self.threshold_variants),
            "limitations": list(self.limitations),
            "variant_results": [
                {
                    "variant_id": variant.variant_id,
                    "thresholds": asdict(variant.thresholds),
                    "evaluable_count": variant.evaluable_count,
                    "classification_counts": variant.classification_counts,
                    "flips_from_baseline": list(variant.flips_from_baseline),
                    "profile_results": [asdict(row) for row in variant.profile_results],
                }
                for variant in self.variant_results
            ],
            "recommendation": self.recommendation,
        }


def _thresholds_from_variant(row: dict[str, Any]) -> AdamClassificationThresholds:
    baseline = DEFAULT_CLASSIFICATION_THRESHOLDS
    return AdamClassificationThresholds(
        prime_pressure_min=float(row.get("prime_pressure_min", baseline.prime_pressure_min)),
        prime_ignition_min=float(row.get("prime_ignition_min", baseline.prime_ignition_min)),
        subprime_primary_min=float(row.get("subprime_primary_min", baseline.subprime_primary_min)),
        subprime_secondary_min=float(
            row.get("subprime_secondary_min", baseline.subprime_secondary_min)
        ),
        watch_min=float(row.get("watch_min", baseline.watch_min)),
        high_coverage_min=float(row.get("high_coverage_min", baseline.high_coverage_min)),
        moderate_coverage_min=float(row.get("moderate_coverage_min", baseline.moderate_coverage_min)),
        low_coverage_min=float(row.get("low_coverage_min", baseline.low_coverage_min)),
    )


def evaluate_profile_with_thresholds(
    profile: dict[str, Any],
    *,
    min_dimension_weight: int,
    classification_thresholds: AdamClassificationThresholds,
) -> ProfileEvaluation:
    return evaluate_profile(
        profile,
        min_dimension_weight=min_dimension_weight,
        classification_thresholds=classification_thresholds,
    )


def run_classification_threshold_sweep(
    experiment: dict[str, Any],
) -> AdamThresholdCalibrationReport:
    profiles = experiment.get("profiles", [])
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("experiment profiles must be a non-empty list")

    variants_raw = experiment.get("threshold_variants", [])
    if not isinstance(variants_raw, list) or not variants_raw:
        raise ValueError("threshold_variants must be a non-empty list")

    baseline_id = str(
        experiment.get("baseline_variant_id", variants_raw[0].get("variant_id", "baseline"))
    )
    min_floor = int(experiment.get("baseline_min_dimension_weight", MIN_DIMENSION_WEIGHT))

    baseline_thresholds = _thresholds_from_variant(
        next(
            row for row in variants_raw
            if str(row.get("variant_id")) == baseline_id
        )
    )

    baseline_by_profile: dict[str, str] = {}
    for profile in profiles:
        evaluation = evaluate_profile_with_thresholds(
            profile,
            min_dimension_weight=min_floor,
            classification_thresholds=baseline_thresholds,
        )
        baseline_by_profile[evaluation.profile_id] = evaluation.classification

    variant_results: list[ThresholdVariantResult] = []
    variant_ids: list[str] = []

    for row in variants_raw:
        variant_id = str(row.get("variant_id", "unknown"))
        variant_ids.append(variant_id)
        thresholds = _thresholds_from_variant(row)
        profile_results: list[ProfileEvaluation] = []
        for profile in profiles:
            profile_results.append(
                evaluate_profile_with_thresholds(
                    profile,
                    min_dimension_weight=min_floor,
                    classification_thresholds=thresholds,
                )
            )

        classification_counts: dict[str, int] = {}
        evaluable_count = 0
        flips: list[dict[str, str]] = []
        for profile_row in profile_results:
            classification_counts[profile_row.classification] = (
                classification_counts.get(profile_row.classification, 0) + 1
            )
            if profile_row.evaluable:
                evaluable_count += 1
            if variant_id != baseline_id:
                baseline_cls = baseline_by_profile.get(profile_row.profile_id)
                if baseline_cls and baseline_cls != profile_row.classification:
                    flips.append(
                        {
                            "profile_id": profile_row.profile_id,
                            "baseline_classification": baseline_cls,
                            "variant_classification": profile_row.classification,
                        }
                    )

        variant_results.append(
            ThresholdVariantResult(
                variant_id=variant_id,
                thresholds=thresholds,
                profile_results=tuple(profile_results),
                evaluable_count=evaluable_count,
                classification_counts=classification_counts,
                flips_from_baseline=tuple(flips),
            )
        )

    recommendation = _recommend_thresholds(baseline_id, variant_results)
    return AdamThresholdCalibrationReport(
        experiment_version=str(experiment.get("experiment_version", "unknown")),
        methodology_id=str(experiment.get("methodology_id", ADAM_POLICY_ID)),
        baseline_variant_id=baseline_id,
        baseline_thresholds=baseline_thresholds,
        threshold_variants=tuple(variant_ids),
        limitations=LIMITATIONS,
        variant_results=tuple(variant_results),
        recommendation=recommendation,
    )


def _recommend_thresholds(
    baseline_id: str,
    variants: tuple[ThresholdVariantResult, ...],
) -> dict[str, Any]:
    baseline_row = next(v for v in variants if v.variant_id == baseline_id)
    other_variants = [v for v in variants if v.variant_id != baseline_id]

    anchors = {
        "full_provider_prime": "PRIME",
        "finviz_pressure_ignition_core": "SUBPRIME",
        "watch_not_qualified": "NOT_QUALIFIED",
        "subprime_pressure_led": "SUBPRIME",
        "watch_mid": "WATCH",
    }

    baseline_map = {
        row.profile_id: row.classification for row in baseline_row.profile_results
    }
    anchors_ok = True
    reasons: list[str] = []
    rejected_variants: list[str] = []

    for profile_id, expected in anchors.items():
        actual = baseline_map.get(profile_id)
        if actual == expected:
            reasons.append(f"Baseline keeps `{profile_id}` at {expected}.")
        else:
            anchors_ok = False
            reasons.append(
                f"Baseline misclassifies `{profile_id}` as {actual} (expected {expected})."
            )

    for variant in other_variants:
        finviz_flip = next(
            (
                flip
                for flip in variant.flips_from_baseline
                if flip["profile_id"] == "finviz_pressure_ignition_core"
                and flip["variant_classification"] == "PRIME"
            ),
            None,
        )
        prime_flip = next(
            (
                flip
                for flip in variant.flips_from_baseline
                if flip["profile_id"] == "full_provider_prime"
                and flip["baseline_classification"] == "PRIME"
                and flip["variant_classification"] != "PRIME"
            ),
            None,
        )
        watch_flip = next(
            (
                flip
                for flip in variant.flips_from_baseline
                if flip["profile_id"] == "watch_not_qualified"
            ),
            None,
        )

        if finviz_flip:
            rejected_variants.append(variant.variant_id)
            reasons.append(
                f"Reject `{variant.variant_id}` — promotes Finviz core to PRIME without "
                "full provider coverage."
            )

        if prime_flip:
            rejected_variants.append(variant.variant_id)
            reasons.append(
                f"Reject `{variant.variant_id}` — demotes full_provider_prime from PRIME "
                f"to {prime_flip['variant_classification']}."
            )

        if watch_flip:
            rejected_variants.append(variant.variant_id)
            reasons.append(
                f"Reject `{variant.variant_id}` — flips watch_not_qualified: "
                f"{watch_flip['baseline_classification']} → "
                f"{watch_flip['variant_classification']}."
            )

    reasons.append(
        "PRIME requires HIGH coverage (85%+ weight); Finviz-only rows stay SUBPRIME "
        "until borrow/acceleration/catalyst legs arrive."
    )

    return {
        "action": "RETAIN_BASELINE" if anchors_ok else "REVIEW_REQUIRED",
        "baseline_variant_id": baseline_id,
        "rationale": reasons,
        "rejected_variants": rejected_variants,
        "provisional": True,
    }


def render_threshold_markdown(report: AdamThresholdCalibrationReport) -> str:
    lines = [
        "# Adam Classification Threshold Calibration Report",
        "",
        f"- Experiment: `{report.experiment_version}`",
        f"- Methodology: `{report.methodology_id}`",
        f"- Baseline variant: `{report.baseline_variant_id}`",
        "",
        "## Limitations",
        "",
    ]
    for item in report.limitations:
        lines.append(f"- **{item['code']}** — {item['statement']}")
    lines.extend(
        ["", "## Recommendation", "", f"- Action: **{report.recommendation['action']}**"]
    )
    for reason in report.recommendation.get("rationale", []):
        lines.append(f"- {reason}")
    lines.extend(["", "## Threshold variants", ""])
    for variant in report.variant_results:
        lines.append(f"### {variant.variant_id}")
        lines.append("")
        lines.append(f"- Evaluable profiles: {variant.evaluable_count}")
        lines.append(f"- Classification counts: {variant.classification_counts}")
        if variant.flips_from_baseline:
            lines.append(f"- Flips from baseline: {len(variant.flips_from_baseline)}")
            for flip in variant.flips_from_baseline:
                lines.append(
                    f"  - `{flip['profile_id']}`: "
                    f"{flip['baseline_classification']} → {flip['variant_classification']}"
                )
        else:
            lines.append("- Flips from baseline: 0")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_threshold_report(report: AdamThresholdCalibrationReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.public_dict()
    output_path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    output_path.with_suffix(".md").write_text(
        render_threshold_markdown(report), encoding="utf-8"
    )


__all__ = [
    "AdamCalibrationReport",
    "AdamThresholdCalibrationReport",
    "evaluate_profile",
    "evaluate_profile_with_thresholds",
    "load_experiment",
    "render_markdown",
    "render_threshold_markdown",
    "run_classification_threshold_sweep",
    "run_weight_floor_sweep",
    "write_report",
    "write_threshold_report",
]
