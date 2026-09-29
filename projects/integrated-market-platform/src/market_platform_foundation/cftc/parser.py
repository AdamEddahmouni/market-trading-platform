"""Parse official CFTC SODA rows into category-level position records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import CotParticipantCategory, CotReportFamily
from .datasets import CotDatasetSpec


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {".", "NA", "N/A"}:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class CotCategoryRow:
    participant_category: CotParticipantCategory
    long_positions: int | None
    short_positions: int | None
    spreading_positions: int | None = None
    trader_count_long: int | None = None
    trader_count_short: int | None = None
    trader_count_spreading: int | None = None
    change_long: int | None = None
    change_short: int | None = None
    change_spreading: int | None = None


@dataclass(frozen=True, slots=True)
class CotParsedReport:
    position_date: str
    market_and_exchange_names: str
    cftc_contract_market_code: str
    cftc_commodity_code: str
    open_interest: int | None
    categories: tuple[CotCategoryRow, ...]
    source_row_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


# Official CFTC Public Reporting column names (dataset column metadata, verified 2026-09-28).
# The API's names are irregular ("_all" on some columns, not others; "swap__" double
# underscore; "spead" in the legacy change column) — they are copied, never normalized.
# Order per category: (long, short, spread | None).
TFF_CATEGORY_FIELDS: tuple[tuple[CotParticipantCategory, str, str, str | None], ...] = (
    (CotParticipantCategory.DEALER_INTERMEDIARY, "dealer_positions_long_all", "dealer_positions_short_all", "dealer_positions_spread_all"),
    (CotParticipantCategory.ASSET_MANAGER_INSTITUTIONAL, "asset_mgr_positions_long", "asset_mgr_positions_short", "asset_mgr_positions_spread"),
    (CotParticipantCategory.LEVERAGED_FUNDS, "lev_money_positions_long", "lev_money_positions_short", "lev_money_positions_spread"),
    (CotParticipantCategory.OTHER_REPORTABLES, "other_rept_positions_long", "other_rept_positions_short", "other_rept_positions_spread"),
    (CotParticipantCategory.NON_REPORTABLES, "nonrept_positions_long_all", "nonrept_positions_short_all", None),
)

DISAGGREGATED_CATEGORY_FIELDS: tuple[tuple[CotParticipantCategory, str, str, str | None], ...] = (
    (CotParticipantCategory.PRODUCER_MERCHANT, "prod_merc_positions_long", "prod_merc_positions_short", None),
    (CotParticipantCategory.SWAP_DEALER, "swap_positions_long_all", "swap__positions_short_all", "swap__positions_spread_all"),
    (CotParticipantCategory.MANAGED_MONEY, "m_money_positions_long_all", "m_money_positions_short_all", "m_money_positions_spread"),
    (CotParticipantCategory.OTHER_REPORTABLE, "other_rept_positions_long", "other_rept_positions_short", "other_rept_positions_spread"),
    (CotParticipantCategory.NON_REPORTABLE, "nonrept_positions_long_all", "nonrept_positions_short_all", None),
)

LEGACY_CATEGORY_FIELDS: tuple[tuple[CotParticipantCategory, str, str, str | None], ...] = (
    (CotParticipantCategory.COMMERCIAL, "comm_positions_long_all", "comm_positions_short_all", None),
    (CotParticipantCategory.NON_COMMERCIAL, "noncomm_positions_long_all", "noncomm_positions_short_all", "noncomm_positions_spread"),
    (CotParticipantCategory.NON_REPORTABLE_LEGACY, "nonrept_positions_long_all", "nonrept_positions_short_all", None),
)

# (traders long, traders short, traders spread) — non-reportables have no trader counts.
TRADER_COUNT_FIELDS: dict[CotParticipantCategory, tuple[str | None, str | None, str | None]] = {
    CotParticipantCategory.DEALER_INTERMEDIARY: ("traders_dealer_long_all", "traders_dealer_short_all", "traders_dealer_spread_all"),
    CotParticipantCategory.ASSET_MANAGER_INSTITUTIONAL: ("traders_asset_mgr_long_all", "traders_asset_mgr_short_all", "traders_asset_mgr_spread"),
    CotParticipantCategory.LEVERAGED_FUNDS: ("traders_lev_money_long_all", "traders_lev_money_short_all", "traders_lev_money_spread"),
    CotParticipantCategory.OTHER_REPORTABLES: ("traders_other_rept_long_all", "traders_other_rept_short", "traders_other_rept_spread"),
    CotParticipantCategory.PRODUCER_MERCHANT: ("traders_prod_merc_long_all", "traders_prod_merc_short_all", None),
    CotParticipantCategory.SWAP_DEALER: ("traders_swap_long_all", "traders_swap_short_all", "traders_swap_spread_all"),
    CotParticipantCategory.MANAGED_MONEY: ("traders_m_money_long_all", "traders_m_money_short_all", "traders_m_money_spread_all"),
    CotParticipantCategory.OTHER_REPORTABLE: ("traders_other_rept_long_all", "traders_other_rept_short", "traders_other_rept_spread"),
    CotParticipantCategory.COMMERCIAL: ("traders_comm_long_all", "traders_comm_short_all", None),
    CotParticipantCategory.NON_COMMERCIAL: ("traders_noncomm_long_all", "traders_noncomm_short_all", "traders_noncomm_spread_all"),
}

# Week-over-week changes as published by the CFTC (OBSERVED, not recomputed).
CHANGE_FIELDS: dict[CotParticipantCategory, tuple[str | None, str | None, str | None]] = {
    CotParticipantCategory.DEALER_INTERMEDIARY: ("change_in_dealer_long_all", "change_in_dealer_short_all", "change_in_dealer_spread_all"),
    CotParticipantCategory.ASSET_MANAGER_INSTITUTIONAL: ("change_in_asset_mgr_long", "change_in_asset_mgr_short", "change_in_asset_mgr_spread"),
    CotParticipantCategory.LEVERAGED_FUNDS: ("change_in_lev_money_long", "change_in_lev_money_short", "change_in_lev_money_spread"),
    CotParticipantCategory.OTHER_REPORTABLES: ("change_in_other_rept_long", "change_in_other_rept_short", "change_in_other_rept_spread"),
    CotParticipantCategory.NON_REPORTABLES: ("change_in_nonrept_long_all", "change_in_nonrept_short_all", None),
    CotParticipantCategory.PRODUCER_MERCHANT: ("change_in_prod_merc_long", "change_in_prod_merc_short", None),
    CotParticipantCategory.SWAP_DEALER: ("change_in_swap_long_all", "change_in_swap_short_all", "change_in_swap_spread_all"),
    CotParticipantCategory.MANAGED_MONEY: ("change_in_m_money_long_all", "change_in_m_money_short_all", "change_in_m_money_spread"),
    CotParticipantCategory.OTHER_REPORTABLE: ("change_in_other_rept_long", "change_in_other_rept_short", "change_in_other_rept_spread"),
    CotParticipantCategory.NON_REPORTABLE: ("change_in_nonrept_long_all", "change_in_nonrept_short_all", None),
    CotParticipantCategory.COMMERCIAL: ("change_in_comm_long_all", "change_in_comm_short_all", None),
    CotParticipantCategory.NON_COMMERCIAL: ("change_in_noncomm_long_all", "change_in_noncomm_short_all", "change_in_noncomm_spead_all"),
    CotParticipantCategory.NON_REPORTABLE_LEGACY: ("change_in_nonrept_long_all", "change_in_nonrept_short_all", None),
}


def _category_fields(report_family: CotReportFamily) -> tuple[tuple[CotParticipantCategory, str, str, str | None], ...]:
    if report_family == CotReportFamily.TFF:
        return TFF_CATEGORY_FIELDS
    if report_family == CotReportFamily.DISAGGREGATED:
        return DISAGGREGATED_CATEGORY_FIELDS
    if report_family == CotReportFamily.LEGACY:
        return LEGACY_CATEGORY_FIELDS
    return ()


def _extract_categories(
    row: dict[str, Any],
    fields: tuple[tuple[CotParticipantCategory, str, str, str | None], ...],
) -> tuple[CotCategoryRow, ...]:
    def value(key: str | None) -> int | None:
        # Socrata omits null columns from a row: a missing key is unknown, never zero.
        return _parse_int(row.get(key)) if key else None

    categories: list[CotCategoryRow] = []
    for category, long_key, short_key, spread_key in fields:
        traders = TRADER_COUNT_FIELDS.get(category, (None, None, None))
        changes = CHANGE_FIELDS.get(category, (None, None, None))
        categories.append(
            CotCategoryRow(
                participant_category=category,
                long_positions=value(long_key),
                short_positions=value(short_key),
                spreading_positions=value(spread_key),
                trader_count_long=value(traders[0]),
                trader_count_short=value(traders[1]),
                trader_count_spreading=value(traders[2]),
                change_long=value(changes[0]),
                change_short=value(changes[1]),
                change_spreading=value(changes[2]),
            )
        )
    return tuple(categories)


def parse_cot_row(row: dict[str, Any], *, spec: CotDatasetSpec) -> CotParsedReport:
    position_date = str(row.get("report_date_as_yyyy_mm_dd", "") or row.get("report_date", ""))[:10]
    return CotParsedReport(
        position_date=position_date,
        market_and_exchange_names=str(row.get("market_and_exchange_names", "")),
        cftc_contract_market_code=str(row.get("cftc_contract_market_code", "")),
        cftc_commodity_code=str(row.get("cftc_commodity_code", "")),
        open_interest=_parse_int(row.get("open_interest_all")),
        categories=_extract_categories(row, _category_fields(spec.report_family)),
        source_row_id=str(row.get(":id", "") or row.get("id", "")),
        raw=dict(row),
    )


def detect_scope_in_row(row: dict[str, Any]) -> str | None:
    """Detect futures_options_code in All-dataset rows — returns 'FutOnly' or 'Combined'."""
    code = row.get("futonly_or_combined")
    if code:
        return str(code)
    fo = row.get("futures_options_code")
    if fo:
        return str(fo)
    return None


__all__ = [
    "CHANGE_FIELDS",
    "CotCategoryRow",
    "CotParsedReport",
    "DISAGGREGATED_CATEGORY_FIELDS",
    "TRADER_COUNT_FIELDS",
    "LEGACY_CATEGORY_FIELDS",
    "TFF_CATEGORY_FIELDS",
    "detect_scope_in_row",
    "parse_cot_row",
]
