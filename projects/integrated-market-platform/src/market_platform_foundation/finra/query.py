"""Synchronous FINRA Query API helpers. Async is available but unused for small queries."""

from __future__ import annotations

from typing import Any

from .transport import SYNC_RECORD_LIMIT, FinraResponse, FinraTransport

GROUP_OTC = "otcMarket"
DATASET_SHORT_INTEREST = "consolidatedShortInterest"
DATASET_REG_SHO_DAILY = "regShoDaily"
DATASET_OTC_THRESHOLD = "thresholdList"


def dataset_path(group: str, dataset: str) -> str:
    return f"/data/group/{group}/name/{dataset}"


def metadata_path(group: str, dataset: str) -> str:
    return f"/metadata/group/{group}/name/{dataset}"


def compare_filter(field_name: str, field_value: str, compare_type: str = "EQUAL") -> dict[str, str]:
    return {"compareType": compare_type, "fieldName": field_name, "fieldValue": field_value}


def query_dataset(
    transport: FinraTransport,
    *,
    group: str,
    dataset: str,
    filters: list[dict[str, str]] | None = None,
    fields: list[str] | None = None,
    limit: int = SYNC_RECORD_LIMIT,
    offset: int = 0,
    date_range: tuple[str, str, str] | None = None,
) -> FinraResponse:
    payload: dict[str, Any] = {"limit": min(int(limit), 5000), "offset": int(offset)}
    if filters:
        payload["compareFilters"] = filters
    if date_range:
        # FINRA returns rows oldest-first and refuses to sort without the date partition key,
        # so "the latest rows" is asked for as a date window: (field, start, end).
        field_name, start, end = date_range
        payload["dateRangeFilters"] = [{"fieldName": field_name, "startDate": start[:10], "endDate": end[:10]}]
    if fields:
        payload["fields"] = fields
    return transport.post(dataset_path(group, dataset), payload)


def query_short_interest(
    transport: FinraTransport,
    *,
    symbol: str | None = None,
    settlement_date: str | None = None,
    limit: int = SYNC_RECORD_LIMIT,
    since: str | None = None,
    until: str | None = None,
) -> FinraResponse:
    filters: list[dict[str, str]] = []
    if symbol:
        filters.append(compare_filter("symbolCode", symbol.upper()))
    if settlement_date:
        filters.append(compare_filter("settlementDate", settlement_date[:10]))
    return query_dataset(
        transport,
        group=GROUP_OTC,
        dataset=DATASET_SHORT_INTEREST,
        filters=filters or None,
        limit=limit,
        date_range=("settlementDate", since, until) if since and until and not settlement_date else None,
    )


def query_otc_threshold(
    transport: FinraTransport,
    *,
    symbol: str | None = None,
    trade_date: str | None = None,
    limit: int = SYNC_RECORD_LIMIT,
) -> FinraResponse:
    filters: list[dict[str, str]] = []
    if symbol:
        filters.append(compare_filter("issueSymbolIdentifier", symbol.upper()))
    if trade_date:
        filters.append(compare_filter("tradeDate", trade_date[:10]))
    return query_dataset(
        transport,
        group=GROUP_OTC,
        dataset=DATASET_OTC_THRESHOLD,
        filters=filters or None,
        limit=limit,
    )


def query_reg_sho_daily(
    transport: FinraTransport,
    *,
    symbol: str | None = None,
    trade_report_date: str | None = None,
    limit: int = SYNC_RECORD_LIMIT,
    since: str | None = None,
    until: str | None = None,
) -> FinraResponse:
    filters: list[dict[str, str]] = []
    if symbol:
        filters.append(compare_filter("securitiesInformationProcessorSymbolIdentifier", symbol.upper()))
    if trade_report_date:
        filters.append(compare_filter("tradeReportDate", trade_report_date[:10]))
    return query_dataset(
        transport,
        group=GROUP_OTC,
        dataset=DATASET_REG_SHO_DAILY,
        filters=filters or None,
        limit=limit,
        date_range=("tradeReportDate", since, until) if since and until and not trade_report_date else None,
    )
