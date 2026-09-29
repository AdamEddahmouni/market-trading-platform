"""Latest CFTC Commitments of Traders positioning per futures root, for the Screener (S12).

Code-exact mapping only: a root maps to the one CFTC contract market that reports
it (verified against CFTC Public Reporting market names on 2026-09-28). Micro
contracts are their own CFTC markets and are never merged into the full-size family.
Financial futures (equity indices, rates, FX, VIX, crypto) use the Traders in
Financial Futures report; physical commodities use the Disaggregated report. The
categories of the two reports are different and are never mapped onto each other.

Clocks: ``report_date`` is the Tuesday the positions are as of; ``publication_time``
is the official release (normally Friday 15:30 ET, later around holidays). A report
is visible — historically and now — only from its publication time.

Nothing here predicts price. Net = long − short per category is DERIVED; the weekly
changes are the CFTC's own published ``change_in_*`` columns (OBSERVED).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from .contracts import CotParticipantCategory, CotReportFamily
from .datasets import CotDataset, dataset_spec
from .parser import parse_cot_row
from .release_schedule import is_visible_at, publication_datetime_et, release_for_position_date

SOURCE_URL = "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"
DATASET_URL = "https://publicreporting.cftc.gov/resource/{dataset}.json"


@dataclass(frozen=True, slots=True)
class PositioningMarket:
    root: str
    code: str
    report: CotReportFamily
    market_name: str          # CFTC market name at verification (the live row's name is displayed)


_TFF, _DIS = CotReportFamily.TFF, CotReportFamily.DISAGGREGATED
#: Root → the CFTC contract market that reports it. Verified 2026-09-28 (report of 2026-09-22).
POSITIONING_MARKETS: dict[str, PositioningMarket] = {market.root: market for market in (
    PositioningMarket("ES", "13874A", _TFF, "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("MES", "13874U", _TFF, "MICRO E-MINI S&P 500 INDEX - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("NQ", "209742", _TFF, "NASDAQ MINI - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("MNQ", "209747", _TFF, "MICRO E-MINI NASDAQ-100 INDEX - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("RTY", "239742", _TFF, "RUSSELL E-MINI - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("M2K", "239747", _TFF, "MICRO E-MINI RUSSELL 2000 INDX - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("YM", "124603", _TFF, "DJIA x $5 - CHICAGO BOARD OF TRADE"),
    PositioningMarket("ZN", "043602", _TFF, "UST 10Y NOTE - CHICAGO BOARD OF TRADE"),
    PositioningMarket("ZB", "020601", _TFF, "UST BOND - CHICAGO BOARD OF TRADE"),
    PositioningMarket("ZF", "044601", _TFF, "UST 5Y NOTE - CHICAGO BOARD OF TRADE"),
    PositioningMarket("ZT", "042601", _TFF, "UST 2Y NOTE - CHICAGO BOARD OF TRADE"),
    PositioningMarket("UB", "020604", _TFF, "ULTRA UST BOND - CHICAGO BOARD OF TRADE"),
    PositioningMarket("TN", "043607", _TFF, "ULTRA UST 10Y - CHICAGO BOARD OF TRADE"),
    PositioningMarket("SR3", "134741", _TFF, "SOFR-3M - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("6E", "099741", _TFF, "EURO FX - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("6J", "097741", _TFF, "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("6B", "096742", _TFF, "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("VX", "1170E1", _TFF, "VIX FUTURES - CBOE FUTURES EXCHANGE"),
    PositioningMarket("BTC", "133741", _TFF, "BITCOIN - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("MBT", "133742", _TFF, "MICRO BITCOIN - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("ETH", "146021", _TFF, "ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("MET", "146022", _TFF, "MICRO ETHER - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("CL", "067651", _DIS, "WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE"),
    PositioningMarket("NG", "023651", _DIS, "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE"),
    PositioningMarket("GC", "088691", _DIS, "GOLD - COMMODITY EXCHANGE INC."),
    PositioningMarket("MGC", "088695", _DIS, "MICRO GOLD - COMMODITY EXCHANGE INC."),
    PositioningMarket("SI", "084691", _DIS, "SILVER - COMMODITY EXCHANGE INC."),
    PositioningMarket("HG", "085692", _DIS, "COPPER- #1 - COMMODITY EXCHANGE INC."),
    PositioningMarket("ZC", "002602", _DIS, "CORN - CHICAGO BOARD OF TRADE"),
    PositioningMarket("ZS", "005602", _DIS, "SOYBEANS - CHICAGO BOARD OF TRADE"),
    PositioningMarket("ZW", "001602", _DIS, "WHEAT-SRW - CHICAGO BOARD OF TRADE"),
    PositioningMarket("LE", "057642", _DIS, "LIVE CATTLE - CHICAGO MERCANTILE EXCHANGE"),
    PositioningMarket("HE", "054642", _DIS, "LEAN HOGS - CHICAGO MERCANTILE EXCHANGE"),
)}
DATASETS = {_TFF: CotDataset.TFF_FUTURES_ONLY, _DIS: CotDataset.DISAGGREGATED_FUTURES_ONLY}
CATEGORY_LABELS = {
    CotParticipantCategory.DEALER_INTERMEDIARY: "Dealer / intermediary",
    CotParticipantCategory.ASSET_MANAGER_INSTITUTIONAL: "Asset manager / institutional",
    CotParticipantCategory.LEVERAGED_FUNDS: "Leveraged funds",
    CotParticipantCategory.OTHER_REPORTABLES: "Other reportables",
    CotParticipantCategory.NON_REPORTABLES: "Non-reportables",
    CotParticipantCategory.PRODUCER_MERCHANT: "Producer / merchant / processor / user",
    CotParticipantCategory.SWAP_DEALER: "Swap dealers",
    CotParticipantCategory.MANAGED_MONEY: "Managed money",
    CotParticipantCategory.OTHER_REPORTABLE: "Other reportables",
    CotParticipantCategory.NON_REPORTABLE: "Non-reportables",
}
NET_METHOD = "DERIVED: net = reported long − reported short for the category. Positioning is not a price forecast."


def publication_for(report_date: date) -> tuple[datetime, str]:
    """Official publication time for a position date; a date outside the loaded schedule is inferred and flagged."""

    release = release_for_position_date(report_date)
    if release is not None:
        return publication_datetime_et(release.publication_date).astimezone(UTC), (
            "CFTC_OFFICIAL_SCHEDULE_DELAYED" if release.delayed else "CFTC_OFFICIAL_SCHEDULE")
    return publication_datetime_et(report_date + timedelta(days=3)).astimezone(UTC), "PUBLICATION_TIME_INFERRED_TUESDAY_PLUS_3"


def where_clause(codes: list[str], since: date) -> str:
    quoted = ", ".join(f"'{code}'" for code in sorted(set(codes)) if code.isalnum() or code.replace("+", "").isalnum())
    return f"cftc_contract_market_code in ({quoted}) AND report_date_as_yyyy_mm_dd >= '{since.isoformat()}T00:00:00.000'"


def build_positioning(rows: list[dict[str, Any]], market: PositioningMarket, *, now: datetime) -> dict[str, Any] | None:
    """The newest report for ``market`` that was public at ``now``; None when none is visible."""

    spec = dataset_spec(DATASETS[market.report])
    candidates: list[tuple[date, dict[str, Any]]] = []
    for row in rows:
        if str(row.get("cftc_contract_market_code") or "") != market.code:
            continue
        try:
            report_date = date.fromisoformat(str(row.get("report_date_as_yyyy_mm_dd") or "")[:10])
        except ValueError:
            continue
        candidates.append((report_date, row))
    candidates.sort(key=lambda item: item[0], reverse=True)
    for report_date, row in candidates:
        published, basis = publication_for(report_date)
        release = release_for_position_date(report_date)
        visible = is_visible_at(release.publication_date, now) if release else now >= published
        if not visible:
            continue  # not public yet at `now` — never shown early
        parsed = parse_cot_row(row, spec=spec)
        categories = []
        for item in parsed.categories:
            net = (item.long_positions - item.short_positions
                   if item.long_positions is not None and item.short_positions is not None else None)
            net_change = (item.change_long - item.change_short
                          if item.change_long is not None and item.change_short is not None else None)
            categories.append({
                "id": item.participant_category.value, "label": CATEGORY_LABELS.get(item.participant_category, item.participant_category.value),
                "long": item.long_positions, "short": item.short_positions, "spreading": item.spreading_positions,
                "change_long": item.change_long, "change_short": item.change_short, "change_spreading": item.change_spreading,
                "net": net, "net_change": net_change, "traders_long": item.trader_count_long,
                "traders_short": item.trader_count_short,
            })
        return {
            "root": market.root, "report": market.report.value, "report_label": spec.label,
            "cftc_contract_market_code": market.code, "market_name": parsed.market_and_exchange_names or market.market_name,
            "report_date": report_date.isoformat(), "publication_time": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "publication_basis": basis, "available_at": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open_interest": parsed.open_interest,
            "change_open_interest": _int(row.get("change_in_open_interest_all")),
            "categories": categories, "net_method": NET_METHOD, "source_url": SOURCE_URL,
            "dataset": spec.dataset_id, "source_row_id": parsed.source_row_id,
        }
    return None


def _int(value: Any) -> int | None:
    try:
        return int(float(str(value).replace(",", ""))) if value not in (None, "") else None
    except ValueError:
        return None


__all__ = ["CATEGORY_LABELS", "DATASETS", "NET_METHOD", "POSITIONING_MARKETS", "PositioningMarket", "SOURCE_URL",
           "build_positioning", "publication_for", "where_clause"]
