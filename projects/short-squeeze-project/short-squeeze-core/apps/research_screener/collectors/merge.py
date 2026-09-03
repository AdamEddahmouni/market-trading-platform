from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from ..truth import DataMode, FieldValue, Freshness, ValueStatus, known, missing

if TYPE_CHECKING:
    from ..live_providers import ProviderBundle
    from .store import EvidenceStore


def _can_overlay(existing: FieldValue, *, override_policy: str) -> bool:
    if existing.status == ValueStatus.KNOWN:
        return False
    if override_policy == "display_fallback" and existing.status == ValueStatus.NOT_CONFIGURED:
        return True
    return existing.status != ValueStatus.KNOWN


def supplemental_fields(
    symbol: str,
    fields: dict[str, FieldValue],
    store: EvidenceStore | None,
    *,
    external_providers: ProviderBundle | None = None,
) -> dict[str, FieldValue]:
    """Merge collector store cells without clobbering canonical KNOWN provider cells."""
    if store is None:
        return {}
    override_policy = os.environ.get("COLLECTOR_OVERRIDE_POLICY", "never").strip().lower()
    merged: dict[str, FieldValue] = {}
    records = store.get(symbol)
    if not records:
        return merged

    for record in records:
        hints = record.field_hints
        admissibility = hints.get("research_admissibility", "RESEARCH_INADMISSIBLE")
        provider = record.source_id
        received = record.received_at

        if hints.get("finra_si_shares") is not None:
            target = "finra_published_si_shares"
            if target not in fields or _can_overlay(fields[target], override_policy=override_policy):
                merged[target] = known(
                    int(hints["finra_si_shares"]),
                    unit="SHARES",
                    provider=provider,
                    event_time=received,
                    received_time=received,
                    freshness=Freshness.DELAYED,
                    data_mode=DataMode.HISTORICAL,
                    evidence_id=f"collector:{symbol}:{target}:{received}",
                    readiness="FINRA_PUBLISHED_SHORT_INTEREST",
                    research_admissibility=admissibility,
                )

        if hints.get("published_short_interest") is not None:
            target = "published_short_interest"
            existing = fields.get(target)
            if existing is None or _can_overlay(existing, override_policy=override_policy):
                merged[target] = known(
                    float(hints["published_short_interest"]),
                    unit="PERCENT",
                    provider=provider,
                    event_time=received,
                    received_time=received,
                    freshness=Freshness.DELAYED,
                    data_mode=DataMode.HISTORICAL,
                    evidence_id=f"collector:{symbol}:psi:{received}",
                    readiness="FINRA_PUBLISHED_SHORT_INTEREST",
                    provider_field="published_short_interest_pct",
                    research_admissibility=admissibility,
                )

        if hints.get("finra_daily_short_volume") is not None:
            target = "finra_daily_short_volume"
            if target not in fields or _can_overlay(fields.get(target, missing(ValueStatus.NOT_CONFIGURED, "")), override_policy=override_policy):
                merged[target] = known(
                    int(str(hints["finra_daily_short_volume"]).replace(",", "")),
                    unit="SHARES",
                    provider=provider,
                    event_time=received,
                    received_time=received,
                    freshness=Freshness.DELAYED,
                    data_mode=DataMode.HISTORICAL,
                    evidence_id=f"collector:{symbol}:dsv:{received}",
                    readiness="DISPLAY_ONLY_FINRA_DAILY_SHORT_VOLUME",
                    research_admissibility="RESEARCH_INADMISSIBLE",
                )

        if hints.get("collector_last_price") is not None:
            target = "collector_last_price"
            merged[target] = known(
                float(hints["collector_last_price"]),
                unit="PRICE",
                provider=provider,
                event_time=received,
                received_time=received,
                freshness=Freshness.UNKNOWN_AGE,
                data_mode=DataMode.HISTORICAL,
                evidence_id=f"collector:{symbol}:price:{received}",
                readiness="DISPLAY_ONLY_COLLECTOR_QUOTE",
                research_admissibility="RESEARCH_INADMISSIBLE",
            )

        if hints.get("social_mention_count") is not None:
            merged["social_mention_count"] = known(
                int(hints["social_mention_count"]),
                unit="COUNT",
                provider=provider,
                event_time=received,
                received_time=received,
                freshness=Freshness.CURRENT,
                data_mode=DataMode.HISTORICAL,
                evidence_id=f"collector:{symbol}:social:{received}",
                readiness="EXPERIMENTAL_SOCIAL_ADJUNCT",
                research_admissibility="RESEARCH_INADMISSIBLE",
            )

    return merged


def extract_headlines(records: list[Any]) -> list[dict[str, Any]]:
    headlines: list[dict[str, Any]] = []
    for record in records:
        items = record.field_hints.get("headlines") or record.payload.get("headlines")
        if not items:
            continue
        for item in items:
            headline = item.get("headline") or item.get("title")
            if not headline:
                continue
            headlines.append(
                {
                    "headline": headline,
                    "timestamp": item.get("timestamp"),
                    "provider": item.get("provider", record.source_id),
                    "url": item.get("url"),
                }
            )
    return headlines


__all__ = ["extract_headlines", "supplemental_fields"]
