"""Parse Cboe options reference CSV metadata and versioning."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass

from .contracts import AvailabilityPrecision, CboeExchangeCode, OptionsReferenceFileObservation
from .normalize import parse_iso_timestamp
from .quality import CboeOptionsQualityFlag
from .registry import CBOE_EXCHANGE_REGISTRY
from .transport import CboeOptionsTransport


REFERENCE_CATEGORIES = (
    "all_series",
    "underlying",
    "market_maker_registered",
    "constituent_series",
)


@dataclass(frozen=True, slots=True)
class ReferenceCapture:
    observation: OptionsReferenceFileObservation
    row_samples: tuple[dict[str, str], ...]


def _content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest().upper()


def parse_reference_csv(
    csv_text: str,
    *,
    exchange: CboeExchangeCode,
    reference_category: str,
    source_url: str,
    retrieved_time: str,
    ingested_time: str,
    http_last_modified: str = "",
    provider_first_observed_time: str = "",
    source_url_version: str = "cdn_v1",
    sample_rows: int = 0,
) -> ReferenceCapture:
    content_hash = _content_hash(csv_text)
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise ValueError("CBOE_REFERENCE_SCHEMA_CHANGED")

    headers = tuple(reader.fieldnames)
    rows = list(reader)
    exchange_entry = CBOE_EXCHANGE_REGISTRY[exchange]
    available_time = (
        parse_iso_timestamp(http_last_modified)
        or provider_first_observed_time
        or ingested_time
    )
    observation = OptionsReferenceFileObservation(
        reference_category=reference_category,
        exchange=exchange,
        source_file_id=f"{exchange_entry.reference_cdn_prefix}:{reference_category}",
        source_url=source_url,
        schema_version=f"{reference_category}:{len(headers)}",
        row_count=len(rows),
        headers=headers,
        content_hash=content_hash,
        available_time=available_time,
        availability_precision=(
            AvailabilityPrecision.HTTP_LAST_MODIFIED_PROXY
            if http_last_modified
            else AvailabilityPrecision.FIRST_OBSERVED
        ),
        retrieved_time=retrieved_time,
        ingested_time=ingested_time,
        http_last_modified=http_last_modified,
        provider_first_observed_time=provider_first_observed_time or ingested_time,
        source_url_version=source_url_version,
        provenance_ref=f"cboe_options:reference:{exchange.value}:{reference_category}",
        predictive=False,
    )
    samples = tuple(dict(row) for row in rows[:sample_rows]) if sample_rows else ()
    return ReferenceCapture(observation=observation, row_samples=samples)


def reference_urls_for_exchange(exchange: CboeExchangeCode) -> dict[str, str]:
    entry = CBOE_EXCHANGE_REGISTRY[exchange]
    return {
        category: CboeOptionsTransport.reference_file_url(entry.reference_cdn_prefix, category)
        for category in REFERENCE_CATEGORIES
    }


__all__ = [
    "REFERENCE_CATEGORIES",
    "ReferenceCapture",
    "parse_reference_csv",
    "reference_urls_for_exchange",
]
