"""Normalize immutable acquired market data through the Phase 1 bar adapter."""

import hashlib
import json
from datetime import UTC, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.diagnostics import NormalizationDiagnostic
from squeeze_core.adapters.market_bars import (
    BarCompletionStatus,
    BarInterval,
    BarSession,
    BarTimestampMeaning,
    BarVolumeUnit,
    MarketBarRecord,
    normalize_market_bar_records,
)
from squeeze_core.contracts import EntitlementState, IngestionMethod, Observation
from squeeze_core.metrics.identifiers import deterministic_metric_id
from .outcome_acquisition import (
    AcquisitionDataType,
    AcquisitionManifest,
    AcquisitionResultState,
)


_INTERVALS = {
    "1m": BarInterval.ONE_MINUTE,
    "5m": BarInterval.FIVE_MINUTES,
    "15m": BarInterval.FIFTEEN_MINUTES,
    "30m": BarInterval.THIRTY_MINUTES,
    "60m": BarInterval.ONE_HOUR,
    "1h": BarInterval.ONE_HOUR,
    "1d": BarInterval.ONE_DAY,
    "1_MINUTE": BarInterval.ONE_MINUTE,
    "5_MINUTES": BarInterval.FIVE_MINUTES,
    "15_MINUTES": BarInterval.FIFTEEN_MINUTES,
    "30_MINUTES": BarInterval.THIRTY_MINUTES,
    "1_HOUR": BarInterval.ONE_HOUR,
    "1_DAY": BarInterval.ONE_DAY,
}


class HistoricalMarketDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    acquisition_id: str
    raw_sha256: str
    provider: str
    adjustment_policy: str
    observations: tuple[Observation, ...]
    diagnostics: tuple[NormalizationDiagnostic, ...] = ()
    rejected_record_count: int = 0
    deterministic_id: str

    @field_validator("observations")
    @classmethod
    def sort_observations(cls, value: tuple[Observation, ...]) -> tuple[Observation, ...]:
        return tuple(sorted(value, key=_bar_order_key))


def _bar_order_key(observation: Observation) -> tuple[str, str]:
    start = observation.provenance.provider_metadata.get("bar_start")
    return (str(start or ""), str(observation.observation_id))


def _local_zone(name: str | None):
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            if name == "America/New_York":
                # The amendment range is in July 2026, when New York is UTC-4.
                return timezone(timedelta(hours=-4), name="America/New_York")
    return UTC


def _session(moment: datetime, timezone_name: str | None) -> BarSession:
    local = moment.astimezone(_local_zone(timezone_name)).timetz().replace(tzinfo=None)
    if time(4) <= local < time(9, 30):
        return BarSession.PREMARKET
    if time(9, 30) <= local < time(16):
        return BarSession.REGULAR
    if time(16) <= local < time(20):
        return BarSession.AFTER_HOURS
    return BarSession.OVERNIGHT


def _daily_boundaries(moment: datetime, timezone_name: str | None) -> tuple[str, str, str]:
    zone = _local_zone(timezone_name)
    session_date = moment.astimezone(zone).date()
    start = datetime.combine(session_date, time(9, 30), tzinfo=zone)
    end = datetime.combine(session_date, time(16), tzinfo=zone)
    return start.isoformat(), end.isoformat(), session_date.isoformat()


def _record(
    *,
    manifest: AcquisitionManifest,
    meta: dict[str, Any],
    interval: BarInterval,
    timestamp: object,
    quote: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    moment = (
        None
        if timestamp is None
        else datetime.fromtimestamp(int(timestamp), tz=UTC)
    )
    provider_id = f"{manifest.symbol}-{interval.value}-{timestamp}"

    def value(field: str) -> object:
        values = quote.get(field)
        return values[index] if isinstance(values, list) and index < len(values) else None

    timezone_name = str(meta.get("exchangeTimezoneName") or manifest.response_timezone or "UTC")
    if interval is BarInterval.ONE_DAY and moment is not None:
        bar_start, bar_end, session_date = _daily_boundaries(moment, timezone_name)
        provider_timestamp = None
        session = BarSession.REGULAR
    else:
        bar_start = None
        bar_end = None
        provider_timestamp = None if moment is None else moment.isoformat()
        session_date = None if moment is None else moment.astimezone(_local_zone(timezone_name)).date().isoformat()
        session = BarSession.UNKNOWN if moment is None else _session(moment, timezone_name)

    return {
        "source_record_id": provider_id,
        "provider_schema": "MARKET_BAR_V1",
        "record_type": "MARKET_BAR",
        "fixture_origin": "SANITIZED_RECORDED_SAMPLE",
        "provider": manifest.provider,
        "provider_record_id": provider_id,
        "symbol": manifest.symbol,
        "exchange": meta.get("exchangeName"),
        "interval": interval.value,
        "provider_timestamp": provider_timestamp,
        "timestamp_meaning": BarTimestampMeaning.START.value,
        "bar_start": bar_start,
        "bar_end": bar_end,
        "open": value("open"),
        "high": value("high"),
        "low": value("low"),
        "close": value("close"),
        "volume": value("volume"),
        "trade_count": None,
        "vwap": None,
        "volume_unit": BarVolumeUnit.SHARES.value,
        "session": session.value,
        "session_date": session_date,
        "timezone": timezone_name,
        "status": BarCompletionStatus.COMPLETED.value,
        "publication_timestamp": manifest.retrieved_at.isoformat(),
        "capture_timestamp": manifest.retrieved_at.isoformat(),
        "provider_metadata": {
            "raw_acquisition_id": manifest.acquisition_id,
            "raw_sha256": manifest.raw_sha256,
            "adjustment_policy": manifest.adjustment_policy,
            "session_scope": manifest.session_scope,
            "price_hint": meta.get("priceHint"),
        },
    }


def normalize_acquired_market_bars(
    manifest: AcquisitionManifest,
    raw_bytes: bytes,
) -> HistoricalMarketDataset:
    if manifest.data_type not in {
        AcquisitionDataType.INTRADAY_MARKET_BARS,
        AcquisitionDataType.DAILY_MARKET_BARS,
    }:
        raise ValueError("manifest data type is not a supported market-bar acquisition")
    if manifest.result_state not in {
        AcquisitionResultState.SUCCESS,
        AcquisitionResultState.PARTIAL,
    }:
        raise ValueError("only successful or partial acquisitions can be normalized")
    digest = f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"
    if digest != manifest.raw_sha256:
        raise ValueError("raw bytes do not match the acquisition manifest SHA-256")

    document = json.loads(raw_bytes)
    chart = document.get("chart") if isinstance(document, dict) else None
    results = chart.get("result") if isinstance(chart, dict) else None
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise ValueError("market-bar raw response has no chart result")
    result = results[0]
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    timestamps = result.get("timestamp")
    indicators = result.get("indicators")
    quotes = indicators.get("quote") if isinstance(indicators, dict) else None
    quote = quotes[0] if isinstance(quotes, list) and quotes and isinstance(quotes[0], dict) else {}
    if not isinstance(timestamps, list):
        raise ValueError("market-bar raw response has no timestamp collection")

    raw_interval = str(meta.get("dataGranularity") or manifest.bar_size or "")
    interval = _INTERVALS.get(raw_interval) or _INTERVALS.get(str(manifest.bar_size))
    if interval is None:
        raise ValueError(f"unsupported acquired market-bar interval: {raw_interval}")

    records = tuple(
        MarketBarRecord.model_validate(
            _record(
                manifest=manifest,
                meta=meta,
                interval=interval,
                timestamp=timestamp,
                quote=quote,
                index=index,
            )
        )
        for index, timestamp in enumerate(timestamps)
    )
    context = AdapterContext(
        ingested_at=manifest.retrieved_at,
        source_timezone=manifest.response_timezone,
        provider=manifest.provider,
        adapter_version="phase-2v-outcome-acquisition.v1",
        normalization_version="market-bar-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.DOWNLOADED,
        source_endpoint_name=f"acquisition:{manifest.acquisition_id}",
    )
    normalized = normalize_market_bar_records(records, context)
    rejected = sum(
        1
        for item in normalized.diagnostics
        if item.severity.value == "ERROR" and not item.normalization_continued
    )
    observations = tuple(sorted(normalized.observations, key=_bar_order_key))
    identity = {
        "result_type": "PHASE_2V_HISTORICAL_MARKET_DATASET",
        "provider": manifest.provider,
        "adjustment_policy": manifest.adjustment_policy,
        "observation_ids": sorted(item.observation_id for item in observations),
        "rejected_record_count": rejected,
    }
    return HistoricalMarketDataset(
        acquisition_id=manifest.acquisition_id,
        raw_sha256=digest,
        provider=manifest.provider,
        adjustment_policy=manifest.adjustment_policy or "UNKNOWN",
        observations=observations,
        diagnostics=normalized.diagnostics,
        rejected_record_count=rejected,
        deterministic_id=deterministic_metric_id(identity),
    )


__all__ = ["HistoricalMarketDataset", "normalize_acquired_market_bars"]
