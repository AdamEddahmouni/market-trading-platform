"""Calibration diagnostics without fitting (BUILD 16)."""

from __future__ import annotations

from .provenance import probability_for_view, validate_evaluated_probability
from .types import CalibrationDiagnostics, EvaluationCohortRow, EvaluationSpec, ReliabilityBin


def reliability_bin_boundaries(bin_count: int) -> tuple[tuple[float, float], ...]:
    width = 1.0 / bin_count
    boundaries: list[tuple[float, float]] = []
    for index in range(bin_count):
        lower = index * width
        upper = lower + width
        if index == bin_count - 1:
            boundaries.append((lower, upper))
        else:
            boundaries.append((lower, upper))
    return tuple(boundaries)


def assign_bin(probability: float, boundaries: tuple[tuple[float, float], ...]) -> int:
    for index, (lower, upper) in enumerate(boundaries):
        if index == len(boundaries) - 1:
            if lower <= probability <= upper:
                return index
        elif lower <= probability < upper:
            return index
    return len(boundaries) - 1


def compute_calibration_diagnostics(
    rows: tuple[EvaluationCohortRow, ...],
    spec: EvaluationSpec,
) -> CalibrationDiagnostics | None:
    if not rows:
        return None

    boundaries = reliability_bin_boundaries(spec.calibration_bin_count)
    bin_probs: list[list[float]] = [[] for _ in boundaries]
    bin_labels: list[list[int]] = [[] for _ in boundaries]

    for row in rows:
        probability = probability_for_view(row.forecast, spec.probability_view)
        if probability is None or row.binary_label is None:
            continue
        p = validate_evaluated_probability(probability)
        index = assign_bin(p, boundaries)
        bin_probs[index].append(p)
        bin_labels[index].append(row.binary_label)

    bins: list[ReliabilityBin] = []
    total = sum(len(values) for values in bin_probs)
    if total == 0:
        return None

    ece = 0.0
    mce = 0.0
    for index, (lower, upper) in enumerate(boundaries):
        count = len(bin_probs[index])
        if count == 0:
            bins.append(
                ReliabilityBin(
                    lower=lower,
                    upper=upper,
                    count=0,
                    mean_predicted_probability=None,
                    empirical_positive_rate=None,
                    calibration_gap=None,
                )
            )
            continue
        mean_p = sum(bin_probs[index]) / count
        empirical = sum(bin_labels[index]) / count
        gap = abs(mean_p - empirical)
        weight = count / total
        ece += weight * gap
        mce = max(mce, gap)
        bins.append(
            ReliabilityBin(
                lower=lower,
                upper=upper,
                count=count,
                mean_predicted_probability=mean_p,
                empirical_positive_rate=empirical,
                calibration_gap=gap,
            )
        )

    decomposition = _brier_decomposition(rows, spec, boundaries)
    return CalibrationDiagnostics(
        bins=tuple(bins),
        ece=ece,
        mce=mce,
        brier_reliability=decomposition.get("reliability"),
        brier_resolution=decomposition.get("resolution"),
        brier_uncertainty=decomposition.get("uncertainty"),
    )


def _brier_decomposition(
    rows: tuple[EvaluationCohortRow, ...],
    spec: EvaluationSpec,
    boundaries: tuple[tuple[float, float], ...],
) -> dict[str, float]:
    pairs: list[tuple[float, int]] = []
    for row in rows:
        probability = probability_for_view(row.forecast, spec.probability_view)
        if probability is None or row.binary_label is None:
            continue
        p = validate_evaluated_probability(probability)
        pairs.append((p, row.binary_label))
    if not pairs:
        return {}
    overall_rate = sum(y for _, y in pairs) / len(pairs)
    uncertainty = overall_rate * (1.0 - overall_rate)
    reliability = 0.0
    resolution = 0.0
    total = len(pairs)
    for index in range(len(boundaries)):
        members = [
            (p, y)
            for p, y in pairs
            if assign_bin(p, boundaries) == index
        ]
        if not members:
            continue
        n_k = len(members)
        mean_p = sum(p for p, _ in members) / n_k
        mean_y = sum(y for _, y in members) / n_k
        reliability += (n_k / total) * (mean_p - mean_y) ** 2
        resolution += (n_k / total) * (mean_y - overall_rate) ** 2
    return {
        "reliability": reliability,
        "resolution": resolution,
        "uncertainty": uncertainty,
    }


__all__ = [
    "assign_bin",
    "compute_calibration_diagnostics",
    "reliability_bin_boundaries",
]
