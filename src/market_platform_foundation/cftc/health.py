"""CFTC COT source health and capability characterization."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .datasets import CotDataset, DATASET_SPECS
from .mapping import CotProductMapper
from .quality import CotQualityFlag
from .release_schedule import latest_published_release, next_expected_release, publication_time_utc
from .transport import CotTransport, CotTransportError


def source_health(
    transport: CotTransport | None = None,
    mapper: CotProductMapper | None = None,
) -> dict[str, Any]:
    transport = transport or CotTransport()
    mapper = mapper or CotProductMapper()
    reachable = transport.reachable()
    latest_pub = latest_published_release()
    next_pub = next_expected_release()
    latest_available_time = publication_time_utc(latest_pub) if latest_pub else ""
    return {
        "source": "cftc_cot",
        "reachable": reachable,
        "latest_report_publication_date": str(latest_pub or ""),
        "latest_available_time": latest_available_time,
        "next_expected_release": str(next_pub or ""),
        "report_family_coverage": sorted({spec.report_family.value for spec in DATASET_SPECS.values()}),
        "product_mapping_health": mapper.mapping_health(),
        "schema_health": "observed" if reachable else CotQualityFlag.SOURCE_UNAVAILABLE.value,
    }


def live_probe(
    transport: CotTransport | None = None,
    *,
    market_filter: str = "E-MINI S&P 500",
) -> dict[str, Any]:
    transport = transport or CotTransport()
    result: dict[str, Any] = {
        "tested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reachable": False,
    }
    try:
        tff_fo = transport.query_dataset(
            CotDataset.TFF_FUTURES_ONLY,
            where=f"market_and_exchange_names like '%{market_filter}%'",
            limit=1,
            order="report_date_as_yyyy_mm_dd DESC",
        )
        result["reachable"] = True
        result["tff_futures_only"] = {
            "count": len(tff_fo),
            "latest": tff_fo[0] if tff_fo else None,
        }
        tff_combined = transport.query_dataset(
            CotDataset.TFF_COMBINED,
            where=f"market_and_exchange_names like '%{market_filter}%'",
            limit=1,
            order="report_date_as_yyyy_mm_dd DESC",
        )
        result["tff_combined"] = {"count": len(tff_combined)}
        disagg = transport.query_dataset(
            CotDataset.DISAGGREGATED_FUTURES_ONLY,
            where="market_and_exchange_names like '%CRUDE OIL%'",
            limit=1,
            order="report_date_as_yyyy_mm_dd DESC",
        )
        result["disaggregated_futures_only"] = {"count": len(disagg)}
        hierarchy = transport.query_product_hierarchy(limit=3)
        result["product_hierarchy"] = {
            "count": len(hierarchy),
            "fields": sorted(hierarchy[0].keys()) if hierarchy else [],
        }
        if tff_fo:
            raw_date = str(tff_fo[0].get("report_date_as_yyyy_mm_dd", ""))
            result["latest_observed_release"] = raw_date[:10] if raw_date else ""
        result["next_expected_release"] = str(next_expected_release() or "")
    except CotTransportError as exc:
        result["error"] = str(exc)
        result["quality_flags"] = [CotQualityFlag.SOURCE_UNAVAILABLE.value]
    return result


def capability_report(transport: CotTransport | None = None) -> dict[str, Any]:
    transport = transport or CotTransport()
    health = source_health(transport)
    probe = live_probe(transport)
    return {
        "source": "cftc_cot",
        "tested_at": probe.get("tested_at"),
        "reports": {
            "tff": {"datasets": [CotDataset.TFF_FUTURES_ONLY.value, CotDataset.TFF_COMBINED.value]},
            "disaggregated": {
                "datasets": [
                    CotDataset.DISAGGREGATED_FUTURES_ONLY.value,
                    CotDataset.DISAGGREGATED_COMBINED.value,
                ]
            },
            "legacy": {
                "datasets": [CotDataset.LEGACY_FUTURES_ONLY.value, CotDataset.LEGACY_COMBINED.value]
            },
        },
        "scopes": {
            "futures_only": {"enforced": True},
            "combined": {"enforced": True, "double_count_protection": True},
        },
        "product_mapping": health.get("product_mapping_health", {}),
        "publication": {
            "schedule": "official_2026_cftc",
            "release_time_et": "15:30",
            "position_day": "Tuesday (holiday-adjusted)",
        },
        "pit": {"release_lag_enforced": True},
        "live_probe": probe,
        "quality": health,
        "limitations": [
            "weekly lag",
            "aggregate categories only",
            "no individual trader identity",
            "no transaction timing",
            "classification changes affect week-over-week deltas",
            "contract-family level not specific expiration",
        ],
    }


__all__ = ["capability_report", "live_probe", "source_health"]
