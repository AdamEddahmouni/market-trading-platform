from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import EventType, Observation
from squeeze_core.contracts.validation import require_aware_utc
from squeeze_core.serialization import canonical_hash


class BarExpectationState(StrEnum):
    EXPECTED = "EXPECTED"
    SESSION_CLOSED = "SESSION_CLOSED"
    UNKNOWN_EXPECTATION = "UNKNOWN_EXPECTATION"


class BarSeriesDiagnosticCode(StrEnum):
    UNSUPPORTED_BAR_METADATA = "UNSUPPORTED_BAR_METADATA"
    NOT_YET_PUBLISHED = "NOT_YET_PUBLISHED"
    NOT_YET_RECEIVED = "NOT_YET_RECEIVED"
    EFFECTIVE_AFTER_AS_OF = "EFFECTIVE_AFTER_AS_OF"
    DUPLICATE_BOUNDARY = "DUPLICATE_BOUNDARY"
    OVERLAPPING_INTERVAL = "OVERLAPPING_INTERVAL"
    EXPECTED_INTERVAL_MISSING = "EXPECTED_INTERVAL_MISSING"
    SESSION_CLOSED = "SESSION_CLOSED"
    UNKNOWN_EXPECTATION = "UNKNOWN_EXPECTATION"


class BarExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: datetime
    end: datetime
    state: BarExpectationState

    @field_validator("start", "end")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        return require_aware_utc(value)

    @model_validator(mode="after")
    def valid_boundary(self) -> "BarExpectation":
        if self.end <= self.start:
            raise ValueError("expectation end must be after start")
        return self


class BarSeriesPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1)
    as_of: datetime
    interval: BarInterval | None = None
    sessions: tuple[BarSession, ...] = ()
    expectations: tuple[BarExpectation, ...] = ()

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class BarSeriesDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: BarSeriesDiagnosticCode
    message: str
    observation_ids: tuple[str, ...] = ()
    start: datetime | None = None
    end: datetime | None = None

    @field_validator("start", "end")
    @classmethod
    def normalize_optional_time(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)


class BarSeries(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    series_id: str
    symbol: str
    as_of: datetime
    interval: BarInterval | None
    sessions: tuple[BarSession, ...]
    observations: tuple[Observation, ...]
    latest_observation_id: str | None
    diagnostics: tuple[BarSeriesDiagnostic, ...]
    series_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


def _metadata_time(observation: Observation, key: str) -> datetime:
    value = observation.provenance.provider_metadata.get(key)
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"BAR observation has invalid structured {key}") from exc
    if not isinstance(value, datetime):
        raise ValueError(f"BAR observation is missing structured {key}")
    return require_aware_utc(value)


def _boundary_key(observation: Observation) -> tuple[datetime, datetime, str | None]:
    return (
        _metadata_time(observation, "bar_start"),
        _metadata_time(observation, "bar_end"),
        observation.provenance.provider_metadata.get("session_date"),
    )


def _is_revision_pair(left: Observation, right: Observation) -> bool:
    if left.observation_id in right.parent_observation_ids:
        return True
    if right.observation_id in left.parent_observation_ids:
        return True
    left_supersedes = left.provenance.provider_metadata.get("supersedes_provider_record_id")
    right_supersedes = right.provenance.provider_metadata.get("supersedes_provider_record_id")
    return left_supersedes == right.source_record_id or right_supersedes == left.source_record_id


def _sort_key(observation: Observation) -> tuple[object, ...]:
    return (
        _metadata_time(observation, "bar_start"),
        observation.source,
        observation.effective_timestamp,
        observation.observation_id,
    )


def build_bar_series(
    observations: Iterable[Observation], policy: BarSeriesPolicy
) -> BarSeries:
    included: list[Observation] = []
    diagnostics: list[BarSeriesDiagnostic] = []
    requested_sessions = {item.value for item in policy.sessions}
    for observation in observations:
        if observation.event_type is not EventType.BAR or observation.symbol != policy.symbol:
            continue
        if policy.interval is not None and observation.payload.timeframe != policy.interval.value:
            continue
        source_session = str(observation.provenance.provider_metadata.get("session", "UNKNOWN"))
        if requested_sessions and source_session not in requested_sessions:
            continue
        try:
            _metadata_time(observation, "bar_start")
            _metadata_time(observation, "bar_end")
        except ValueError:
            diagnostics.append(
                BarSeriesDiagnostic(
                    code=BarSeriesDiagnosticCode.UNSUPPORTED_BAR_METADATA,
                    message="Legacy BAR observation lacks Phase 1H boundary metadata and is not guessed into the series.",
                    observation_ids=(observation.observation_id,),
                )
            )
            continue
        if observation.source_timestamp > policy.as_of:
            diagnostics.append(
                BarSeriesDiagnostic(
                    code=BarSeriesDiagnosticCode.NOT_YET_PUBLISHED,
                    message="Market-bar record was not provider-published at as-of.",
                    observation_ids=(observation.observation_id,),
                )
            )
            continue
        if observation.received_timestamp > policy.as_of:
            diagnostics.append(
                BarSeriesDiagnostic(
                    code=BarSeriesDiagnosticCode.NOT_YET_RECEIVED,
                    message="Market-bar record was not locally received at as-of.",
                    observation_ids=(observation.observation_id,),
                )
            )
            continue
        if observation.effective_timestamp > policy.as_of:
            diagnostics.append(
                BarSeriesDiagnostic(
                    code=BarSeriesDiagnosticCode.EFFECTIVE_AFTER_AS_OF,
                    message="Market-bar record effective time is after as-of.",
                    observation_ids=(observation.observation_id,),
                )
            )
            continue
        included.append(observation)
    included.sort(key=_sort_key)

    by_boundary: dict[tuple[datetime, datetime, str | None], list[Observation]] = {}
    for observation in included:
        by_boundary.setdefault(_boundary_key(observation), []).append(observation)
    for boundary, items in sorted(by_boundary.items()):
        unresolved = [
            (left, right)
            for index, left in enumerate(items)
            for right in items[index + 1 :]
            if not _is_revision_pair(left, right)
        ]
        if unresolved:
            diagnostics.append(
                BarSeriesDiagnostic(
                    code=BarSeriesDiagnosticCode.DUPLICATE_BOUNDARY,
                    message="Multiple independent records share one bar boundary; all are preserved.",
                    observation_ids=tuple(sorted({item.observation_id for pair in unresolved for item in pair})),
                    start=boundary[0],
                    end=boundary[1],
                )
            )

    unique_boundaries = sorted(by_boundary)
    for index, left in enumerate(unique_boundaries):
        for right in unique_boundaries[index + 1 :]:
            if right[0] >= left[1]:
                break
            if left[:2] == right[:2]:
                continue
            diagnostics.append(
                BarSeriesDiagnostic(
                    code=BarSeriesDiagnosticCode.OVERLAPPING_INTERVAL,
                    message="Distinct bar boundaries overlap; neither record is changed.",
                    observation_ids=tuple(
                        sorted(
                            item.observation_id
                            for boundary in (left, right)
                            for item in by_boundary[boundary]
                        )
                    ),
                    start=right[0],
                    end=min(left[1], right[1]),
                )
            )

    present = {(key[0], key[1]) for key in by_boundary}
    for expectation in sorted(policy.expectations, key=lambda item: (item.start, item.end, item.state.value)):
        key = (expectation.start, expectation.end)
        if expectation.state is BarExpectationState.EXPECTED and key not in present:
            code = BarSeriesDiagnosticCode.EXPECTED_INTERVAL_MISSING
            message = "An explicitly expected fixed interval has no eligible bar; no bar is synthesized."
        elif expectation.state is BarExpectationState.SESSION_CLOSED:
            code = BarSeriesDiagnosticCode.SESSION_CLOSED
            message = "The explicit fixture policy identifies this interval as session-closed."
        elif expectation.state is BarExpectationState.UNKNOWN_EXPECTATION:
            code = BarSeriesDiagnosticCode.UNKNOWN_EXPECTATION
            message = "The explicit fixture policy cannot determine whether a bar should exist."
        else:
            continue
        diagnostics.append(
            BarSeriesDiagnostic(
                code=code,
                message=message,
                start=expectation.start,
                end=expectation.end,
            )
        )

    diagnostics.sort(
        key=lambda item: (
            item.code.value,
            item.start or datetime.min.replace(tzinfo=policy.as_of.tzinfo),
            item.end or datetime.min.replace(tzinfo=policy.as_of.tzinfo),
            item.observation_ids,
            item.message,
        )
    )
    preliminary = {
        "symbol": policy.symbol,
        "as_of": policy.as_of,
        "interval": policy.interval,
        "sessions": policy.sessions,
        "observations": tuple(included),
        "latest_observation_id": None if not included else included[-1].observation_id,
        "diagnostics": tuple(diagnostics),
    }
    series_id = f"bar-series-{canonical_hash(preliminary)[:24]}"
    series_hash = canonical_hash({"series_id": series_id, **preliminary})
    return BarSeries(series_id=series_id, **preliminary, series_hash=series_hash)
