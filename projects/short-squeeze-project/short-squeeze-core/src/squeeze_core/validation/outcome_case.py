"""Separate BIYA outcome amendment and conclusion policy.

The original Phase 2V case is an immutable input. This module never rebuilds or updates
that object; it produces a new result whose conclusion concerns outcome confirmation
while stating that methodology remains unverified.
"""

from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from squeeze_core.metrics.identifiers import deterministic_metric_id

from .models import MethodologyConclusion, OriginalValueState, ValidationCase
from .outcome_amendment import (
    BIYA_EARLIEST_BOUNDARY,
    BIYA_LATEST_BOUNDARY,
    BoundaryOutcomeObservation,
    OutcomeEvaluationWindow,
    OutcomeMissingDataState,
)


class OutcomeSubstantialMovePolicy(StrEnum):
    BOTH_BOUNDARIES_25_PERCENT = (
        "both_detection_boundaries_maximum_return_at_least_25_percent.v1"
    )


class OutcomeConfirmationState(StrEnum):
    CONFIRMED = "CONFIRMED"
    NOT_CONFIRMED = "NOT_CONFIRMED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class OutcomeConfirmationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = "BIYA"
    state: OutcomeConfirmationState
    policy: OutcomeSubstantialMovePolicy = (
        OutcomeSubstantialMovePolicy.BOTH_BOUNDARIES_25_PERCENT
    )
    threshold_percent: Decimal = Decimal("25")
    earliest_boundary_return_percent: Decimal | None = None
    latest_boundary_return_percent: Decimal | None = None
    supporting_boundary_outcome_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    deterministic_id: str

    @field_validator("supporting_boundary_outcome_ids", "limitations")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))


class BiyaOutcomeAmendmentCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    amendment_id: str = "phase-2v-biya-outcome-data-amendment"
    symbol: str = "BIYA"
    original_case_id: str
    original_case_deterministic_id: str
    original_conclusion: MethodologyConclusion
    original_values_recovered: int
    boundary_outcomes: tuple[BoundaryOutcomeObservation, ...]
    confirmation: OutcomeConfirmationResult
    conclusion: MethodologyConclusion
    contextual_evidence_ids: tuple[str, ...] = ()
    unchanged_forensic_findings: tuple[str, ...]
    limitations: tuple[str, ...]
    deterministic_id: str

    @field_validator("boundary_outcomes")
    @classmethod
    def sort_outcomes(
        cls, value: tuple[BoundaryOutcomeObservation, ...]
    ) -> tuple[BoundaryOutcomeObservation, ...]:
        return tuple(sorted(value, key=lambda item: item.boundary))

    @field_validator(
        "contextual_evidence_ids", "unchanged_forensic_findings", "limitations"
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))

    @model_validator(mode="after")
    def conclusion_is_outcome_only(self) -> "BiyaOutcomeAmendmentCase":
        permitted = {
            MethodologyConclusion.OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED,
            MethodologyConclusion.INSUFFICIENT_EVIDENCE,
        }
        if self.conclusion not in permitted:
            raise ValueError("outcome amendment cannot validate original methodology")
        if (
            self.confirmation.state is OutcomeConfirmationState.CONFIRMED
            and self.conclusion
            is not MethodologyConclusion.OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED
        ):
            raise ValueError("confirmed outcome requires the unverified-methodology conclusion")
        return self


def _dataset_return(outcome: BoundaryOutcomeObservation) -> Decimal | None:
    window = next(
        (
            item
            for item in outcome.windows
            if item.window is OutcomeEvaluationWindow.DATASET_END
        ),
        None,
    )
    if (
        outcome.reference.price is None
        or window is None
        or window.missing_data_state is OutcomeMissingDataState.UNAVAILABLE
    ):
        return None
    return window.maximum_observed_return_percent


def build_outcome_confirmation(
    outcomes: Sequence[BoundaryOutcomeObservation],
) -> OutcomeConfirmationResult:
    by_boundary = {item.boundary: item for item in outcomes}
    earliest = by_boundary.get(BIYA_EARLIEST_BOUNDARY)
    latest = by_boundary.get(BIYA_LATEST_BOUNDARY)
    earliest_return = None if earliest is None else _dataset_return(earliest)
    latest_return = None if latest is None else _dataset_return(latest)
    limitations: list[str] = []

    if earliest_return is None or latest_return is None:
        state = OutcomeConfirmationState.INSUFFICIENT_DATA
        limitations.append(
            "both detection boundaries require a historical reference and dataset-end maximum"
        )
    elif earliest_return >= Decimal("25") and latest_return >= Decimal("25"):
        state = OutcomeConfirmationState.CONFIRMED
    else:
        state = OutcomeConfirmationState.NOT_CONFIRMED
        limitations.append(
            "the fixed substantial-move threshold was not met from both detection boundaries"
        )

    draft = OutcomeConfirmationResult(
        state=state,
        earliest_boundary_return_percent=earliest_return,
        latest_boundary_return_percent=latest_return,
        supporting_boundary_outcome_ids=tuple(
            item.deterministic_id for item in (earliest, latest) if item is not None
        ),
        limitations=tuple(limitations),
        deterministic_id="",
    )
    identity = {
        "result_type": "PHASE_2V_OUTCOME_CONFIRMATION",
        "symbol": draft.symbol,
        "state": draft.state,
        "policy": draft.policy,
        "threshold_percent": draft.threshold_percent,
        "earliest_boundary_return_percent": draft.earliest_boundary_return_percent,
        "latest_boundary_return_percent": draft.latest_boundary_return_percent,
        "supporting_boundary_outcome_ids": sorted(draft.supporting_boundary_outcome_ids),
    }
    return draft.model_copy(
        update={"deterministic_id": deterministic_metric_id(identity)}
    )


_UNCHANGED_FINDINGS = (
    "BIYA original values remain unknown",
    "no original BIYA score or label survives",
    "no original BIYA days-to-cover, news, or market value survives",
    "the original platform log records provider failures",
    "Prime/Subprime logic at detection was momentum-heavy",
    "borrow fee, days to cover, and TTM Squeeze did not feed the original Prime/Subprime rubric",
    "the Short Interest (%) column was mislabeled",
    "news timestamp handling was inadequate",
    "cross-provider corroboration failed",
    "the historical methodology remains unreproducible from surviving artifacts",
)


def build_biya_outcome_amendment_case(
    original_case: ValidationCase,
    outcomes: Sequence[BoundaryOutcomeObservation],
    *,
    contextual_evidence_ids: Sequence[str] = (),
) -> BiyaOutcomeAmendmentCase:
    if original_case.symbol != "BIYA":
        raise ValueError("the BIYA outcome amendment requires the BIYA validation case")
    if original_case.conclusion is None:
        raise ValueError("the original validation case has no conclusion")

    recovered_states = {
        OriginalValueState.RECOVERED,
        OriginalValueState.DERIVED,
        OriginalValueState.DEFAULT_SUBSTITUTED,
    }
    recovered = (
        0
        if original_case.original_snapshot is None
        else sum(
            item.state in recovered_states
            for item in original_case.original_snapshot.original_field_values
        )
    )
    confirmation = build_outcome_confirmation(outcomes)
    conclusion = (
        MethodologyConclusion.OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED
        if confirmation.state is OutcomeConfirmationState.CONFIRMED
        else MethodologyConclusion.INSUFFICIENT_EVIDENCE
    )
    draft = BiyaOutcomeAmendmentCase(
        original_case_id=original_case.case_id,
        original_case_deterministic_id=original_case.deterministic_id,
        original_conclusion=original_case.conclusion.conclusion,
        original_values_recovered=recovered,
        boundary_outcomes=tuple(outcomes),
        confirmation=confirmation,
        conclusion=conclusion,
        contextual_evidence_ids=tuple(contextual_evidence_ids),
        unchanged_forensic_findings=_UNCHANGED_FINDINGS,
        limitations=(
            "later market evidence was unavailable to the original detection replay",
            "price movement does not establish short-covering causation",
            "outcome confirmation does not validate missing original platform inputs",
            "one historical case cannot validate a generalized methodology",
        ),
        deterministic_id="",
    )
    identity = {
        "result_type": "PHASE_2V_BIYA_OUTCOME_AMENDMENT_CASE",
        "amendment_id": draft.amendment_id,
        "original_case_deterministic_id": draft.original_case_deterministic_id,
        "boundary_outcome_ids": sorted(
            item.deterministic_id for item in draft.boundary_outcomes
        ),
        "confirmation_id": draft.confirmation.deterministic_id,
        "conclusion": draft.conclusion,
        "contextual_evidence_ids": sorted(draft.contextual_evidence_ids),
    }
    return draft.model_copy(
        update={"deterministic_id": deterministic_metric_id(identity)}
    )


__all__ = [
    "BiyaOutcomeAmendmentCase",
    "OutcomeConfirmationResult",
    "OutcomeConfirmationState",
    "OutcomeSubstantialMovePolicy",
    "build_biya_outcome_amendment_case",
    "build_outcome_confirmation",
]
