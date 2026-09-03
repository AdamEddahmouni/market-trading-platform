"""Boundary-based retrospective outcome observations for the Phase 2V amendment.

The values describe retained market bars. They do not simulate an order or infer that
observed movement was caused by short covering.
"""

from datetime import UTC, datetime, time, timedelta, timezone
from decimal import Decimal, localcontext
from enum import StrEnum
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, field_validator

from squeeze_core.contracts import EventType, MarketSession, Observation
from squeeze_core.contracts.validation import require_aware_utc
from squeeze_core.metrics.identifiers import deterministic_metric_id

from .outcome_normalization import HistoricalMarketDataset


BIYA_EARLIEST_BOUNDARY = datetime(2026, 7, 17, 14, 23, 58, tzinfo=UTC)
BIYA_LATEST_BOUNDARY = datetime(2026, 7, 17, 16, 54, 58, tzinfo=UTC)
_NEW_YORK_JULY = timezone(timedelta(hours=-4), name="America/New_York")


class OutcomeReferencePolicy(StrEnum):
    FIRST_ELIGIBLE_BAR_CLOSE = "first_eligible_trade_bar_close_at_or_after_boundary.v1"


class OutcomeEvaluationWindow(StrEnum):
    MINUTES_15 = "15_MINUTES"
    MINUTES_30 = "30_MINUTES"
    HOUR_1 = "1_HOUR"
    SESSION_CLOSE = "REGULAR_SESSION_CLOSE"
    NEXT_SESSION_OPEN = "NEXT_REGULAR_SESSION_OPEN"
    NEXT_SESSION_CLOSE = "NEXT_REGULAR_SESSION_CLOSE"
    HOURS_24 = "24_HOURS"
    DATASET_END = "MAXIMUM_THROUGH_DATASET_END"


class OutcomeMissingDataState(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class OutcomeReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy: OutcomeReferencePolicy = OutcomeReferencePolicy.FIRST_ELIGIBLE_BAR_CLOSE
    boundary: datetime
    price: Decimal | None = None
    bar_start: datetime | None = None
    bar_end: datetime | None = None
    observation_id: str | None = None
    adjustment_policy: str
    deterministic_id: str

    @field_validator("boundary", "bar_start", "bar_end")
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)


class BoundaryOutcomeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    window: OutcomeEvaluationWindow
    window_start: datetime
    requested_window_end: datetime | None = None
    observed_window_end: datetime | None = None
    reference_price: Decimal | None = None
    close_price: Decimal | None = None
    maximum_observed_price: Decimal | None = None
    maximum_observed_return_percent: Decimal | None = None
    minimum_observed_price: Decimal | None = None
    maximum_adverse_move_percent: Decimal | None = None
    time_to_maximum_seconds: int | None = None
    time_to_minimum_seconds: int | None = None
    volume: int | None = None
    halt_event_ids: tuple[str, ...] = ()
    supporting_observation_ids: tuple[str, ...] = ()
    session_coverage: tuple[str, ...] = ()
    missing_data_state: OutcomeMissingDataState
    limitations: tuple[str, ...] = ()
    deterministic_id: str

    @field_validator("window_start", "requested_window_end", "observed_window_end")
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)

    @field_validator(
        "halt_event_ids", "supporting_observation_ids", "session_coverage", "limitations"
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))


class BoundaryOutcomeObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    symbol: str
    boundary: datetime
    dataset_id: str
    raw_acquisition_id: str
    provider: str
    reference: OutcomeReference
    windows: tuple[BoundaryOutcomeWindow, ...]
    limitations: tuple[str, ...] = ()
    deterministic_id: str

    @field_validator("boundary")
    @classmethod
    def normalize_boundary(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @field_validator("windows")
    @classmethod
    def sort_windows(
        cls, value: tuple[BoundaryOutcomeWindow, ...]
    ) -> tuple[BoundaryOutcomeWindow, ...]:
        order = {item: index for index, item in enumerate(OutcomeEvaluationWindow)}
        return tuple(sorted(value, key=lambda item: order[item.window]))

    @field_validator("limitations")
    @classmethod
    def sort_limitations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))


def _metadata(observation: Observation, key: str) -> Any:
    return observation.provenance.provider_metadata.get(key)


def _moment(value: object) -> datetime:
    if isinstance(value, datetime):
        return require_aware_utc(value)
    if isinstance(value, str):
        return require_aware_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    raise ValueError("market bar is missing a timezone-aware boundary")


def _bar_start(observation: Observation) -> datetime:
    return _moment(_metadata(observation, "bar_start"))


def _bar_end(observation: Observation) -> datetime:
    return _moment(_metadata(observation, "bar_end"))


def _adjustment(observation: Observation) -> str:
    nested = _metadata(observation, "provider_metadata")
    if isinstance(nested, dict) and nested.get("adjustment_policy") is not None:
        return str(nested["adjustment_policy"])
    return "UNKNOWN"


def _percent(reference: Decimal, value: Decimal) -> Decimal | None:
    if reference == 0:
        return None
    with localcontext() as context:
        context.prec = 28
        return ((value - reference) / reference) * Decimal("100")


def _session_close(moment: datetime) -> datetime:
    local_date = moment.astimezone(_NEW_YORK_JULY).date()
    return datetime.combine(local_date, time(16), tzinfo=_NEW_YORK_JULY).astimezone(UTC)


def _next_regular_date(bars: Sequence[Observation], boundary: datetime):
    current = boundary.astimezone(_NEW_YORK_JULY).date()
    dates = {
        _bar_start(item).astimezone(_NEW_YORK_JULY).date()
        for item in bars
        if item.market_session is MarketSession.REGULAR
        and _bar_start(item).astimezone(_NEW_YORK_JULY).date() > current
    }
    return min(dates, default=None)


def _window_identity(window: BoundaryOutcomeWindow) -> dict[str, Any]:
    return {
        "result_type": "PHASE_2V_BOUNDARY_OUTCOME_WINDOW",
        "window": window.window,
        "window_start": window.window_start,
        "requested_window_end": window.requested_window_end,
        "reference_price": window.reference_price,
        "supporting_observation_ids": sorted(window.supporting_observation_ids),
        "halt_event_ids": sorted(window.halt_event_ids),
        "missing_data_state": window.missing_data_state,
    }


def _build_window(
    window: OutcomeEvaluationWindow,
    *,
    boundary: datetime,
    reference_price: Decimal | None,
    bars: Sequence[Observation],
    requested_end: datetime | None,
    dataset_end: datetime | None,
    halt_ids: Sequence[str] = (),
    forced_partial: bool = False,
) -> BoundaryOutcomeWindow:
    ordered = sorted(bars, key=lambda item: (_bar_start(item), str(item.observation_id)))
    if reference_price is None or not ordered:
        draft = BoundaryOutcomeWindow(
            window=window,
            window_start=boundary,
            requested_window_end=requested_end,
            missing_data_state=OutcomeMissingDataState.UNAVAILABLE,
            limitations=("no eligible market bar exists for this outcome window",),
            deterministic_id="",
        )
        return draft.model_copy(
            update={"deterministic_id": deterministic_metric_id(_window_identity(draft))}
        )

    highs = [item.payload.high for item in ordered]
    lows = [item.payload.low for item in ordered]
    maximum = max(highs)
    minimum = min(lows)
    maximum_bar = next(item for item in ordered if item.payload.high == maximum)
    minimum_bar = next(item for item in ordered if item.payload.low == minimum)
    volumes = [item.payload.volume for item in ordered]
    limitations: list[str] = []
    if any(value is None for value in volumes):
        limitations.append("one or more bars have missing volume")
    partial_bar = any(str(_metadata(item, "status")) == "PARTIAL" for item in ordered)
    if partial_bar:
        limitations.append("partial bar extrema included with explicit limitation")

    gap = False
    for prior, current in zip(ordered, ordered[1:]):
        same_session = prior.market_session is current.market_session
        same_date = (
            _bar_start(prior).astimezone(_NEW_YORK_JULY).date()
            == _bar_start(current).astimezone(_NEW_YORK_JULY).date()
        )
        timeframe = prior.payload.timeframe
        expected = {
            "1_MINUTE": 60,
            "5_MINUTES": 300,
            "15_MINUTES": 900,
            "30_MINUTES": 1800,
            "1_HOUR": 3600,
        }.get(timeframe)
        if expected and same_session and same_date:
            if (_bar_start(current) - _bar_start(prior)).total_seconds() > expected:
                gap = True
    if gap:
        limitations.append("one or more expected bar intervals are missing")

    incomplete_end = requested_end is not None and (
        dataset_end is None or dataset_end < requested_end
    )
    missing = (
        OutcomeMissingDataState.PARTIAL
        if forced_partial or partial_bar or gap or incomplete_end
        else OutcomeMissingDataState.COMPLETE
    )
    draft = BoundaryOutcomeWindow(
        window=window,
        window_start=boundary,
        requested_window_end=requested_end,
        observed_window_end=max(_bar_end(item) for item in ordered),
        reference_price=reference_price,
        close_price=ordered[-1].payload.close,
        maximum_observed_price=maximum,
        maximum_observed_return_percent=_percent(reference_price, maximum),
        minimum_observed_price=minimum,
        maximum_adverse_move_percent=_percent(reference_price, minimum),
        time_to_maximum_seconds=max(
            0, int((_bar_start(maximum_bar) - boundary).total_seconds())
        ),
        time_to_minimum_seconds=max(
            0, int((_bar_start(minimum_bar) - boundary).total_seconds())
        ),
        volume=(None if all(value is None for value in volumes) else sum(value or 0 for value in volumes)),
        halt_event_ids=tuple(halt_ids),
        supporting_observation_ids=tuple(str(item.observation_id) for item in ordered),
        session_coverage=tuple(item.market_session.value for item in ordered),
        missing_data_state=missing,
        limitations=tuple(limitations),
        deterministic_id="",
    )
    return draft.model_copy(
        update={"deterministic_id": deterministic_metric_id(_window_identity(draft))}
    )


def build_boundary_outcome(
    boundary: datetime,
    dataset: HistoricalMarketDataset,
    *,
    halt_observations: Sequence[Observation] = (),
) -> BoundaryOutcomeObservation:
    boundary = require_aware_utc(boundary)
    bars = tuple(
        sorted(
            (
                item
                for item in dataset.observations
                if item.event_type is EventType.BAR
                and item.symbol == "BIYA"
                and item.quality.state.value != "CONFLICTED"
            ),
            key=lambda item: (_bar_start(item), str(item.observation_id)),
        )
    )
    adjustment_states = {_adjustment(item) for item in bars}
    adjustment_states.discard("UNKNOWN")
    if len(adjustment_states) > 1 or (
        adjustment_states and dataset.adjustment_policy not in adjustment_states
    ):
        raise ValueError("market bars have incompatible adjustment status")

    reference_bar = next((item for item in bars if _bar_start(item) >= boundary), None)
    reference_price = None if reference_bar is None else reference_bar.payload.close
    reference = OutcomeReference(
        boundary=boundary,
        price=reference_price,
        bar_start=None if reference_bar is None else _bar_start(reference_bar),
        bar_end=None if reference_bar is None else _bar_end(reference_bar),
        observation_id=None if reference_bar is None else str(reference_bar.observation_id),
        adjustment_policy=dataset.adjustment_policy,
        deterministic_id="",
    )
    reference = reference.model_copy(
        update={
            "deterministic_id": deterministic_metric_id(
                {
                    "result_type": "PHASE_2V_OUTCOME_REFERENCE",
                    "policy": reference.policy,
                    "boundary": boundary,
                    "price": reference.price,
                    "observation_id": reference.observation_id,
                    "adjustment_policy": reference.adjustment_policy,
                }
            )
        }
    )

    start = None if reference_bar is None else _bar_start(reference_bar)
    eligible = tuple(item for item in bars if start is not None and _bar_start(item) >= start)
    dataset_end = max((_bar_end(item) for item in eligible), default=None)
    current_close = _session_close(boundary)
    next_date = _next_regular_date(eligible, boundary)
    next_open = (
        None
        if next_date is None
        else datetime.combine(next_date, time(9, 30), tzinfo=_NEW_YORK_JULY).astimezone(UTC)
    )
    next_close = (
        None
        if next_date is None
        else datetime.combine(next_date, time(16), tzinfo=_NEW_YORK_JULY).astimezone(UTC)
    )

    halt_pairs = tuple(
        (str(item.observation_id), item.payload.halt_time)
        for item in halt_observations
        if item.event_type is EventType.TRADING_HALT
        and item.symbol == "BIYA"
        and item.payload.halt_time is not None
    )

    def select(end: datetime | None, *, regular_only: bool = False) -> tuple[Observation, ...]:
        if start is None:
            return ()
        return tuple(
            item
            for item in eligible
            if (end is None or _bar_start(item) < end)
            and (not regular_only or item.market_session is MarketSession.REGULAR)
        )

    definitions: list[tuple[OutcomeEvaluationWindow, datetime | None, tuple[Observation, ...], bool]] = []
    for window, duration in (
        (OutcomeEvaluationWindow.MINUTES_15, timedelta(minutes=15)),
        (OutcomeEvaluationWindow.MINUTES_30, timedelta(minutes=30)),
        (OutcomeEvaluationWindow.HOUR_1, timedelta(hours=1)),
    ):
        end = boundary + duration
        definitions.append((window, end, select(end), False))
    definitions.append(
        (
            OutcomeEvaluationWindow.SESSION_CLOSE,
            current_close,
            tuple(
                item
                for item in select(current_close, regular_only=True)
                if _bar_start(item).astimezone(_NEW_YORK_JULY).date()
                == boundary.astimezone(_NEW_YORK_JULY).date()
            ),
            False,
        )
    )
    next_bars = tuple(
        item
        for item in eligible
        if next_date is not None
        and item.market_session is MarketSession.REGULAR
        and _bar_start(item).astimezone(_NEW_YORK_JULY).date() == next_date
    )
    definitions.append(
        (
            OutcomeEvaluationWindow.NEXT_SESSION_OPEN,
            None if not next_bars else _bar_end(next_bars[0]),
            next_bars[:1],
            False,
        )
    )
    definitions.append(
        (OutcomeEvaluationWindow.NEXT_SESSION_CLOSE, next_close, next_bars, False)
    )
    definitions.append(
        (OutcomeEvaluationWindow.HOURS_24, boundary + timedelta(hours=24), select(boundary + timedelta(hours=24)), False)
    )
    definitions.append(
        (OutcomeEvaluationWindow.DATASET_END, dataset_end, eligible, False)
    )

    windows = []
    for window, end, selected, forced_partial in definitions:
        halt_ids = tuple(
            halt_id
            for halt_id, halt_time in halt_pairs
            if halt_time is not None
            and halt_time >= boundary
            and (end is None or halt_time < end)
        )
        windows.append(
            _build_window(
                window,
                boundary=boundary,
                reference_price=reference_price,
                bars=selected,
                requested_end=end,
                dataset_end=dataset_end,
                halt_ids=halt_ids,
                forced_partial=forced_partial,
            )
        )

    draft = BoundaryOutcomeObservation(
        symbol="BIYA",
        boundary=boundary,
        dataset_id=dataset.deterministic_id,
        raw_acquisition_id=dataset.acquisition_id,
        provider=dataset.provider,
        reference=reference,
        windows=tuple(windows),
        limitations=(
            "observed movement does not establish short-covering causation",
            "historical outcome evidence cannot reconstruct missing original platform values",
        ),
        deterministic_id="",
    )
    identity = {
        "result_type": "PHASE_2V_BOUNDARY_OUTCOME_OBSERVATION",
        "symbol": draft.symbol,
        "boundary": draft.boundary,
        "dataset_id": draft.dataset_id,
        "reference_id": draft.reference.deterministic_id,
        "window_ids": sorted(item.deterministic_id for item in draft.windows),
    }
    return draft.model_copy(
        update={"deterministic_id": deterministic_metric_id(identity)}
    )


__all__ = [
    "BIYA_EARLIEST_BOUNDARY",
    "BIYA_LATEST_BOUNDARY",
    "BoundaryOutcomeObservation",
    "BoundaryOutcomeWindow",
    "OutcomeEvaluationWindow",
    "OutcomeMissingDataState",
    "OutcomeReference",
    "OutcomeReferencePolicy",
    "build_boundary_outcome",
]
