"""Parse U.S. options market volume and market-share CSV."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass

from .contracts import (
    AvailabilityPrecision,
    CoverageScope,
    ExchangeGroupCode,
    ExchangeScope,
    MarketScope,
    OptionsFeatureLayer,
    OptionsMarketStatisticObservation,
    OptionsStatisticFamily,
    PitHistoryClass,
    ProductScope,
)
from .normalize import parse_float, parse_int, parse_trade_date
from .quality import CboeOptionsQualityFlag, default_activity_flags
from .registry import resolve_exchange_group


DELAY_POLICY_MINIMUM = "DELAYED_DATA_MINIMUM_20_MINUTES"


@dataclass(frozen=True, slots=True)
class MarketVolumeCapture:
    trade_date: str
    source_data_as_of_time: str
    content_hash: str
    observations: tuple[OptionsMarketStatisticObservation, ...]


def _content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest().upper()


def _base_flags(*extra: str) -> tuple[str, ...]:
    flags = list(default_activity_flags())
    flags.append(CboeOptionsQualityFlag.DELAYED_DATA.value)
    flags.extend(extra)
    return tuple(dict.fromkeys(flags))


def _matched_volume_id(group: ExchangeGroupCode) -> str:
    if group == ExchangeGroupCode.ALL_MARKET:
        return "US_OPTIONS_TOTAL_MATCHED_VOLUME"
    if group == ExchangeGroupCode.CBOE_GROUP:
        return "CBOE_GROUP_MATCHED_VOLUME"
    return f"{group.value}_MATCHED_VOLUME"


def _market_share_id(group: ExchangeGroupCode) -> str:
    if group == ExchangeGroupCode.CBOE_GROUP:
        return "CBOE_GROUP_MARKET_SHARE"
    return f"{group.value}_MARKET_SHARE"


def parse_market_volume_csv(
    csv_text: str,
    *,
    retrieved_time: str,
    ingested_time: str,
    trade_date: str = "",
    source_data_as_of_time: str = "",
    source_artifact_id: str = "cboe_market_volume_summary",
) -> MarketVolumeCapture:
    """Map Market Participant rows to exchange groups; publisher remains CBOE."""

    content_hash = _content_hash(csv_text)
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise ValueError("CBOE_MARKET_VOLUME_SCHEMA_CHANGED")

    observations: list[OptionsMarketStatisticObservation] = []
    group_volumes: dict[ExchangeGroupCode, int] = {}
    group_shares: dict[ExchangeGroupCode, float] = {}
    parsed_trade_date = parse_trade_date(trade_date)
    parsed_as_of = source_data_as_of_time or ingested_time
    available_time = ingested_time

    participant_key = next(
        (name for name in reader.fieldnames if name.lower().replace("_", " ") in {"market participant", "participant", "exchange"}),
        reader.fieldnames[0],
    )
    volume_key = next(
        (
            name
            for name in reader.fieldnames
            if any(
                token in name.lower()
                for token in ("matched", "volume", "contracts", "total option")
            )
        ),
        "",
    )
    share_key = next((name for name in reader.fieldnames if "share" in name.lower()), "")
    date_key = next(
        (name for name in reader.fieldnames if "date" in name.lower() or name.lower() == "day"),
        "",
    )

    for row in reader:
        participant = str(row.get(participant_key, "")).strip()
        if not participant:
            continue
        group = resolve_exchange_group(participant)
        if group is None:
            continue
        matched = parse_int(row.get(volume_key))
        share = parse_float(row.get(share_key))
        if date_key and not parsed_trade_date:
            parsed_trade_date = parse_trade_date(row.get(date_key))
        if matched is not None:
            group_volumes[group] = matched
        if share is not None:
            group_shares[group] = share

    total_row = group_volumes.get(ExchangeGroupCode.ALL_MARKET)
    if not group_shares and total_row:
        for group, matched in group_volumes.items():
            if group == ExchangeGroupCode.ALL_MARKET or matched is None:
                continue
            group_shares[group] = matched / total_row

    component_total = sum(
        volume
        for group, volume in group_volumes.items()
        if group != ExchangeGroupCode.ALL_MARKET
    )
    reconciliation_flags: list[str] = []
    if total_row is not None and component_total and abs(total_row - component_total) > max(1, total_row * 0.01):
        reconciliation_flags.append(CboeOptionsQualityFlag.TOTAL_RECONCILIATION_MISMATCH.value)

    for group, matched in group_volumes.items():
        exchange_scope = ExchangeScope.CBOE_GROUP if group == ExchangeGroupCode.CBOE_GROUP else ExchangeScope.UNSPECIFIED
        observations.append(
            OptionsMarketStatisticObservation(
                canonical_statistic_id=_matched_volume_id(group),
                statistic_family=OptionsStatisticFamily.MATCHED_VOLUME,
                metric="MATCHED_VOLUME",
                product_scope=ProductScope.TOTAL,
                exchange_scope=exchange_scope,
                market_scope=MarketScope.US_OPTIONS_MARKET,
                coverage_scope=CoverageScope.US_OPTIONS_MARKET,
                trade_date=parsed_trade_date,
                source_value=float(matched),
                normalized_value=float(matched),
                unit="contracts",
                total_value=matched,
                publisher="CBOE",
                reported_exchange_group=group,
                source_data_as_of_time=parsed_as_of,
                available_time=available_time,
                availability_precision=AvailabilityPrecision.DELAY_POLICY_BOUND,
                provider_first_observed_time=available_time,
                retrieved_time=retrieved_time,
                ingested_time=ingested_time,
                source_artifact_id=source_artifact_id,
                source_delay_policy=DELAY_POLICY_MINIMUM,
                content_hash=content_hash,
                feature_layer=OptionsFeatureLayer.RAW,
                history_class=PitHistoryClass.PROSPECTIVE_VERSIONED_PIT,
                quality_flags=_base_flags(*reconciliation_flags),
                provenance_ref=f"cboe_options:market_volume:{group.value}:{parsed_trade_date}",
                predictive=False,
            )
        )

    for group, share in group_shares.items():
        exchange_scope = ExchangeScope.CBOE_GROUP if group == ExchangeGroupCode.CBOE_GROUP else ExchangeScope.UNSPECIFIED
        observations.append(
            OptionsMarketStatisticObservation(
                canonical_statistic_id=_market_share_id(group),
                statistic_family=OptionsStatisticFamily.MARKET_SHARE,
                metric="MARKET_SHARE",
                product_scope=ProductScope.TOTAL,
                exchange_scope=exchange_scope,
                market_scope=MarketScope.US_OPTIONS_MARKET,
                coverage_scope=CoverageScope.US_OPTIONS_MARKET,
                trade_date=parsed_trade_date,
                source_value=share,
                normalized_value=share,
                unit="fraction",
                publisher="CBOE",
                reported_exchange_group=group,
                source_data_as_of_time=parsed_as_of,
                available_time=available_time,
                availability_precision=AvailabilityPrecision.DELAY_POLICY_BOUND,
                provider_first_observed_time=available_time,
                retrieved_time=retrieved_time,
                ingested_time=ingested_time,
                source_artifact_id=source_artifact_id,
                source_delay_policy=DELAY_POLICY_MINIMUM,
                content_hash=content_hash,
                feature_layer=OptionsFeatureLayer.RAW,
                history_class=PitHistoryClass.PROSPECTIVE_VERSIONED_PIT,
                quality_flags=_base_flags(*reconciliation_flags),
                provenance_ref=f"cboe_options:market_share:{group.value}:{parsed_trade_date}",
                predictive=False,
            )
        )

    return MarketVolumeCapture(
        trade_date=parsed_trade_date,
        source_data_as_of_time=parsed_as_of,
        content_hash=content_hash,
        observations=tuple(observations),
    )


__all__ = ["DELAY_POLICY_MINIMUM", "MarketVolumeCapture", "parse_market_volume_csv"]
