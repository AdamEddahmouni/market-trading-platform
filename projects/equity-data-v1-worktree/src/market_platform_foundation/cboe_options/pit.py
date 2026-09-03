"""Point-in-time selectors for Cboe options statistics evidence."""

from __future__ import annotations

from .contracts import (
    OptionContractActivitySnapshot,
    OptionsMarketStatisticObservation,
    OptionsReferenceFileObservation,
    OptionsStatisticFamily,
)


def statistic_as_of(
    observations: list[OptionsMarketStatisticObservation] | tuple[OptionsMarketStatisticObservation, ...],
    *,
    decision_time: str,
    canonical_statistic_id: str | None = None,
    trade_date: str | None = None,
    bucket_start: str | None = None,
) -> OptionsMarketStatisticObservation | None:
    visible = [
        obs
        for obs in observations
        if obs.available_time and obs.available_time <= decision_time
        and (canonical_statistic_id is None or obs.canonical_statistic_id == canonical_statistic_id)
        and (trade_date is None or obs.trade_date == trade_date)
        and (bucket_start is None or obs.bucket_start == bucket_start)
    ]
    if not visible:
        return None
    return max(visible, key=lambda obs: (obs.available_time, obs.ingested_time, obs.content_hash))


def statistics_as_of(
    observations: list[OptionsMarketStatisticObservation] | tuple[OptionsMarketStatisticObservation, ...],
    *,
    decision_time: str,
    statistic_family: OptionsStatisticFamily | None = None,
    trade_date: str | None = None,
) -> tuple[OptionsMarketStatisticObservation, ...]:
    visible = [
        obs
        for obs in observations
        if obs.available_time and obs.available_time <= decision_time
        and (statistic_family is None or obs.statistic_family == statistic_family)
        and (trade_date is None or obs.trade_date == trade_date)
    ]
    latest_by_key: dict[str, OptionsMarketStatisticObservation] = {}
    for obs in visible:
        key = ":".join(
            (
                obs.canonical_statistic_id,
                obs.trade_date,
                obs.bucket_start or "",
                obs.reported_exchange_group.value if obs.reported_exchange_group else "",
            )
        )
        current = latest_by_key.get(key)
        if current is None or (obs.available_time, obs.ingested_time, obs.content_hash) > (
            current.available_time,
            current.ingested_time,
            current.content_hash,
        ):
            latest_by_key[key] = obs
    return tuple(sorted(latest_by_key.values(), key=lambda obs: obs.canonical_statistic_id))


def snapshot_as_of(
    observations: list[OptionContractActivitySnapshot] | tuple[OptionContractActivitySnapshot, ...],
    *,
    decision_time: str,
    contract_id: str | None = None,
) -> OptionContractActivitySnapshot | None:
    visible = [
        obs
        for obs in observations
        if obs.available_time and obs.available_time <= decision_time
        and (contract_id is None or obs.contract_id == contract_id)
    ]
    if not visible:
        return None
    return max(visible, key=lambda obs: (obs.available_time, obs.ingested_time, obs.content_hash))


def reference_as_of(
    observations: list[OptionsReferenceFileObservation] | tuple[OptionsReferenceFileObservation, ...],
    *,
    decision_time: str,
    exchange: str | None = None,
    reference_category: str | None = None,
) -> OptionsReferenceFileObservation | None:
    visible = [
        obs
        for obs in observations
        if obs.available_time and obs.available_time <= decision_time
        and (exchange is None or obs.exchange.value == exchange)
        and (reference_category is None or obs.reference_category == reference_category)
    ]
    if not visible:
        return None
    return max(visible, key=lambda obs: (obs.available_time, obs.content_hash))


__all__ = [
    "reference_as_of",
    "snapshot_as_of",
    "statistic_as_of",
    "statistics_as_of",
]
