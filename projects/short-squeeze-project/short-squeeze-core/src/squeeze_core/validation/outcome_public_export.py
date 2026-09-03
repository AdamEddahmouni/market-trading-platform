"""Whitelisted deterministic public projection of the BIYA outcome amendment."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from squeeze_core.metrics.identifiers import deterministic_metric_id

from .models import PublicValidationCase, ValidationCase
from .outcome_case import BiyaOutcomeAmendmentCase
from .public_export import build_public_validation_case


class PublicOutcomeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    window: str
    maximum_observed_return_percent: Decimal | None
    maximum_adverse_move_percent: Decimal | None
    maximum_observed_price: Decimal | None
    minimum_observed_price: Decimal | None
    time_to_maximum_seconds: int | None
    time_to_minimum_seconds: int | None
    volume: Decimal | None
    missing_data_state: str
    session_coverage: tuple[str, ...]


class PublicBoundaryOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    boundary: str
    reference_policy: str
    reference_price: Decimal | None
    reference_bar_start: str | None
    windows: tuple[PublicOutcomeWindow, ...]


class PublicBiyaOutcomeExport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: str = "1.0.0"
    amendment_id: str
    original_case: PublicValidationCase
    detection_window: tuple[str, str]
    conclusion: str
    confirmation_policy: str
    threshold_percent: Decimal
    boundaries: tuple[PublicBoundaryOutcome, ...]
    context: tuple[dict[str, object], ...]
    limitations: tuple[str, ...]
    methodology_boundary: str
    deterministic_id: str


def build_public_biya_outcome_export(
    original: ValidationCase,
    amendment: BiyaOutcomeAmendmentCase,
    *,
    context: tuple[dict[str, object], ...] = (),
) -> PublicBiyaOutcomeExport:
    if len(amendment.boundary_outcomes) != 2:
        raise ValueError("public outcome export requires both detection boundaries")
    boundaries = tuple(
        PublicBoundaryOutcome(
            boundary=item.boundary.isoformat().replace("+00:00", "Z"),
            reference_policy=item.reference.policy.value,
            reference_price=item.reference.price,
            reference_bar_start=(None if item.reference.bar_start is None else
                                 item.reference.bar_start.isoformat().replace("+00:00", "Z")),
            windows=tuple(PublicOutcomeWindow(
                window=window.window.value,
                maximum_observed_return_percent=window.maximum_observed_return_percent,
                maximum_adverse_move_percent=window.maximum_adverse_move_percent,
                maximum_observed_price=window.maximum_observed_price,
                minimum_observed_price=window.minimum_observed_price,
                time_to_maximum_seconds=window.time_to_maximum_seconds,
                time_to_minimum_seconds=window.time_to_minimum_seconds,
                volume=window.volume,
                missing_data_state=window.missing_data_state.value,
                session_coverage=window.session_coverage,
            ) for window in item.windows),
        ) for item in amendment.boundary_outcomes
    )
    base = build_public_validation_case(original)
    detection = original.detection_time_evidence
    if detection is None or detection.window_start is None or detection.window_end is None:
        raise ValueError("BIYA case requires its established detection window")
    identity = {
        "result_type": "PHASE_2V_PUBLIC_OUTCOME_EXPORT",
        "amendment_id": amendment.amendment_id,
        "original_public_id": base.deterministic_id,
        "amendment_deterministic_id": amendment.deterministic_id,
        "context": list(context),
    }
    return PublicBiyaOutcomeExport(
        amendment_id=amendment.amendment_id,
        original_case=base,
        detection_window=(detection.window_start.isoformat().replace("+00:00", "Z"),
                          detection.window_end.isoformat().replace("+00:00", "Z")),
        conclusion=amendment.conclusion.value,
        confirmation_policy=amendment.confirmation.policy.value,
        threshold_percent=amendment.confirmation.threshold_percent,
        boundaries=boundaries,
        context=context,
        limitations=amendment.limitations,
        methodology_boundary=(
            "Later price movement can confirm the outcome but cannot reconstruct or validate "
            "missing original platform inputs."
        ),
        deterministic_id=deterministic_metric_id(identity),
    )


__all__ = ["PublicBiyaOutcomeExport", "build_public_biya_outcome_export"]
