"""Latest CFTC Commitments of Traders positioning per futures root, for the Screener (S12, S15).

Code-exact mapping only: a root maps to the one CFTC contract market that reports it
(verified against CFTC Public Reporting on 2026-09-29, report of 2026-09-22). The key
is the IMP *root*, never a dated contract, so a lead-contract roll (ESZ26 → ESH27)
keeps the same market. Micro contracts are their own CFTC markets and are never merged
into the full-size family. Financial futures (equity indices, rates, FX, VIX, crypto)
use the Traders in Financial Futures report; physical commodities use the Disaggregated
report. The categories of the two reports are different and are never mapped onto
each other. Every mapping states its evidence basis; roots without a market carry an
explicit decision in ``root_coverage``.

Clocks: ``report_date`` is the Tuesday the positions are as of; ``publication_time``
is the official release (normally Friday 15:30 ET, later around holidays). A report
is visible — historically and now — only from its publication time.

Nothing here predicts price. Net = long − short per category and the % of open
interest ratios are DERIVED; the weekly changes are the CFTC's own published
``change_in_*`` columns (OBSERVED).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from .contracts import CotParticipantCategory, CotReportFamily
from .datasets import CotDataset, dataset_spec
from .parser import parse_cot_row
from .release_schedule import ReleaseCalendar

#: Vendored official tables only; the Screener service swaps in a calendar extended from the live CFTC page.
DEFAULT_CALENDAR = ReleaseCalendar.vendored()

SOURCE_URL = "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"
DATASET_URL = "https://publicreporting.cftc.gov/resource/{dataset}.json"


class MappingBasis(StrEnum):
    """Why a root is associated with a CFTC market. Nothing is matched by name similarity."""

    #: The provider venue is the CFTC market's exchange and the provider product is the same contract.
    EXCHANGE_PLUS_PRODUCT = "EXCHANGE_PLUS_PRODUCT"
    #: The provider gives no venue, or names the product differently from the CFTC (an official
    #: exchange rename or product code); the association is recorded with its reference.
    CURATED_OFFICIAL_ALIAS = "CURATED_OFFICIAL_ALIAS"


#: Deterministic confidence per basis (no numeric score). ``AMBIGUOUS`` roots are never mapped here.
CONFIDENCE = {MappingBasis.EXCHANGE_PLUS_PRODUCT: "EXACT", MappingBasis.CURATED_OFFICIAL_ALIAS: "SUPPORTED_ALIAS"}


@dataclass(frozen=True, slots=True)
class PositioningMarket:
    root: str
    code: str
    report: CotReportFamily
    market_name: str          # CFTC market name at verification (the live row's name is displayed)
    basis: MappingBasis = MappingBasis.EXCHANGE_PLUS_PRODUCT
    note: str = ""
    former_names: tuple[str, ...] = ()   # earlier official names of the same market code (history is not rewritten)

    @property
    def confidence(self) -> str:
        return CONFIDENCE[self.basis]


_TFF, _DIS = CotReportFamily.TFF, CotReportFamily.DISAGGREGATED
_ALIAS = MappingBasis.CURATED_OFFICIAL_ALIAS
_NO_VENUE = "The provider lists no venue for this root; CME Group product code {code}."
_CME, _CBT = "CHICAGO MERCANTILE EXCHANGE", "CHICAGO BOARD OF TRADE"
_NYM, _CMX = "NEW YORK MERCANTILE EXCHANGE", "COMMODITY EXCHANGE INC."


def _m(root: str, code: str, report: CotReportFamily, name: str, exchange: str, *,
       basis: MappingBasis = MappingBasis.EXCHANGE_PLUS_PRODUCT, note: str = "",
       former: tuple[str, ...] = ()) -> PositioningMarket:
    return PositioningMarket(root, code, report, f"{name} - {exchange}", basis, note, former)


#: Root → the CFTC contract market that reports it. Verified 2026-09-29 (report of 2026-09-22).
POSITIONING_MARKETS: dict[str, PositioningMarket] = {market.root: market for market in (
    # Equity indices (TFF)
    _m("ES", "13874A", _TFF, "E-MINI S&P 500", _CME),
    _m("MES", "13874U", _TFF, "MICRO E-MINI S&P 500 INDEX", _CME),
    _m("EMD", "33874A", _TFF, "E-MINI S&P 400 STOCK INDEX", _CME),
    _m("NQ", "209742", _TFF, "NASDAQ MINI", _CME),
    _m("MNQ", "209747", _TFF, "MICRO E-MINI NASDAQ-100 INDEX", _CME),
    _m("RTY", "239742", _TFF, "RUSSELL E-MINI", _CME),
    _m("M2K", "239747", _TFF, "MICRO E-MINI RUSSELL 2000 INDX", _CME),
    _m("YM", "124603", _TFF, "DJIA x $5", _CBT, former=("DOW JONES INDUSTRIAL AVG- x $5 - CHICAGO BOARD OF TRADE",)),
    _m("MYM", "124608", _TFF, "MICRO E-MINI DJIA (x$0.5)", _CBT),
    _m("NIY", "240743", _TFF, "NIKKEI STOCK AVERAGE YEN DENOM", _CME, basis=_ALIAS, note=_NO_VENUE.format(code="NIY")),
    _m("NKD", "240741", _TFF, "NIKKEI STOCK AVERAGE", _CME, basis=_ALIAS,
       note=_NO_VENUE.format(code="NKD") + " The dollar-denominated Nikkei; the yen contract is NIY."),
    # Rates (TFF)
    _m("ZN", "043602", _TFF, "UST 10Y NOTE", _CBT),
    _m("ZB", "020601", _TFF, "UST BOND", _CBT, former=("U.S. TREASURY BONDS - CHICAGO BOARD OF TRADE",)),
    _m("ZF", "044601", _TFF, "UST 5Y NOTE", _CBT),
    _m("ZT", "042601", _TFF, "UST 2Y NOTE", _CBT),
    _m("UB", "020604", _TFF, "ULTRA UST BOND", _CBT, former=("ULTRA U.S. TREASURY BONDS - CHICAGO BOARD OF TRADE",)),
    _m("TN", "043607", _TFF, "ULTRA UST 10Y", _CBT),
    _m("10Y", "04360Y", _TFF, "MICRO 10 YEAR YIELD", _CBT),
    _m("SR3", "134741", _TFF, "SOFR-3M", _CME, basis=_ALIAS,
       note=_NO_VENUE.format(code="SR3") + " Not the FMX Futures Exchange SOFR-3M market (134FM1)."),
    # FX (TFF)
    _m("6E", "099741", _TFF, "EURO FX", _CME),
    _m("6J", "097741", _TFF, "JAPANESE YEN", _CME),
    _m("6B", "096742", _TFF, "BRITISH POUND", _CME, former=("BRITISH POUND STERLING - CHICAGO MERCANTILE EXCHANGE",)),
    _m("6A", "232741", _TFF, "AUSTRALIAN DOLLAR", _CME),
    _m("6C", "090741", _TFF, "CANADIAN DOLLAR", _CME),
    _m("6L", "102741", _TFF, "BRAZILIAN REAL", _CME),
    _m("6M", "095741", _TFF, "MEXICAN PESO", _CME),
    _m("6N", "112741", _TFF, "NZ DOLLAR", _CME),
    _m("6S", "092741", _TFF, "SWISS FRANC", _CME),
    _m("6Z", "122741", _TFF, "SO AFRICAN RAND", _CME, former=("SOUTH AFRICAN RAND - CHICAGO MERCANTILE EXCHANGE",)),
    _m("RP", "299741", _TFF, "EURO FX/BRITISH POUND XRATE", _CME),
    _m("RY", "399741", _TFF, "EURO FX/JAPANESE YEN XRATE", _CME),
    # Volatility (TFF)
    _m("VX", "1170E1", _TFF, "VIX FUTURES", "CBOE FUTURES EXCHANGE"),
    # Crypto (TFF) — the provider lists no venue for CME crypto futures.
    _m("BTC", "133741", _TFF, "BITCOIN", _CME, basis=_ALIAS, note=_NO_VENUE.format(code="BTC")),
    _m("MBT", "133742", _TFF, "MICRO BITCOIN", _CME, basis=_ALIAS, note=_NO_VENUE.format(code="MBT")),
    _m("ETH", "146021", _TFF, "ETHER CASH SETTLED", _CME, basis=_ALIAS, note=_NO_VENUE.format(code="ETH")),
    _m("METH", "146022", _TFF, "MICRO ETHER", _CME, basis=_ALIAS,
       note=_NO_VENUE.format(code="MET") + " The provider root is METH."),
    _m("SOL", "177741", _TFF, "SOL", _CME, basis=_ALIAS, note=_NO_VENUE.format(code="SOL")),
    _m("MSL", "177742", _TFF, "MICRO SOL", _CME, basis=_ALIAS, note=_NO_VENUE.format(code="MSL")),
    _m("XRP", "176740", _TFF, "XRP", _CME, basis=_ALIAS,
       note=_NO_VENUE.format(code="XRP") + " Not the Coinbase Derivatives XRP market (176LM2)."),
    _m("MXP", "176741", _TFF, "MICRO XRP", _CME, basis=_ALIAS, note=_NO_VENUE.format(code="MXP")),
    # Energy (Disaggregated)
    _m("CL", "067651", _DIS, "WTI-PHYSICAL", _NYM,
       note="The physically delivered WTI contract; not WTI FINANCIAL CRUDE OIL (06765A) or ICE WTI (067411)."),
    _m("BZ", "06765T", _DIS, "BRENT LAST DAY", _NYM),
    _m("NG", "023651", _DIS, "NAT GAS NYME", _NYM,
       note="The physically delivered Henry Hub contract; not the Henry Hub financial markets (03565B, 023A55, 023A56)."),
    _m("QG", "023655", _DIS, "E-MINI NATURAL GAS", _NYM),
    _m("HO", "022651", _DIS, "NY HARBOR ULSD", _NYM, basis=_ALIAS,
       note="NYMEX's heating oil contract (code HO) is the NY Harbor ULSD future.",
       former=("NY HARBOR USLD - NEW YORK MERCANTILE EXCHANGE",)),
    _m("RB", "111659", _DIS, "GASOLINE RBOB", _NYM),
    # Metals (Disaggregated)
    _m("GC", "088691", _DIS, "GOLD", _CMX),
    _m("MGC", "088695", _DIS, "MICRO GOLD", _CMX),
    _m("SI", "084691", _DIS, "SILVER", _CMX),
    _m("SIL", "084694", _DIS, "MICRO SILVER", _CMX),
    _m("HG", "085692", _DIS, "COPPER- #1", _CMX, former=("COPPER-GRADE #1 - COMMODITY EXCHANGE INC.",)),
    _m("MHG", "085699", _DIS, "MICRO COPPER", _CMX),
    _m("PA", "075651", _DIS, "PALLADIUM", _NYM),
    _m("PL", "076651", _DIS, "PLATINUM", _NYM),
    _m("ALI", "191691", _DIS, "ALUMINUM", _CMX,
       note="The COMEX aluminum future; not the aluminum premium markets (191693, 191696)."),
    # Agriculture (Disaggregated)
    _m("ZC", "002602", _DIS, "CORN", _CBT),
    _m("ZS", "005602", _DIS, "SOYBEANS", _CBT),
    _m("XK", "005603", _DIS, "MINI SOYBEANS", _CBT),
    _m("ZW", "001602", _DIS, "WHEAT-SRW", _CBT),
    _m("KE", "001612", _DIS, "WHEAT-HRW", _CBT, basis=_ALIAS,
       note="KC HRW wheat moved from the Kansas City Board of Trade to CBOT; same CFTC market code.",
       former=("WHEAT - KANSAS CITY BOARD OF TRADE",)),
    _m("ZL", "007601", _DIS, "SOYBEAN OIL", _CBT),
    _m("ZM", "026603", _DIS, "SOYBEAN MEAL", _CBT),
    _m("ZO", "004603", _DIS, "OATS", _CBT),
    _m("ZR", "039601", _DIS, "ROUGH RICE", _CBT),
    # Livestock (Disaggregated)
    _m("LE", "057642", _DIS, "LIVE CATTLE", _CME),
    _m("GF", "061641", _DIS, "FEEDER CATTLE", _CME),
    _m("HE", "054642", _DIS, "LEAN HOGS", _CME),
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
OI_METHOD = "DERIVED: category long (short) ÷ total open interest × 100, for the same report."
#: Quality flag: a mapped market with rows in the window, but none in the newest public release.
NOT_IN_LATEST_RELEASE = "KNOWN_MARKET_NOT_IN_LATEST_RELEASE"
#: Why a report family is used for the Screener. Legacy is never the primary report here: every mapped
#: market is published in TFF or Disaggregated, which separate the participant categories Legacy merges.
REPORT_SELECTION_POLICY = ("Financial futures use Traders in Financial Futures; physical commodities use "
                           "Disaggregated. Legacy (commercial / non-commercial) is used only as mapping reference.")
#: Row keys that identify a Socrata row rather than its content (duplicate detection ignores them).
_ROW_ID_KEYS = frozenset({":id", "id", ":created_at", ":updated_at"})


def publication_for(report_date: date, calendar: ReleaseCalendar = DEFAULT_CALENDAR) -> tuple[datetime, str]:
    """Official publication time for a position date; a date no official table covers is inferred and flagged
    (holiday weeks conservatively: the next business day after Friday)."""

    published, basis = calendar.publication(report_date)
    return published.astimezone(UTC), basis


def latest_scheduled_report_date(now: datetime, calendar: ReleaseCalendar = DEFAULT_CALENDAR) -> date | None:
    """The newest position date whose release time has passed at ``now`` — any year, official or inferred."""

    return calendar.latest_visible_position(now)


def where_clause(codes: list[str], since: date) -> str:
    quoted = ", ".join(f"'{code}'" for code in sorted(set(codes)) if code.isalnum() or code.replace("+", "").isalnum())
    return f"cftc_contract_market_code in ({quoted}) AND report_date_as_yyyy_mm_dd >= '{since.isoformat()}T00:00:00.000'"


def _content(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in _ROW_ID_KEYS}


def _pct(part: int | None, whole: int | None) -> float | None:
    return round(100.0 * part / whole, 1) if part is not None and whole else None


def build_positioning(rows: list[dict[str, Any]], market: PositioningMarket, *, now: datetime,
                      calendar: ReleaseCalendar = DEFAULT_CALENDAR) -> dict[str, Any] | None:
    """The newest report for ``market`` that was public at ``now``; None when none is visible."""

    spec = dataset_spec(DATASETS[market.report])
    by_date: dict[date, list[dict[str, Any]]] = {}
    for row in rows:
        if str(row.get("cftc_contract_market_code") or "").strip() != market.code:
            continue
        try:
            report_date = date.fromisoformat(str(row.get("report_date_as_yyyy_mm_dd") or "")[:10])
        except ValueError:
            continue
        by_date.setdefault(report_date, []).append(row)
    for report_date in sorted(by_date, reverse=True):
        published, basis = publication_for(report_date, calendar)
        if now < published:
            continue  # not public yet at `now` — never shown early
        # Deterministic identity: the same (market code, report date) always resolves to the same row.
        candidates = sorted(by_date[report_date], key=lambda item: str(item.get("id") or item.get(":id") or ""))
        flags: list[str] = []
        if len(candidates) > 1:
            distinct = {repr(sorted(_content(row).items())) for row in candidates}
            flags.append("DUPLICATE_ROW_IGNORED" if len(distinct) == 1 else "CONFLICTING_DUPLICATE_ROWS")
        row = candidates[0]
        parsed = parse_cot_row(row, spec=spec)
        # Two different rows for one market and date: neither is shown as the published value.
        conflicting = "CONFLICTING_DUPLICATE_ROWS" in flags
        open_interest = None if conflicting else parsed.open_interest
        categories = []
        for item in () if conflicting else parsed.categories:
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
                "long_pct_oi": _pct(item.long_positions, open_interest), "short_pct_oi": _pct(item.short_positions, open_interest),
            })
        # Identity is the market code; the name is compared only to surface an official rename.
        # Whitespace is not a rename (the live MICRO ETHER row carries a double space).
        live_name = " ".join(parsed.market_and_exchange_names.split())
        if live_name and live_name not in (market.market_name, *market.former_names):
            flags.append("MARKET_NAME_DIFFERS_FROM_REFERENCE")
        latest = latest_scheduled_report_date(now, calendar)
        if latest is not None and report_date < latest:
            # The market exists (it has earlier rows) but is absent from the newest public release.
            # That is not "no CFTC market": the report shown is the newest one this market has.
            flags.append(NOT_IN_LATEST_RELEASE)
        return {
            "root": market.root, "report": market.report.value, "report_label": spec.label,
            "coverage_state": "MAPPED",
            "quality_state": "CONFLICTING_DUPLICATE_ROWS" if conflicting else "OK",
            "cftc_contract_market_code": market.code, "market_name": live_name or market.market_name,
            "reference_market_name": market.market_name,
            "report_date": report_date.isoformat(), "publication_time": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "publication_basis": basis, "available_at": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "latest_scheduled_report_date": latest.isoformat() if latest else None,
            "open_interest": open_interest,
            "change_open_interest": None if conflicting else _int(row.get("change_in_open_interest_all")),
            "categories": categories, "net_method": NET_METHOD, "oi_method": OI_METHOD, "source_url": SOURCE_URL,
            "dataset": spec.dataset_id, "source_row_id": parsed.source_row_id,
            "mapping": {"basis": market.basis.value, "confidence": market.confidence, "note": market.note or None},
            "quality_flags": flags,
        }
    return None


def _int(value: Any) -> int | None:
    try:
        return int(float(str(value).replace(",", ""))) if value not in (None, "") else None
    except ValueError:
        return None


__all__ = ["CATEGORY_LABELS", "CONFIDENCE", "DATASETS", "MappingBasis", "NET_METHOD", "NOT_IN_LATEST_RELEASE", "OI_METHOD",
           "DEFAULT_CALENDAR", "POSITIONING_MARKETS", "PositioningMarket", "REPORT_SELECTION_POLICY", "SOURCE_URL", "build_positioning",
           "latest_scheduled_report_date", "publication_for", "where_clause"]
