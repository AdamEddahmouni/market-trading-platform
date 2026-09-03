"""Normalize Reg SHO daily short-sale volume. Flow, not inventory."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..short_intelligence.clocks import clocks_short_sale
from ..short_intelligence.contracts import ObservationFamily, ShortSaleVolumeObservation
from ..short_intelligence.identity import SymbolMap


def _int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(str(value)))
        except (TypeError, ValueError):
            return None


def finra_reported_short_sale_ratio(short_sale_volume: int | None, total: int | None) -> float | None:
    """Share of the compatible FINRA-reported denominator. Not market_short_ratio."""
    if short_sale_volume is None or total in (None, 0):
        return None
    return float(short_sale_volume) / float(total)


def normalize_short_sale_row(
    row: dict[str, Any],
    *,
    symbol_map: SymbolMap,
    observed_time: str,
    retrieved_time: str,
    finra_request_id: str = "",
) -> ShortSaleVolumeObservation:
    symbol = str(row.get("securitiesInformationProcessorSymbolIdentifier") or "").strip().upper()
    trade_date = str(row.get("tradeReportDate") or "")[:10]
    quality: list[str] = []
    resolved = symbol_map.resolve(symbol, as_of=trade_date or observed_time)
    if "IDENTITY_UNRESOLVED" in resolved.quality_flags:
        quality.append("IDENTITY_UNRESOLVED")
    short_sale = _int(row.get("shortParQuantity"))
    short_exempt = _int(row.get("shortExemptParQuantity"))
    total = _int(row.get("totalParQuantity"))
    return ShortSaleVolumeObservation(
        observation_family=ObservationFamily.SHORT_SALE_VOLUME,
        instrument_id=resolved.instrument_id,
        provider_symbol=symbol,
        trade_report_date=trade_date,
        reporting_facility_code=str(row.get("reportingFacilityCode") or ""),
        market_code=str(row.get("marketCode") or ""),
        short_sale_volume=short_sale,
        short_exempt_volume=short_exempt,
        finra_reported_total_volume=total,
        finra_reported_short_sale_ratio=finra_reported_short_sale_ratio(short_sale, total),
        provider="finra.query",
        source_dataset="otcMarket/regShoDaily",
        clocks=clocks_short_sale(
            trade_report_date=trade_date,
            observed_time=observed_time,
            retrieved_time=retrieved_time,
        ),
        quality_flags=tuple(dict.fromkeys(quality)),
        raw_payload_hash=sha256_bytes(canonical_bytes(row)),
        finra_request_id=finra_request_id,
    )


def aggregate_short_sale_rows(
    rows: tuple[ShortSaleVolumeObservation, ...] | list[ShortSaleVolumeObservation],
) -> dict[str, Any]:
    """Explicit aggregation. Raw facility rows remain the source of truth."""
    facilities: list[str] = []
    short_sale = 0
    short_exempt = 0
    total = 0
    missing = False
    for row in rows:
        facilities.append(f"{row.reporting_facility_code}:{row.market_code}")
        if row.short_sale_volume is None or row.finra_reported_total_volume is None:
            missing = True
            continue
        short_sale += row.short_sale_volume
        short_exempt += int(row.short_exempt_volume or 0)
        total += row.finra_reported_total_volume
    return {
        "short_sale_volume": None if missing and not rows else short_sale,
        "short_exempt_volume": None if missing and not rows else short_exempt,
        "finra_reported_total_volume": None if missing and not rows else total,
        "finra_reported_short_sale_ratio": finra_reported_short_sale_ratio(
            None if missing else short_sale,
            None if missing else total,
        ),
        "reporting_facilities": facilities,
        "source_row_count": len(list(rows)),
        "aggregation": "SUM_OVER_RETAINED_FACILITY_ROWS",
        "denominator": "finra_reported_total_volume",
    }
