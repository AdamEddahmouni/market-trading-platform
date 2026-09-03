import json
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from pathlib import Path

from squeeze_core.adapters.market_bars import BarInterval, BarSession
from squeeze_core.contracts import (
    AssetClass,
    EventType,
    MarketSession,
    MarketSnapshotPayload,
    Observation,
    PayloadType,
    Quality,
    QualityState,
    PublishedShortInterestPayload,
)
from squeeze_core.evaluation import RuleEvaluationRequest
from squeeze_core.evaluation.policies import lookup_policy
from squeeze_core.evidence import CoverageDomain
from squeeze_core.metrics import MetricName, MetricUnit
from squeeze_core.metrics.days_to_cover import DaysToCoverRequest, build_days_to_cover_result
from squeeze_core.metrics.models import ProviderScopeMode, TrailingWindow, WindowType
from squeeze_core.metrics.relative_volume import RelativeVolumeRequest, build_relative_volume_result
from squeeze_core.metrics.returns import ReturnRequest, build_return_result
from squeeze_core.metrics.selection import bar_end, bar_start
from squeeze_core.metrics.short_interest_changes import (
    ShortInterestComparisonRequest,
    build_short_interest_change_result,
)
from squeeze_core.readiness import (
    DomainCoverageSnapshot,
    EvidenceConflictSummary,
    InputSufficiencyResult,
    StructuralState,
)


ROOT = Path(__file__).resolve().parents[2]
OUTCOME_FIXTURES = ROOT / "tests" / "fixtures" / "validation" / "outcome_amendment"
EARLIEST = datetime(2026, 7, 17, 14, 23, 58, tzinfo=UTC)
LATEST = datetime(2026, 7, 17, 16, 54, 58, tzinfo=UTC)
POLICY = lookup_policy("phase_3a_transparent_candidate_policy.v1")
BAR_PROVIDER = "yahoo-chart"
METRIC_BAR_PROVIDER = "YAHOO-CHART"
SI_PROVIDER = "finra"
RELATIVE_VOLUME_WINDOW = TrailingWindow(
    window_type=WindowType.BAR_COUNT,
    requested_count=20,
    minimum_samples=10,
    exclude_current_bar=True,
)
DAYS_TO_COVER_WINDOW = TrailingWindow(
    window_type=WindowType.BAR_COUNT,
    requested_count=10,
    minimum_samples=5,
    exclude_current_bar=True,
)
STARTING_SI_PERIOD = date(2026, 6, 15)
ENDING_SI_PERIOD = date(2026, 6, 30)


def _jsonl(name: str) -> tuple[Observation, ...]:
    path = OUTCOME_FIXTURES / name
    if not path.exists():
        return ()
    return tuple(
        Observation.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _bar_end_time(observation: Observation) -> datetime:
    return datetime.fromisoformat(
        str(observation.provenance.provider_metadata["bar_end"]).replace("Z", "+00:00")
    )


def _public_historical_projection(
    observation: Observation, availability_time: datetime | None = None
) -> Observation:
    moment = availability_time or observation.source_timestamp
    return observation.model_copy(update={
        "source_timestamp": moment,
        "received_timestamp": moment,
        "effective_timestamp": moment,
    })


def _eligible_at(observation: Observation, as_of: datetime) -> bool:
    if observation.event_type is EventType.PUBLISHED_SHORT_INTEREST:
        return observation.source_timestamp <= as_of
    return observation.effective_timestamp <= as_of


def _project_short_interest(observation: Observation) -> Observation:
    return _public_historical_projection(observation, observation.source_timestamp)


def admissible_projected_bars(as_of: datetime) -> tuple[Observation, ...]:
    projected: list[Observation] = []
    for item in _jsonl("biya_market_bars_intraday.jsonl"):
        bar_end_time = _bar_end_time(item)
        if bar_end_time <= as_of:
            projected.append(_public_historical_projection(item, bar_end_time))
    return tuple(projected)


def admissible_projected_daily_bars(as_of: datetime) -> tuple[Observation, ...]:
    projected: list[Observation] = []
    for item in _jsonl("biya_market_bars_daily.jsonl"):
        bar_end_time = _bar_end_time(item)
        if bar_end_time <= as_of:
            projected.append(_public_historical_projection(item, bar_end_time))
    return tuple(projected)


def admissible_short_interest(as_of: datetime) -> tuple[Observation, ...]:
    projected: list[Observation] = []
    for item in _jsonl("biya_short_interest.jsonl"):
        if item.event_type is not EventType.PUBLISHED_SHORT_INTEREST:
            continue
        if _eligible_at(item, as_of):
            projected.append(_project_short_interest(item))
    return tuple(projected)


def _latest_short_interest(as_of: datetime) -> Observation | None:
    eligible = admissible_short_interest(as_of)
    if not eligible:
        return None
    return max(eligible, key=lambda item: item.effective_timestamp)


def _derived_float_snapshot(as_of: datetime) -> Observation | None:
    latest = _latest_short_interest(as_of)
    if latest is None or not isinstance(latest.payload, PublishedShortInterestPayload):
        return None
    float_shares = latest.payload.float_shares
    if float_shares is None and latest.payload.short_shares and latest.payload.short_float_percent:
        with localcontext() as ctx:
            ctx.prec = 28
            float_shares = int(
                Decimal(latest.payload.short_shares)
                / (latest.payload.short_float_percent / Decimal(100))
            )
    if float_shares is None:
        return None
    return latest.model_copy(update={
        "event_type": EventType.MARKET_SNAPSHOT,
        "payload_type": PayloadType.MARKET_SNAPSHOT,
        "payload": MarketSnapshotPayload(float_shares=float_shares),
        "provenance": latest.provenance.model_copy(update={
            "provider_metadata": {
                **latest.provenance.provider_metadata,
                "derived_from": "published_short_interest_float_derivation.v1",
                "source_observation_id": str(latest.observation_id),
            },
        }),
    })


def computed_input_metrics(as_of: datetime) -> tuple:
    bars = admissible_projected_bars(as_of)
    metrics = []
    if len(bars) >= 2:
        first_bar, last_bar = bars[0], bars[-1]
        percentage = build_return_result(
            bars,
            ReturnRequest(
                symbol="BIYA",
                asset_class=AssetClass.EQUITY,
                as_of=as_of,
                source_interval=BarInterval.ONE_MINUTE,
                start_bar_start=bar_start(first_bar),
                start_bar_end=bar_end(first_bar),
                end_bar_start=bar_start(last_bar),
                end_bar_end=bar_end(last_bar),
                provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
                provider=METRIC_BAR_PROVIDER,
            ),
            MetricName.PERCENTAGE_RETURN,
        )
        if percentage.quality.state is QualityState.KNOWN_VALUE:
            metrics.append(percentage.model_copy(update={"provider": BAR_PROVIDER}))

        relative_volume = build_relative_volume_result(
            bars,
            RelativeVolumeRequest(
                symbol="BIYA",
                asset_class=AssetClass.EQUITY,
                as_of=as_of,
                source_interval=BarInterval.ONE_MINUTE,
                target_bar_start=bar_start(last_bar),
                target_bar_end=bar_end(last_bar),
                window=RELATIVE_VOLUME_WINDOW,
                provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
                provider=METRIC_BAR_PROVIDER,
            ),
        )
        if relative_volume.quality.state is QualityState.KNOWN_VALUE:
            metrics.append(relative_volume.model_copy(update={"provider": BAR_PROVIDER}))

    si_observations = admissible_short_interest(as_of)
    daily_bars = admissible_projected_daily_bars(as_of)
    if si_observations:
        si_change = build_short_interest_change_result(
            si_observations,
            ShortInterestComparisonRequest(
                symbol="BIYA",
                asset_class=AssetClass.EQUITY,
                as_of=as_of,
                provider=SI_PROVIDER,
                starting_reporting_period=STARTING_SI_PERIOD,
                ending_reporting_period=ENDING_SI_PERIOD,
            ),
            MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE,
        )
        if si_change.quality.state is QualityState.KNOWN_VALUE:
            metrics.append(si_change.model_copy(update={"provider": SI_PROVIDER}))

        days_to_cover = build_days_to_cover_result(
            (*si_observations, *daily_bars),
            DaysToCoverRequest(
                symbol="BIYA",
                asset_class=AssetClass.EQUITY,
                as_of=as_of,
                short_interest_provider=SI_PROVIDER,
                short_interest_reporting_period=ENDING_SI_PERIOD,
                volume_provider=BAR_PROVIDER,
                volume_interval=BarInterval.ONE_DAY,
                volume_session_scope=(BarSession.REGULAR,),
                volume_window=DAYS_TO_COVER_WINDOW,
            ),
        )
        if days_to_cover.quality.state is QualityState.KNOWN_VALUE:
            metrics.append(days_to_cover.model_copy(update={"provider": SI_PROVIDER}))

    return tuple(metrics)


def historical_detection_observations(as_of: datetime) -> tuple[Observation, ...]:
    bars_with_end = tuple(
        (item, _bar_end_time(item))
        for item in _jsonl("biya_market_bars_intraday.jsonl")
    )
    bars = tuple((item, bar_end_time) for item, bar_end_time in bars_with_end if bar_end_time <= as_of)
    latest_bar, latest_bar_end = max(bars, key=lambda pair: pair[1])
    news = _jsonl("biya_news.jsonl")
    action = _jsonl("biya_corporate_actions.jsonl")
    short_interest = admissible_short_interest(as_of)
    snapshot = _derived_float_snapshot(as_of)
    extras = tuple(item for item in (snapshot, *short_interest) if item is not None)
    return tuple(
        _public_historical_projection(
            item,
            latest_bar_end if item is latest_bar else (
                item.source_timestamp
                if item.event_type is EventType.PUBLISHED_SHORT_INTEREST
                else None
            ),
        )
        for item in (latest_bar, *news, *action, *extras)
    )


def _quality(as_of: datetime) -> Quality:
    return Quality(state=QualityState.KNOWN_VALUE, evaluated_at=as_of)


def readiness(as_of: datetime):
    requested = (
        CoverageDomain.BORROW_AVAILABILITY,
        CoverageDomain.BORROW_FEE,
        CoverageDomain.MARKET_BARS,
        CoverageDomain.NEWS,
        CoverageDomain.PUBLISHED_SHORT_INTEREST,
    )
    present = [CoverageDomain.MARKET_BARS, CoverageDomain.NEWS]
    unavailable = [CoverageDomain.BORROW_AVAILABILITY, CoverageDomain.BORROW_FEE]
    if admissible_short_interest(as_of):
        present.append(CoverageDomain.PUBLISHED_SHORT_INTEREST)
    else:
        unavailable.append(CoverageDomain.PUBLISHED_SHORT_INTEREST)
    coverage = DomainCoverageSnapshot(
        symbol="BIYA", asset_class=AssetClass.EQUITY, as_of=as_of,
        requested_domains=requested,
        present_domains=tuple(present),
        unavailable_domains=tuple(unavailable),
        quality=_quality(as_of),
    )
    conflicts = EvidenceConflictSummary(
        symbol="BIYA", asset_class=AssetClass.EQUITY, as_of=as_of,
        conflict_count=0, quality=_quality(as_of),
    )
    metrics = computed_input_metrics(as_of)
    has_relative_volume = any(
        getattr(item, "metric_name", None) is MetricName.RELATIVE_VOLUME for item in metrics
    )
    sufficiency = InputSufficiencyResult(
        operation="candidate-evaluation", policy_version="phase_3a_biya_readiness.v1",
        symbol="BIYA", asset_class=AssetClass.EQUITY, as_of=as_of,
        structural_state=(
            StructuralState.SUFFICIENT if has_relative_volume else StructuralState.INSUFFICIENT
        ),
        insufficient_history_inputs=() if has_relative_volume else ("relative-volume-history",),
        quality=_quality(as_of),
    )
    return coverage, conflicts, sufficiency


def request(as_of: datetime, *, observations: tuple[Observation, ...] | None = None):
    inputs = historical_detection_observations(as_of) if observations is None else observations
    return RuleEvaluationRequest(
        symbol="BIYA", asset_class=AssetClass.EQUITY, as_of=as_of,
        policy_version=POLICY.policy_version,
        enabled_rule_ids=POLICY.enabled_rule_ids,
        provider_scope=(BAR_PROVIDER, "yahoo-search", SI_PROVIDER),
        input_observations=inputs,
        input_metrics=computed_input_metrics(as_of),
        input_readiness_results=readiness(as_of),
    )


def by_rule(evaluation):
    return {item.rule_id: item for item in evaluation.rule_results}
