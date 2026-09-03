from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from squeeze_core.contracts import EventType, Observation
from squeeze_core.contracts.validation import require_aware_utc
from squeeze_core.serialization import canonical_hash


class TradeQuoteSeriesDiagnosticCode(StrEnum):
    NOT_YET_PUBLISHED = "NOT_YET_PUBLISHED"
    NOT_YET_RECEIVED = "NOT_YET_RECEIVED"
    EFFECTIVE_AFTER_AS_OF = "EFFECTIVE_AFTER_AS_OF"
    FUTURE_EVENT = "FUTURE_EVENT"
    MISSING_EVENT_TIMESTAMP = "MISSING_EVENT_TIMESTAMP"
    MISSING_SEQUENCE = "MISSING_SEQUENCE"
    UNKNOWN_SEQUENCE_SCOPE = "UNKNOWN_SEQUENCE_SCOPE"
    DUPLICATE_SEQUENCE = "DUPLICATE_SEQUENCE"
    SAME_SEQUENCE_CONFLICT = "SAME_SEQUENCE_CONFLICT"
    SEQUENCE_RESET = "SEQUENCE_RESET"
    OUT_OF_ORDER_SEQUENCE = "OUT_OF_ORDER_SEQUENCE"
    INCOMPATIBLE_SEQUENCE_SCOPES = "INCOMPATIBLE_SEQUENCE_SCOPES"
    NORMAL_QUOTE = "NORMAL_QUOTE"
    LOCKED_QUOTE = "LOCKED_QUOTE"
    CROSSED_QUOTE = "CROSSED_QUOTE"
    ONE_SIDED_QUOTE = "ONE_SIDED_QUOTE"
    UNKNOWN_QUOTE_STATE = "UNKNOWN_QUOTE_STATE"


class TradeQuoteSeriesPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1)
    as_of: datetime
    providers: tuple[str, ...] = ()
    venues: tuple[str, ...] = ()
    market_scopes: tuple[str, ...] = ()

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class TradeQuoteSeriesDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: TradeQuoteSeriesDiagnosticCode
    message: str
    observation_ids: tuple[str, ...] = ()
    sequence_scope: str | None = None
    sequence_number: int | None = Field(default=None, ge=0)


class TradeQuoteSeries(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    series_id: str
    symbol: str
    as_of: datetime
    trades: tuple[Observation, ...]
    quotes: tuple[Observation, ...]
    latest_trade_observation_id: str | None
    latest_quote_observation_id: str | None
    lifecycle_chains: tuple[tuple[str, ...], ...]
    diagnostics: tuple[TradeQuoteSeriesDiagnostic, ...]
    series_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


def _metadata(observation: Observation) -> dict[str, object]:
    return observation.provenance.provider_metadata


def _event_time(observation: Observation) -> datetime | None:
    value = _metadata(observation).get("event_timestamp")
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return value if isinstance(value, datetime) else None


def _stream_key(observation: Observation) -> tuple[str, ...] | None:
    metadata = _metadata(observation)
    scope = str(metadata.get("sequence_scope", "UNKNOWN"))
    if observation.sequence_number is None or scope == "UNKNOWN":
        return None
    provider = str(metadata.get("provider", observation.provenance.provider))
    record_type = observation.event_type.value
    if scope == "PROVIDER_GLOBAL":
        suffix: tuple[str, ...] = ()
    elif scope == "SYMBOL":
        suffix = (observation.symbol or "",)
    elif scope == "VENUE":
        suffix = (observation.symbol or "", str(metadata.get("venue") or "UNKNOWN"))
    elif scope == "CHANNEL":
        suffix = (str(metadata.get("sequence_channel") or "UNKNOWN"),)
    elif scope == "SESSION":
        suffix = (str(metadata.get("sequence_session") or "UNKNOWN"),)
    else:
        return None
    return (provider, record_type, scope, *suffix)


def _sort_key(observation: Observation) -> tuple[object, ...]:
    event = _event_time(observation) or observation.source_timestamp
    stream = _stream_key(observation) or ("~",)
    sequence = observation.sequence_number if observation.sequence_number is not None else 2**63
    return (event, stream, sequence, observation.effective_timestamp, observation.observation_id)


def _diagnostic(
    code: TradeQuoteSeriesDiagnosticCode,
    message: str,
    observations: Iterable[Observation] = (),
    *,
    scope: str | None = None,
    sequence: int | None = None,
) -> TradeQuoteSeriesDiagnostic:
    return TradeQuoteSeriesDiagnostic(
        code=code,
        message=message,
        observation_ids=tuple(sorted(item.observation_id for item in observations)),
        sequence_scope=scope,
        sequence_number=sequence,
    )


def _lifecycle_chains(observations: list[Observation]) -> tuple[tuple[str, ...], ...]:
    by_key = {
        (str(_metadata(item).get("provider", item.provenance.provider)), item.source_record_id): item
        for item in observations
    }
    chains: list[tuple[str, ...]] = []
    for item in observations:
        metadata = _metadata(item)
        prior_id = metadata.get("supersedes_provider_record_id")
        if not prior_id:
            continue
        prior = by_key.get((str(metadata.get("provider", item.provenance.provider)), str(prior_id)))
        if prior is not None:
            chains.append((prior.observation_id, item.observation_id))
    return tuple(sorted(chains))


def build_trade_quote_series(
    observations: Iterable[Observation], policy: TradeQuoteSeriesPolicy
) -> TradeQuoteSeries:
    included: list[Observation] = []
    diagnostics: list[TradeQuoteSeriesDiagnostic] = []
    providers = set(policy.providers)
    venues = set(policy.venues)
    scopes = set(policy.market_scopes)
    for observation in observations:
        if observation.event_type not in {EventType.TRADE, EventType.QUOTE}:
            continue
        if observation.symbol != policy.symbol:
            continue
        metadata = _metadata(observation)
        if providers and str(metadata.get("provider")) not in providers:
            continue
        if venues and str(metadata.get("venue")) not in venues:
            continue
        if scopes and str(metadata.get("market_scope")) not in scopes:
            continue
        if observation.source_timestamp > policy.as_of:
            diagnostics.append(_diagnostic(
                TradeQuoteSeriesDiagnosticCode.NOT_YET_PUBLISHED,
                "Record was not provider-available at as-of.", (observation,)
            ))
            continue
        if observation.received_timestamp > policy.as_of:
            diagnostics.append(_diagnostic(
                TradeQuoteSeriesDiagnosticCode.NOT_YET_RECEIVED,
                "Record was not locally received at as-of.", (observation,)
            ))
            continue
        if observation.effective_timestamp > policy.as_of:
            diagnostics.append(_diagnostic(
                TradeQuoteSeriesDiagnosticCode.EFFECTIVE_AFTER_AS_OF,
                "Record effective time is after as-of.", (observation,)
            ))
            continue
        event = _event_time(observation)
        if event is None:
            diagnostics.append(_diagnostic(
                TradeQuoteSeriesDiagnosticCode.MISSING_EVENT_TIMESTAMP,
                "Record lacks structured event time and is not guessed into the series.",
                (observation,),
            ))
            continue
        if event > policy.as_of:
            diagnostics.append(_diagnostic(
                TradeQuoteSeriesDiagnosticCode.FUTURE_EVENT,
                "Event time is after as-of.", (observation,)
            ))
            continue
        included.append(observation)
        scope = str(metadata.get("sequence_scope", "UNKNOWN"))
        if observation.sequence_number is None:
            diagnostics.append(_diagnostic(
                TradeQuoteSeriesDiagnosticCode.MISSING_SEQUENCE,
                "Record has no sequence number.", (observation,), scope=scope
            ))
        elif scope == "UNKNOWN":
            diagnostics.append(_diagnostic(
                TradeQuoteSeriesDiagnosticCode.UNKNOWN_SEQUENCE_SCOPE,
                "Sequence number has unknown scope and is not compared.",
                (observation,), scope=scope, sequence=observation.sequence_number,
            ))
        if observation.event_type is EventType.QUOTE:
            state = str(metadata.get("quote_market_state", "UNKNOWN"))
            state_code = {
                "NORMAL": TradeQuoteSeriesDiagnosticCode.NORMAL_QUOTE,
                "LOCKED": TradeQuoteSeriesDiagnosticCode.LOCKED_QUOTE,
                "CROSSED": TradeQuoteSeriesDiagnosticCode.CROSSED_QUOTE,
                "UNKNOWN": TradeQuoteSeriesDiagnosticCode.UNKNOWN_QUOTE_STATE,
            }.get(state, TradeQuoteSeriesDiagnosticCode.UNKNOWN_QUOTE_STATE)
            diagnostics.append(_diagnostic(state_code, f"Objective quote state is {state}.", (observation,)))
            if observation.payload.bid_price is None or observation.payload.ask_price is None:
                diagnostics.append(_diagnostic(
                    TradeQuoteSeriesDiagnosticCode.ONE_SIDED_QUOTE,
                    "Quote is one-sided; no missing side is fabricated.", (observation,)
                ))

    by_provider_type: dict[tuple[str, str], set[str]] = defaultdict(set)
    streams: dict[tuple[str, ...], list[Observation]] = defaultdict(list)
    for observation in included:
        metadata = _metadata(observation)
        provider_type = (
            str(metadata.get("provider", observation.provenance.provider)),
            observation.event_type.value,
        )
        by_provider_type[provider_type].add(str(metadata.get("sequence_scope", "UNKNOWN")))
        key = _stream_key(observation)
        if key is not None:
            streams[key].append(observation)
    for provider_type, found_scopes in sorted(by_provider_type.items()):
        comparable = {item for item in found_scopes if item != "UNKNOWN"}
        if len(comparable) > 1:
            related = [
                item for item in included
                if str(_metadata(item).get("provider", item.provenance.provider)) == provider_type[0]
                and item.event_type.value == provider_type[1]
            ]
            diagnostics.append(_diagnostic(
                TradeQuoteSeriesDiagnosticCode.INCOMPATIBLE_SEQUENCE_SCOPES,
                "Incompatible sequence scopes are preserved and not compared.", related
            ))
    for key, stream in sorted(streams.items()):
        arrival_order = sorted(
            stream,
            key=lambda item: (
                int(_metadata(item).get("arrival_index", 2**31)),
                item.observation_id,
            ),
        )
        previous: int | None = None
        by_sequence: dict[int, list[Observation]] = defaultdict(list)
        for item in arrival_order:
            sequence = item.sequence_number
            assert sequence is not None
            by_sequence[sequence].append(item)
            reset = bool(_metadata(item).get("sequence_reset", False))
            if reset:
                diagnostics.append(_diagnostic(
                    TradeQuoteSeriesDiagnosticCode.SEQUENCE_RESET,
                    "Explicit sequence reset begins a new comparison generation.",
                    (item,), scope=key[2], sequence=sequence,
                ))
                previous = sequence
                continue
            if previous is not None and sequence < previous:
                diagnostics.append(_diagnostic(
                    TradeQuoteSeriesDiagnosticCode.OUT_OF_ORDER_SEQUENCE,
                    "Arrival sequence decreased within one compatible scope.",
                    (item,), scope=key[2], sequence=sequence,
                ))
            previous = sequence
        for sequence, items in sorted(by_sequence.items()):
            if len(items) < 2:
                continue
            diagnostics.append(_diagnostic(
                TradeQuoteSeriesDiagnosticCode.DUPLICATE_SEQUENCE,
                "Multiple records share one compatible sequence number.",
                items, scope=key[2], sequence=sequence,
            ))
            semantic_hashes = {canonical_hash(item.payload) for item in items}
            if len(semantic_hashes) > 1:
                diagnostics.append(_diagnostic(
                    TradeQuoteSeriesDiagnosticCode.SAME_SEQUENCE_CONFLICT,
                    "Same compatible sequence number has changed canonical content.",
                    items, scope=key[2], sequence=sequence,
                ))

    included.sort(key=_sort_key)
    trades = tuple(item for item in included if item.event_type is EventType.TRADE)
    quotes = tuple(item for item in included if item.event_type is EventType.QUOTE)
    diagnostics.sort(key=lambda item: (
        item.code.value, item.sequence_scope or "", item.sequence_number if item.sequence_number is not None else -1,
        item.observation_ids, item.message,
    ))
    preliminary = {
        "symbol": policy.symbol,
        "as_of": policy.as_of,
        "trades": trades,
        "quotes": quotes,
        "latest_trade_observation_id": None if not trades else trades[-1].observation_id,
        "latest_quote_observation_id": None if not quotes else quotes[-1].observation_id,
        "lifecycle_chains": _lifecycle_chains(included),
        "diagnostics": tuple(diagnostics),
    }
    series_id = f"trade-quote-series-{canonical_hash(preliminary)[:24]}"
    series_hash = canonical_hash({"series_id": series_id, **preliminary})
    return TradeQuoteSeries(series_id=series_id, **preliminary, series_hash=series_hash)
