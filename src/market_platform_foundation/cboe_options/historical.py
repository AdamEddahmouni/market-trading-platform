"""Historical Cboe options volume archive and download characterization."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass

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
from .transport import CboeOptionsTransport


@dataclass(frozen=True, slots=True)
class HistoricalPcArchiveCapture:
    content_hash: str
    observations: tuple[OptionsMarketStatisticObservation, ...]


@dataclass(frozen=True, slots=True)
class HistoricalVolumeCharacterization:
    status: str
    form_url: str
    exchange_coverage: str
    aggregation_modes: tuple[str, ...]
    metric_modes: tuple[str, ...]
    notes: tuple[str, ...]


HISTORICAL_VOLUME_CHARACTERIZATION = HistoricalVolumeCharacterization(
    status="CHARACTERIZED_ONLY",
    form_url=CboeOptionsTransport.historical_volume_form_url(),
    exchange_coverage="CBOE_EXCHANGE_FAMILY",
    aggregation_modes=("daily", "weekly", "monthly", "annual"),
    metric_modes=("sum", "adv"),
    notes=(
        "Form POST URLs may fail without browser session — not canonical ingestion",
        "Historical volume is activity evidence — not chain, quote, or OI history",
        "ADV semantics follow source trading-day methodology",
    ),
)


def _content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest().upper()


def parse_totalpc_archive_csv(
    csv_text: str,
    *,
    retrieved_time: str,
    ingested_time: str,
    source_artifact_id: str = "cboe_totalpc_archive",
) -> HistoricalPcArchiveCapture:
    """Parse totalpc.csv historical put/call ratio archive."""

    content_hash = _content_hash(csv_text)
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise ValueError("CBOE_TOTALPC_SCHEMA_CHANGED")

    date_key = next((name for name in reader.fieldnames if "date" in name.lower()), reader.fieldnames[0])
    ratio_key = next((name for name in reader.fieldnames if "ratio" in name.lower() or "pc" in name.lower()), "")
    call_key = next((name for name in reader.fieldnames if "call" in name.lower()), "")
    put_key = next((name for name in reader.fieldnames if "put" in name.lower()), "")

    observations: list[OptionsMarketStatisticObservation] = []
    for row in reader:
        trade_date = parse_trade_date(row.get(date_key))
        if not trade_date:
            continue
        calls = parse_int(row.get(call_key)) if call_key else None
        puts = parse_int(row.get(put_key)) if put_key else None
        source_ratio = parse_ratio(row.get(ratio_key)) if ratio_key else None
        derived_ratio, reconciliation = reconcile_ratio(
            call_value=calls,
            put_value=puts,
            source_ratio=source_ratio,
        )
        flags = list(default_activity_flags())
        flags.append(CboeOptionsQualityFlag.HISTORICAL_PUBLICATION_TIME_UNKNOWN.value)
        if reconciliation == RatioReconciliationStatus.MISMATCH:
            flags.append(CboeOptionsQualityFlag.SOURCE_RATIO_MISMATCH.value)

        observations.append(
            OptionsMarketStatisticObservation(
                canonical_statistic_id="TOTAL_PUT_CALL_RATIO",
                statistic_family=OptionsStatisticFamily.PUT_CALL_RATIO,
                metric="PUT_CALL_RATIO",
                product_scope=ProductScope.TOTAL,
                exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
                market_scope=MarketScope.CBOE_EXCHANGES,
                coverage_scope=CoverageScope.CBOE_EXCHANGES,
                trade_date=trade_date,
                source_value=source_ratio,
                normalized_value=derived_ratio if derived_ratio is not None else source_ratio,
                unit="ratio",
                call_value=calls,
                put_value=puts,
                source_ratio=source_ratio,
                derived_ratio=derived_ratio,
                ratio_reconciliation_status=reconciliation,
                available_time=ingested_time,
                availability_precision=AvailabilityPrecision.UNKNOWN,
                provider_first_observed_time=ingested_time,
                retrieved_time=retrieved_time,
                ingested_time=ingested_time,
                source_artifact_id=source_artifact_id,
                content_hash=content_hash,
                feature_layer=OptionsFeatureLayer.RAW,
                history_class=PitHistoryClass.HISTORICAL_PUBLICATION_TIME_UNKNOWN,
                quality_flags=tuple(dict.fromkeys(flags)),
                provenance_ref=f"cboe_options:historical_pc:{trade_date}",
                predictive=False,
            )
        )

    return HistoricalPcArchiveCapture(content_hash=content_hash, observations=tuple(observations))


def characterize_historical_volume_download() -> HistoricalVolumeCharacterization:
    return HISTORICAL_VOLUME_CHARACTERIZATION


__all__ = [
    "HISTORICAL_VOLUME_CHARACTERIZATION",
    "HistoricalPcArchiveCapture",
    "HistoricalVolumeCharacterization",
    "characterize_historical_volume_download",
    "parse_totalpc_archive_csv",
]
