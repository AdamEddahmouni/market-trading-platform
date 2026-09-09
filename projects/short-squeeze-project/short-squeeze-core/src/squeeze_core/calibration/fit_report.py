"""Phase 4 item 1.3 — feasibility gates and the NOT_CALIBRATED report skeleton.

This module is the reporting half of sprint item 1.3
(``docs/research/SHORT_SQUEEZE_SPRINT_PLAN_2026-09-06.md`` §1.3). It implements the
**feasibility-gate ladder** of the preregistration §8.1 and the report structure that
carries a failing ladder to the owner honestly — with the failing gate(s) named and
``RESEARCH_ONLY`` retention made explicit.

This is a **skeleton, not a fit**: no model is estimated, no probability is produced,
and no fitted threshold exists. If — and only if — every feasibility gate passes does
this module hand off to the (not yet implemented) fitting stage; the preregistration
§10 open items (O-2/O-3/O-4/O-6) remain gating inputs regardless of what this code
evaluates structurally. The gate inputs (dataset labels, fold plan) are committed
fixtures and the 1.2 harness output; they are not re-derived here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from squeeze_core.calibration.walkforward import WalkForwardDiagnostics

if TYPE_CHECKING:  # pragma: no cover
    from squeeze_core.research.models import ResearchDataset

#: Version of the reporting skeleton itself.
FIT_REPORT_VERSION = "phase_4_fit_report_skeleton.v1"
#: Preregistration this report is accountable to.
PREREGISTRATION_VERSION = "phase_4_calibration_preregistration.v0.6-draft"

#: Preregistered minimum for F-1 (evaluable positives) and F-2 (evaluable
#: negatives) — preregistration §8.1.
MINIMUM_POSITIVE_EVENTS = 10
MINIMUM_NEGATIVE_EVENTS = 10

#: Preregistered minimum for F-3 — the walk-forward harness §7 degeneracy floor.
MINIMUM_NON_EMPTY_EVALUATION_FOLDS = 2


class HorizonSlotStatus(StrEnum):
    """Status of a horizon slot in ``HorizonModelSnapshot.hazard_by_horizon``.

    Uses exactly the snapshot contract's vocabulary (`RESEARCH_ONLY |
    CALIBRATED`, ``src/squeeze_core/intelligence/contracts.py``): a slot may
    only become ``CALIBRATED`` through the item 1.4 wiring after the gates pass
    and the owner-gated fitting stage succeeds — nothing is force-flipped
    (preregistration §2.3, §8.2).
    """

    CALIBRATED = "CALIBRATED"
    RESEARCH_ONLY = "RESEARCH_ONLY"


class Phase4Verdict(StrEnum):
    """The overall Phase 4 result reported to the owner (preregistration §8.2)."""

    NOT_CALIBRATED = "NOT_CALIBRATED"


class FeasibilityGateId(StrEnum):
    """The preregistered feasibility gates (preregistration §8.1)."""

    F1_EVALUABLE_POSITIVES = "F-1"
    F2_EVALUABLE_NEGATIVES = "F-2"
    F3_FOLD_STRUCTURE = "F-3"
    F4_HORIZON_DATA = "F-4"


class EvaluationStatus(StrEnum):
    """Whether a gate could be evaluated structurally."""

    EVALUATED = "EVALUATED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class FeasibilityGateResult(BaseModel):
    """One gate's structural verdict plus the inputs it was measured on."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gate_id: FeasibilityGateId
    description: str
    threshold: str
    status: EvaluationStatus
    passed: bool | None = None
    observed: str
    """Human-readable measurement, e.g. ``"3 positives < 10 required"``."""
    inputs: dict[str, str] = Field(default_factory=dict)
    """Provenance of the measurement (fixture / diagnostics report names)."""


class OutcomeCounts(BaseModel):
    """Historical outcome-label counts, measured from the committed dataset.

    Mapping to the calibration target (preregistration §3): ``Y_1 = 1`` iff the
    label is ``SUBSTANTIAL_UPWARD_MOVE`` (the +25%/24 h upward predicate). The
    downward predicate is retained for continuity but is not the squeeze target.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    positive_y1: int = Field(ge=0)
    negative_y1: int = Field(ge=0)
    downward_mirror: int = Field(ge=0)
    unevaluable: int = Field(ge=0)
    total_evaluable: int = Field(ge=0)
    unique_symbols: int = Field(ge=0)

    @property
    def positive_base_rate(self) -> float | None:
        """Empirical positive rate over evaluable rows; ``None`` if empty."""
        if self.total_evaluable == 0:
            return None
        return self.positive_y1 / self.total_evaluable


class HorizonCoverage(BaseModel):
    """Per-horizon coverage under the O-1 gate (preregistration §3, §8.1 F-4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizon_days: int
    owned_forward_path_data: bool
    slot_status: HorizonSlotStatus


class FitReportSkeleton(BaseModel):
    """The item 1.3 report contract: gates, coverage, verdict, retention.

    Deliberately carries **no probabilities, no metrics, no fitted
    parameters** — a fit result can only be attached by the (owner-gated)
    fitting stage once every feasibility gate passes and §10 is locked.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    fit_report_version: str = FIT_REPORT_VERSION
    preregistration_version: str = PREREGISTRATION_VERSION
    walk_forward_diagnostics_version: str = "phase_4_walkforward_harness.v1"

    dataset_counts: OutcomeCounts
    feasibility_gates: tuple[FeasibilityGateResult, ...]
    horizon_coverage: tuple[HorizonCoverage, ...]

    all_feasibility_gates_passed: bool
    """True iff every **structurally decidable** gate (F-1..F-3) passed.

    F-4 is an owner data-feasibility statement (O-1) recorded with
    ``passed=None``; it constrains which horizons may be calibrated but never
    fails the ladder by itself.
    """
    verdict: Phase4Verdict = Phase4Verdict.NOT_CALIBRATED
    failing_gates: tuple[FeasibilityGateId, ...] = ()
    unevaluated_gates: tuple[FeasibilityGateId, ...] = ()

    research_only_retained: bool = True
    fit_attempted: bool = False
    fit_blocked_by: tuple[str, ...] = Field(default_factory=tuple)
    """Preregistration §10 open items that still block any fit (O-2/O-3/O-4/O-6)."""

    notes: tuple[str, ...] = Field(default_factory=tuple)
    limitations: tuple[str, ...] = Field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Gate ladder
# ---------------------------------------------------------------------------


def _counts_from_rows(rows: Iterable[Any]) -> OutcomeCounts:
    """Measure historical outcome counts from dataset rows.

    Rows are historical iff ``case_type is not SYNTHETIC_EDGE_CASE`` (ADR-0053
    synthetic evaluations are excluded from historical analysis by policy).
    Only ``case_type``, ``symbol``, and ``outcome_label`` are read, so tests may
    pass lightweight stand-ins for :class:`ResearchDatasetRow`.

    The mapping to ``Y_1`` follows preregistration §3: only
    ``SUBSTANTIAL_UPWARD_MOVE`` is a positive; ``NO_SUBSTANTIAL_UPWARD_MOVE`` is
    the negative class; ``SUBSTANTIAL_DOWNWARD_MOVE`` is the retained mirror,
    not the squeeze target; ``MIXED_OR_VOLATILE`` / ``OUTCOME_UNKNOWN`` /
    ``OUTCOME_INSUFFICIENT_DATA`` are unevaluable for this target.
    """
    from squeeze_core.research.models import (
        CandidateCaseType,
        OutcomeLabel,
    )

    positives = negatives = mirror = unevaluable = 0
    symbols: set[str] = set()
    for row in rows:
        if row.case_type is CandidateCaseType.SYNTHETIC_EDGE_CASE:
            continue
        symbols.add(row.symbol.strip().upper())
        if row.outcome_label is OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE:
            positives += 1
        elif row.outcome_label is OutcomeLabel.NO_SUBSTANTIAL_UPWARD_MOVE:
            negatives += 1
        elif row.outcome_label is OutcomeLabel.SUBSTANTIAL_DOWNWARD_MOVE:
            mirror += 1
        else:
            unevaluable += 1
    return OutcomeCounts(
        positive_y1=positives,
        negative_y1=negatives,
        downward_mirror=mirror,
        unevaluable=unevaluable,
        total_evaluable=positives + negatives,
        unique_symbols=len(symbols),
    )


def _counts_from_dataset(dataset: "ResearchDataset") -> OutcomeCounts:
    """Measure outcome counts from a deserialized :class:`ResearchDataset`."""
    return _counts_from_rows(dataset.rows)


def _gate_f1(counts: OutcomeCounts) -> FeasibilityGateResult:
    passed = counts.positive_y1 >= MINIMUM_POSITIVE_EVENTS
    return FeasibilityGateResult(
        gate_id=FeasibilityGateId.F1_EVALUABLE_POSITIVES,
        description="evaluable positives (Y_1 = 1 at horizon 1)",
        threshold=f">= {MINIMUM_POSITIVE_EVENTS}",
        status=EvaluationStatus.EVALUATED,
        passed=passed,
        observed=(
            f"{counts.positive_y1} positives "
            f"{'>=' if passed else '<'} {MINIMUM_POSITIVE_EVENTS} required"
        ),
        inputs={
            "source": "tests/fixtures/research/phase_3b_research_dataset.json",
            "mapping": "outcome_label SUBSTANTIAL_UPWARD_MOVE -> Y_1 = 1 (prereg §3)",
        },
    )


def _gate_f2(counts: OutcomeCounts) -> FeasibilityGateResult:
    passed = counts.negative_y1 >= MINIMUM_NEGATIVE_EVENTS
    return FeasibilityGateResult(
        gate_id=FeasibilityGateId.F2_EVALUABLE_NEGATIVES,
        description="evaluable negatives (Y_1 = 0 at horizon 1)",
        threshold=f">= {MINIMUM_NEGATIVE_EVENTS}",
        status=EvaluationStatus.EVALUATED,
        passed=passed,
        observed=(
            f"{counts.negative_y1} negatives "
            f"{'>=' if passed else '<'} {MINIMUM_NEGATIVE_EVENTS} required"
        ),
        inputs={
            "source": "tests/fixtures/research/phase_3b_research_dataset.json",
            "mapping": "outcome_label NO_SUBSTANTIAL_UPWARD_MOVE -> Y_1 = 0 (prereg §3)",
        },
    )


def _gate_f3(diagnostics: WalkForwardDiagnostics) -> FeasibilityGateResult:
    non_empty = diagnostics.non_empty_evaluation_fold_count
    passed = non_empty >= MINIMUM_NON_EMPTY_EVALUATION_FOLDS
    return FeasibilityGateResult(
        gate_id=FeasibilityGateId.F3_FOLD_STRUCTURE,
        description="non-empty chronological evaluation folds (prereg §7)",
        threshold=f">= {MINIMUM_NON_EMPTY_EVALUATION_FOLDS}",
        status=EvaluationStatus.EVALUATED,
        passed=passed,
        observed=f"{non_empty} non-empty evaluation folds "
        f"{'>=' if passed else '<'} {MINIMUM_NON_EMPTY_EVALUATION_FOLDS} required",
        inputs={"source": "reports/calibration/phase_4_walk_forward_plan.json"},
    )


def _gate_f4(
    owned_horizons: frozenset[int] = frozenset({1}),
) -> tuple[FeasibilityGateResult, tuple[HorizonCoverage, ...]]:
    """F-4: horizon-data coverage (O-1).

    ``owned_horizons`` lists horizons with owned forward-path data. Only
    horizon 1 is directly supportable while O-1 is open (prereg §2.3 — every
    owned outcome label carries ``horizon = 24_HOURS``); the multi-day slots
    stay ``RESEARCH_ONLY``. F-4 is recorded with ``passed=None``: it is an
    owner data-feasibility statement, not a dataset measurement, so it cannot
    pass or fail structurally — it constrains which horizons may be calibrated.
    """
    # While the report is a skeleton (no fit), every slot stays RESEARCH_ONLY
    # in the snapshot contract's vocabulary; ``owned_forward_path_data``
    # records *why* a slot cannot calibrate (no data at all vs. no fit yet).
    coverage = tuple(
        HorizonCoverage(
            horizon_days=horizon,
            owned_forward_path_data=horizon in owned_horizons,
            slot_status=HorizonSlotStatus.RESEARCH_ONLY,
        )
        for horizon in (1, 3, 5, 10, 20)
    )
    multi_day_owned = sorted(h for h in owned_horizons if h > 1)
    gate = FeasibilityGateResult(
        gate_id=FeasibilityGateId.F4_HORIZON_DATA,
        description="owned forward-path data for any horizon k > 1 to be calibrated (O-1)",
        threshold="owned multi-day forward paths for each calibrated horizon k > 1",
        status=EvaluationStatus.EVALUATED,
        passed=None,
        observed=(
            "no owned multi-day forward-path data (O-1 open): horizons 3/5/10/20 "
            "stay RESEARCH_ONLY; only horizon 1 is directly supportable"
            if not multi_day_owned
            else f"owned multi-day horizons: {multi_day_owned}"
        ),
        inputs={
            "source": "tests/fixtures/research/*_outcome_observation.json (horizon=24_HOURS)",
            "rule": "no backfill into unsupported horizons (prereg §2.3)",
        },
    )
    return gate, coverage


def evaluate_feasibility_gates(
    counts: OutcomeCounts,
    diagnostics: WalkForwardDiagnostics,
    *,
    owned_multi_day_horizons: frozenset[int] = frozenset(),
) -> tuple[tuple[FeasibilityGateResult, ...], tuple[HorizonCoverage, ...]]:
    """Run the preregistered feasibility ladder in §8.1 order (F-1..F-4).

    Returns the gate results and the per-horizon coverage implied by F-4.
    """
    f4_gate, coverage = _gate_f4(
        owned_horizons=frozenset({1}) | owned_multi_day_horizons
    )
    return (
        _gate_f1(counts),
        _gate_f2(counts),
        _gate_f3(diagnostics),
        f4_gate,
    ), coverage


def build_fit_report_skeleton(
    counts: OutcomeCounts,
    diagnostics: WalkForwardDiagnostics,
    *,
    owned_multi_day_horizons: frozenset[int] = frozenset(),
) -> FitReportSkeleton:
    """Build the item 1.3 report skeleton from measured gate inputs.

    The verdict is ``NOT_CALIBRATED`` iff any F-gate fails (prereg §8.2); with
    the committed cohort that is the honest default. No fitting is attempted
    here and no probability is produced; ``fit_blocked_by`` carries the §10
    open items that gate the fitting stage itself.
    """
    gates, coverage = evaluate_feasibility_gates(
        counts, diagnostics, owned_multi_day_horizons=owned_multi_day_horizons
    )
    failing = tuple(
        gate.gate_id
        for gate in gates
        if gate.status is EvaluationStatus.EVALUATED and gate.passed is False
    )
    unevaluated = tuple(
        gate.gate_id
        for gate in gates
        if gate.status is EvaluationStatus.NOT_EVALUABLE or gate.passed is None
    )

    if failing:
        failing_names = ", ".join(gate.value for gate in failing)
        notes: tuple[str, ...] = (
            f"Feasibility gate(s) failed: {failing_names}. The Phase 4 result is "
            "reported as NOT_CALIBRATED with the failing gate(s) named "
            "(preregistration §8.2); the evaluator's RESEARCH_ONLY slots are "
            "retained and nothing is force-flipped to CALIBRATED.",
        )
    elif unevaluated:
        unevaluated_names = ", ".join(gate.value for gate in unevaluated)
        notes = (
            f"All structurally decidable feasibility gates pass. Gate(s) "
            f"{unevaluated_names} are owner data-feasibility statements (O-1), "
            "recorded with passed=None: multi-day slots stay RESEARCH_ONLY "
            "regardless. The fitting stage remains blocked on preregistration "
            "§10 (O-2/O-3/O-4/O-6).",
        )
    else:
        notes = (
            "All feasibility gates pass structurally. This report is a skeleton: "
            "the fitting stage remains blocked on preregistration §10 "
            "(O-2/O-3/O-4/O-6 owner/reviewer confirmations).",
        )

    limitations = (
        "HISTORICAL_CASE_BOUNDARIES_NOT_INDEPENDENT",
        "DETECTION_EVALUABILITY_LIMITED",
        "SINGLE_HORIZON_SUPPORTABLE_WHILE_O1_OPEN",
        "COUNTERFACTUAL_EXPLORATION_ONLY",
        "SMALL_SAMPLE_WARNING",
        "REPORT_SKELETON_NO_FIT_NO_PROBABILITY",
    )

    blocked = (
        "O-2: regime cutpoints + purge/embargo addendum — reviewer confirmation pending",
        "O-3: feature table addendum — reviewer confirmation pending",
        "O-4: reference cost set addendum — owner confirmation pending",
        "O-6: preregistration owner review (status -> approved or amended) pending",
    )
    if failing:
        blocked = (
            *blocked,
            "feasibility: " + ", ".join(gate.value for gate in failing),
        )

    return FitReportSkeleton(
        dataset_counts=counts,
        feasibility_gates=gates,
        horizon_coverage=coverage,
        all_feasibility_gates_passed=not failing,
        verdict=Phase4Verdict.NOT_CALIBRATED,
        failing_gates=failing,
        unevaluated_gates=unevaluated,
        research_only_retained=True,
        fit_attempted=False,
        fit_blocked_by=blocked,
        notes=notes,
        limitations=limitations,
    )


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_fit_report_markdown(report: FitReportSkeleton) -> str:
    """Render the skeleton as the committed item 1.3 Markdown report."""
    lines: list[str] = [
        "# Phase 4 — Baseline fit report (item 1.3)",
        "",
        f"- Report: `{report.fit_report_version}`",
        f"- Preregistration: `{report.preregistration_version}`",
        f"- Walk-forward diagnostics: `{report.walk_forward_diagnostics_version}`",
        f"- Verdict: **{report.verdict.value}**",
        f"- RESEARCH_ONLY retained: **{'yes' if report.research_only_retained else 'no'}**",
        f"- Fit attempted: **{'yes' if report.fit_attempted else 'no'}**",
        "",
        "## Outcome counts (historical rows only; SYN excluded per ADR-0053)",
        "",
        "| Quantity | Count |",
        "|---|---:|",
        f"| Positives (Y_1 = 1, upward predicate) | {report.dataset_counts.positive_y1} |",
        f"| Negatives (Y_1 = 0) | {report.dataset_counts.negative_y1} |",
        f"| Downward mirror (not the squeeze target) | {report.dataset_counts.downward_mirror} |",
        f"| Unevaluable for this target | {report.dataset_counts.unevaluable} |",
        f"| Total evaluable | {report.dataset_counts.total_evaluable} |",
        f"| Unique symbols | {report.dataset_counts.unique_symbols} |",
    ]
    base_rate = report.dataset_counts.positive_base_rate
    lines.append(
        f"| Positive base rate | {base_rate:.4f} |" if base_rate is not None
        else "| Positive base rate | n/a |"
    )
    lines += [
        "",
        "## Feasibility gates (preregistration §8.1)",
        "",
        "| Gate | Rule | Observed | Verdict |",
        "|---|---|---|---|",
    ]
    for gate in report.feasibility_gates:
        if gate.status is EvaluationStatus.NOT_EVALUABLE or gate.passed is None:
            verdict = "NOT_EVALUABLE (owner data feasibility, O-1)"
        elif gate.passed:
            verdict = "PASS"
        else:
            verdict = "**FAIL**"
        lines.append(
            f"| {gate.gate_id.value} | {gate.description} — {gate.threshold} | "
            f"{gate.observed} | {verdict} |"
        )
    lines += ["", "## Horizon coverage (prereg §2.3 no-backfill rule)", ""]
    for coverage in report.horizon_coverage:
        lines.append(
            f"- Horizon {coverage.horizon_days:>2}d: "
            f"owned data = {'yes' if coverage.owned_forward_path_data else 'no'} — "
            f"slot status `{coverage.slot_status.value}`"
        )
    lines += ["", "## Notes", ""]
    for note in report.notes:
        lines.append(f"- {note}")
    lines += ["", "## Fit blockers (preregistration §10)", ""]
    for blocker in report.fit_blocked_by:
        lines.append(f"- {blocker}")
    lines += ["", "## Limitations", ""]
    for limitation in report.limitations:
        lines.append(f"- {limitation}")
    lines += [
        "",
        "This is a reporting skeleton, not a fit result: no model was estimated and no "
        "probability was produced. Fitting starts only when every feasibility gate "
        "passes **and** preregistration §10 is locked; until then "
        "`HorizonModelSnapshot.hazard_by_horizon` slots stay `RESEARCH_ONLY`.",
        "",
    ]
    return "\n".join(lines)
