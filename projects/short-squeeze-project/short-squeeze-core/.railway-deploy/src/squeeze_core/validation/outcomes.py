"""Retrospective outcome observation.

What happened after a candidate was detected, measured from bars that actually exist.
This is deliberately *not* a trade, a backtest, or a causal claim:

- No entry, exit, fill, position size, P&L, stop, or target is computed, and the model
  has no field to hold one.
- A missing window is reported as unobserved, never zero-filled and never interpolated.
- A price rise is never labelled a short squeeze. `causal_interpretation` is only ever
  set from an explicit caller argument, never inferred from the numbers here.
"""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.contracts import Quality
from squeeze_core.contracts.enums import QualityState

from .diagnostics import ValidationDiagnostic, ValidationDiagnosticCode, sort_diagnostics
from .identifiers import deterministic_validation_id, outcome_observation_identity
from .models import CandidateOutcomeObservation, OutcomeWindow, OutcomeWindowObservation


def _percent_change(reference: Decimal, value: Decimal) -> Decimal | None:
    if reference == 0:
        return None
    return ((value - reference) / reference) * Decimal("100")


def build_outcome_window(
    window: OutcomeWindow,
    *,
    reference_price: Decimal | None = None,
    window_end_time: datetime | None = None,
    high_price: Decimal | None = None,
    low_price: Decimal | None = None,
    close_price: Decimal | None = None,
    volume: int | None = None,
    limitations: Sequence[str] = (),
) -> OutcomeWindowObservation:
    """One evaluation window. Supplying no prices produces an explicitly unobserved
    window rather than a zero-valued one."""

    observed = any(item is not None for item in (high_price, low_price, close_price))
    if not observed:
        return OutcomeWindowObservation(
            window=window,
            observed=False,
            window_end_time=window_end_time,
            limitations=tuple(limitations) or ("no market bars available for this window",),
        )

    return_percent = (
        _percent_change(reference_price, close_price)
        if reference_price is not None and close_price is not None
        else None
    )
    return OutcomeWindowObservation(
        window=window,
        observed=True,
        window_end_time=window_end_time,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=volume,
        return_percent=return_percent,
        limitations=tuple(limitations),
    )


def build_outcome_observation(
    symbol: str,
    windows: Sequence[OutcomeWindowObservation],
    *,
    detection_time_evidence_id: str | None = None,
    reference_price: Decimal | None = None,
    reference_price_time: datetime | None = None,
    time_to_maximum_seconds: int | None = None,
    halt_events: Sequence[str] = (),
    volume_observations: Sequence[str] = (),
    window_end: datetime | None = None,
    data_sources: Sequence[str] = (),
    limitations: Sequence[str] = (),
    causal_interpretation: str | None = None,
) -> CandidateOutcomeObservation:
    """Aggregate window observations into one retrospective record.

    Maxima and minima are taken only over windows that were actually observed. When no
    window was observed, every aggregate stays None and the result carries
    VALIDATION_OUTCOME_DATA_INCOMPLETE -- an absent outcome, not a flat one.
    """

    observed = [item for item in windows if item.observed]
    diagnostics: list[ValidationDiagnostic] = []

    unobserved = [item for item in windows if not item.observed]
    for item in unobserved:
        diagnostics.append(
            ValidationDiagnostic(
                code=ValidationDiagnosticCode.VALIDATION_OUTCOME_DATA_INCOMPLETE,
                severity=DiagnosticSeverity.WARNING,
                message=f"no market data for the {item.window.value} window; not computed",
                field_id=item.window.value,
            )
        )

    highs = [item.high_price for item in observed if item.high_price is not None]
    lows = [item.low_price for item in observed if item.low_price is not None]

    maximum_price = max(highs) if highs else None
    minimum_price = min(lows) if lows else None

    maximum_return = (
        _percent_change(reference_price, maximum_price)
        if reference_price is not None and maximum_price is not None
        else None
    )
    adverse_move = (
        _percent_change(reference_price, minimum_price)
        if reference_price is not None and minimum_price is not None
        else None
    )

    if observed:
        quality = Quality(state=QualityState.KNOWN_VALUE)
    else:
        quality = Quality(
            state=QualityState.MISSING,
            reasons=("no market bars are available for any requested window",),
        )

    draft = CandidateOutcomeObservation(
        symbol=symbol.strip().upper(),
        detection_time_evidence_id=detection_time_evidence_id,
        reference_price=reference_price,
        reference_price_time=reference_price_time,
        subsequent_windows=tuple(windows),
        maximum_observed_price=maximum_price,
        maximum_observed_return_percent=maximum_return,
        time_to_maximum_seconds=time_to_maximum_seconds,
        minimum_observed_price=minimum_price,
        maximum_adverse_move_percent=adverse_move,
        halt_events=tuple(halt_events),
        volume_observations=tuple(volume_observations),
        window_end=window_end,
        data_sources=tuple(data_sources),
        limitations=tuple(limitations),
        causal_interpretation=causal_interpretation,
        quality=quality,
        diagnostics=sort_diagnostics(diagnostics),
        deterministic_id="",
    )
    return draft.model_copy(
        update={
            "deterministic_id": deterministic_validation_id(outcome_observation_identity(draft))
        }
    )


def unobserved_outcome(
    symbol: str,
    *,
    detection_time_evidence_id: str | None = None,
    windows: Sequence[OutcomeWindow] = tuple(OutcomeWindow),
    limitations: Sequence[str] = (),
) -> CandidateOutcomeObservation:
    """An outcome observation for a candidate with no available market data.

    Used for BIYA: the workspace contains no BIYA bar at any interval on any date, so
    every window is explicitly uncomputable rather than omitted (which would read as
    'not asked') or zeroed (which would read as 'no move').
    """

    return build_outcome_observation(
        symbol,
        tuple(build_outcome_window(window) for window in windows),
        detection_time_evidence_id=detection_time_evidence_id,
        limitations=tuple(limitations)
        or (
            "no market bars for this symbol exist in the workspace at any interval or date",
            "outcome measurement requires acquiring historical bars; see the acquisition manifest",
        ),
    )


__all__ = ["build_outcome_observation", "build_outcome_window", "unobserved_outcome"]
