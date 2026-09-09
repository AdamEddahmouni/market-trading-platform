"""Phase 4 walk-forward scaffold: folds, regimes, purge/embargo — no fitting.

Implements the pre-registered walk-forward *split machinery* from
[phase-4-calibration-preregistration.md](../../../docs/phase-4-calibration-preregistration.md)
(§2.2 dependence rule, §6 regime slices, §7 purge/embargo and degeneracy gate)
and the fixed cutpoints from
[phase-4-calibration-regime-cutpoints-addendum.md](../../../docs/phase-4-calibration-regime-cutpoints-addendum.md)
(open item O-2: purge 30 / embargo 15 calendar days; four exhaustive half-open
UTC regime slices).

This module is **outcome-blind machinery**: it orders and partitions labeled
boundaries and reports their structure. It never fits a model, never produces a
probability, and never consumes outcome labels. Fitting is gated on the
preregistration's open items (O-2/O-3/O-4 confirmations, O-6 owner review) —
sprint item 1.2 builds this scaffold; item 1.3 does the first fit.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from squeeze_core.research.models import RetrospectiveOutcomeObservation

# ---------------------------------------------------------------------------
# Pre-registered constants (phase-4-calibration-regime-cutpoints-addendum.md)
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"
HARNESS_VERSION = "phase_4_walkforward_harness.v1"
PREREGISTRATION_VERSION = "phase_4_calibration_preregistration.v0.6-draft"

#: Purge window ``w`` — 30 calendar days per training boundary (O-2 addendum §4).
PURGE_CALENDAR_DAYS = 30
#: Embargo window ``e`` — 15 calendar days per training boundary (O-2 addendum §4).
EMBARGO_CALENDAR_DAYS = 15

#: A fold plan is degenerate below two non-empty evaluation folds (prereg §7).
MINIMUM_NON_EMPTY_EVALUATION_FOLDS = 2


class RegimeSlice(StrEnum):
    """Exhaustive, half-open ``[start, end)`` UTC slices (O-2 addendum §3)."""

    PRE_2020 = "PRE_2020"
    MEME_REGIME = "MEME_REGIME"
    HIGH_RATE = "HIGH_RATE"
    POST_NORMALIZATION = "POST_NORMALIZATION"
    UNASSIGNED = "UNASSIGNED"


class _RegimeCutpoint(BaseModel):
    """Immutable half-open interval for one regime slice."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    regime: RegimeSlice
    start: datetime | None
    end: datetime | None

    @model_validator(mode="after")
    def require_aware_bounds(self) -> "_RegimeCutpoint":
        for bound in (self.start, self.end):
            if bound is not None and bound.tzinfo is None:
                raise ValueError("regime cutpoints must be timezone-aware")
        return self

    def contains(self, value: datetime) -> bool:
        if value.tzinfo is None:
            raise ValueError("boundary time must be timezone-aware")
        if self.start is not None and value < self.start:
            return False
        if self.end is not None and value >= self.end:
            return False
        return True


def _aware(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


#: Half-open ``[start, end)`` intervals; a boundary exactly at a cutpoint
#: belongs to the later slice (O-2 addendum §3 membership rule).
REGIME_CUTPOINTS: tuple[_RegimeCutpoint, ...] = (
    _RegimeCutpoint(regime=RegimeSlice.PRE_2020, start=None, end=_aware(2020, 1, 1)),
    _RegimeCutpoint(
        regime=RegimeSlice.MEME_REGIME, start=_aware(2020, 1, 1), end=_aware(2022, 3, 16)
    ),
    _RegimeCutpoint(
        regime=RegimeSlice.HIGH_RATE, start=_aware(2022, 3, 16), end=_aware(2024, 9, 18)
    ),
    _RegimeCutpoint(
        regime=RegimeSlice.POST_NORMALIZATION, start=_aware(2024, 9, 18), end=None
    ),
)


def regime_slice_for_boundary(boundary_time: datetime) -> RegimeSlice:
    """Assign the pre-registered regime slice for one boundary time.

    Intervals are half-open ``[start, end)`` at UTC; a boundary exactly equal to
    a cutpoint belongs to the later slice. A naive (timezone-unaware) input is
    rejected — boundary times are aware UTC throughout this codebase.
    """
    for cutpoint in REGIME_CUTPOINTS:
        if cutpoint.contains(boundary_time):
            return cutpoint.regime
    return RegimeSlice.UNASSIGNED


# ---------------------------------------------------------------------------
# Inputs and outputs
# ---------------------------------------------------------------------------


class WalkForwardInputError(ValueError):
    """Raised when the labeled boundary set cannot be split walk-forward."""


class BoundaryObservation(BaseModel):
    """One labeled boundary: the unit the harness orders and partitions.

    Carries identity, ordering, and grouping data only — **no outcome label**.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    symbol: str
    boundary_time: datetime
    source_path: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        return normalized

    @field_validator("boundary_time")
    @classmethod
    def require_aware_boundary(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("boundary_time must be timezone-aware")
        return value


class FoldPlan(BaseModel):
    """One chronological fold: boundary indices, symbols, and exclusion windows.

    Indices address the chronologically ordered boundary list produced by
    :func:`plan_walk_forward_folds`; they are stable for a given ordered input
    set, which keeps the plan serializable and auditable.

    Window fields, relative to the evaluation window start ``E``:

    - ``purge_window`` ``[E - w, E)`` — clears the longest pre-registered label
      window (20 trading days ≈ 28 calendar days) before the fold (O-2 §4);
    - ``embargo_window`` ``[E - w - e, E - w)`` — additional serial-correlation
      buffer beyond the purge; it **precedes the purge window in absolute time**.

    A training boundary at time ``t`` is admissible iff ``t < E - (w + e)``
    (its label window plus embargo buffer clear before the fold starts).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    fold_index: int
    train_boundary_indices: tuple[int, ...]
    evaluation_boundary_indices: tuple[int, ...]
    train_window_start: datetime
    train_window_end: datetime
    purge_window_start: datetime
    purge_window_end: datetime
    embargo_window_start: datetime
    embargo_window_end: datetime
    train_symbols: tuple[str, ...]
    evaluation_symbols: tuple[str, ...]
    regimes_in_fold: tuple[RegimeSlice, ...] = ()


class WalkForwardPlan(BaseModel):
    """The full fold plan plus the partition's structural verdicts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SCHEMA_VERSION
    harness_version: str = HARNESS_VERSION
    preregistration_version: str = PREREGISTRATION_VERSION
    purge_calendar_days: int = PURGE_CALENDAR_DAYS
    embargo_calendar_days: int = EMBARGO_CALENDAR_DAYS
    folds: tuple[FoldPlan, ...]
    symbol_groups: tuple[tuple[str, ...], ...] = ()
    regime_counts: dict[RegimeSlice, int] = Field(default_factory=dict)
    empty_regimes: tuple[RegimeSlice, ...] = ()
    degenerate: bool = False
    degeneracy_reason: str | None = None

    @field_validator("folds")
    @classmethod
    def non_empty_folds(cls, value: tuple[FoldPlan, ...]) -> tuple[FoldPlan, ...]:
        if not value:
            raise ValueError("a walk-forward plan requires at least one fold")
        return value


class WalkForwardFoldDiagnostics(BaseModel):
    """Structural diagnostics for one fold. **No probabilities, no metrics.**"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fold_index: int
    train_boundary_count: int
    evaluation_boundary_count: int
    train_symbol_count: int
    evaluation_symbol_count: int
    train_symbol_overlap: tuple[str, ...] = ()
    purge_days: int = PURGE_CALENDAR_DAYS
    embargo_days: int = EMBARGO_CALENDAR_DAYS


class WalkForwardDiagnostics(BaseModel):
    """Aggregate structural diagnostics over the whole plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SCHEMA_VERSION
    harness_version: str = HARNESS_VERSION
    preregistration_version: str = PREREGISTRATION_VERSION
    boundary_count: int
    symbol_count: int
    fold_count: int
    non_empty_evaluation_fold_count: int
    folds_with_empty_training: int
    degenerate: bool
    degeneracy_reason: str | None
    purge_calendar_days: int = PURGE_CALENDAR_DAYS
    embargo_calendar_days: int = EMBARGO_CALENDAR_DAYS
    regime_counts: dict[RegimeSlice, int] = Field(default_factory=dict)
    empty_regimes: tuple[RegimeSlice, ...] = ()
    folds: tuple[WalkForwardFoldDiagnostics, ...]
    limitations: tuple[str, ...] = ()


#: Limitation codes carried on every diagnostics report (prereg §2.2/§2.3).
WALK_FORWARD_LIMITATIONS: tuple[str, ...] = (
    "HISTORICAL_CASE_BOUNDARIES_NOT_INDEPENDENT",
    "DETECTION_EVALUABILITY_LIMITED",
    "SINGLE_HORIZON_SUPPORTABLE_WHILE_O1_OPEN",
    "STRUCTURE_ONLY_NO_FIT_NO_PROBABILITY",
)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def boundary_observations_from_bytes(
    payload: bytes, source_path: str | None = None
) -> tuple[BoundaryObservation, ...]:
    """Parse one or more committed outcome-observation fixtures.

    Accepts either a single JSON object (one ``RetrospectiveOutcomeObservation``)
    or a JSON array of them. Outcome fields are deliberately dropped: the
    harness carries identity and ordering data only.
    """
    document = json.loads(payload.decode("utf-8"))
    items = document if isinstance(document, list) else [document]
    observations: list[BoundaryObservation] = []
    for item in items:
        observation = RetrospectiveOutcomeObservation.model_validate(item)
        observations.append(
            BoundaryObservation(
                case_id=observation.case_id,
                symbol=observation.symbol,
                boundary_time=observation.detection_boundary,
                source_path=source_path,
            )
        )
    return tuple(observations)


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def _evaluation_run(
    ordered: Sequence[BoundaryObservation],
    group_order: Sequence[int],
    groups: Sequence[Sequence[int]],
    cursor: int,
) -> tuple[list[int], int]:
    """Grow one whole-cluster evaluation run starting at ``group_order[cursor]``.

    Groups are ordered by first boundary time. A group whose first boundary
    falls inside the current window must join the run — otherwise its cluster
    would straddle the fold boundary (ADR-0054). Inclusion can extend the
    window, so the loop runs to a fixpoint. Returns the member group ids and
    the index one past the last consumed group.
    """
    included: list[int] = [group_order[cursor]]
    window_end = ordered[groups[group_order[cursor]][-1]].boundary_time
    consumed = cursor + 1
    changed = True
    while changed:
        changed = False
        while consumed < len(group_order):
            group_id = group_order[consumed]
            first_boundary = ordered[groups[group_id][0]].boundary_time
            if first_boundary <= window_end:
                included.append(group_id)
                last_boundary = ordered[groups[group_id][-1]].boundary_time
                if last_boundary > window_end:
                    window_end = last_boundary
                consumed += 1
                changed = True
            else:
                break
    return included, consumed


def plan_walk_forward_folds(
    boundaries: Sequence[BoundaryObservation],
    *,
    purge_calendar_days: int = PURGE_CALENDAR_DAYS,
    embargo_calendar_days: int = EMBARGO_CALENDAR_DAYS,
) -> WalkForwardPlan:
    """Order, group, and partition labeled boundaries walk-forward.

    Rules (preregistration §2.2, §7; O-2 addendum §4–§5):

    - chronological order by boundary time (ties broken by case id);
    - all boundaries of one symbol form one dependent group (ADR-0054) and are
      assigned to evaluation whole — a cluster never straddles a fold split;
    - each fold holds out the next unconsumed cluster run as evaluation data;
      training is every boundary of a non-evaluation symbol whose time is at
      least ``w + e`` calendar days before the evaluation window start
      (expanding window: earlier evaluation folds become training data);
    - boundaries inside the purge/embargo windows belong to no fold;
    - with fewer than two non-empty evaluation folds the plan is flagged
      degenerate and reported as such — no re-shuffling is attempted.
    """
    if not boundaries:
        raise WalkForwardInputError("no boundaries supplied")
    if purge_calendar_days < 0 or embargo_calendar_days < 0:
        raise WalkForwardInputError("purge/embargo windows must be non-negative")

    ordered = sorted(boundaries, key=lambda item: (item.boundary_time, item.case_id))

    group_index_by_symbol: dict[str, int] = {}
    groups: list[list[int]] = []
    for index, boundary in enumerate(ordered):
        group_index = group_index_by_symbol.get(boundary.symbol)
        if group_index is None:
            group_index = len(groups)
            group_index_by_symbol[boundary.symbol] = group_index
            groups.append([])
        groups[group_index].append(index)
    group_order = sorted(range(len(groups)), key=lambda g: ordered[groups[g][0]].boundary_time)

    regime_counts: dict[RegimeSlice, int] = {}
    for boundary in ordered:
        regime = regime_slice_for_boundary(boundary.boundary_time)
        regime_counts[regime] = regime_counts.get(regime, 0) + 1
    empty_regimes = tuple(
        regime
        for regime in RegimeSlice
        if regime is not RegimeSlice.UNASSIGNED and regime_counts.get(regime, 0) == 0
    )

    purge = timedelta(days=purge_calendar_days)
    embargo = timedelta(days=embargo_calendar_days)

    folds: list[FoldPlan] = []
    cursor = 0
    while cursor < len(group_order):
        run_groups, cursor = _evaluation_run(ordered, group_order, groups, cursor)
        evaluation_indices = sorted(
            index for group_id in run_groups for index in groups[group_id]
        )
        evaluation_start = ordered[evaluation_indices[0]].boundary_time
        evaluation_symbols = {ordered[i].symbol for i in evaluation_indices}

        embargo_window_start = evaluation_start - purge - embargo
        purge_window_start = evaluation_start - purge

        train_indices = [
            index
            for index, boundary in enumerate(ordered)
            if boundary.symbol not in evaluation_symbols
            and boundary.boundary_time < embargo_window_start
        ]

        purge_end = evaluation_start
        fold_train_symbols = {ordered[i].symbol for i in train_indices}
        regimes_in_fold = tuple(
            regime
            for regime in RegimeSlice
            if any(
                regime_slice_for_boundary(ordered[index].boundary_time) is regime
                for index in sorted((*train_indices, *evaluation_indices))
            )
        )
        folds.append(
            FoldPlan(
                fold_index=len(folds),
                train_boundary_indices=tuple(train_indices),
                evaluation_boundary_indices=tuple(evaluation_indices),
                train_window_start=(
                    ordered[train_indices[0]].boundary_time
                    if train_indices
                    else embargo_window_start
                ),
                train_window_end=(
                    ordered[train_indices[-1]].boundary_time
                    if train_indices
                    else embargo_window_start
                ),
                purge_window_start=purge_window_start,
                purge_window_end=purge_end,
                embargo_window_start=embargo_window_start,
                embargo_window_end=purge_window_start,
                train_symbols=tuple(sorted(fold_train_symbols)),
                evaluation_symbols=tuple(sorted(evaluation_symbols)),
                regimes_in_fold=regimes_in_fold,
            )
        )

    symbol_groups = tuple(
        tuple(ordered[index].case_id for index in group) for group in groups
    )

    non_empty_evaluation_folds = sum(
        1 for fold in folds if fold.evaluation_boundary_indices
    )
    degenerate = non_empty_evaluation_folds < MINIMUM_NON_EMPTY_EVALUATION_FOLDS
    degeneracy_reason = (
        (
            f"only {non_empty_evaluation_folds} non-empty evaluation fold(s) from "
            f"{len(folds)} folds; minimum is {MINIMUM_NON_EMPTY_EVALUATION_FOLDS} "
            "(preregistration §7 degeneracy gate)"
        )
        if degenerate
        else None
    )

    return WalkForwardPlan(
        folds=tuple(folds),
        symbol_groups=symbol_groups,
        regime_counts=regime_counts,
        empty_regimes=empty_regimes,
        degenerate=degenerate,
        degeneracy_reason=degeneracy_reason,
    )


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def walk_forward_diagnostics(plan: WalkForwardPlan) -> WalkForwardDiagnostics:
    """Summarize the structural properties of a fold plan.

    Reported are counts and identity sets only — no outcome-derived quantities.
    Symbol overlap between training and evaluation symbol sets is surfaced
    because a non-empty overlap would violate the ADR-0054 grouping rule.
    """
    fold_rows: list[WalkForwardFoldDiagnostics] = []
    for fold in plan.folds:
        train_symbols = set(fold.train_symbols)
        evaluation_symbols = set(fold.evaluation_symbols)
        fold_rows.append(
            WalkForwardFoldDiagnostics(
                fold_index=fold.fold_index,
                train_boundary_count=len(fold.train_boundary_indices),
                evaluation_boundary_count=len(fold.evaluation_boundary_indices),
                train_symbol_count=len(train_symbols),
                evaluation_symbol_count=len(evaluation_symbols),
                train_symbol_overlap=tuple(sorted(train_symbols & evaluation_symbols)),
                purge_days=plan.purge_calendar_days,
                embargo_days=plan.embargo_calendar_days,
            )
        )

    case_ids = {case_id for group in plan.symbol_groups for case_id in group}
    return WalkForwardDiagnostics(
        boundary_count=len(case_ids),
        symbol_count=len(plan.symbol_groups),
        fold_count=len(plan.folds),
        non_empty_evaluation_fold_count=sum(
            1 for fold in plan.folds if fold.evaluation_boundary_indices
        ),
        folds_with_empty_training=sum(
            1 for fold in plan.folds if not fold.train_boundary_indices
        ),
        degenerate=plan.degenerate,
        degeneracy_reason=plan.degeneracy_reason,
        purge_calendar_days=plan.purge_calendar_days,
        embargo_calendar_days=plan.embargo_calendar_days,
        regime_counts=dict(plan.regime_counts),
        empty_regimes=plan.empty_regimes,
        folds=tuple(fold_rows),
        limitations=WALK_FORWARD_LIMITATIONS,
    )


__all__ = [
    "BoundaryObservation",
    "EMBARGO_CALENDAR_DAYS",
    "PURGE_CALENDAR_DAYS",
    "RegimeSlice",
    "WalkForwardDiagnostics",
    "WalkForwardFoldDiagnostics",
    "WalkForwardInputError",
    "WalkForwardPlan",
    "boundary_observations_from_bytes",
    "plan_walk_forward_folds",
    "regime_slice_for_boundary",
    "walk_forward_diagnostics",
]
