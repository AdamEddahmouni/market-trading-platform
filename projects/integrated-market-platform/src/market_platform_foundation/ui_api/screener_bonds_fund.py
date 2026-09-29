"""Corporate, agency, municipal, and securitized rows for the BONDS universe (S16).

Rows come from the SEC Form N-PORT reference catalog (``fixed_income.nport_catalog``):
CUSIPs that SEC-registered funds reported holding, with reconciled terms. They are
categories inside the one BONDS universe and go through the same canonical query
(``apply_filters`` / ``order_rows`` / ``page_payload``) as Treasury rows.

~320k rows cannot each be a Treasury-style dict (each carries a field-envelope map),
so a ``FundHeldRow`` is a slotted view over one frozen ``NportRecord`` that answers
the exact access paths the canonical query uses — ``row.get(name)``,
``row["instrument"]["instrument_id"]``, ``row["fields"][name]["value"]`` — and turns
into a full page row (``to_dict``) only for the rows a page returns.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..fixed_income.nport_catalog import SOURCE as NPORT_SOURCE, NportRecord
from ..fixed_income.treasury_catalog import DAYS_PER_YEAR, format_coupon, maturity_bucket
from ..xa01.enums import InstrumentKind, XaAssetClass

VENUE = "US_OTC_FIXED_INCOME"
STATE_REFERENCE = "FUND_REPORTED_REFERENCE"
STATE_STALE = "FUND_REPORTED_STALE"
#: Numeric fields every BONDS row carries in its ``fields`` map (Treasury-only ones stay null here).
NUMBER_FIELDS = ("coupon", "years_to_maturity", "days_to_maturity", "maturity_year", "outstanding", "auction_yield",
                 "auction_real_yield", "auction_discount_margin", "bid_to_cover", "reference_rate", "indicative_rate",
                 "fund_count", "fund_par_held", "fund_value_pct", "observed_price", "observed_yield", "benchmark_spread")
_YES_NO = {True: "Yes", False: "No"}


def _envelope(value: float | None, source: str | None, as_of: str | None, state: str, basis: str | None = None) -> dict[str, Any]:
    envelope: dict[str, Any] = {"value": value, "source": source if value is not None else (source or "NONE"),
                                "state": state if value is not None else "UNAVAILABLE",
                                "as_of": as_of if value is not None else None}
    if basis:
        envelope["basis"] = basis
    return envelope


class _FieldsView:
    """``row["fields"]`` for a fund-held row: membership and ``[name]["value"]`` only."""

    __slots__ = ("_row",)

    def __init__(self, row: "FundHeldRow") -> None:
        self._row = row

    def __contains__(self, name: object) -> bool:
        return name in _NUMBERS

    def __getitem__(self, name: str) -> dict[str, Any]:
        return {"value": _NUMBERS[name](self._row)}

    def get(self, name: str, default: Any = None) -> Any:
        return self[name] if name in _NUMBERS else default


class FundHeldRow:
    __slots__ = ("record", "maturity", "years", "days", "bucket", "haystack")

    def __init__(self, record: NportRecord, today: date) -> None:
        self.record = record
        self.maturity = record.maturity.isoformat()
        self.days = (record.maturity - today).days
        self.years = round(self.days / DAYS_PER_YEAR, 4)
        self.bucket = maturity_bucket(self.years)
        self.haystack = "\x1f".join(part for part in (record.cusip, record.title, record.issuer, record.subtype,
                                                      record.category, self.maturity, record.isin) if part).casefold()

    # canonical-query access paths
    def get(self, name: str, default: Any = None) -> Any:
        getter = _TEXT.get(name)
        if getter is not None:
            return getter(self)
        if name == "fields":
            return _FieldsView(self)
        if name == "instrument":
            return self.instrument
        return default

    def __getitem__(self, name: str) -> Any:
        value = self.get(name, _MISSING)
        if value is _MISSING:
            raise KeyError(name)
        return value

    def __contains__(self, name: object) -> bool:
        return name in _TEXT or name in ("fields", "instrument")

    @property
    def instrument(self) -> dict[str, Any]:
        return {"instrument_id": self.record.instrument_id, "venue_id": VENUE, "asset_class": XaAssetClass.BOND.value,
                "instrument_kind": InstrumentKind.BOND.value, "tradability": "REFERENCE_ONLY"}

    def to_dict(self) -> dict[str, Any]:
        """The full page row (same shape as a Treasury row)."""

        record = self.record
        report = record.report_date_max
        fields = {name: _envelope(None, None, None, "UNAVAILABLE") for name in NUMBER_FIELDS}
        fields.update({
            "coupon": _envelope(record.coupon, NPORT_SOURCE, report, STATE_REFERENCE,
                                "ZERO_COUPON" if record.coupon_state == "ZERO_COUPON" else "FUND_REPORTED_CONSENSUS"),
            "years_to_maturity": _envelope(self.years, "IMP_DERIVED", None, "DERIVED"),
            "days_to_maturity": _envelope(float(self.days), "IMP_DERIVED", None, "DERIVED"),
            "maturity_year": _envelope(float(record.maturity.year), NPORT_SOURCE, report, STATE_REFERENCE),
            "fund_count": _envelope(float(record.fund_count), NPORT_SOURCE, report, STATE_REFERENCE, "REPORTING_FUND_SERIES"),
            "fund_par_held": _envelope(_millions(record.par_held), NPORT_SOURCE, report, STATE_REFERENCE, "SUM_OF_REPORTED_PRINCIPAL_USD_MILLIONS"),
            "fund_value_pct": _envelope(record.value_pct_par, NPORT_SOURCE, report, STATE_STALE, "MEDIAN_FUND_FAIR_VALUE_PCT_OF_PAR"),
        })
        return {
            "instrument": self.instrument,
            "symbol": record.cusip, "company": self.get("company"), "sector": None, "industry": None,
            "country": record.country, "earnings_date": None, "recommendation": None, "exchange": None,
            "cusip": record.cusip, "isin": record.isin, "isin_source": record.isin_source, "identity_source": "CUSIP",
            "issuer": record.issuer, "category": record.category, "security_type": record.subtype, "term": None,
            "issue_date": None, "maturity": self.maturity, "maturity_bucket": self.bucket, "tips": "No",
            "frn": self.get("frn"), "callable": None, "coupon_type": self.get("coupon_type"),
            "in_default": _YES_NO[record.in_default], "convertible": _YES_NO[record.convertible], "pik": _YES_NO[record.pik],
            "auction_date": None, "series": None, "report_date": report, "reference_tenor": None, "reference_date": None,
            "reference_reason": None, "observed_date": None, "fields": fields,
        }


_MISSING = object()


def _millions(value: float | None) -> float | None:
    return round(value / 1e6, 3) if value else None


def _coupon_type(record: NportRecord) -> str:
    return {"None": "Zero coupon", "Fixed": "Fixed", "Floating": "Floating", "Variable": "Variable"}.get(
        record.coupon_type, record.coupon_type)


def description(record: NportRecord) -> str:
    """Title as reported, else issuer + coupon + maturity (never invented terms)."""

    if record.title:
        return record.title
    coupon = f" {format_coupon(record.coupon)}%" if record.coupon is not None else ""
    return f"{record.issuer or record.cusip}{coupon} {record.maturity:%b %Y}"


_TEXT: dict[str, Any] = {
    "symbol": lambda row: row.record.cusip, "cusip": lambda row: row.record.cusip,
    "company": lambda row: description(row.record), "issuer": lambda row: row.record.issuer,
    "category": lambda row: row.record.category, "security_type": lambda row: row.record.subtype,
    "isin": lambda row: row.record.isin, "maturity": lambda row: row.maturity,
    "maturity_bucket": lambda row: row.bucket, "coupon_type": lambda row: _coupon_type(row.record),
    "tips": lambda row: "No", "frn": lambda row: "Yes" if row.record.coupon_type == "Floating" else "No",
    "callable": lambda row: None, "in_default": lambda row: _YES_NO[row.record.in_default],
    "convertible": lambda row: _YES_NO[row.record.convertible], "pik": lambda row: _YES_NO[row.record.pik],
    "country": lambda row: row.record.country, "report_date": lambda row: row.record.report_date_max,
    "term": lambda row: None, "issue_date": lambda row: None, "auction_date": lambda row: None,
    "series": lambda row: None, "observed_date": lambda row: None, "reference_tenor": lambda row: None,
}
_NUMBERS: dict[str, Any] = {
    "coupon": lambda row: row.record.coupon, "years_to_maturity": lambda row: row.years,
    "days_to_maturity": lambda row: float(row.days), "maturity_year": lambda row: float(row.record.maturity.year),
    "fund_count": lambda row: float(row.record.fund_count), "fund_par_held": lambda row: _millions(row.record.par_held),
    "fund_value_pct": lambda row: row.record.value_pct_par,
    **{name: (lambda row: None) for name in ("outstanding", "auction_yield", "auction_real_yield", "auction_discount_margin",
                                             "bid_to_cover", "reference_rate", "indicative_rate", "observed_price",
                                             "observed_yield", "benchmark_spread")},
}


def to_page_row(row: Any) -> dict[str, Any]:
    return row.to_dict() if isinstance(row, FundHeldRow) else row


def haystack(row: Any, keys: tuple[str, ...]) -> str:
    if isinstance(row, FundHeldRow):
        return row.haystack
    return "\x1f".join(str(row.get(name) or "") for name in keys).casefold()


# ---------------------------------------------------------------- Quick Preview
_COUPON_NOTES = {
    "CONSENSUS": "Reported by the holding funds and agreeing across filings",
    "ZERO_COUPON": "Reported as a zero-coupon security",
    "COUPON_CONFLICT": "Holding funds report different coupons; none is shown",
    "AMBIGUOUS_RATE_ENCODING": "A single filer's rate could be a fraction or a percent and the title does not settle it",
    "COUPON_TYPE_CONFLICT": "Holding funds disagree on fixed vs floating; none is shown",
    "NOT_FIXED": "Floating or variable coupon; the rate resets and no current rate is published here",
    "NO_FIXED_RATE_REPORTED": "No annualized rate was reported",
}
_REFERENCE_REASONS = {
    "FLOATING_RATE_NO_MATURITY_MATCH": "Floating coupon; no maturity-matched fixed reference",
    "OUTSIDE_CURVE_RANGE": "Maturity lies outside the published curve's tenor range",
    "CURVE_UNAVAILABLE": "Treasury curve publication unavailable",
}


def _item(item_id: str, label: str, value: Any, unit: str, klass: str, source: str | None, as_of: str | None,
          note: str | None = None) -> dict[str, Any]:
    return {"id": item_id, "label": label, "value": value, "unit": unit,
            "class": klass if value is not None else "UNAVAILABLE", "source": source, "as_of": as_of, "note": note}


def _figi_item(figi: dict[str, Any]) -> dict[str, Any]:
    match = (figi.get("items") or [None])[0]
    if match:
        kind = match.get("security_type2") or match.get("security_type") or ""
        note = " · ".join(part for part in (match.get("name"), kind) if part) or None
    else:
        note = "OpenFIGI lookup is off (IMP_OPENFIGI_LIVE)" if figi.get("state") == "NOT_CONFIGURED" else figi.get("reason")
    return _item("figi", "FIGI", match.get("figi") if match else None, "text", "OBSERVED", "OPENFIGI", None, note)


def fund_sections(record: NportRecord, row: dict[str, Any], *, today: date, soma: Any = None,
                  figi: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Preview sections for a fund-held row. ``row`` is the page row after ``with_rates``."""

    report, source, today_iso = record.report_date_max, NPORT_SOURCE, today.isoformat()
    fields = row["fields"]
    derived_isin = record.isin_source == "DERIVED"
    identity = [
        _item("issuer", "Issuer (as reported)", record.issuer, "text", "OBSERVED", source, report),
        _item("title", "Title (as reported)", record.title, "text", "OBSERVED", source, report),
        _item("cusip", "CUSIP", record.cusip, "text", "OBSERVED", source, report),
        _item("isin", "ISIN", record.isin, "text", "DERIVED" if derived_isin else "OBSERVED",
              "IMP_DERIVED" if derived_isin else source, report,
              "Derived from the CUSIP (US prefix + check digit)" if derived_isin else None),
        _item("lei", "Issuer LEI", record.issuer_lei, "text", "OBSERVED", source, report),
        _item("category", "Category", record.category, "text", "OBSERVED", source, report),
        _item("subtype", "Asset type", record.subtype, "text", "OBSERVED", source, report),
        _item("country", "Issuer country", record.country, "text", "OBSERVED", source, report),
        _item("tradability", "Tradability", "Reference only", "text", "OBSERVED", "IMP_XA01", None,
              "No bond execution path exists in IMP"),
    ]
    if figi is not None:
        identity.append(_figi_item(figi))
    terms = [
        _item("coupon", "Coupon", record.coupon, "percent", "OBSERVED", source, report, _COUPON_NOTES.get(record.coupon_state)),
        _item("coupon_type", "Coupon type", _coupon_type(record), "text", "OBSERVED", source, report),
        _item("reported_rate", "Rate reported at the report date", record.reported_rate, "percent", "OBSERVED", source, report,
              "The annualized rate in force on the fund's report date; not a current rate")
        if record.coupon_type != "Fixed" and record.reported_rate is not None else None,
        _item("maturity", "Maturity", record.maturity.isoformat(), "date", "OBSERVED", source, report),
        _item("years", "Years to maturity", fields["years_to_maturity"]["value"], "years", "DERIVED", "IMP_DERIVED", today_iso),
        _item("days", "Days to maturity", fields["days_to_maturity"]["value"], "days", "DERIVED", "IMP_DERIVED", today_iso),
        _item("in_default", "In default (as reported)", _YES_NO[record.in_default], "text", "OBSERVED", source, report),
        _item("pik", "Paid in kind", _YES_NO[record.pik], "text", "OBSERVED", source, report),
        _item("convertible", "Convertible", _YES_NO[record.convertible], "text", "OBSERVED", source, report),
        _item("frequency", "Coupon frequency", None, "text", "UNAVAILABLE", None, None, "Not reported in Form N-PORT"),
        _item("call", "Call / put schedule", None, "text", "UNAVAILABLE", None, None, "Not reported in Form N-PORT"),
        _item("outstanding", "Amount outstanding", None, "USD", "UNAVAILABLE", None, None,
              "No permitted issue-size source is integrated"),
    ]
    municipal = record.category == "Municipal"
    market = [
        _item("price", "Current price", None, "per_100_par", "UNAVAILABLE", None, None,
              "No permitted security-level price source is integrated"),
        _item("latest_trade", "Latest trade", None, "per_100_par", "UNAVAILABLE", "MSRB_EMMA" if municipal else "FINRA_TRACE", None,
              "MSRB EMMA trade data is not licensed for redistribution; not scraped" if municipal
              else "FINRA TRACE security prints require a licensed feed"),
        _item("fund_value", "Fund fair value (median, % of par)", record.value_pct_par, "per_100_par", "STALE", source, report,
              f"The funds' own valuations at their report dates ({record.value_count} line(s)); up to months old, never a quote"),
    ]
    held = soma.for_cusip(record.cusip) if soma is not None else None
    holdings = [
        _item("fund_count", "Reporting fund series", float(record.fund_count), "count", "OBSERVED", source, report),
        _item("par_held", "Principal reported held (sum)", _millions(record.par_held), "USD_MILLIONS", "OBSERVED", source, report,
              "Summed over each reporting fund's latest filing; not the amount outstanding"),
        _item("report_window", "Report dates", f"{record.report_date_min} … {record.report_date_max}", "text", "OBSERVED",
              source, report),
        _item("filed", "Latest filing date", record.filing_date_max, "date", "OBSERVED", source, record.filing_date_max,
              "Form N-PORT holdings become public about 60 days after the report date"),
        _item("soma", "Federal Reserve SOMA par held", _millions(held.par_value) if held else None, "USD_MILLIONS", "OBSERVED",
              "NY_FED_SOMA_HOLDINGS", held.as_of.isoformat() if held else None,
              None if held else "Not in the latest SOMA holdings" if soma is not None else "SOMA holdings unavailable"),
    ]
    analytics_items = [
        _item(item_id, label, None, unit, "UNAVAILABLE", None, None, note) for item_id, label, unit, note in (
            ("ytm", "Yield to maturity (current)", "percent", "Needs a current security price"),
            ("duration", "Modified duration / DV01", "years", "Needs a yield, the coupon schedule, and call terms"),
            ("accrued", "Accrued interest", "per_100_par", "Needs the coupon frequency and dated date, which N-PORT does not report"),
        )
    ]
    reference = fields.get("reference_rate") or {}
    has_reference = reference.get("value") is not None
    rates_items = [
        _item("reference", f"{row.get('reference_tenor')} Treasury par yield" if has_reference else "Treasury curve reference",
              reference.get("value"), "percent", "REFERENCE", reference.get("source"), reference.get("as_of"),
              "Treasury curve point nearest this maturity; not this security's yield" if has_reference
              else _REFERENCE_REASONS.get(row.get("reference_reason") or "")),
        _item("spread", "Spread to Treasury", None, "bp", "UNAVAILABLE", None, None,
              "Needs this security's current yield, which no permitted source supplies"),
    ]
    ratings = [_item("rating", "Credit ratings", None, "text", "UNAVAILABLE", "NRSRO", None,
                     "NRSRO ratings require a licensed feed (terms required); not scraped")]
    return [
        {"id": "identity", "title": "Identity", "items": identity},
        {"id": "terms", "title": "Terms (fund-reported)", "items": [item for item in terms if item is not None]},
        {"id": "market", "title": "Market", "items": market},
        {"id": "holdings", "title": f"Fund holdings · {report}", "items": holdings},
        {"id": "analytics", "title": "Analytics", "items": analytics_items},
        {"id": "ratings", "title": "Ratings", "items": ratings},
        {"id": "rates", "title": "Rates context", "items": rates_items},
    ]
