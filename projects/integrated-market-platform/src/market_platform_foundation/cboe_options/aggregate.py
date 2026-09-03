"""Build bounded OptionsAggregateContext from stored Cboe evidence."""

from __future__ import annotations

from .contracts import OptionsAggregateContext, OptionsStatisticFamily
from .pit import statistics_as_of
from .quality import CboeOptionsQualityFlag
from .store import CboeOptionsStore


def build_options_aggregate_context(
    store: CboeOptionsStore,
    as_of_time: str,
) -> OptionsAggregateContext:
    visible = statistics_as_of(store.statistics, decision_time=as_of_time)
    put_call = tuple(
        obs for obs in visible if obs.statistic_family == OptionsStatisticFamily.PUT_CALL_RATIO
    )
    volume = tuple(
        obs for obs in visible if obs.statistic_family == OptionsStatisticFamily.OPTION_VOLUME
    )
    open_interest = tuple(
        obs for obs in visible if obs.statistic_family == OptionsStatisticFamily.OPEN_INTEREST
    )
    market_share = tuple(
        obs
        for obs in visible
        if obs.statistic_family
        in {OptionsStatisticFamily.MARKET_SHARE, OptionsStatisticFamily.MATCHED_VOLUME}
    )
    intraday = tuple(
        obs
        for obs in visible
        if obs.statistic_family
        in {OptionsStatisticFamily.INTRADAY_CUMULATIVE, OptionsStatisticFamily.INTRADAY_INTERVAL}
    )

    snapshots = tuple(
        obs for obs in store.snapshots if obs.available_time and obs.available_time <= as_of_time
    )

    quality_flags: set[str] = set()
    for obs in visible:
        quality_flags.update(obs.quality_flags)
    for obs in snapshots:
        quality_flags.update(obs.quality_flags)

    staleness: dict[str, str | None] = {}
    for label, rows in (
        ("daily_put_call", put_call),
        ("volume", volume),
        ("open_interest", open_interest),
        ("market_share", market_share),
        ("intraday", intraday),
    ):
        staleness[label] = max((obs.available_time for obs in rows), default=None)

    if any(CboeOptionsQualityFlag.DELAYED_DATA.value in obs.quality_flags for obs in market_share):
        quality_flags.add(CboeOptionsQualityFlag.DELAYED_DATA.value)

    return OptionsAggregateContext(
        decision_time=as_of_time,
        put_call_activity=put_call,
        volume_activity=volume,
        open_interest_context=open_interest,
        market_share=market_share,
        exchange_intraday_activity=intraday,
        contract_activity_snapshot=snapshots,
        quality_flags=tuple(sorted(quality_flags)),
        staleness=staleness,
        provenance_ref="cboe_options.aggregate_context",
        predictive=False,
    )


__all__ = ["build_options_aggregate_context"]
