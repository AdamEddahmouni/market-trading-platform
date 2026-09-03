from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from squeeze_core.contracts import EventType, Observation, QualityState

from .diagnostics import MetricDiagnostic, MetricDiagnosticCode

_WARNING = "WARNING"
_ERROR = "ERROR"


@dataclass(frozen=True)
class PressureSelectionRequest:
    symbol: str
    as_of: datetime
    provider: str


@dataclass(frozen=True)
class PressureResolution:
    observation: Observation | None
    diagnostics: tuple[MetricDiagnostic, ...]


def _provider(observation: Observation) -> str:
    return observation.provenance.provider


def _revision_number(observation: Observation) -> int:
    value = observation.provenance.provider_metadata.get("revision_number")
    return 0 if value is None else int(value)


def _revision_status(observation: Observation) -> str | None:
    value = observation.provenance.provider_metadata.get("revision_status")
    return None if value is None else str(value)


def eligible_pressure_observations(
    observations: Iterable[Observation],
    *,
    event_type: EventType,
    request: PressureSelectionRequest,
) -> tuple[Observation, ...]:
    """symbol + event_type + provider match, then source_timestamp <= as_of AND
    received_timestamp <= as_of AND effective_timestamp <= as_of -- the same three-gate
    eligibility rule documented for PUBLISHED_SHORT_INTEREST in
    docs/point-in-time-evidence-policy.md, applied uniformly to borrow observations (whose
    source_timestamp == effective_timestamp by construction, so the gate degenerates to two
    equivalent checks plus received_timestamp, never fewer checks)."""

    result = []
    for observation in observations:
        if observation.event_type is not event_type:
            continue
        if observation.symbol != request.symbol:
            continue
        if _provider(observation) != request.provider:
            continue
        if observation.source_timestamp > request.as_of:
            continue
        if observation.received_timestamp > request.as_of:
            continue
        if observation.effective_timestamp > request.as_of:
            continue
        result.append(observation)
    return tuple(result)


def resolve_short_interest_at_period(
    observations: Iterable[Observation],
    request: PressureSelectionRequest,
    *,
    reporting_period: date,
    not_found_code: MetricDiagnosticCode,
) -> PressureResolution:
    """Groups eligible PUBLISHED_SHORT_INTEREST observations for (symbol, provider) by
    payload.settlement_date -- the exact key FINRA's own normalizer groups conflicts by
    (normalizer.py:601-605) -- and resolves the single latest-eligible-as-of-as_of record at
    the requested period, or a diagnostic explaining why none qualifies. Mirrors
    metrics/selection.py's _resolve_group shape without depending on any bar-specific helper
    (docs/phase-2c-design.md Section 3.1)."""

    candidates = [
        item
        for item in eligible_pressure_observations(
            observations, event_type=EventType.PUBLISHED_SHORT_INTEREST, request=request
        )
        if item.payload.settlement_date == reporting_period
    ]
    if not candidates:
        return PressureResolution(
            observation=None,
            diagnostics=(
                MetricDiagnostic(
                    code=not_found_code,
                    severity=_WARNING,
                    message="No point-in-time eligible published short-interest record exists for the requested reporting period.",
                ),
            ),
        )

    conflicted = [item for item in candidates if item.quality.state is QualityState.CONFLICTED]
    if conflicted:
        ids = tuple(sorted(item.observation_id for item in conflicted))
        return PressureResolution(
            observation=None,
            diagnostics=(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.PRESSURE_METRIC_CONFLICTED_INPUT,
                    severity=_ERROR,
                    message="Same-period published short-interest records conflict; no winner is selected.",
                    observation_ids=ids,
                ),
            ),
        )

    chosen = max(
        candidates,
        key=lambda item: (_revision_number(item), item.effective_timestamp, item.observation_id),
    )

    if _revision_status(chosen) == "CANCELLED":
        return PressureResolution(
            observation=None,
            diagnostics=(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.SHORT_INTEREST_CANCELLED_INPUT,
                    severity=_WARNING,
                    message="The latest eligible revision for this reporting period is cancelled.",
                    observation_ids=(chosen.observation_id,),
                ),
            ),
        )

    if chosen.payload.short_shares is None:
        return PressureResolution(
            observation=None,
            diagnostics=(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.SHORT_INTEREST_MISSING_VALUE,
                    severity=_WARNING,
                    message="The latest eligible revision for this reporting period has no published short-shares value.",
                    observation_ids=(chosen.observation_id,),
                ),
            ),
        )

    return PressureResolution(observation=chosen, diagnostics=())


def resolve_short_interest_revision(
    observations: Iterable[Observation],
    request: PressureSelectionRequest,
    *,
    reporting_period: date,
) -> tuple[PressureResolution, PressureResolution]:
    """Returns (original, revision) resolutions for one reporting period
    (docs/phase-2c-design.md Section 3.2). The "ending"/revision side is resolved first via
    resolve_short_interest_at_period; if it has no linked parent (either because no revision
    is eligible yet -- in which case that function already resolved the original record
    itself, which has no parent -- or because the link is genuinely missing), both sides are
    reported unavailable rather than fabricating a self-comparison."""

    observations = tuple(observations)
    ending = resolve_short_interest_at_period(
        observations,
        request,
        reporting_period=reporting_period,
        not_found_code=MetricDiagnosticCode.SHORT_INTEREST_END_NOT_FOUND,
    )
    if ending.observation is None:
        return PressureResolution(None, ending.diagnostics), ending

    parent_ids = ending.observation.parent_observation_ids
    if not parent_ids:
        diagnostics = (
            MetricDiagnostic(
                code=MetricDiagnosticCode.SHORT_INTEREST_REVISION_NOT_FOUND,
                severity=_WARNING,
                message="No revision is linked to the latest eligible record for this reporting period.",
                observation_ids=(ending.observation.observation_id,),
            ),
        )
        return PressureResolution(None, diagnostics), PressureResolution(None, diagnostics)

    by_id = {item.observation_id: item for item in observations}
    original = by_id.get(parent_ids[0])
    original_eligible = (
        original is not None
        and original.source_timestamp <= request.as_of
        and original.received_timestamp <= request.as_of
        and original.effective_timestamp <= request.as_of
    )
    if not original_eligible:
        diagnostics = (
            MetricDiagnostic(
                code=MetricDiagnosticCode.SHORT_INTEREST_REVISION_LINK_MISSING,
                severity=_WARNING,
                message="The revision's linked prior record is not present or not point-in-time eligible.",
                observation_ids=(ending.observation.observation_id,),
            ),
        )
        return PressureResolution(None, diagnostics), PressureResolution(None, diagnostics)

    return PressureResolution(original, ()), ending


def resolve_borrow_observation_at(
    observations: Iterable[Observation],
    request: PressureSelectionRequest,
    *,
    event_type: EventType,
    effective_timestamp: datetime,
    not_found_code: MetricDiagnosticCode,
) -> PressureResolution:
    """Groups eligible BORROW_FEE/BORROW_AVAILABILITY observations for (symbol, provider,
    event_type) by effective_timestamp -- the exact key IBKR's own normalizer groups conflicts
    by (normalizer.py:540-544) -- and resolves the single observation at the requested,
    caller-supplied exact boundary. No revision/lifecycle concept exists for borrow data
    (docs/phase-2c-design.md Section 3.3), so there is no cancellation/correction branch here
    -- only found / not-found / conflicted."""

    candidates = [
        item
        for item in eligible_pressure_observations(observations, event_type=event_type, request=request)
        if item.effective_timestamp == effective_timestamp
    ]
    if not candidates:
        return PressureResolution(
            observation=None,
            diagnostics=(
                MetricDiagnostic(
                    code=not_found_code,
                    severity=_WARNING,
                    message="No point-in-time eligible borrow record exists at the requested boundary.",
                ),
            ),
        )

    conflicted = [item for item in candidates if item.quality.state is QualityState.CONFLICTED]
    if conflicted:
        ids = tuple(sorted(item.observation_id for item in conflicted))
        return PressureResolution(
            observation=None,
            diagnostics=(
                MetricDiagnostic(
                    code=MetricDiagnosticCode.PRESSURE_METRIC_CONFLICTED_INPUT,
                    severity=_ERROR,
                    message="Same-boundary borrow records conflict; no winner is selected.",
                    observation_ids=ids,
                ),
            ),
        )

    chosen = max(candidates, key=lambda item: item.observation_id)
    return PressureResolution(observation=chosen, diagnostics=())
