"""Bonds / Fixed Income universe for the Main Screener (S9).

Rows are outstanding U.S. Treasury marketable securities from the official
Treasury Fiscal Data catalog. Every row carries its CUSIP-keyed XA-01
sovereign identity and is REFERENCE_ONLY: nothing here reaches execution.

Each value keeps its own clock and class:

- terms: Treasury reference data (event clock of the auction dataset);
- auction facts: the named auction's published results;
- amount outstanding: the MSPD month-end record date;
- curve reference: the Treasury par curve for the nearest published tenor on
  one publication date — a benchmark, never the security's yield;
- on-the-run bill closing bids: Treasury's daily bill rates, attached only to
  the CUSIP the feed names;
- derived analytics: deterministic formulas on those inputs, labeled DERIVED.

No security-level current price, yield to maturity, spread, trade, rating, or
credit field exists, because no permitted universe-wide source supplies one.
Corporate and agency coverage is reported as unavailable, never invented.

Treasury sources are opt-in with ``IMP_TREASURY_LIVE=1`` (the same pattern
as the other ``IMP_*_LIVE`` public sources); fixtures never enter this path.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from datetime import UTC, date, datetime
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

from ..fixed_income import analytics
from ..fixed_income.finra_fixed_income import load_treasury_aggregates, trace_capability
from ..fixed_income.fred_context import load_fred_context
from ..fixed_income.http import failure_code
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
from .screener_filters import apply_filters, field_value
from .screener_query import ScreenerQuery, order_rows, page_payload

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
SEARCH_KEYS = ("symbol", "company", "issuer", "security_type", "maturity", "term", "series")
MARKET_SESSION = "PUBLICATION_BASED"
_NUMBERS = ("coupon", "years_to_maturity", "days_to_maturity", "maturity_year", "outstanding", "auction_yield",
            "auction_real_yield", "auction_discount_margin", "bid_to_cover", "reference_rate", "indicative_rate")
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
    }
    return {
        "instrument": {"instrument_id": canonical_treasury_id(security), "venue_id": VENUE,
                       "asset_class": XaAssetClass.SOVEREIGN_DEBT.value,
                       "instrument_kind": InstrumentKind.SOVEREIGN_SECURITY.value, "tradability": "REFERENCE_ONLY"},
        # CUSIP is the identity shown in the pinned column; it is never a ticker.
        "symbol": security.cusip, "company": security.description, "sector": None, "industry": None,
        "country": "USA", "earnings_date": None, "recommendation": None, "exchange": None,
        "cusip": security.cusip, "isin": None, "identity_source": "CUSIP", "issuer": ISSUER,
        "security_type": security.kind, "term": security.original_term, "issue_date": security.issue_date.isoformat(),
        "maturity": security.maturity_date.isoformat(), "maturity_bucket": maturity_bucket(years),
        "tips": "Yes" if security.tips else "No", "frn": "Yes" if security.frn else "No",
        "callable": None if security.callable is None else "Yes" if security.callable else "No",
        "auction_date": auction_as_of, "series": security.series,
        "reference_tenor": None, "reference_date": None, "reference_reason": None,
        "fields": fields,
    }


def _reference(security_kind: str, years: float, rates: TreasuryRates | None) -> dict[str, Any]:
    if security_kind == FRN:
        return {"state": "UNAVAILABLE", "reason": "FRN_INDEXED_TO_13_WEEK_BILL"}
    publication = (rates.latest_real if security_kind == TIPS else rates.latest_nominal) if rates else None
    return match_reference(years, publication)


def with_rates(row: dict[str, Any], rates: TreasuryRates | None) -> dict[str, Any]:
    """A page row carrying the publication context current at response time."""

    years = row["fields"]["years_to_maturity"]["value"]
    reference = _reference(row["security_type"], years, rates)
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
    quote = bills.for_cusip(row["cusip"]) if bills else None
    if quote is not None and quote.coupon_equivalent is not None:
        fields["indicative_rate"] = _field(quote.coupon_equivalent, RATES_SOURCE, bills.date.isoformat(), "PUBLICATION",
                                           "CLOSING_BID_COUPON_EQUIVALENT")
    return decorated


class BondScreener:
    def __init__(self, *, env: Mapping[str, str] = os.environ,
                 catalog_loader: Callable[..., TreasuryCatalog] = load_treasury_catalog,
                 rates_loader: Callable[..., TreasuryRates] = fetch_rates,
                 fred_loader: Callable[..., dict[str, Any]] = load_fred_context,
                 finra_loader: Callable[..., dict[str, Any]] = load_treasury_aggregates,
                 clock: Callable[[], float] = time.monotonic,
                 today: Callable[[], date] = lambda: datetime.now(ET).date(),
                 now: Callable[[], str] = _now) -> None:
        self._env, self._clock, self._today, self._now = env, clock, today, now
        self._catalog_loader, self._rates_loader = catalog_loader, rates_loader
        self._fred_loader, self._finra_loader = fred_loader, finra_loader
        self._lock = threading.RLock()
        self._catalog_entry: tuple[float, TreasuryCatalog | None, str | None] | None = None
        self._rates_entry: tuple[float, TreasuryRates | None, str | None] | None = None
        self._context: dict[str, tuple[float, dict[str, Any]]] = {}
        self._projected: OrderedDict[tuple[str, date], list[dict[str, Any]]] = OrderedDict()
        self._ordered: OrderedDict[tuple[Any, ...], list[dict[str, Any]]] = OrderedDict()
        self.catalog_loads = 0
        self.rates_loads = 0

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

    def _cached_context(self, key: str, loader: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            cached = self._context.get(key)
            if cached and self._clock() - cached[0] < CONTEXT_TTL_S:
                return cached[1]
        try:
            value = loader()
        except Exception as exc:  # noqa: BLE001
            value = {"state": "UNAVAILABLE", "reason": failure_code(exc), "items": [], "rows": []}
        with self._lock:
            self._context[key] = (self._clock(), value)
        return value

    def _rows(self, catalog: TreasuryCatalog | None) -> list[dict[str, Any]]:
        if catalog is None:
            return []
        today = self._today()
        key = (catalog.fetched_at, today)
        with self._lock:
            rows = self._projected.get(key)
            if rows is None:
                # Outstanding is re-validated whenever the date changes: a matured security leaves.
                rows = [project_row(security, today=today, catalog=catalog) for security in catalog.outstanding(today)]
                self._projected[key] = rows
                while len(self._projected) > RETAINED_PROJECTIONS:
                    self._projected.popitem(last=False)
            return rows

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

    # ------------------------------------------------------------ Screener
    def read(self, query: ScreenerQuery, *, force_refresh: bool = False) -> dict[str, Any]:
        if query.result_set is not None:
            with self._lock:
                pinned = next((rows for (fetched, day), rows in self._projected.items()
                               if fetched == query.result_set and day == self._today()), None)
            if pinned is None:
                raise ValueError("RESULT_SET_CHANGED")
            catalog, error = (self._catalog_entry[1] if self._catalog_entry else None), None
            rows, as_of = pinned, query.result_set
        else:
            catalog, error = self._catalog(force=force_refresh)
            rows = self._rows(catalog)
            as_of = catalog.fetched_at if catalog else None
        rates, rates_error = self._rates() if rows else (None, None)
        treasury = len(rows)
        envelope = {
            "schema_version": SCHEMA_VERSION, "universe": query.universe, "generated_at": self._now(),
            "market_session": MARKET_SESSION, "universe_as_of": as_of, "screener_as_of": as_of,
            "evaluation": "CATALOG", "snapshot": None, "unfiltered_count": treasury,
            "provider_health": self._health(catalog, error, rates, rates_error, rows),
            # Counts per category; unavailable categories are never folded into a total.
            "coverage": {"TREASURY": {"state": "CURRENT" if rows else "UNAVAILABLE", "count": treasury if rows else None},
                         "CORPORATE": {"state": "CORPORATE_COVERAGE_UNAVAILABLE", "count": None},
                         "AGENCY": {"state": "UNAVAILABLE", "count": None}},
        }
        if not rows:
            return {**envelope, "result_set_id": None, "source_error": error or "TREASURY_CATALOG_UNAVAILABLE",
                    **page_payload(query, [])}
        key = (as_of, self._today(), query.identity)
        with self._lock:
            ordered = self._ordered.get(key)
        if ordered is None:
            needle = query.search.casefold()
            matched = [row for row in apply_filters(rows, list(query.filters))
                       if not needle or any(needle in str(row.get(name) or "").casefold() for name in SEARCH_KEYS)]
            ordered = order_rows(matched, query.sort, query.descending, field_value)
            with self._lock:
                self._ordered[key] = ordered
                while len(self._ordered) > RESULT_CACHE_ENTRIES:
                    self._ordered.popitem(last=False)
        page = page_payload(query, ordered)
        page["rows"] = [with_rates(row, rates) for row in page["rows"]]
        return {**envelope, "result_set_id": as_of, "source_error": None, **page}

    def row_for(self, instrument_id: str) -> tuple[dict[str, Any] | None, str | None]:
        catalog, error = self._catalog()
        row = next((row for row in self._rows(catalog) if row["instrument"]["instrument_id"] == instrument_id), None)
        return row, error

    def window(self, symbols: list[str]) -> dict[str, Any]:
        """Bonds have no streaming quotes; the window reports that per row."""

        return {"schema_version": SCHEMA_VERSION, "generated_at": self._now(), "market_session": MARKET_SESSION,
                "active": 0, "cap": 0,
                "quotes": {symbol: {"state": "UNAVAILABLE", "reason": "NO_STREAMING_BOND_QUOTES", "fields": {}}
                           for symbol in symbols}}

    # ------------------------------------------------------------ context
    def _security(self, instrument_id: str) -> tuple[TreasurySecurity | None, dict[str, Any] | None]:
        catalog, _error = self._catalog()
        if catalog is None:
            return None, None
        row = next((row for row in self._rows(catalog) if row["instrument"]["instrument_id"] == instrument_id), None)
        if row is None:
            return None, None
        return next(item for item in catalog.securities if item.cusip == row["cusip"]), row

    def _fred(self) -> dict[str, Any]:
        return self._cached_context("fred", lambda: self._fred_loader(today=self._today(), retrieved=self._now()))

    def _finra(self) -> dict[str, Any]:
        return self._cached_context("finra", lambda: self._finra_loader(today=self._today(), env=self._env))

    def sources(self, rates: TreasuryRates | None, rates_error: str | None, *, fred: dict[str, Any] | None = None,
                finra: dict[str, Any] | None = None) -> list[dict[str, Any]]:
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
        return items

    def preview(self, instrument_id: str, rules: list[dict[str, Any]]) -> dict[str, Any] | None:
        from .screener_preview import explain_matches

        security, row = self._security(instrument_id)
        if security is None or row is None:
            return None
        today = self._today()
        rates, rates_error = self._rates()
        decorated = with_rates(row, rates)
        return {
            "schema_version": PREVIEW_SCHEMA_VERSION, "universe": "BONDS", "generated_at": self._now(),
            "market_session": MARKET_SESSION,
            "instrument": {**row["instrument"], "cusip": security.cusip, "isin": None, "identity_source": "CUSIP",
                           "issuer": ISSUER, "description": security.description, "security_type": security.kind,
                           "series": security.series},
            "sections": security_sections(security, decorated, rates, today=today),
            "why": {"matched": explain_matches(row, rules, universe="BONDS")},
            "sources": self.sources(rates, rates_error),
            "capabilities": [{"panel": panel, "state": state, "reason": reason} for panel, state, reason in CAPABILITIES],
        }

    def rates_curve(self, instrument_id: str | None) -> dict[str, Any] | None:
        security, row = self._security(instrument_id) if instrument_id else (None, None)
        if instrument_id and security is None:
            return None
        today = self._today()
        rates, rates_error = self._rates()
        fred = self._fred()
        finra = self._finra()
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

        selected = None
        if security is not None and row is not None:
            decorated = with_rates(row, rates)
            selected = {"instrument_id": row["instrument"]["instrument_id"], "cusip": security.cusip,
                        "description": security.description, "security_type": security.kind,
                        "maturity": row["maturity"], "years_to_maturity": row["fields"]["years_to_maturity"]["value"],
                        "reference": _reference(security.kind, row["fields"]["years_to_maturity"]["value"], rates),
                        "indicative": decorated["fields"]["indicative_rate"] if decorated["fields"]["indicative_rate"]["value"] is not None else None,
                        "auction_yield": row["fields"]["auction_yield"], "auction_real_yield": row["fields"]["auction_real_yield"],
                        "spread": {"state": "UNAVAILABLE", "reason": "NO_CURRENT_SECURITY_YIELD",
                                   "note": "A spread needs this security's current yield; the auction yield and the curve have different clocks."}}
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
            "finra": {"trace": trace_capability(), "aggregates": finra},
            "sources": self.sources(rates, rates_error, fred=fred, finra=finra),
        }


def _item(item_id: str, label: str, value: Any, unit: str, klass: str, source: str | None, as_of: str | None,
          note: str | None = None) -> dict[str, Any]:
    return {"id": item_id, "label": label, "value": value, "unit": unit,
            "class": klass if value is not None else "UNAVAILABLE", "source": source, "as_of": as_of, "note": note}


def security_sections(security: TreasurySecurity, row: dict[str, Any], rates: TreasuryRates | None, *,
                      today: date) -> list[dict[str, Any]]:
    fields, terms_as_of = row["fields"], row["fields"]["coupon"]["as_of"]
    auction = security.latest_auction
    auction_as_of = auction.auction_date.isoformat() if auction else None
    frequency = {0: "None (discount instrument)", 2: "Semiannual", 4: "Quarterly"}.get(
        -1 if security.payments_per_year is None else security.payments_per_year)
    identity = [
        _item("issuer", "Issuer", ISSUER, "text", "OBSERVED", SOURCE_AUCTIONS, terms_as_of),
        _item("cusip", "CUSIP", security.cusip, "text", "OBSERVED", security.source, terms_as_of),
        _item("isin", "ISIN", None, "text", "OBSERVED", None, None, "Not published in this source"),
        _item("type", "Security type", security.kind, "text", "OBSERVED", security.source, terms_as_of),
        _item("series", "Series", security.series, "text", "OBSERVED", SOURCE_AUCTIONS, terms_as_of),
        _item("tradability", "Tradability", "Reference only", "text", "OBSERVED", "IMP_XA01", None,
              "No bond execution path exists in IMP"),
    ]
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
    rates_items.append(_item("spread", "Spread to benchmark", None, "bp", "UNAVAILABLE", None, None,
                             "Needs this security's current yield, which no permitted source supplies"))
    return [
        {"id": "identity", "title": "Identity", "items": identity},
        {"id": "terms", "title": "Terms", "items": [item for item in terms if item is not None]},
        {"id": "market", "title": "Market", "items": market},
        {"id": "auction", "title": f"Latest auction{f' · {auction_as_of}' if auction_as_of else ''}", "items": auction_items(security)},
        {"id": "analytics", "title": "Analytics", "items": analytics_items(security, today)},
        {"id": "rates", "title": "Rates context", "items": rates_items},
    ]


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
