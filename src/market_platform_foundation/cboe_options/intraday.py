"""Parse Cboe exchange intraday cumulative statistics."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .contracts import (
    AvailabilityPrecision,
    CoverageScope,
    ExchangeScope,
    MarketScope,
    OptionsFeatureLayer,
    OptionsMarketStatisticObservation,
    OptionsStatisticFamily,
    PitHistoryClass,
    ProductScope,
    RatioReconciliationStatus,
)
from .normalize import parse_int, parse_ratio, parse_trade_date, reconcile_ratio
from .quality import CboeOptionsQualityFlag, default_activity_flags

CHICAGO = ZoneInfo("America/Chicago")


@dataclass(frozen=True, slots=True)
class IntradayStatisticsCapture:
    trade_date: str
    exchange_scope: ExchangeScope
    timezone: str
    content_hash: str
    cumulative: tuple[OptionsMarketStatisticObservation, ...]
    intervals: tuple[OptionsMarketStatisticObservation, ...]


def _content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest().upper()


def _base_flags(*extra: str) -> tuple[str, ...]:
    flags = list(default_activity_flags())
    flags.extend(extra)
    return tuple(dict.fromkeys(flags))


def _extract_rows(html: str) -> list[dict[str, Any]]:
    next_match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.S,
    )
    if next_match:
        try:
            payload = json.loads(next_match.group(1))
        except json.JSONDecodeError:
            payload = {}
        text = json.dumps(payload)
        for key in ("intradayStatistics", "marketStatistics", "timeBuckets", "rows"):
            match = re.search(rf'"{key}"\s*:\s*(\[.*?\])', text, re.S)
            if match:
                try:
                    rows = json.loads(match.group(1))
                    if isinstance(rows, list) and rows:
                        return rows
                except json.JSONDecodeError:
                    pass

    for key in ("intradayStatistics", "marketStatistics", "timeBuckets"):
        rows = _extract_embedded_array(html, key)
        if rows:
            return rows
    return []


def _extract_embedded_array(html: str, key: str) -> list[dict[str, Any]]:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*(\[.*?\])', html, re.S)
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _bucket_timestamp(trade_date: str, time_label: str) -> tuple[str, str]:
    trade = parse_trade_date(trade_date)
    label = time_label.strip().upper().replace(" CT", "").replace(" CST", "").replace(" CDT", "")
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            clock = datetime.strptime(label, fmt).time()
            start = datetime.fromisoformat(f"{trade}T{clock.hour:02d}:{clock.minute:02d}:00").replace(tzinfo=CHICAGO)
            end = start
            return start.isoformat(), end.isoformat()
        except ValueError:
            continue
    return "", ""


def _cumulative_observation(
    *,
    trade_date: str,
    bucket_start: str,
    bucket_end: str,
    calls: int | None,
    puts: int | None,
    total: int | None,
    source_ratio: float | None,
    retrieved_time: str,
    ingested_time: str,
    source_artifact_id: str,
    content_hash: str,
    quality_flags: tuple[str, ...],
) -> OptionsMarketStatisticObservation:
    derived_ratio, reconciliation = reconcile_ratio(
        call_value=calls,
        put_value=puts,
        source_ratio=source_ratio,
    )
    flags = _base_flags(*quality_flags)
    if reconciliation == RatioReconciliationStatus.MISMATCH:
        flags = _base_flags(*quality_flags, CboeOptionsQualityFlag.SOURCE_RATIO_MISMATCH.value)

    return OptionsMarketStatisticObservation(
        canonical_statistic_id="CBOE_INTRADAY_CUMULATIVE",
        statistic_family=OptionsStatisticFamily.INTRADAY_CUMULATIVE,
        metric="CUMULATIVE_VOLUME",
        product_scope=ProductScope.TOTAL,
        exchange_scope=ExchangeScope.CBOE_OPTIONS,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        trade_date=trade_date,
        bucket_start=bucket_start,
        bucket_end=bucket_end,
        source_value=float(total) if total is not None else None,
        normalized_value=float(total) if total is not None else None,
        unit="contracts",
        call_value=calls,
        put_value=puts,
        total_value=total,
        source_ratio=source_ratio,
        derived_ratio=derived_ratio,
        ratio_reconciliation_status=reconciliation,
        source_data_as_of_time=bucket_end or ingested_time,
        available_time=bucket_end or ingested_time,
        availability_precision=AvailabilityPrecision.TIMESTAMP,
        provider_first_observed_time=ingested_time,
        retrieved_time=retrieved_time,
        ingested_time=ingested_time,
        source_artifact_id=source_artifact_id,
        content_hash=content_hash,
        timezone="America/Chicago",
        feature_layer=OptionsFeatureLayer.RAW,
        history_class=PitHistoryClass.CURRENT_SNAPSHOT_ONLY,
        quality_flags=flags,
        provenance_ref=f"cboe_options:intraday:cumulative:{trade_date}:{bucket_start}",
        predictive=False,
    )


def _interval_observation(
    *,
    trade_date: str,
    bucket_start: str,
    bucket_end: str,
    calls: int | None,
    puts: int | None,
    total: int | None,
    retrieved_time: str,
    ingested_time: str,
    source_artifact_id: str,
    content_hash: str,
    quality_flags: tuple[str, ...],
) -> OptionsMarketStatisticObservation:
    return OptionsMarketStatisticObservation(
        canonical_statistic_id="CBOE_INTRADAY_INTERVAL",
        statistic_family=OptionsStatisticFamily.INTRADAY_INTERVAL,
        metric="INTERVAL_VOLUME",
        product_scope=ProductScope.TOTAL,
        exchange_scope=ExchangeScope.CBOE_OPTIONS,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        trade_date=trade_date,
        bucket_start=bucket_start,
        bucket_end=bucket_end,
        source_value=float(total) if total is not None else None,
        normalized_value=float(total) if total is not None else None,
        unit="contracts",
        call_value=calls,
        put_value=puts,
        total_value=total,
        source_data_as_of_time=bucket_end or ingested_time,
        available_time=bucket_end or ingested_time,
        availability_precision=AvailabilityPrecision.TIMESTAMP,
        provider_first_observed_time=ingested_time,
        retrieved_time=retrieved_time,
        ingested_time=ingested_time,
        source_artifact_id=source_artifact_id,
        content_hash=content_hash,
        timezone="America/Chicago",
        feature_layer=OptionsFeatureLayer.DETERMINISTIC_DERIVED,
        history_class=PitHistoryClass.CURRENT_SNAPSHOT_ONLY,
        quality_flags=_base_flags(*quality_flags),
        provenance_ref=f"cboe_options:intraday:interval:{trade_date}:{bucket_start}",
        predictive=False,
    )


def parse_intraday_statistics_html(
    html: str,
    *,
    retrieved_time: str,
    ingested_time: str,
    trade_date: str = "",
    source_artifact_id: str = "cboe_intraday_market_statistics",
    exchange_scope: ExchangeScope = ExchangeScope.CBOE_OPTIONS,
) -> IntradayStatisticsCapture:
    content_hash = _content_hash(html)
    parsed_trade_date = parse_trade_date(trade_date) or parse_trade_date(
        re.search(r'"tradeDate"\s*:\s*"([^"]+)"', html).group(1)
        if re.search(r'"tradeDate"\s*:\s*"([^"]+)"', html)
        else ""
    )

    rows = _extract_rows(html)
    cumulative_rows: list[OptionsMarketStatisticObservation] = []
    interval_rows: list[OptionsMarketStatisticObservation] = []
    previous_calls: int | None = None
    previous_puts: int | None = None
    previous_total: int | None = None

    for row in rows:
        time_label = str(row.get("time") or row.get("bucket") or row.get("label") or "")
        bucket_start, bucket_end = _bucket_timestamp(parsed_trade_date, time_label)
        calls = parse_int(row.get("calls") or row.get("call"))
        puts = parse_int(row.get("puts") or row.get("put"))
        total = parse_int(row.get("total"))
        source_ratio = parse_ratio(row.get("pcRatio") or row.get("ratio") or row.get("pc_ratio"))

        flags: list[str] = []
        if previous_calls is not None and calls is not None and calls < previous_calls:
            flags.append(CboeOptionsQualityFlag.CUMULATIVE_SERIES_NONMONOTONIC.value)
        if previous_puts is not None and puts is not None and puts < previous_puts:
            flags.append(CboeOptionsQualityFlag.CUMULATIVE_SERIES_NONMONOTONIC.value)
        if previous_total is not None and total is not None and total < previous_total:
            flags.append(CboeOptionsQualityFlag.CUMULATIVE_SERIES_NONMONOTONIC.value)

        cumulative_rows.append(
            _cumulative_observation(
                trade_date=parsed_trade_date,
                bucket_start=bucket_start,
                bucket_end=bucket_end,
                calls=calls,
                puts=puts,
                total=total,
                source_ratio=source_ratio,
                retrieved_time=retrieved_time,
                ingested_time=ingested_time,
                source_artifact_id=source_artifact_id,
                content_hash=content_hash,
                quality_flags=tuple(flags),
            )
        )

        interval_calls = None if calls is None or previous_calls is None else calls - previous_calls
        interval_puts = None if puts is None or previous_puts is None else puts - previous_puts
        interval_total = None if total is None or previous_total is None else total - previous_total
        interval_flags = list(flags)
        if any(value is not None and value < 0 for value in (interval_calls, interval_puts, interval_total)):
            interval_flags.append(CboeOptionsQualityFlag.CUMULATIVE_SERIES_NONMONOTONIC.value)
            interval_calls = interval_puts = interval_total = None

        if previous_calls is not None:
            interval_rows.append(
                _interval_observation(
                    trade_date=parsed_trade_date,
                    bucket_start=bucket_start,
                    bucket_end=bucket_end,
                    calls=interval_calls,
                    puts=interval_puts,
                    total=interval_total,
                    retrieved_time=retrieved_time,
                    ingested_time=ingested_time,
                    source_artifact_id=source_artifact_id,
                    content_hash=content_hash,
                    quality_flags=tuple(interval_flags),
                )
            )

        previous_calls, previous_puts, previous_total = calls, puts, total

    return IntradayStatisticsCapture(
        trade_date=parsed_trade_date,
        exchange_scope=exchange_scope,
        timezone="America/Chicago",
        content_hash=content_hash,
        cumulative=tuple(cumulative_rows),
        intervals=tuple(interval_rows),
    )


__all__ = ["IntradayStatisticsCapture", "parse_intraday_statistics_html"]
