"""Parse Cboe daily options market statistics from embedded page JSON."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

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
from .normalize import parse_int, parse_iso_timestamp, parse_ratio, parse_trade_date, reconcile_ratio
from .quality import CboeOptionsQualityFlag, default_activity_flags
from .registry import RATIO_PRODUCT_TO_CANONICAL, STATISTIC_REGISTRY, resolve_product_scope


@dataclass(frozen=True, slots=True)
class DailyStatisticsCapture:
    trade_date: str
    last_updated: str
    source_artifact_id: str
    content_hash: str
    observations: tuple[OptionsMarketStatisticObservation, ...]


def _content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest().upper()


def _extract_options_data_json(html: str) -> dict[str, Any] | None:
    """Extract optionsData object from Cboe Next.js flight payloads."""

    markers = ('optionsData\\":{', '"optionsData":{', "optionsData':{")
    for marker in markers:
        start = html.find(marker)
        if start < 0:
            continue
        brace_start = html.find("{", start)
        if brace_start < 0:
            continue
        depth = 0
        for index in range(brace_start, min(len(html), brace_start + 250_000)):
            char = html[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    fragment = html[brace_start : index + 1]
                    for escaped, plain in (('\\"', '"'), ("\\\\", "\\")):
                        fragment = fragment.replace(escaped, plain)
                    try:
                        payload = json.loads(fragment)
                    except json.JSONDecodeError:
                        break
                    return payload if isinstance(payload, dict) else None
    return None


def _extract_trade_date_from_html(html: str) -> str:
    for key in ("tradeDate", "asOfDate", "reportDate"):
        value = _extract_meta(html, key)
        if value:
            return parse_trade_date(value)
    match = re.search(
        r"last updated[^0-9]*(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})",
        html,
        re.I,
    )
    if match:
        return parse_trade_date(match.group(1))
    match = re.search(r"(\d{4}-\d{2}-\d{2})", html)
    if match:
        return parse_trade_date(match.group(1))
    return ""


def _volume_rows_from_options_data(options_data: dict[str, Any]) -> list[tuple[ProductScope, str, dict[str, Any]]]:
    rows: list[tuple[ProductScope, str, dict[str, Any]]] = []
    for product_label, payload in options_data.items():
        if product_label == "ratios" or not isinstance(payload, list):
            continue
        product_scope = resolve_product_scope(str(product_label))
        for item in payload:
            if not isinstance(item, dict):
                continue
            metric_label = str(item.get("name") or "").upper()
            rows.append((product_scope, metric_label, item))
    return rows


def _extract_json_array(html: str, key: str) -> list[dict[str, Any]]:
    pattern = rf'"{re.escape(key)}"\s*:\s*(\[.*?\])'
    match = re.search(pattern, html, re.S)
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _extract_meta(html: str, key: str) -> str:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]+)"', html)
    return match.group(1) if match else ""


def _ratio_product_from_label(label: str) -> ProductScope:
    text = label.strip().upper()
    if "TOTAL PUT/CALL" in text:
        return ProductScope.TOTAL
    if "INDEX PUT/CALL" in text:
        return ProductScope.INDEX
    if "EXCHANGE TRADED PRODUCTS PUT/CALL" in text:
        return ProductScope.EXCHANGE_TRADED_PRODUCT
    if "EQUITY PUT/CALL" in text:
        return ProductScope.EQUITY
    if "VIX" in text and "PUT/CALL" in text:
        return ProductScope.VIX
    if "SPX + SPXW" in text or "SPX+SPXW" in text:
        return ProductScope.SPX_SPXW
    return ProductScope.OTHER


def _base_flags(*extra: str) -> tuple[str, ...]:
    flags = list(default_activity_flags())
    flags.extend(extra)
    return tuple(dict.fromkeys(flags))


def _make_ratio_observation(
    *,
    product_scope: ProductScope,
    source_ratio: float | None,
    call_value: int | None,
    put_value: int | None,
    trade_date: str,
    available_time: str,
    retrieved_time: str,
    ingested_time: str,
    source_artifact_id: str,
    content_hash: str,
    canonical_id: str | None = None,
) -> OptionsMarketStatisticObservation:
    derived_ratio, reconciliation = reconcile_ratio(
        call_value=call_value,
        put_value=put_value,
        source_ratio=source_ratio,
    )
    flags = _base_flags()
    if reconciliation == RatioReconciliationStatus.MISMATCH:
        flags = _base_flags(CboeOptionsQualityFlag.SOURCE_RATIO_MISMATCH.value)
    if reconciliation == RatioReconciliationStatus.UNDEFINED_DENOMINATOR and source_ratio is None:
        flags = _base_flags(CboeOptionsQualityFlag.UNDEFINED_RATIO.value)
    if source_ratio is None and derived_ratio is None:
        flags = _base_flags(CboeOptionsQualityFlag.MISSING_VALUE.value)

    registry = STATISTIC_REGISTRY.get(canonical_id or RATIO_PRODUCT_TO_CANONICAL.get(product_scope, ""))
    canonical_statistic_id = registry.canonical_statistic_id if registry else f"{product_scope.value}_PUT_CALL_RATIO"

    return OptionsMarketStatisticObservation(
        canonical_statistic_id=canonical_statistic_id,
        statistic_family=OptionsStatisticFamily.PUT_CALL_RATIO,
        metric="PUT_CALL_RATIO",
        product_scope=product_scope,
        exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        trade_date=trade_date,
        source_value=source_ratio,
        normalized_value=derived_ratio if derived_ratio is not None else source_ratio,
        unit="ratio",
        call_value=call_value,
        put_value=put_value,
        source_ratio=source_ratio,
        derived_ratio=derived_ratio,
        ratio_reconciliation_status=reconciliation,
        source_data_as_of_time=available_time,
        available_time=available_time,
        availability_precision=AvailabilityPrecision.FIRST_OBSERVED,
        provider_first_observed_time=available_time,
        retrieved_time=retrieved_time,
        ingested_time=ingested_time,
        source_artifact_id=source_artifact_id,
        content_hash=content_hash,
        feature_layer=OptionsFeatureLayer.RAW,
        history_class=PitHistoryClass.PROSPECTIVE_VERSIONED_PIT,
        quality_flags=flags,
        provenance_ref=f"cboe_options:daily:{canonical_statistic_id}:{trade_date}",
        predictive=False,
    )


def _make_volume_oi_observation(
    *,
    product_scope: ProductScope,
    metric: str,
    statistic_family: OptionsStatisticFamily,
    call_value: int | None,
    put_value: int | None,
    total_value: int | None,
    trade_date: str,
    available_time: str,
    retrieved_time: str,
    ingested_time: str,
    source_artifact_id: str,
    content_hash: str,
) -> OptionsMarketStatisticObservation:
    canonical_id = {
        (OptionsStatisticFamily.OPTION_VOLUME, ProductScope.TOTAL, "CALL_VOLUME"): "TOTAL_CALL_VOLUME",
        (OptionsStatisticFamily.OPTION_VOLUME, ProductScope.TOTAL, "PUT_VOLUME"): "TOTAL_PUT_VOLUME",
        (OptionsStatisticFamily.OPEN_INTEREST, ProductScope.TOTAL, "TOTAL_OPEN_INTEREST"): "TOTAL_OPEN_INTEREST",
    }.get((statistic_family, product_scope, metric), f"{product_scope.value}_{metric}")

    flags = _base_flags()
    if total_value is None and call_value is None and put_value is None:
        flags = _base_flags(CboeOptionsQualityFlag.MISSING_VALUE.value)

    return OptionsMarketStatisticObservation(
        canonical_statistic_id=canonical_id,
        statistic_family=statistic_family,
        metric=metric,
        product_scope=product_scope,
        exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        trade_date=trade_date,
        source_value=float(total_value) if total_value is not None else None,
        normalized_value=float(total_value) if total_value is not None else None,
        unit="contracts",
        call_value=call_value,
        put_value=put_value,
        total_value=total_value,
        source_data_as_of_time=available_time,
        available_time=available_time,
        availability_precision=AvailabilityPrecision.FIRST_OBSERVED,
        provider_first_observed_time=available_time,
        retrieved_time=retrieved_time,
        ingested_time=ingested_time,
        source_artifact_id=source_artifact_id,
        content_hash=content_hash,
        feature_layer=OptionsFeatureLayer.RAW,
        history_class=PitHistoryClass.PROSPECTIVE_VERSIONED_PIT,
        quality_flags=flags,
        provenance_ref=f"cboe_options:daily:{canonical_id}:{trade_date}",
        predictive=False,
    )


def parse_daily_statistics_html(
    html: str,
    *,
    retrieved_time: str,
    ingested_time: str,
    source_artifact_id: str = "cboe_daily_market_statistics",
) -> DailyStatisticsCapture:
    """Extract put/call ratios and volume/OI arrays embedded in daily page HTML."""

    content_hash = _content_hash(html)
    trade_date = parse_trade_date(_extract_meta(html, "tradeDate"))
    last_updated = parse_iso_timestamp(_extract_meta(html, "lastUpdated"))
    available_time = last_updated or ingested_time

    options_data = _extract_options_data_json(html)
    if options_data:
        if not trade_date:
            trade_date = _extract_trade_date_from_html(html)
        if not last_updated:
            last_updated = available_time

    observations: list[OptionsMarketStatisticObservation] = []
    volume_by_product: dict[tuple[ProductScope, str], dict[str, int | None]] = {}

    ratio_rows = _extract_json_array(html, "putCallRatios")
    if not ratio_rows and options_data:
        ratio_rows = options_data.get("ratios") if isinstance(options_data.get("ratios"), list) else []

    for row in ratio_rows:
        label = str(row.get("name") or row.get("label") or row.get("product") or "")
        product_scope = _ratio_product_from_label(label)
        if product_scope == ProductScope.OTHER:
            product_scope = resolve_product_scope(label)
        source_ratio = parse_ratio(row.get("value") or row.get("ratio"))
        call_value = parse_int(row.get("call") or row.get("calls"))
        put_value = parse_int(row.get("put") or row.get("puts"))
        observations.append(
            _make_ratio_observation(
                product_scope=product_scope,
                source_ratio=source_ratio,
                call_value=call_value,
                put_value=put_value,
                trade_date=trade_date,
                available_time=available_time,
                retrieved_time=retrieved_time,
                ingested_time=ingested_time,
                source_artifact_id=source_artifact_id,
                content_hash=content_hash,
            )
        )

    volume_rows = _extract_json_array(html, "volumeAndOpenInterest")
    if not volume_rows and options_data:
        for product_scope, metric_label, item in _volume_rows_from_options_data(options_data):
            call_value = parse_int(item.get("call") or item.get("calls"))
            put_value = parse_int(item.get("put") or item.get("puts"))
            total_value = parse_int(item.get("total"))
            key = (product_scope, metric_label)
            bucket = volume_by_product.setdefault(key, {})
            bucket["call"] = call_value
            bucket["put"] = put_value
            bucket["total"] = total_value
    else:
        for row in volume_rows:
            product_label = str(row.get("product") or row.get("category") or row.get("name") or "")
            metric_label = str(row.get("name") or row.get("metric") or "").upper()
            product_scope = resolve_product_scope(product_label)
            call_value = parse_int(row.get("call") or row.get("calls"))
            put_value = parse_int(row.get("put") or row.get("puts"))
            total_value = parse_int(row.get("total"))
            key = (product_scope, metric_label)
            bucket = volume_by_product.setdefault(key, {})
            bucket["call"] = call_value
            bucket["put"] = put_value
            bucket["total"] = total_value

    if not trade_date and ingested_time:
        trade_date = parse_trade_date(ingested_time[:10])

    for (product_scope, metric_label), values in volume_by_product.items():
        if "OPEN INTEREST" in metric_label:
            family = OptionsStatisticFamily.OPEN_INTEREST
            metric = "TOTAL_OPEN_INTEREST"
        elif "VOLUME" in metric_label:
            family = OptionsStatisticFamily.OPTION_VOLUME
            metric = metric_label.replace(" ", "_") or "TOTAL_VOLUME"
        else:
            continue
        observations.append(
            _make_volume_oi_observation(
                product_scope=product_scope,
                metric=metric,
                statistic_family=family,
                call_value=values.get("call"),
                put_value=values.get("put"),
                total_value=values.get("total"),
                trade_date=trade_date,
                available_time=available_time,
                retrieved_time=retrieved_time,
                ingested_time=ingested_time,
                source_artifact_id=source_artifact_id,
                content_hash=content_hash,
            )
        )

    if not observations:
        observations.append(
            OptionsMarketStatisticObservation(
                canonical_statistic_id="DAILY_STATISTICS_UNPARSED",
                statistic_family=OptionsStatisticFamily.PUT_CALL_RATIO,
                metric="PUT_CALL_RATIO",
                product_scope=ProductScope.TOTAL,
                exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
                market_scope=MarketScope.CBOE_EXCHANGES,
                coverage_scope=CoverageScope.CBOE_EXCHANGES,
                trade_date=trade_date,
                source_value=None,
                normalized_value=None,
                unit="ratio",
                available_time=available_time,
                availability_precision=AvailabilityPrecision.UNKNOWN,
                retrieved_time=retrieved_time,
                ingested_time=ingested_time,
                source_artifact_id=source_artifact_id,
                content_hash=content_hash,
                quality_flags=_base_flags(
                    CboeOptionsQualityFlag.SCHEMA_CHANGED.value,
                    CboeOptionsQualityFlag.MISSING_VALUE.value,
                ),
                provenance_ref="cboe_options:daily:unparsed",
                predictive=False,
            )
        )

    return DailyStatisticsCapture(
        trade_date=trade_date,
        last_updated=last_updated,
        source_artifact_id=source_artifact_id,
        content_hash=content_hash,
        observations=tuple(observations),
    )


__all__ = ["DailyStatisticsCapture", "parse_daily_statistics_html"]
