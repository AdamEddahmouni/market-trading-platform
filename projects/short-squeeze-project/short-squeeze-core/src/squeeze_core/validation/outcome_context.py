"""Additive context evidence for the BIYA outcome amendment.

FINRA daily short-sale volume deliberately has its own contract.  News and corporate
actions use Phase 1 observations; unavailable domains remain explicit empty contexts.
"""

import csv
import hashlib
import io
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.finra import normalize_finra_short_interest_records
from squeeze_core.adapters.news import normalize_news_records
from squeeze_core.contracts import (
    AssetClass,
    Completeness,
    CorporateActionPayload,
    DataFreshness,
    EntitlementState,
    EventType,
    IngestionMethod,
    MarketSession,
    Observation,
    ObservationKind,
    PayloadType,
    Provenance,
    Quality,
    QualityState,
)
from squeeze_core.metrics.identifiers import deterministic_metric_id

from .outcome_acquisition import AcquisitionDataType, AcquisitionManifest
from .outcome_amendment import BIYA_EARLIEST_BOUNDARY, BIYA_LATEST_BOUNDARY


class EvidenceAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class NewsTiming(StrEnum):
    BEFORE_EARLIEST_BOUNDARY = "BEFORE_EARLIEST_BOUNDARY"
    WITHIN_DETECTION_WINDOW = "WITHIN_DETECTION_WINDOW"
    AFTER_LATEST_BOUNDARY = "AFTER_LATEST_BOUNDARY"
    UNKNOWN = "UNKNOWN"


class NewsTimingItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    observation_id: str
    headline: str
    publisher: str | None
    publication_time: datetime | None
    retrieval_time: datetime
    sanitized_url: str | None = None
    timing: NewsTiming


class NewsTimingCollection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    data_type: str = "NEWS"
    acquisition_id: str
    observations: tuple[Observation, ...]
    items: tuple[NewsTimingItem, ...]
    diagnostics: tuple[object, ...] = ()
    deterministic_id: str


class FinraShortSaleVolumeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    trade_date: date
    symbol: str
    short_volume: Decimal
    short_exempt_volume: Decimal
    total_volume: Decimal
    market_scope: str


class FinraShortSaleVolumeCollection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    data_type: str = "FINRA_SHORT_SALE_VOLUME"
    acquisition_id: str
    provider: str
    retrieved_at: datetime
    records: tuple[FinraShortSaleVolumeRecord, ...]
    limitations: tuple[str, ...] = (
        "Daily short-sale volume is transactional volume and is not published short interest.",
    )
    deterministic_id: str


class CorporateActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    observation_id: str
    action_type: str
    effective_date: date
    split_ratio: str | None = None


class CorporateActionCollection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    data_type: str = "CORPORATE_ACTIONS"
    acquisition_id: str
    observations: tuple[Observation, ...]
    actions: tuple[CorporateActionItem, ...]
    limitations: tuple[str, ...]
    deterministic_id: str


class UnavailableEvidenceContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    data_type: str
    acquisition_manifest_id: str
    availability: EvidenceAvailability = EvidenceAvailability.UNAVAILABLE
    evidence_ids: tuple[str, ...] = ()
    limitation: str
    deterministic_id: str


class PublishedShortInterestCollection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    data_type: str = "PUBLISHED_SHORT_INTEREST"
    acquisition_id: str
    provider: str
    retrieved_at: datetime
    observations: tuple[Observation, ...]
    limitations: tuple[str, ...] = (
        "Published short interest is a settlement-period position, not daily short-sale volume.",
    )
    deterministic_id: str


def _finra_si_row(row: dict[str, str], line_no: int, symbol: str) -> dict[str, object] | None:
    row_symbol = (
        row.get("Symbol")
        or row.get("symbol")
        or row.get("SYMBOL")
        or ""
    ).strip().upper()
    if row_symbol != symbol:
        return None
    short_shares = (
        row.get("Current Short Position")
        or row.get("Short Shares")
        or row.get("short_shares")
        or ""
    ).strip()
    settlement = (
        row.get("Settlement Date")
        or row.get("settlement_date")
        or row.get("SettlementDate")
        or ""
    ).strip()
    if not short_shares or not settlement:
        return None
    previous = (row.get("Previous Short Position") or row.get("previous_short_shares") or "").strip()
    pct = row.get("Short % of Float") or row.get("short_float_percent") or ""
    publication = row.get("Publication Date") or ""
    if not publication:
        settlement_date = datetime.strptime(settlement, "%Y-%m-%d").date()
        if settlement_date.day <= 15:
            publication = f"{settlement_date.year}-{settlement_date.month:02d}-27"
        else:
            next_month = settlement_date.month + 1
            year = settlement_date.year
            if next_month > 12:
                next_month = 1
                year += 1
            publication = f"{year}-{next_month:02d}-11"
    return {
        "source_record_id": f"finra-si-line-{line_no}",
        "provider_schema": "FINRA_SHORT_INTEREST_V1",
        "record_type": "PUBLISHED_SHORT_INTEREST",
        "fixture_origin": "SANITIZED_RECORDED_SAMPLE",
        "symbol": row_symbol,
        "short_shares": short_shares.replace(",", ""),
        "previous_short_shares": previous.replace(",", "") if previous else None,
        "settlement_date": settlement,
        "publication_date": publication,
        "publication_timezone": "UTC",
        "date_only_publication_policy": "END_OF_PUBLICATION_DATE",
        "short_float_percent": pct.replace("%", "").strip() if pct else None,
        "short_float_percent_unit": "PERCENT_POINTS" if pct else None,
        "revision_status": row.get("record_status") or "ORIGINAL",
    }


def _verify(manifest: AcquisitionManifest, raw: bytes, kind: AcquisitionDataType) -> None:
    if manifest.data_type is not kind:
        raise ValueError(f"expected {kind.value} acquisition")
    digest = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    if digest != manifest.raw_sha256:
        raise ValueError("raw bytes do not match acquisition manifest")


def _timing(moment: datetime | None) -> NewsTiming:
    if moment is None:
        return NewsTiming.UNKNOWN
    if moment < BIYA_EARLIEST_BOUNDARY:
        return NewsTiming.BEFORE_EARLIEST_BOUNDARY
    if moment <= BIYA_LATEST_BOUNDARY:
        return NewsTiming.WITHIN_DETECTION_WINDOW
    return NewsTiming.AFTER_LATEST_BOUNDARY


def normalize_yahoo_news(manifest: AcquisitionManifest, raw: bytes) -> NewsTimingCollection:
    _verify(manifest, raw, AcquisitionDataType.NEWS)
    document = json.loads(raw)
    items = document.get("news", [])
    records = []
    for item in items:
        published = item.get("providerPublishTime")
        records.append({
            "source_record_id": str(item.get("uuid")),
            "provider_schema": "NEWS_ITEM_V1",
            "record_type": "NEWS_ITEM",
            "fixture_origin": "SANITIZED_RECORDED_SAMPLE",
            "source_shape": "PROVIDER_NEUTRAL",
            "provider": manifest.provider,
            "provider_record_id": str(item.get("uuid")),
            "headline": item.get("title"),
            "publisher": item.get("publisher"),
            "published_at": None if published is None else datetime.fromtimestamp(int(published), UTC).isoformat(),
            "capture_timestamp": manifest.retrieved_at.isoformat(),
            "symbols": item.get("relatedTickers") or [manifest.symbol],
            "content_type": item.get("type"),
            "provider_metadata": {
                "raw_acquisition_id": manifest.acquisition_id,
                "raw_sha256": manifest.raw_sha256,
            },
        })
    context = AdapterContext(
        ingested_at=manifest.retrieved_at,
        source_timezone="UTC",
        provider=manifest.provider,
        adapter_version="phase-2v-outcome-news.v1",
        normalization_version="news-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.DOWNLOADED,
        source_endpoint_name="historical-news-search",
    )
    normalized = normalize_news_records(records, context)
    timing_items = tuple(
        NewsTimingItem(
            observation_id=str(observation.observation_id),
            headline=observation.payload.headline,
            publisher=observation.payload.publisher,
            publication_time=observation.payload.published_at,
            retrieval_time=manifest.retrieved_at,
            timing=_timing(observation.payload.published_at),
        )
        for observation in normalized.observations
    )
    identity = {"result_type": "PHASE_2V_NEWS_TIMING", "acquisition_id": manifest.acquisition_id,
                "observation_ids": sorted(item.observation_id for item in timing_items)}
    return NewsTimingCollection(
        acquisition_id=manifest.acquisition_id,
        observations=normalized.observations,
        items=timing_items,
        diagnostics=normalized.diagnostics,
        deterministic_id=deterministic_metric_id(identity),
    )


def parse_finra_short_sale_volume(manifest: AcquisitionManifest, raw: bytes) -> FinraShortSaleVolumeCollection:
    _verify(manifest, raw, AcquisitionDataType.FINRA_SHORT_SALE_VOLUME)
    records = []
    lines = raw.decode("utf-8-sig").splitlines()
    if not lines:
        raise ValueError("FINRA short-sale-volume response is empty")
    fields = lines[0].split("|")
    for line in lines[1:]:
        values = line.split("|")
        if len(values) != len(fields):
            continue
        row = dict(zip(fields, values, strict=True))
        if str(row.get("Symbol", "")).upper() != manifest.symbol:
            continue
        records.append(FinraShortSaleVolumeRecord(
            trade_date=datetime.strptime(row["Date"], "%Y%m%d").date(),
            symbol=manifest.symbol,
            short_volume=Decimal(row["ShortVolume"]),
            short_exempt_volume=Decimal(row["ShortExemptVolume"]),
            total_volume=Decimal(row["TotalVolume"]),
            market_scope=row["Market"],
        ))
    identity = {"result_type": "PHASE_2V_FINRA_SHORT_SALE_VOLUME", "acquisition_id": manifest.acquisition_id,
                "records": [item.model_dump(mode="python") for item in records]}
    return FinraShortSaleVolumeCollection(
        acquisition_id=manifest.acquisition_id, provider=manifest.provider,
        retrieved_at=manifest.retrieved_at, records=tuple(records),
        deterministic_id=deterministic_metric_id(identity),
    )


def parse_yahoo_corporate_actions(manifest: AcquisitionManifest, raw: bytes) -> CorporateActionCollection:
    _verify(manifest, raw, AcquisitionDataType.CORPORATE_ACTIONS)
    document = json.loads(raw)
    results = document.get("chart", {}).get("result") or []
    splits = (results[0].get("events", {}).get("splits", {}) if results else {})
    observations = []
    actions = []
    for key, split in sorted(splits.items()):
        moment = datetime.fromtimestamp(int(split["date"]), UTC)
        ratio = split.get("splitRatio")
        observation = Observation(
            schema_version="1.0.0", event_type=EventType.CORPORATE_ACTION,
            symbol=manifest.symbol, asset_class=AssetClass.EQUITY, source=manifest.provider,
            source_record_id=f"{manifest.symbol}-split-{key}", source_timestamp=moment,
            received_timestamp=manifest.retrieved_at, effective_timestamp=moment,
            market_session=MarketSession.REGULAR, data_freshness=DataFreshness.HISTORICAL,
            observation_kind=ObservationKind.PROVIDER_PUBLISHED,
            quality=Quality(state=QualityState.KNOWN_VALUE, evaluated_at=manifest.retrieved_at,
                            completeness=Completeness.COMPLETE),
            payload_type=PayloadType.CORPORATE_ACTION,
            payload=CorporateActionPayload(action_type="REVERSE_SPLIT", effective_date=moment.date(),
                                           description=f"BIYA reverse split {ratio}"),
            provenance=Provenance(provider=manifest.provider, ingestion_method=IngestionMethod.DOWNLOADED,
                                  origin_kind=ObservationKind.PROVIDER_PUBLISHED, normalized=True,
                                  normalization_version="phase-2v-corporate-action.v1",
                                  completeness=Completeness.COMPLETE,
                                  entitlement_state=EntitlementState.NOT_APPLICABLE,
                                  source_timezone="UTC",
                                  provider_metadata={"raw_acquisition_id": manifest.acquisition_id,
                                                     "raw_sha256": manifest.raw_sha256,
                                                     "split_ratio": ratio}),
            timezone="UTC", raw_payload_hash=manifest.raw_sha256,
            normalization_version="phase-2v-corporate-action.v1",
        )
        observations.append(observation)
        actions.append(CorporateActionItem(observation_id=str(observation.observation_id),
                                           action_type="REVERSE_SPLIT", effective_date=moment.date(),
                                           split_ratio=ratio))
    identity = {"result_type": "PHASE_2V_CORPORATE_ACTIONS", "acquisition_id": manifest.acquisition_id,
                "observation_ids": sorted(item.observation_id for item in actions)}
    return CorporateActionCollection(
        acquisition_id=manifest.acquisition_id, observations=tuple(observations), actions=tuple(actions),
        limitations=("The 1:10 reverse split became effective before the outcome window; retained bars use the provider's recorded post-split price basis.",),
        deterministic_id=deterministic_metric_id(identity),
    )


def parse_finra_published_short_interest(
    manifest: AcquisitionManifest, raw: bytes
) -> PublishedShortInterestCollection:
    _verify(manifest, raw, AcquisitionDataType.PUBLISHED_SHORT_INTEREST)
    lines = raw.decode("utf-8-sig").splitlines()
    if not lines:
        raise ValueError("FINRA published short-interest response is empty")
    delimiter = "|" if "|" in lines[0] else ","
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    records: list[dict[str, object]] = []
    for line_no, row in enumerate(reader, start=2):
        parsed = _finra_si_row(row, line_no, manifest.symbol)
        if parsed is not None:
            records.append(parsed)
    context = AdapterContext(
        ingested_at=manifest.retrieved_at,
        source_timezone="America/New_York",
        provider=manifest.provider,
        adapter_version="phase-2v-outcome-finra-si.v1",
        normalization_version="finra-short-interest-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.DOWNLOADED,
        source_endpoint_name="historical-finra-published-short-interest",
    )
    normalized = normalize_finra_short_interest_records(records, context)
    if not normalized.accepted:
        raise ValueError(f"FINRA SI normalization failed: {normalized.rejection}")
    identity = {
        "result_type": "PHASE_2V_PUBLISHED_SHORT_INTEREST",
        "acquisition_id": manifest.acquisition_id,
        "observation_ids": sorted(str(item.observation_id) for item in normalized.observations),
    }
    return PublishedShortInterestCollection(
        acquisition_id=manifest.acquisition_id,
        provider=manifest.provider,
        retrieved_at=manifest.retrieved_at,
        observations=normalized.observations,
        deterministic_id=deterministic_metric_id(identity),
    )


def build_unavailable_context(data_type: str, acquisition_manifest_id: str) -> UnavailableEvidenceContext:
    identity = {"result_type": "PHASE_2V_UNAVAILABLE_CONTEXT", "data_type": data_type,
                "acquisition_manifest_id": acquisition_manifest_id}
    return UnavailableEvidenceContext(
        data_type=data_type, acquisition_manifest_id=acquisition_manifest_id,
        limitation=f"{data_type} historical evidence was unavailable; no values were fabricated.",
        deterministic_id=deterministic_metric_id(identity),
    )


__all__ = [
    "CorporateActionCollection", "EvidenceAvailability", "FinraShortSaleVolumeCollection",
    "NewsTiming", "NewsTimingCollection", "PublishedShortInterestCollection",
    "UnavailableEvidenceContext", "build_unavailable_context", "normalize_yahoo_news",
    "parse_finra_published_short_interest", "parse_finra_short_sale_volume",
    "parse_yahoo_corporate_actions",
]
