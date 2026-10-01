"""Bonds / Fixed Income universe for the Main Screener (S9, extended in S16).

Rows are outstanding U.S. Treasury marketable securities from the official
Treasury Fiscal Data catalog plus (S16) the Corporate, Agency, Municipal, and
Securitized categories: CUSIPs that SEC-registered funds reported holding in
Form N-PORT (``screener_bonds_fund``). Categories are filters inside the one
BONDS universe. Every row carries its CUSIP-keyed XA-01 identity and is
REFERENCE_ONLY: nothing here reaches execution.

Each value keeps its own clock and class:

- terms: Treasury reference data (event clock of the auction dataset);
- auction facts: the named auction's published results;
- amount outstanding: the MSPD month-end record date;
- curve reference: the Treasury par curve for the nearest published tenor on
  one publication date — a benchmark, never the security's yield;
- on-the-run bill closing bids: Treasury's daily bill rates, attached only to
  the CUSIP the feed names;
- derived analytics: deterministic formulas on those inputs, labeled DERIVED;
- (S16) observed operation prices: the weighted-average accepted price for a
  CUSIP in a Treasury buyback or a New York Fed outright purchase — a dated
  transaction observation; the yield, durations, DV01, and spread to the
  same-day interpolated par curve computed from it carry that date;
- (S16) TIPS index ratios and FRN daily indexes/accruals (Treasury, per CUSIP);
- (S16) fund-held rows: N-PORT terms reconciled across reporting funds and the
  funds' own fair values at their report date (stale, never a price).

No security-level *current* price, current yield, trade, or rating exists,
because no permitted universe-wide source supplies one.

Treasury, Treasury-market, and New York Fed sources are opt-in with
``IMP_TREASURY_LIVE=1`` (the same pattern as the other ``IMP_*_LIVE`` public
sources); fund-held rows need an N-PORT catalog built under
``IMP_NPORT_DATA_ROOT``. Fixtures never enter this path.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from datetime import UTC, date, datetime
from itertools import takewhile
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

from ..fixed_income import analytics
from ..fixed_income.finra_fixed_income import load_market_breadth, load_treasury_aggregates, trace_capability
from ..fixed_income.fred_context import load_fred_context
from ..fixed_income.http import failure_code
from ..fixed_income.identifiers import isin_from_cusip
from ..fixed_income.nport_catalog import CATEGORIES, ROOT_ENV as NPORT_ROOT_ENV, ManagedCatalog, NportCatalog, iter_records
from ..fixed_income.nyfed import SOURCE_OPERATIONS, SOURCE_RATES as NYFED_RATES, SOURCE_SOMA, SomaHoldings, load_reference_rates, load_soma
from ..fixed_income.observed import observed_measures
from ..fixed_income.openfigi import OpenFigi
from ..fixed_income.treasury_market import (
    SOURCE_BUYBACKS, SOURCE_FRN, SOURCE_TIPS, TreasuryMarketData, fetch_market_data,
)
from ..fixed_income.treasury_catalog import (
    BILL, CMB, FRN, ISSUER, SOURCE_AUCTIONS, SOURCE_MSPD, TIPS, TreasuryCatalog, TreasurySecurity,
    days_to_maturity, format_coupon, load_treasury_catalog, maturity_bucket, years_to_maturity,
)
from ..fixed_income.treasury_rates import (
    BILLS, NOMINAL, REAL, SOURCE as RATES_SOURCE, TreasuryRates, breakevens, curve_shape, curve_spreads,
    fetch_rates, match_reference, publication_state,
)
from ..xa01.compatibility import register_sovereign_security
from ..xa01.enums import InstrumentKind, XaAssetClass
from ..xa01.errors import Xa01Error
from ..xa01.identity import derive_canonical_id, sovereign_identity_key
from .screener_bonds_fund import FundHeldRow, _figi_item, fund_sections, haystack, to_page_row
from .screener_filters import apply_filters, field_value
from .screener_query import ScreenerQuery, exact_matches_first, order_rows, page_payload

ET = ZoneInfo("America/New_York")
SCHEMA_VERSION = "screener/1.0.0"
PREVIEW_SCHEMA_VERSION = "screener-bond-preview/1.0.0"
RATES_SCHEMA_VERSION = "screener-rates-curve/1.0.0"
LIVE_FLAG = "IMP_TREASURY_LIVE"
CATALOG_TTL_S = 6 * 3600
RATES_TTL_S = 30 * 60
CONTEXT_TTL_S = 6 * 3600
FAILURE_RETRY_S = 5 * 60
RETAINED_PROJECTIONS = 2
RESULT_CACHE_ENTRIES = 16
VENUE = "US_TREASURY"
SEARCH_KEYS = ("symbol", "company", "issuer", "security_type", "maturity", "term", "series", "isin", "category")
MARKET_TTL_S = 30 * 60
TREASURY_CATEGORY = "Treasury"
MARKET_SESSION = "PUBLICATION_BASED"
_NUMBERS = ("coupon", "years_to_maturity", "days_to_maturity", "maturity_year", "outstanding", "auction_yield",
            "auction_real_yield", "auction_discount_margin", "bid_to_cover", "reference_rate", "indicative_rate",
            "fund_count", "fund_par_held", "fund_value_pct", "observed_price", "observed_yield", "benchmark_spread")
#: Specialist-panel capability for this universe, with the reason a panel is absent.
CAPABILITIES: tuple[tuple[str, str, str | None], ...] = (
    ("rates_curve", "SUPPORTED", None),
    ("charts", "UNAVAILABLE", "NO_SECURITY_PRICE_HISTORY"),
    ("order_flow", "UNAVAILABLE", "NO_FIXED_INCOME_TRADE_STREAM"),
    ("cvd", "UNAVAILABLE", "NO_SIGNED_TRADE_DATA"),
    ("level2", "UNAVAILABLE", "NO_FIXED_INCOME_DEPTH"),
    ("futures", "UNAVAILABLE", "NO_VERIFIED_RATES_FUTURES_RELATIONSHIP"),
    ("options", "NOT_APPLICABLE", "NOT_AN_OPTIONABLE_INSTRUMENT"),
    ("short_squeeze", "NOT_APPLICABLE", "EQUITY_INTELLIGENCE_ONLY"),
)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_treasury_id(security: TreasurySecurity) -> str:
    """The XA-01 sovereign identity keyed by CUSIP (registered once, derived identically)."""

    try:
        return register_sovereign_security(
            cusip=security.cusip, issuer=ISSUER, security_type=security.kind,
            issue_date=security.issue_date.isoformat(), maturity_date=security.maturity_date.isoformat(),
            coupon="" if security.coupon_pct is None else format_coupon(security.coupon_pct))
    except Xa01Error:
        # Descriptive metadata changed since first registration; identity is CUSIP-only and unchanged.
        return derive_canonical_id(instrument_kind=InstrumentKind.SOVEREIGN_SECURITY,
                                   asset_class=XaAssetClass.SOVEREIGN_DEBT,
                                   identity_key=sovereign_identity_key(cusip=security.cusip))


def _field(value: float | None, source: str | None, as_of: str | None, state: str, basis: str | None = None) -> dict[str, Any]:
    envelope: dict[str, Any] = {"value": value, "source": source if value is not None else (source or "NONE"),
                                "state": state if value is not None else "UNAVAILABLE",
                                "as_of": as_of if value is not None else None}
    if basis:
        envelope["basis"] = basis
    return envelope


def _auction_yield(security: TreasurySecurity) -> tuple[float | None, str | None]:
    auction = security.latest_auction
    if auction is None or security.kind in (TIPS, FRN):
        return None, None
    if security.kind in (BILL, CMB):
        return auction.high_investment_rate, "HIGH_INVESTMENT_RATE"
    return auction.high_yield, "HIGH_YIELD"


def project_row(security: TreasurySecurity, *, today: date, catalog: TreasuryCatalog) -> dict[str, Any]:
    auction = security.latest_auction
    auction_as_of = auction.auction_date.isoformat() if auction else None
    years = years_to_maturity(security.maturity_date, today)
    terms_as_of = catalog.fetched_at
    auction_yield, basis = _auction_yield(security)
    mspd = catalog.mspd_record_date.isoformat() if catalog.mspd_record_date else None
    fields = {
        "coupon": _field(security.coupon_pct, SOURCE_AUCTIONS, terms_as_of, "CURRENT_METADATA"),
        "years_to_maturity": _field(round(years, 4), "IMP_DERIVED", today.isoformat(), "DERIVED"),
        "days_to_maturity": _field(float(days_to_maturity(security.maturity_date, today)), "IMP_DERIVED", today.isoformat(), "DERIVED"),
        "maturity_year": _field(float(security.maturity_date.year), security.source, terms_as_of, "CURRENT_METADATA"),
        "outstanding": _field(round(security.mspd_outstanding_musd / 1000, 3) if security.mspd_outstanding_musd is not None else None,
                              SOURCE_MSPD, mspd, "PUBLICATION"),
        "auction_yield": _field(auction_yield, SOURCE_AUCTIONS, auction_as_of, "AUCTION_RESULT", basis),
        "auction_real_yield": _field(auction.high_yield if auction and security.kind == TIPS else None, SOURCE_AUCTIONS,
                                     auction_as_of, "AUCTION_RESULT", "REAL_HIGH_YIELD"),
        "auction_discount_margin": _field(auction.high_discount_margin if auction and security.kind == FRN else None,
                                          SOURCE_AUCTIONS, auction_as_of, "AUCTION_RESULT", "HIGH_DISCOUNT_MARGIN"),
        "bid_to_cover": _field(auction.bid_to_cover if auction else None, SOURCE_AUCTIONS, auction_as_of, "AUCTION_RESULT"),
        "reference_rate": _field(None, RATES_SOURCE, None, "REFERENCE"),
        "indicative_rate": _field(None, RATES_SOURCE, None, "PUBLICATION"),
        # Fund-held measures do not apply to Treasuries; observed-operation values attach per page (``with_observed``).
        **{name: _field(None, None, None, "UNAVAILABLE") for name in ("fund_count", "fund_par_held", "fund_value_pct",
                                                                        "observed_price", "observed_yield", "benchmark_spread")},
    }
    return {
        "instrument": {"instrument_id": canonical_treasury_id(security), "venue_id": VENUE,
                       "asset_class": XaAssetClass.SOVEREIGN_DEBT.value,
                       "instrument_kind": InstrumentKind.SOVEREIGN_SECURITY.value, "tradability": "REFERENCE_ONLY"},
        # CUSIP is the identity shown in the pinned column; it is never a ticker.
        "symbol": security.cusip, "company": security.description, "sector": None, "industry": None,
        "country": "USA", "earnings_date": None, "recommendation": None, "exchange": None,
        "cusip": security.cusip, "isin": isin_from_cusip(security.cusip), "isin_source": "DERIVED",
        "identity_source": "CUSIP", "issuer": ISSUER, "category": TREASURY_CATEGORY, "security_type": security.kind, "term": security.original_term, "issue_date": security.issue_date.isoformat(),
        "maturity": security.maturity_date.isoformat(), "maturity_bucket": maturity_bucket(years),
        "tips": "Yes" if security.tips else "No", "frn": "Yes" if security.frn else "No",
        "callable": None if security.callable is None else "Yes" if security.callable else "No",
        "coupon_type": "Floating" if security.kind == FRN else "Zero coupon" if security.kind in (BILL, CMB) else "Fixed",
        "in_default": None, "convertible": None, "pik": None, "report_date": None, "observed_date": None,
        "auction_date": auction_as_of, "series": security.series,
        "reference_tenor": None, "reference_date": None, "reference_reason": None,
        "fields": fields,
    }


def _reference(security_kind: str, years: float, rates: TreasuryRates | None, *, floating: bool = False) -> dict[str, Any]:
    if security_kind == FRN:
        return {"state": "UNAVAILABLE", "reason": "FRN_INDEXED_TO_13_WEEK_BILL"}
    if floating:
        return {"state": "UNAVAILABLE", "reason": "FLOATING_RATE_NO_MATURITY_MATCH"}
    publication = (rates.latest_real if security_kind == TIPS else rates.latest_nominal) if rates else None
    return match_reference(years, publication)


def with_rates(row: dict[str, Any], rates: TreasuryRates | None) -> dict[str, Any]:
    """A page row carrying the publication context current at response time."""

    years = row["fields"]["years_to_maturity"]["value"]
    reference = _reference(row["security_type"], years, rates,
                           floating=row.get("category") != TREASURY_CATEGORY and row.get("frn") == "Yes")
    fields = dict(row["fields"])
    decorated = {**row, "fields": fields}
    if reference["state"] == "REFERENCE":
        curve = "REAL_PAR" if reference["curve"] == REAL else "NOMINAL_PAR"
        fields["reference_rate"] = _field(reference["value"], RATES_SOURCE, reference["publication_date"], "REFERENCE",
                                          f"{curve}_{reference['tenor']}")
        decorated.update(reference_tenor=f"{reference['tenor']}{' real' if reference['curve'] == REAL else ''}",
                         reference_date=reference["publication_date"], reference_reason=None)
    else:
        decorated.update(reference_reason=reference["reason"])
    bills = rates.latest_bills if rates else None
    quote = bills.for_cusip(row["cusip"]) if bills and row.get("category") == TREASURY_CATEGORY else None
    if quote is not None and quote.coupon_equivalent is not None:
        fields["indicative_rate"] = _field(quote.coupon_equivalent, RATES_SOURCE, bills.date.isoformat(), "PUBLICATION",
                                           "CLOSING_BID_COUPON_EQUIVALENT")
    return decorated


def with_observed(row: dict[str, Any], observed: dict[str, Any] | None) -> dict[str, Any]:
    """Attach a Treasury row's latest observed operation price and what follows from it (dated)."""

    if not observed:
        return row
    fields = dict(row["fields"])
    day = observed["operation_date"]
    fields["observed_price"] = _field(observed["price"], observed["source"], day, "DATED_OBSERVATION",
                                      observed["kind"] + ("_REAL_PRICE" if observed["price_basis"].startswith("REAL") else
                                                          "_FROM_DISCOUNT_RATE" if observed.get("quoted_discount_rate") is not None
                                                          else ""))
    fields["observed_yield"] = _field(observed["yield"], "IMP_DERIVED", day, "DERIVED", observed["yield_basis"])
    benchmark = observed.get("benchmark") or {}
    fields["benchmark_spread"] = _field(benchmark.get("spread_bp"), "IMP_DERIVED", day, "DERIVED",
                                        f"{benchmark['curve']}_LINEAR_{benchmark['lower_tenor']}_{benchmark['upper_tenor']}"
                                        if benchmark.get("spread_bp") is not None else None)
    return {**row, "fields": fields, "observed_date": day}


class BondScreener:
    def __init__(self, *, env: Mapping[str, str] = os.environ,
                 catalog_loader: Callable[..., TreasuryCatalog] = load_treasury_catalog,
                 rates_loader: Callable[..., TreasuryRates] = fetch_rates,
                 fred_loader: Callable[..., dict[str, Any]] = load_fred_context,
                 finra_loader: Callable[..., dict[str, Any]] = load_treasury_aggregates,
                 breadth_loader: Callable[..., dict[str, Any]] = load_market_breadth,
                 market_loader: Callable[..., TreasuryMarketData] = fetch_market_data,
                 nyfed_rates_loader: Callable[[], dict[str, Any]] = load_reference_rates,
                 soma_loader: Callable[[], SomaHoldings] = load_soma,
                 nport: ManagedCatalog | None | bool = True,
                 openfigi: OpenFigi | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 today: Callable[[], date] = lambda: datetime.now(ET).date(),
                 now: Callable[[], str] = _now) -> None:
        self._env, self._clock, self._today, self._now = env, clock, today, now
        self._catalog_loader, self._rates_loader = catalog_loader, rates_loader
        self._fred_loader, self._finra_loader, self._breadth_loader = fred_loader, finra_loader, breadth_loader
        self._market_loader, self._nyfed_rates_loader, self._soma_loader = market_loader, nyfed_rates_loader, soma_loader
        # ``True``: the managed N-PORT root named by IMP_NPORT_DATA_ROOT (if any); tests inject a catalog or None.
        root = env.get(NPORT_ROOT_ENV)
        self._nport = (ManagedCatalog(root) if root else None) if nport is True else (nport or None)
        self._figi = openfigi or OpenFigi(env=env)
        self._lock = threading.RLock()
        self._catalog_entry: tuple[float, TreasuryCatalog | None, str | None] | None = None
        self._rates_entry: tuple[float, TreasuryRates | None, str | None] | None = None
        self._market_entry: tuple[float, TreasuryMarketData | None, str | None] | None = None
        self._observed: tuple[Any, dict[str, dict[str, Any]]] | None = None
        self._context: dict[str, tuple[float, Any]] = {}
        self._projected: OrderedDict[tuple[Any, ...], list[Any]] = OrderedDict()
        self._ordered: OrderedDict[tuple[Any, ...], list[Any]] = OrderedDict()
        self.catalog_loads = 0
        self.rates_loads = 0
        self.market_loads = 0

    # ------------------------------------------------------------ sources
    def enabled(self) -> bool:
        return self._env.get(LIVE_FLAG) == "1"

    def _catalog(self, *, force: bool = False) -> tuple[TreasuryCatalog | None, str | None]:
        if not self.enabled():
            return None, "TREASURY_NOT_CONFIGURED"
        with self._lock:
            entry = self._catalog_entry
            if entry is not None and not force:
                loaded_at, catalog, error = entry
                ttl = CATALOG_TTL_S if error is None else FAILURE_RETRY_S
                if self._clock() - loaded_at < ttl:
                    return catalog, error
            try:
                self.catalog_loads += 1
                catalog, error = self._catalog_loader(today=self._today(), fetched_at=self._now()), None
            except Exception as exc:  # noqa: BLE001 — stable code; the last good catalog stays visible
                catalog, error = (entry[1] if entry else None), failure_code(exc)
            self._catalog_entry = (self._clock(), catalog, error)
            return catalog, error

    def _rates(self) -> tuple[TreasuryRates | None, str | None]:
        if not self.enabled():
            return None, "TREASURY_NOT_CONFIGURED"
        with self._lock:
            entry = self._rates_entry
            # Day-aware: a new trading date always re-reads the publication.
            if entry is not None:
                loaded_at, rates, error = entry
                ttl = RATES_TTL_S if error is None else FAILURE_RETRY_S
                if self._clock() - loaded_at < ttl:
                    return rates, error
            try:
                self.rates_loads += 1
                rates = self._rates_loader(today=self._today(), fetched_at=self._now())
                error = None if rates.nominal else rates.errors.get(NOMINAL, "NO_PUBLICATION")
            except Exception as exc:  # noqa: BLE001
                rates, error = (entry[1] if entry else None), failure_code(exc)
            self._rates_entry = (self._clock(), rates, error)
            return rates, error

    def _market(self) -> tuple[TreasuryMarketData | None, str | None]:
        """TIPS index ratios, FRN indexes, and observed operation prices (one cached bundle)."""

        if not self.enabled():
            return None, "TREASURY_NOT_CONFIGURED"
        with self._lock:
            entry = self._market_entry
            if entry is not None and self._clock() - entry[0] < (MARKET_TTL_S if entry[2] is None else FAILURE_RETRY_S):
                return entry[1], entry[2]
            try:
                self.market_loads += 1
                market, error = self._market_loader(today=self._today(), fetched_at=self._now()), None
            except Exception as exc:  # noqa: BLE001
                market, error = (entry[1] if entry else None), failure_code(exc)
            self._market_entry = (self._clock(), market, error)
            return market, error

    def _observed_index(self, catalog: TreasuryCatalog | None, rates: TreasuryRates | None) -> dict[str, dict[str, Any]]:
        """Dated analytics for every Treasury CUSIP with an observed operation price (computed once per inputs)."""

        market, _error = self._market() if catalog is not None else (None, None)
        if catalog is None or market is None or not market.prices:
            return {}
        key = (catalog.fetched_at, market.fetched_at, rates.fetched_at if rates else None)
        with self._lock:
            if self._observed is not None and self._observed[0] == key:
                return self._observed[1]
        securities = {security.cusip: security for security in catalog.securities}
        index = {cusip: observed_measures(securities[cusip], observation, rates)
                 for cusip, observation in market.prices.items() if cusip in securities}
        with self._lock:
            self._observed = (key, index)
        return index

    def _cached_context(self, key: str, loader: Callable[[], Any], ttl: float = CONTEXT_TTL_S) -> Any:
        with self._lock:
            cached = self._context.get(key)
            if cached and self._clock() - cached[0] < ttl:
                return cached[1]
        try:
            value = loader()
        except Exception as exc:  # noqa: BLE001
            value = {"state": "UNAVAILABLE", "reason": failure_code(exc), "items": [], "rows": []}
        with self._lock:
            self._context[key] = (self._clock(), value)
        return value

    def _nyfed_rates(self) -> dict[str, Any]:
        if not self.enabled():
            return {"state": "NOT_CONFIGURED", "reason": LIVE_FLAG + "_NOT_SET", "items": []}
        return self._cached_context("nyfed_rates", self._nyfed_rates_loader, MARKET_TTL_S)

    def _soma(self) -> SomaHoldings | None:
        if not self.enabled():
            return None
        value = self._cached_context("soma", self._soma_loader)
        return value if isinstance(value, SomaHoldings) else None

    def _fund_catalog(self) -> tuple[NportCatalog | None, dict[str, Any]]:
        if self._nport is None:
            return None, {"refresh_state": "NOT_CONFIGURED", "refresh_reason": NPORT_ROOT_ENV + "_NOT_SET", "managed": False}
        return self._nport.current()

    @staticmethod
    def _result_set(catalog: TreasuryCatalog | None, funds: NportCatalog | None) -> str | None:
        if catalog is None and funds is None:
            return None
        treasury = catalog.fetched_at if catalog else ""
        return f"{treasury}|{funds.meta.get('generation')}" if funds is not None else treasury

    def _rows(self, catalog: TreasuryCatalog | None, funds: NportCatalog | None = None) -> list[Any]:
        """Treasury rows (dicts) followed by fund-held rows (slotted views); one list per inputs and day."""

        if catalog is None and funds is None:
            return []
        today = self._today()
        key = (self._result_set(catalog, funds), today)
        with self._lock:
            rows = self._projected.get(key)
            if rows is None:
                # Outstanding is re-validated whenever the date changes: a matured security leaves.
                rows = [project_row(security, today=today, catalog=catalog) for security in catalog.outstanding(today)] \
                    if catalog is not None else []
                rows += [FundHeldRow(record, today) for record in iter_records(funds, today)]
                self._projected[key] = rows
                while len(self._projected) > RETAINED_PROJECTIONS:
                    self._projected.popitem(last=False)
            return rows

    def _coverage(self, catalog: TreasuryCatalog | None, error: str | None, rows: list[Any],
                  funds: NportCatalog | None, fund_status: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Counts per category and, separately, each category's source and clock. Never a folded total."""

        treasury = sum(1 for row in rows if isinstance(row, dict))
        coverage = {"TREASURY": {"state": "CURRENT" if treasury else "UNAVAILABLE", "count": treasury if treasury else None}}
        detail: dict[str, Any] = {"TREASURY": {"source": SOURCE_AUCTIONS, "as_of": catalog.fetched_at if catalog else None,
                                               "reason": error if not treasury else None,
                                               "basis": "Outstanding marketable Treasury securities (Fiscal Data auctions + MSPD)"}}
        counts: dict[str, int] = {}
        for row in rows:
            if isinstance(row, FundHeldRow):
                counts[row.record.category] = counts.get(row.record.category, 0) + 1
        refresh = fund_status.get("refresh_state")
        for category in CATEGORIES:
            key = category.upper()
            if funds is None:
                state = "NOT_CONFIGURED" if refresh in (None, "NOT_CONFIGURED") else "UNAVAILABLE"
                coverage[key] = {"state": state, "count": None}
                detail[key] = {"source": "SEC_FORM_NPORT", "as_of": None,
                               "reason": fund_status.get("refresh_reason") or fund_status.get("load_problem"), "basis": None}
                continue
            coverage[key] = {"state": "FUND_HELD_REFERENCE", "count": counts.get(category, 0)}
            detail[key] = {"source": "SEC_FORM_NPORT", "as_of": funds.meta.get("report_date_max"),
                           "dataset": funds.meta.get("source_dataset"), "refresh_state": refresh,
                           "reason": None, "basis": "CUSIPs reported held by SEC-registered funds (Form N-PORT), "
                                                    "reconciled across filings; not every outstanding bond"}
        return coverage, detail

    def _health(self, catalog: TreasuryCatalog | None, error: str | None,
                rates: TreasuryRates | None, rates_error: str | None, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        today = self._today()
        nominal = rates.latest_nominal if rates else None
        return [
            {"provider": "US_TREASURY_FISCAL_DATA", "role": "IDENTITY_SOURCE",
             "state": "NOT_CONFIGURED" if error == "TREASURY_NOT_CONFIGURED" else
                      "DEGRADED" if error and rows else "UNAVAILABLE" if error else "HEALTHY", "reason": error},
            {"provider": SOURCE_MSPD, "role": "AMOUNT_OUTSTANDING",
             "state": "UNAVAILABLE" if catalog is None or catalog.mspd_error else "PUBLICATION_CURRENT",
             "reason": catalog.mspd_error if catalog else error},
            {"provider": RATES_SOURCE, "role": "REFERENCE_CURVE",
             "state": "NOT_CONFIGURED" if rates_error == "TREASURY_NOT_CONFIGURED" else
                      publication_state(nominal.date if nominal else None, today), "reason": rates_error},
            {"provider": "FINRA_TRACE", "role": "SECURITY_TRADES", "state": "FINRA_TERMS_REQUIRED",
             "reason": "LICENSED_TRACE_FEED_REQUIRED"},
        ]

    @staticmethod
    def _fund_health(funds: NportCatalog | None, status: dict[str, Any]) -> dict[str, Any]:
        state = status.get("refresh_state") or "NOT_CONFIGURED"
        return {"provider": "SEC_FORM_NPORT", "role": "FUND_HELD_REFERENCE_CATALOG",
                "state": ("NOT_CONFIGURED" if funds is None and state == "NOT_CONFIGURED" else
                          "UNAVAILABLE" if funds is None else state),
                "reason": status.get("refresh_reason") or status.get("load_problem"),
                "as_of": funds.meta.get("report_date_max") if funds else None}

    # ------------------------------------------------------------ Screener
    def read(self, query: ScreenerQuery, *, force_refresh: bool = False) -> dict[str, Any]:
        funds, fund_status = self._fund_catalog()
        if query.result_set is not None:
            with self._lock:
                pinned = next((rows for (result_set, day), rows in self._projected.items()
                               if result_set == query.result_set and day == self._today()), None)
            if pinned is None:
                raise ValueError("RESULT_SET_CHANGED")
            catalog, error = (self._catalog_entry[1] if self._catalog_entry else None), None
            rows, result_set = pinned, query.result_set
        else:
            catalog, error = self._catalog(force=force_refresh)
            rows = self._rows(catalog, funds)
            result_set = self._result_set(catalog, funds) if rows else None
        as_of = catalog.fetched_at if catalog else (funds.meta.get("filing_date_max") if funds else None)
        rates, rates_error = self._rates() if rows else (None, None)
        coverage, coverage_sources = self._coverage(catalog, error, rows, funds, fund_status)
        envelope = {
            "schema_version": SCHEMA_VERSION, "universe": query.universe, "generated_at": self._now(),
            "market_session": MARKET_SESSION, "universe_as_of": as_of, "screener_as_of": as_of,
            "evaluation": "CATALOG", "snapshot": None, "unfiltered_count": len(rows),
            "provider_health": [*self._health(catalog, error, rates, rates_error, rows), self._fund_health(funds, fund_status)],
            # Counts per category; unavailable categories are never folded into a total.
            "coverage": coverage, "coverage_sources": coverage_sources,
        }
        if not rows:
            return {**envelope, "result_set_id": None, "source_error": error or "TREASURY_CATALOG_UNAVAILABLE",
                    **page_payload(query, [])}
        key = (result_set, self._today(), query.identity)
        with self._lock:
            ordered = self._ordered.get(key)
        if ordered is None:
            needle = query.search.casefold()
            matched = [row for row in apply_filters(rows, list(query.filters))
                       if not needle or needle in haystack(row, SEARCH_KEYS)]
            ordered = exact_matches_first(order_rows(matched, query.sort, query.descending, field_value), needle,
                                          ("symbol", "isin"))
            with self._lock:
                self._ordered[key] = ordered
                while len(self._ordered) > RESULT_CACHE_ENTRIES:
                    self._ordered.popitem(last=False)
        page = page_payload(query, ordered)
        observed = self._observed_index(catalog, rates) if any(isinstance(row, dict) for row in page["rows"]) else {}
        page["rows"] = [with_observed(with_rates(to_page_row(row), rates), observed.get(row["cusip"]))
                        for row in page["rows"]]
        return {**envelope, "result_set_id": result_set, "source_error": None, **page}

    def _find(self, instrument_id: str) -> tuple[Any, TreasuryCatalog | None, str | None]:
        """(row, Treasury catalog, error): Treasury rows by scan (hundreds), fund rows by id index."""

        catalog, error = self._catalog()
        funds, _status = self._fund_catalog()
        rows = self._rows(catalog, funds)
        # Treasury rows (dicts) lead the list; stop at the first fund-held view instead of walking all of them.
        treasury = next((row for row in takewhile(lambda row: isinstance(row, dict), rows)
                         if row["instrument"]["instrument_id"] == instrument_id), None)
        if treasury is not None or funds is None:
            return treasury, catalog, error
        record = funds.by_instrument(instrument_id)
        if record is None or record.maturity <= self._today():
            return None, catalog, error
        return FundHeldRow(record, self._today()), catalog, error

    def row_for(self, instrument_id: str) -> tuple[dict[str, Any] | None, str | None]:
        row, _catalog, error = self._find(instrument_id)
        return (to_page_row(row) if row is not None else None), error

    def treasury_rows(self) -> tuple[list[dict[str, Any]], str | None]:
        """Every outstanding Treasury row, from the same cached projection the Screener pages use.

        Consumers that key on Treasury CUSIPs (News) need all of them, not a page of the whole
        universe: fund-held rows outnumber Treasuries several hundred to one.
        """

        catalog, error = self._catalog()
        funds, _status = self._fund_catalog()
        rows = self._rows(catalog, funds)
        return [to_page_row(row) for row in takewhile(lambda row: isinstance(row, dict), rows)], error

    def window(self, symbols: list[str]) -> dict[str, Any]:
        """Bonds have no streaming quotes; the window reports that per row."""

        return {"schema_version": SCHEMA_VERSION, "generated_at": self._now(), "market_session": MARKET_SESSION,
                "active": 0, "cap": 0,
                "quotes": {symbol: {"state": "UNAVAILABLE", "reason": "NO_STREAMING_BOND_QUOTES", "fields": {}}
                           for symbol in symbols}}

    # ------------------------------------------------------------ context
    def _security(self, instrument_id: str) -> tuple[TreasurySecurity | None, dict[str, Any] | None]:
        row, catalog, _error = self._find(instrument_id)
        if catalog is None or not isinstance(row, dict):
            return None, None
        return next(item for item in catalog.securities if item.cusip == row["cusip"]), row

    def _fred(self) -> dict[str, Any]:
        return self._cached_context("fred", lambda: self._fred_loader(today=self._today(), retrieved=self._now()))

    def _finra(self) -> dict[str, Any]:
        return self._cached_context("finra", lambda: self._finra_loader(today=self._today(), env=self._env))

    def sources(self, rates: TreasuryRates | None, rates_error: str | None, *, fred: dict[str, Any] | None = None,
                finra: dict[str, Any] | None = None, nyfed: dict[str, Any] | None = None,
                breadth: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """The source/licence matrix: every input the universe could use, with its clock and state."""

        catalog, error = self._catalog()
        today = self._today()
        nominal, real, bills = ((rates.latest_nominal, rates.latest_real, rates.latest_bills) if rates else (None, None, None))
        not_configured = error == "TREASURY_NOT_CONFIGURED"

        def curve_state(publication: Any, kind: str) -> tuple[str, str | None]:
            if not_configured:
                return "NOT_CONFIGURED", LIVE_FLAG + "_NOT_SET"
            if publication is None:
                return "UNAVAILABLE", (rates.errors.get(kind) if rates else rates_error)
            return publication_state(publication.date, today), None

        items = [
            {"id": "TREASURY_CATALOG", "label": "Treasury terms & auctions", "provider": "U.S. Treasury Fiscal Data",
             "clock": "EVENT_REFERENCE", "state": "NOT_CONFIGURED" if not_configured else "UNAVAILABLE" if catalog is None else
             "DEGRADED" if error else "CURRENT", "as_of": catalog.fetched_at if catalog else None,
             "reason": (LIVE_FLAG + "_NOT_SET") if not_configured else error},
            {"id": "TREASURY_OUTSTANDING", "label": "Amounts outstanding (MSPD)", "provider": "U.S. Treasury Fiscal Data",
             "clock": "MONTHLY_PUBLICATION", "state": "NOT_CONFIGURED" if not_configured else
             "UNAVAILABLE" if catalog is None or catalog.mspd_error else "PUBLICATION_CURRENT",
             "as_of": catalog.mspd_record_date.isoformat() if catalog and catalog.mspd_record_date else None,
             "reason": catalog.mspd_error if catalog else None},
        ]
        for source_id, label, publication, kind in (("TREASURY_CURVE", "Par yield curve (nominal)", nominal, NOMINAL),
                                                    ("TREASURY_REAL_CURVE", "Par real yield curve", real, REAL),
                                                    ("TREASURY_BILL_RATES", "Daily bill rates", bills, BILLS)):
            state, reason = curve_state(publication, kind)
            items.append({"id": source_id, "label": label, "provider": "U.S. Treasury", "clock": "DAILY_PUBLICATION",
                          "state": state, "as_of": publication.date.isoformat() if publication else None, "reason": reason})
        if fred is not None:
            items.append({"id": "FRED_RATES", "label": "Policy, credit & conditions", "provider": "FRED",
                          "clock": "SERIES_PUBLICATION", "state": fred.get("state"), "reason": fred.get("reason"),
                          "as_of": max((item["observation_date"] for item in fred.get("items", []) if item.get("observation_date")), default=None)})
        trace = trace_capability()
        items.append({"id": "FINRA_TRACE", "label": "Security trade prints (TRACE)", "provider": "FINRA",
                      "clock": "TRANSACTION", "state": trace["state"], "as_of": None, "reason": "LICENSED_TRACE_FEED_REQUIRED"})
        if finra is not None:
            items.append({"id": "FINRA_AGGREGATES", "label": "TRACE Treasury aggregates", "provider": "FINRA",
                          "clock": "DAILY_PUBLICATION", "state": finra.get("state"), "as_of": finra.get("trade_date"),
                          "reason": finra.get("reason")})
        if breadth is not None:
            items.append({"id": "FINRA_BREADTH", "label": "TRACE corporate & agency market breadth", "provider": "FINRA",
                          "clock": "DAILY_PUBLICATION", "state": breadth.get("state"), "reason": breadth.get("reason"),
                          "as_of": max((item.get("trade_date") or "" for item in breadth.get("categories", {}).values()), default=None) or None})
        items += self._s16_sources(not_configured, nyfed)
        return items

    def _s16_sources(self, not_configured: bool, nyfed: dict[str, Any] | None) -> list[dict[str, Any]]:
        live_reason = LIVE_FLAG + "_NOT_SET"
        nyfed = nyfed if nyfed is not None else self._nyfed_rates()
        market, market_error = self._market()
        funds, fund_status = self._fund_catalog()
        soma = self._soma()

        def feed(feed_id: str, label: str, provider: str, clock: str, key: str, count_key: str) -> dict[str, Any]:
            if not_configured:
                return {"id": feed_id, "label": label, "provider": provider, "clock": clock, "state": "NOT_CONFIGURED",
                        "as_of": None, "reason": live_reason}
            reason = market.errors.get(key) if market else market_error
            return {"id": feed_id, "label": label, "provider": provider, "clock": clock,
                    "state": "UNAVAILABLE" if reason else "CURRENT", "as_of": market.fetched_at if market and not reason else None,
                    "reason": reason, "count": market.counts.get(count_key) if market and not reason else None}

        items = [
            {"id": "NPORT_CATALOG", "label": "Fund-held bonds (Form N-PORT)", "provider": "SEC EDGAR",
             "clock": "QUARTERLY_PUBLICATION_60_DAY_LAG",
             "state": ("NOT_CONFIGURED" if funds is None and fund_status.get("refresh_state") in (None, "NOT_CONFIGURED") else
                       "UNAVAILABLE" if funds is None else fund_status.get("refresh_state") or "CURRENT"),
             "as_of": funds.meta.get("report_date_max") if funds else None,
             "reason": fund_status.get("refresh_reason") or fund_status.get("load_problem"),
             "licence": "Public SEC data; attribution"},
            feed("TREASURY_TIPS_INDEX", "TIPS index ratios", "U.S. Treasury Fiscal Data", "DAILY_PUBLICATION", "TIPS_INDEX", "tips"),
            feed("TREASURY_FRN_INDEX", "FRN daily indexes & accruals", "U.S. Treasury Fiscal Data", "DAILY_PUBLICATION", "FRN_INDEX", "frn"),
            feed("TREASURY_BUYBACKS", "Buyback operation prices", "U.S. Treasury Fiscal Data", "EVENT_OBSERVATION", "BUYBACKS",
                 "buyback_observations"),
            feed("NY_FED_OPERATIONS", "Fed outright purchase prices", "Federal Reserve Bank of New York", "EVENT_OBSERVATION",
                 "FED_OPERATIONS", "fed_observations"),
            {"id": "NY_FED_RATES", "label": "SOFR · EFFR · OBFR · TGCR · BGCR", "provider": "Federal Reserve Bank of New York",
             "clock": "DAILY_PUBLICATION", "state": "NOT_CONFIGURED" if not_configured else (nyfed or {}).get("state"),
             "reason": live_reason if not_configured else (nyfed or {}).get("reason"),
             "as_of": max((item["effective_date"] for item in (nyfed or {}).get("items", [])), default=None)},
            {"id": "NY_FED_SOMA", "label": "SOMA holdings by CUSIP", "provider": "Federal Reserve Bank of New York",
             "clock": "WEEKLY_PUBLICATION", "state": "NOT_CONFIGURED" if not_configured else "CURRENT" if soma else "UNAVAILABLE",
             "as_of": soma.as_of.isoformat() if soma else None, "reason": live_reason if not_configured else None if soma else "SOMA_UNAVAILABLE"},
            {"id": "OPENFIGI", "label": "FIGI identifiers (on preview only)", "provider": "OpenFIGI",
             "clock": "ON_DEMAND", "state": "CONFIGURED" if self._figi.enabled() else "NOT_CONFIGURED", "as_of": None,
             "reason": None if self._figi.enabled() else "IMP_OPENFIGI_LIVE_NOT_SET"},
            {"id": "NRSRO_RATINGS", "label": "Credit ratings", "provider": "NRSROs", "clock": "EVENT_REFERENCE",
             "state": "TERMS_REQUIRED", "as_of": None, "reason": "LICENSED_RATINGS_FEED_REQUIRED"},
            {"id": "MSRB_EMMA", "label": "Municipal trades & disclosures", "provider": "MSRB EMMA", "clock": "TRANSACTION",
             "state": "TERMS_REQUIRED", "as_of": None, "reason": "NOT_LICENSED_FOR_REDISTRIBUTION"},
        ]
        return items

    def preview(self, instrument_id: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
        from .screener_preview import explain_matches

        found, catalog, _error = self._find(instrument_id)
        if found is None:
            return None
        today = self._today()
        rates, rates_error = self._rates()
        soma = self._soma()
        # One OpenFIGI request per opened preview (cached, rate-limited, off unless IMP_OPENFIGI_LIVE=1).
        figi = self._figi.lookup(found["cusip"])
        if isinstance(found, FundHeldRow):
            record = found.record
            decorated = with_rates(found.to_dict(), rates)
            instrument = {**decorated["instrument"], "cusip": record.cusip, "isin": record.isin, "identity_source": "CUSIP",
                          "issuer": record.issuer, "description": decorated["company"], "security_type": record.subtype,
                          "series": None, "category": record.category}
            sections = fund_sections(record, decorated, today=today, soma=soma, figi=figi)
        else:
            security = next(item for item in catalog.securities if item.cusip == found["cusip"])
            market, _market_error = self._market()
            observed = self._observed_index(catalog, rates).get(security.cusip)
            decorated = with_observed(with_rates(found, rates), observed)
            instrument = {**found["instrument"], "cusip": security.cusip, "isin": found["isin"], "identity_source": "CUSIP",
                          "issuer": ISSUER, "description": security.description, "security_type": security.kind,
                          "series": security.series, "category": TREASURY_CATEGORY}
            sections = security_sections(security, decorated, rates, today=today, market_data=market, observed=observed,
                                         soma=soma, figi=figi)
        return {
            "schema_version": PREVIEW_SCHEMA_VERSION, "universe": "BONDS", "generated_at": self._now(),
            "market_session": MARKET_SESSION, "instrument": instrument, "sections": sections,
            "why": {"matched": explain_matches(decorated, rules, universe="BONDS")},
            "sources": self.sources(rates, rates_error),
            "capabilities": [{"panel": panel, "state": state, "reason": reason} for panel, state, reason in CAPABILITIES],
        }

    def rates_curve(self, instrument_id: str | None) -> dict[str, Any] | None:
        found, catalog, _error = self._find(instrument_id) if instrument_id else (None, None, None)
        if instrument_id and found is None:
            return None
        security = (next(item for item in catalog.securities if item.cusip == found["cusip"])
                    if isinstance(found, dict) and catalog is not None else None)
        row = found if security is not None else None
        today = self._today()
        rates, rates_error = self._rates()
        fred = self._fred()
        finra = self._finra()
        breadth = self._cached_context("breadth", lambda: self._breadth_loader(today=self._today(), env=self._env))
        nyfed = self._nyfed_rates()
        nominal = rates.latest_nominal if rates else None
        real = rates.latest_real if rates else None

        def curve(publications: tuple[Any, ...]) -> dict[str, Any]:
            if not publications:
                return {"publication_date": None, "state": "UNAVAILABLE", "points": [], "previous": None, "month_ago": None}
            latest = publications[-1]
            month_ago = next((item for item in reversed(publications) if (latest.date - item.date).days >= 28), None)
            as_dict = lambda item: None if item is None else {  # noqa: E731
                "publication_date": item.date.isoformat(),
                "points": [{"tenor": p.tenor, "years": p.years, "value": p.value} for p in item.points]}
            return {"state": publication_state(latest.date, today), **as_dict(latest),
                    "previous": as_dict(publications[-2] if len(publications) > 1 else None), "month_ago": as_dict(month_ago)}

        no_spread = {"state": "UNAVAILABLE", "reason": "NO_CURRENT_SECURITY_YIELD",
                     "note": "A spread needs this security's current yield; the auction yield and the curve have different clocks."}
        selected = None
        if security is not None and row is not None:
            decorated = with_rates(row, rates)
            observed = self._observed_index(catalog, rates).get(security.cusip)
            benchmark = (observed or {}).get("benchmark") or {}
            spread = no_spread if observed is None or benchmark.get("spread_bp") is None else {
                "state": "DERIVED", "reason": None, "value": benchmark["spread_bp"], "unit": "bp",
                "yield": observed["yield"], "yield_basis": observed["yield_basis"], "price": observed["price"],
                "price_kind": observed["kind"], "source": observed["source"], "operation_date": observed["operation_date"],
                "settlement_date": observed["settlement_date"], "curve": benchmark["curve"],
                "curve_date": benchmark["publication_date"], "par_yield": benchmark["value"],
                "tenors": [benchmark["lower_tenor"], benchmark["upper_tenor"]],
                "note": "Yield at a dated operation price minus the same-day par curve, linearly interpolated; "
                        "an observation on the operation date, not a current spread."}
            selected = {"instrument_id": row["instrument"]["instrument_id"], "cusip": security.cusip,
                        "description": security.description, "security_type": security.kind, "category": TREASURY_CATEGORY,
                        "maturity": row["maturity"], "years_to_maturity": row["fields"]["years_to_maturity"]["value"],
                        "reference": _reference(security.kind, row["fields"]["years_to_maturity"]["value"], rates),
                        "indicative": decorated["fields"]["indicative_rate"] if decorated["fields"]["indicative_rate"]["value"] is not None else None,
                        "auction_yield": row["fields"]["auction_yield"], "auction_real_yield": row["fields"]["auction_real_yield"],
                        "spread": spread}
        elif isinstance(found, FundHeldRow):
            fund_row = found.to_dict()
            years = fund_row["fields"]["years_to_maturity"]["value"]
            selected = {"instrument_id": found.record.instrument_id, "cusip": found.record.cusip,
                        "description": fund_row["company"], "security_type": found.record.subtype,
                        "category": found.record.category, "maturity": fund_row["maturity"], "years_to_maturity": years,
                        "reference": _reference(found.record.subtype, years, rates, floating=fund_row["frn"] == "Yes"),
                        "indicative": None,
                        "auction_yield": _field(None, None, None, "UNAVAILABLE"),
                        "auction_real_yield": _field(None, None, None, "UNAVAILABLE"),
                        "spread": {**no_spread, "note": "A spread to Treasuries needs this bond's current yield; "
                                                         "fund-reported values are stale and are not a price."}}
        credit = [item for item in fred.get("items", []) if item.get("group") in ("CREDIT", "CONDITIONS")]
        policy = [item for item in fred.get("items", []) if item.get("group") in ("POLICY", "INFLATION")]
        return {
            "schema_version": RATES_SCHEMA_VERSION, "universe": "BONDS", "generated_at": self._now(),
            "instrument_id": instrument_id,
            "nominal": curve(rates.nominal if rates else ()), "real": curve(rates.real if rates else ()),
            "spreads": curve_spreads(nominal), "shape": curve_shape(nominal), "breakevens": breakevens(nominal, real),
            "selected": selected,
            "policy": {"state": fred.get("state"), "reason": fred.get("reason"), "items": policy},
            "credit": {"state": fred.get("state"), "reason": fred.get("reason"), "items": credit,
                       "note": "Broad index context; never an individual bond's spread."},
            "finra": {"trace": trace_capability(), "aggregates": finra, "breadth": breadth},
            "nyfed": nyfed,
            "soma": self._soma_summary(),
            "sources": self.sources(rates, rates_error, fred=fred, finra=finra, nyfed=nyfed, breadth=breadth),
        }

    def _soma_summary(self) -> dict[str, Any]:
        soma = self._soma()
        if soma is None:
            return {"state": "NOT_CONFIGURED" if not self.enabled() else "UNAVAILABLE", "as_of": None, "counts": {}}
        return {"state": "PUBLICATION_CURRENT", "as_of": soma.as_of.isoformat(), "counts": dict(soma.counts),
                "source": SOURCE_SOMA}


def _item(item_id: str, label: str, value: Any, unit: str, klass: str, source: str | None, as_of: str | None,
          note: str | None = None) -> dict[str, Any]:
    return {"id": item_id, "label": label, "value": value, "unit": unit,
            "class": klass if value is not None else "UNAVAILABLE", "source": source, "as_of": as_of, "note": note}


def security_sections(security: TreasurySecurity, row: dict[str, Any], rates: TreasuryRates | None, *,
                      today: date, market_data: TreasuryMarketData | None = None, observed: dict[str, Any] | None = None,
                      soma: SomaHoldings | None = None, figi: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    fields, terms_as_of = row["fields"], row["fields"]["coupon"]["as_of"]
    auction = security.latest_auction
    auction_as_of = auction.auction_date.isoformat() if auction else None
    frequency = {0: "None (discount instrument)", 2: "Semiannual", 4: "Quarterly"}.get(
        -1 if security.payments_per_year is None else security.payments_per_year)
    identity = [
        _item("issuer", "Issuer", ISSUER, "text", "OBSERVED", SOURCE_AUCTIONS, terms_as_of),
        _item("cusip", "CUSIP", security.cusip, "text", "OBSERVED", security.source, terms_as_of),
        _item("isin", "ISIN", row.get("isin"), "text", "DERIVED", "IMP_DERIVED", terms_as_of,
              "Derived from the CUSIP (US prefix + check digit)"),
        _item("type", "Security type", security.kind, "text", "OBSERVED", security.source, terms_as_of),
        _item("series", "Series", security.series, "text", "OBSERVED", SOURCE_AUCTIONS, terms_as_of),
        _item("tradability", "Tradability", "Reference only", "text", "OBSERVED", "IMP_XA01", None,
              "No bond execution path exists in IMP"),
    ]
    if figi is not None:
        identity.append(_figi_item(figi))
    coupon_note = ("Bills are discount instruments; a discount rate is not a coupon" if security.kind in (BILL, CMB) else
                   f"Floating: 13-week bill index + {security.frn_spread_pct:.3f}% spread" if security.kind == FRN and security.frn_spread_pct is not None else
                   "Paid on inflation-adjusted principal" if security.kind == TIPS else None)
    terms = [
        _item("coupon", "Coupon", security.coupon_pct, "percent", "OBSERVED", SOURCE_AUCTIONS, terms_as_of, coupon_note),
        _item("frn_spread", "FRN spread", security.frn_spread_pct, "percent", "OBSERVED", SOURCE_AUCTIONS, terms_as_of)
        if security.kind == FRN else None,
        _item("frequency", "Coupon frequency", frequency, "text", "OBSERVED", SOURCE_AUCTIONS, terms_as_of),
        _item("issue", "Original issue", security.issue_date.isoformat(), "date", "OBSERVED", security.source, terms_as_of),
        _item("maturity", "Maturity", security.maturity_date.isoformat(), "date", "OBSERVED", security.source, terms_as_of),
        _item("term", "Original term", security.original_term, "text", "OBSERVED", SOURCE_AUCTIONS, terms_as_of),
        _item("years", "Years to maturity", fields["years_to_maturity"]["value"], "years", "DERIVED", "IMP_DERIVED", today.isoformat()),
        _item("days", "Days to maturity", fields["days_to_maturity"]["value"], "days", "DERIVED", "IMP_DERIVED", today.isoformat()),
        _item("par", "Price basis", "Per 100 of par", "text", "OBSERVED", "IMP", None),
        _item("outstanding", "Amount outstanding", fields["outstanding"]["value"], "USD_BILLIONS", "OBSERVED", SOURCE_MSPD,
              fields["outstanding"]["as_of"], None if fields["outstanding"]["value"] is not None else
              "Not in the latest MSPD month-end statement (issued after its record date, or MSPD unavailable)"),
    ]
    reference = _reference(security.kind, fields["years_to_maturity"]["value"], rates)
    indicative = fields["indicative_rate"]
    bills = rates.latest_bills if rates else None
    bill_quote = bills.for_cusip(security.cusip) if bills else None
    market = [
        _item("price", "Current price", None, "per_100_par", "UNAVAILABLE", None, None,
              "No permitted security-level Treasury price source is integrated"),
        _item("latest_trade", "Latest trade", None, "per_100_par", "UNAVAILABLE", "FINRA_TRACE", None,
              "FINRA TRACE security prints require a licensed feed"),
    ]
    market += observed_items(observed)
    if bill_quote is not None and bills is not None:
        market += [
            _item("closing_discount", "Closing bid · discount", bill_quote.discount_rate, "percent", "OBSERVED", RATES_SOURCE,
                  bills.date.isoformat(), f"Treasury daily bill rates, on-the-run {bill_quote.term} bill; indicative bid, not executable"),
            _item("closing_ce", "Closing bid · coupon-equivalent", indicative["value"], "percent", "OBSERVED", RATES_SOURCE,
                  bills.date.isoformat()),
        ]
    rates_items = []
    if reference["state"] == "REFERENCE":
        previous = (rates.real if reference["curve"] == REAL else rates.nominal)[-2:-1] if rates else ()
        prior = previous[0].value(reference["tenor"]) if previous else None
        rates_items += [
            _item("reference", f"{reference['tenor']} {'real' if reference['curve'] == REAL else 'nominal'} par yield",
                  reference["value"], "percent", "REFERENCE", RATES_SOURCE, reference["publication_date"],
                  "Curve point for the nearest published tenor; not this security's yield"),
            _item("reference_change", "Reference change vs prior publication",
                  round((reference["value"] - prior) * 100, 1) if prior is not None else None, "bp", "DERIVED", RATES_SOURCE,
                  reference["publication_date"]),
        ]
    else:
        rates_items.append(_item("reference", "Curve reference", None, "percent", "UNAVAILABLE", RATES_SOURCE, None,
                                 {"FRN_INDEXED_TO_13_WEEK_BILL": "FRN coupons reset to the 13-week bill; no maturity-matched reference",
                                  "OUTSIDE_CURVE_RANGE": "Maturity lies outside the published curve's tenor range",
                                  "CURVE_UNAVAILABLE": "Treasury curve publication unavailable"}.get(reference.get("reason") or "", None)))
    shape = curve_shape(rates.latest_nominal if rates else None)
    rates_items.append(_item("shape", "Curve shape (3m10y, 2s10s)", None if shape["state"] == "UNAVAILABLE" else shape["state"],
                             "state", "DERIVED", RATES_SOURCE, shape.get("publication_date"), shape["rule"]))
    benchmark = (observed or {}).get("benchmark") or {}
    if benchmark.get("spread_bp") is not None:
        rates_items += [
            _item("spread", "Spread to same-day par curve", benchmark["spread_bp"], "bp", "DERIVED", "IMP_DERIVED",
                  observed["operation_date"],
                  f"Observed-price yield minus the {observed['operation_date']} "
                  f"{'real' if benchmark['curve'] == 'REAL_PAR' else 'nominal'} par curve interpolated "
                  f"{benchmark['lower_tenor']}–{benchmark['upper_tenor']}; dated, not current"),
            _item("benchmark_par", "Interpolated par yield", benchmark["value"], "percent", "DERIVED", RATES_SOURCE,
                  benchmark["publication_date"]),
        ]
    else:
        rates_items.append(_item("spread", "Spread to benchmark", None, "bp", "UNAVAILABLE", None, None,
                                 {"NO_CURVE_ON_OPERATION_DATE": "No curve was published on the operation date",
                                  "OUTSIDE_CURVE_RANGE": "Maturity lies outside the published curve's tenor range",
                                  "FRN_FLOATING_COUPON": "Floating coupon; no fixed-rate yield to compare"}.get(
                                     benchmark.get("reason") or (observed or {}).get("reason") or "",
                                     "Needs this security's yield at an observed price; none in the last 60 days")))
    held = soma.for_cusip(security.cusip) if soma is not None else None
    holdings = [
        _item("soma_par", "Federal Reserve SOMA par held", round(held.par_value / 1e9, 3) if held and held.par_value else None,
              "USD_BILLIONS", "OBSERVED", SOURCE_SOMA, held.as_of.isoformat() if held else None,
              None if held else "Not in the latest SOMA holdings" if soma is not None else "SOMA holdings unavailable"),
        _item("soma_share", "SOMA share of issue", held.percent_outstanding if held else None, "share_percent", "OBSERVED",
              SOURCE_SOMA, held.as_of.isoformat() if held else None),
    ]
    return [
        {"id": "identity", "title": "Identity", "items": identity},
        {"id": "terms", "title": "Terms", "items": [item for item in terms if item is not None]},
        {"id": "market", "title": "Market", "items": market},
        *index_sections(security, market_data),
        {"id": "auction", "title": f"Latest auction{f' · {auction_as_of}' if auction_as_of else ''}", "items": auction_items(security)},
        {"id": "analytics", "title": "Analytics", "items": analytics_items(security, today) + observed_analytics(observed, security)},
        {"id": "holdings", "title": "Federal Reserve holdings", "items": holdings},
        {"id": "ratings", "title": "Ratings", "items": [
            _item("rating", "Credit ratings", None, "text", "UNAVAILABLE", "NRSRO", None,
                  "NRSRO ratings require a licensed feed (terms required); not scraped")]},
        {"id": "rates", "title": "Rates context", "items": rates_items},
    ]


_OBSERVED_LABELS = {"TREASURY_BUYBACK": "Treasury buyback", "FED_BILL_PURCHASE": "Fed bill purchase",
                    "FED_COUPON_PURCHASE": "Fed outright purchase"}


def observed_items(observed: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The latest dated operation price for this CUSIP: an observation on its date, never current."""

    if not observed:
        return [_item("observed_price", "Latest operation price", None, "per_100_par", "UNAVAILABLE", None, None,
                      "No Treasury buyback or Fed outright purchase accepted this CUSIP in the last 60 days")]
    day, source = observed["operation_date"], observed["source"]
    real = observed["price_basis"].startswith("REAL")
    label = _OBSERVED_LABELS.get(observed["kind"], "Operation")
    quoted = observed.get("quoted_discount_rate")
    if quoted is not None:
        # Fed bill purchases are accepted on a discount-rate basis: the rate is observed, the price follows from it.
        price_items = [
            _item("observed_rate", f"{label} discount rate", quoted, "percent", "OBSERVED", source, day,
                  f"Weighted-average accepted bank-discount rate on {day}; settles {observed['settlement_date']}. "
                  "A dated observation, not a quote"),
            _item("observed_price", f"{label} price", observed["price"], "per_100_par", "DERIVED", "IMP_DERIVED", day,
                  "From the accepted discount rate, actual/360 to maturity"),
        ]
    else:
        price_items = [
            _item("observed_price", f"{label} price{' (real, unadjusted)' if real else ''}", observed["price"], "per_100_par",
                  "OBSERVED", source, day,
                  f"Weighted-average accepted price on {day}; settles {observed['settlement_date']}. A dated observation, not a quote"),
        ]
    return [
        *price_items,
        _item("observed_par", "Par accepted", observed.get("par_accepted"), "USD", "OBSERVED", source, day),
        _item("observed_yield", "Yield at operation price" + (" (real)" if real else ""), observed.get("yield"), "percent",
              "DERIVED", "IMP_DERIVED", day,
              {"INVESTMENT_RATE": "Investment (coupon-equivalent) rate", "YTM": "Yield to maturity, 31 CFR 356 App. B",
               "REAL_YTM": "Real yield to maturity"}.get(observed.get("yield_basis") or "") if observed.get("yield") is not None
              else {"FRN_FLOATING_COUPON": "A floating-rate note has no fixed-rate yield"}.get(observed.get("reason") or "", observed.get("reason"))),
    ]


def observed_analytics(observed: dict[str, Any] | None, security: TreasurySecurity) -> list[dict[str, Any]]:
    if not observed or observed.get("yield") is None:
        return []
    day = observed["operation_date"]
    note = f"At the {day} operation price, settlement {observed['settlement_date']}; dated, not current"
    real = " (real)" if security.kind == TIPS else ""
    items = [
        _item("obs_modified", f"Modified duration at operation{real}", observed.get("modified"), "years", "DERIVED", "IMP_DERIVED", day, note),
        _item("obs_macaulay", f"Macaulay duration at operation{real}", observed.get("macaulay"), "years", "DERIVED", "IMP_DERIVED", day),
        _item("obs_dv01", f"DV01 at operation{real}", observed.get("dv01"), "per_100_par", "DERIVED", "IMP_DERIVED", day,
              "Price change per 100 par for 1 bp"),
    ]
    if observed.get("discount_rate") is not None and observed.get("quoted_discount_rate") is None:
        items.append(_item("obs_discount", "Bank-discount rate at operation", observed["discount_rate"], "percent", "DERIVED",
                           "IMP_DERIVED", day))
    if observed.get("accrued") is not None:
        items.append(_item("obs_accrued", f"Accrued at settlement{real}", observed["accrued"], "per_100_par", "DERIVED",
                           "IMP_DERIVED", observed["settlement_date"]))
    return items


def index_sections(security: TreasurySecurity, market: TreasuryMarketData | None) -> list[dict[str, Any]]:
    """TIPS index ratio and FRN daily index/accrual for this CUSIP (Treasury publications)."""

    if security.kind == TIPS:
        index = market.tips.get(security.cusip) if market else None
        as_of = index.index_date.isoformat() if index else None
        reason = None if index else ("TIPS index feed unavailable" if market is None or "TIPS_INDEX" in market.errors
                                     else "No index ratio published for this CUSIP")
        return [{"id": "inflation", "title": "Inflation indexation", "items": [
            _item("index_ratio", "Index ratio", index.index_ratio if index else None, "index", "OBSERVED", SOURCE_TIPS, as_of, reason),
            _item("ref_cpi", "Reference CPI", index.ref_cpi if index else None, "index", "OBSERVED", SOURCE_TIPS, as_of),
            _item("adjusted_principal", "Inflation-adjusted principal per 100 par",
                  round(100 * index.index_ratio, 4) if index else None, "per_100_par", "DERIVED", "IMP_DERIVED", as_of,
                  "100 × index ratio on the index date"),
        ]}]
    if security.kind == FRN:
        index = market.frn.get(security.cusip) if market else None
        as_of = index.record_date.isoformat() if index else None
        reason = None if index else ("FRN index feed unavailable" if market is None or "FRN_INDEX" in market.errors
                                     else "No daily index published for this CUSIP")
        period = (f"{index.accrual_start.isoformat()} – {index.accrual_end.isoformat()}"
                  if index and index.accrual_start and index.accrual_end else None)
        return [{"id": "floating", "title": "Floating-rate accrual", "items": [
            _item("daily_index", "Daily index (13-week bill high rate)", index.daily_index if index else None, "percent",
                  "OBSERVED", SOURCE_FRN, as_of, reason),
            _item("frn_spread_daily", "Spread", index.spread if index else None, "percent", "OBSERVED", SOURCE_FRN, as_of),
            _item("accrual_rate", "Daily accrual rate", index.accrual_rate if index else None, "percent", "OBSERVED", SOURCE_FRN, as_of,
                  "Index + spread, floored at zero"),
            _item("period_accrued", "Accrued interest this period per 100", index.period_accrued_per100 if index else None,
                  "per_100_par", "OBSERVED", SOURCE_FRN, as_of, f"Accrual period {period}" if period else None),
        ]}]
    return []


def auction_items(security: TreasurySecurity) -> list[dict[str, Any]]:
    auction = security.latest_auction
    if auction is None:
        return [_item("auction", "Auction results", None, "text", "UNAVAILABLE", SOURCE_AUCTIONS, None,
                      "No completed auction in the current dataset")]
    as_of, source = auction.auction_date.isoformat(), SOURCE_AUCTIONS
    total = auction.competitive_accepted

    def share(value: float | None) -> float | None:
        return round(value / total * 100, 2) if value is not None and total else None

    items = [
        _item("auction_date", "Auction date", as_of, "date", "OBSERVED", source, as_of),
        _item("issue_date", "Issue (settlement) date", auction.issue_date.isoformat(), "date", "OBSERVED", source, as_of),
        _item("reopening", "Reopening", "Yes" if auction.reopening else "No", "text", "OBSERVED", source, as_of),
    ]
    if security.kind in (BILL, CMB):
        items += [_item("discount", "High discount rate", auction.high_discount_rate, "percent", "OBSERVED", source, as_of),
                  _item("investment", "High investment rate", auction.high_investment_rate, "percent", "OBSERVED", source, as_of,
                        "Coupon-equivalent yield at the auction")]
    elif security.kind == FRN:
        items += [_item("margin", "High discount margin", auction.high_discount_margin, "percent", "OBSERVED", source, as_of),
                  _item("index", "Index rate at determination", auction.frn_index_rate, "percent", "OBSERVED", source, as_of)]
    else:
        items.append(_item("high_yield", "High yield (real)" if security.kind == TIPS else "High yield",
                           auction.high_yield, "percent", "OBSERVED", source, as_of))
    if security.kind == TIPS:
        items += [_item("unadjusted_price", "Price (unadjusted, real)", auction.unadjusted_price, "per_100_par", "OBSERVED", source, as_of),
                  _item("adjusted_price", "Price (inflation-adjusted)", auction.high_price, "per_100_par", "OBSERVED", source, as_of,
                        "Unadjusted price × index ratio"),
                  _item("index_ratio", "Index ratio on issue date", auction.index_ratio_on_issue_date, "index", "OBSERVED", source, as_of),
                  _item("ref_cpi", "Reference CPI on issue date", auction.ref_cpi_on_issue_date, "index", "OBSERVED", source, as_of)]
    else:
        items.append(_item("price", "Price", auction.high_price, "per_100_par", "OBSERVED", source, as_of))
    items += [
        _item("bid_to_cover", "Bid-to-cover", auction.bid_to_cover, "ratio", "OBSERVED", source, as_of,
              "An auction fact; not a directional signal"),
        _item("offering", "Offering amount", auction.offering_amount, "USD", "OBSERVED", source, as_of),
        _item("direct", "Direct bidders (share of competitive accepted)", share(auction.direct_bidder_accepted), "share_percent", "DERIVED", source, as_of),
        _item("indirect", "Indirect bidders (share of competitive accepted)", share(auction.indirect_bidder_accepted), "share_percent", "DERIVED", source, as_of),
        _item("dealers", "Primary dealers (share of competitive accepted)", share(auction.primary_dealer_accepted), "share_percent", "DERIVED", source, as_of),
    ]
    return items


def analytics_items(security: TreasurySecurity, today: date) -> list[dict[str, Any]]:
    """Deterministic analytics whose inputs exist; everything else says why not."""

    today_iso = today.isoformat()
    if security.kind in (BILL, CMB):
        days = days_to_maturity(security.maturity_date, today)
        return [_item("macaulay", "Macaulay duration (zero coupon = time to maturity)",
                      round(analytics.bill_macaulay_years(days, today), 4) if days > 0 else None, "years", "DERIVED", "IMP_DERIVED", today_iso),
                _item("modified", "Modified duration / DV01", None, "years", "UNAVAILABLE", None, None,
                      "Needs a current bill yield")]
    if security.kind == FRN:
        return [_item("duration", "Duration / DV01", None, "years", "UNAVAILABLE", None, None,
                      "Fixed-rate duration is not applied to a floating-rate note")]
    items: list[dict[str, Any]] = []
    real = " (real)" if security.kind == TIPS else ""
    try:
        period = analytics.coupon_period(today, security.maturity_date, security.payments_per_year or 2)
        accrued = analytics.accrued_interest(security.coupon_pct, security.payments_per_year, today, security.maturity_date,
                                             dated_date=security.dated_date)
        items += [
            _item("accrued", f"Accrued interest today{real}", round(accrued, 6), "per_100_par", "DERIVED", "IMP_DERIVED", today_iso,
                  "Actual/actual in period, to today's date (settlement lag not applied)" +
                  ("; on unadjusted principal" if security.kind == TIPS else "")),
            _item("next_coupon", "Next coupon date", period.next.isoformat(), "date", "DERIVED", "IMP_DERIVED", today_iso),
            _item("coupons_left", "Coupons remaining", float(len(period.remaining)), "count", "DERIVED", "IMP_DERIVED", today_iso),
        ]
    except analytics.FixedIncomeMathError as exc:
        items.append(_item("accrued", "Accrued interest", None, "per_100_par", "UNAVAILABLE", None, None, exc.code))
    auction = security.latest_auction
    if auction is not None and auction.high_yield is not None:
        as_of = auction.auction_date.isoformat()
        try:
            result = analytics.fixed_coupon_analytics(auction.high_yield, security.coupon_pct, security.payments_per_year,
                                                      auction.issue_date, security.maturity_date, dated_date=security.dated_date)
            note = f"At the {as_of} auction yield{real}, issue-date settlement; not a current market measure"
            items += [
                _item("modified", f"Modified duration at auction{real}", round(result.modified_duration, 4), "years", "DERIVED", "IMP_DERIVED", as_of, note),
                _item("macaulay", f"Macaulay duration at auction{real}", round(result.macaulay_years, 4), "years", "DERIVED", "IMP_DERIVED", as_of, note),
                _item("dv01", f"DV01 at auction{real}", round(result.dv01, 5), "per_100_par", "DERIVED", "IMP_DERIVED", as_of,
                      "Price change per 100 par for 1 bp"),
            ]
        except analytics.FixedIncomeMathError as exc:
            items.append(_item("modified", "Duration at auction", None, "years", "UNAVAILABLE", None, None, exc.code))
    items.append(_item("ytm", "Yield to maturity (current)", None, "percent", "UNAVAILABLE", None, None,
                       "Needs a current security price"))
    return items


_SERVICE: BondScreener | None = None
_SERVICE_LOCK = threading.Lock()


def bond_screener_service() -> BondScreener:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = BondScreener()
    return _SERVICE
