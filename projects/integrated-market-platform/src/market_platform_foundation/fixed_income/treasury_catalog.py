"""U.S. Treasury marketable-security catalog from Treasury Fiscal Data.

Two official datasets, joined by CUSIP:

- **Treasury Securities Auctions Data** (``auctions_query``): typed terms and
  auction results for every auction of a security that has not yet matured.
  Security type, TIPS, FRN, and cash-management-bill status are provider
  flags; nothing is inferred from a name.
- **Monthly Statement of the Public Debt, Table III marketable detail**
  (``mspd_table_3_market``): the securities outstanding at the latest month
  end and the amount outstanding (USD millions).

A security is *outstanding* on a date when it has been issued (original
issue date on or before that date) and has not matured (maturity date after
that date). Securities issued after the MSPD record date are outstanding by
the same rule and carry no MSPD amount. Announced, not-yet-issued securities
are counted but never listed.

Only reference terms and auction facts live here; nothing here is a current
market price or yield.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from .http import FixedIncomeSourceError, Getter, get_json, http_get

FISCAL_DATA = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
AUCTIONS_URL = f"{FISCAL_DATA}/v1/accounting/od/auctions_query"
MSPD_MARKET_URL = f"{FISCAL_DATA}/v1/debt/mspd/mspd_table_3_market"
SOURCE_AUCTIONS = "US_TREASURY_FISCAL_DATA_AUCTIONS"
SOURCE_MSPD = "US_TREASURY_FISCAL_DATA_MSPD"
PAGE_SIZE = 10_000
MAX_PAGES = 5
ISSUER = "U.S. Treasury"

# Typed security kinds (display labels are the stored values).
BILL, CMB, NOTE, BOND, TIPS, FRN = "Bill", "CMB", "Note", "Bond", "TIPS", "FRN"
KINDS = (BILL, CMB, NOTE, BOND, TIPS, FRN)
_BASE_TYPES = {"Bill": BILL, "Note": NOTE, "Bond": BOND}
_MSPD_CLASSES = {"Bills Maturity Value": BILL, "Notes": NOTE, "Bonds": BOND,
                 "Inflation-Protected Securities": TIPS, "Floating Rate Notes": FRN}
_FREQUENCIES = {"Semi-Annual": 2, "Quarterly": 4, "None": 0}
_CUSIP_VALUES = {**{str(d): d for d in range(10)}, **{chr(65 + i): 10 + i for i in range(26)}, "*": 36, "@": 37, "#": 38}

# Half-open maturity buckets in years: [low, high).
MATURITY_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("<1Y", 0.0, 1.0), ("1-3Y", 1.0, 3.0), ("3-5Y", 3.0, 5.0), ("5-7Y", 5.0, 7.0),
    ("7-10Y", 7.0, 10.0), ("10-20Y", 10.0, 20.0), ("20Y+", 20.0, float("inf")),
)
DAYS_PER_YEAR = 365.25


class MalformedRow(ValueError):
    pass


def cusip_valid(value: str) -> bool:
    """Nine characters with a correct CUSIP check digit (modulus 10, double-add-double)."""

    text = value.strip().upper()
    if len(text) != 9 or not text[8].isdigit() or any(char not in _CUSIP_VALUES for char in text[:8]):
        return False
    total = 0
    for index, char in enumerate(text[:8]):
        digit = _CUSIP_VALUES[char] * (2 if index % 2 else 1)
        total += digit // 10 + digit % 10
    return (10 - total % 10) % 10 == int(text[8])


def days_to_maturity(maturity: date, today: date) -> int:
    return (maturity - today).days


def years_to_maturity(maturity: date, today: date) -> float:
    """Calendar days / 365.25; a remaining-maturity measure, not a day-count basis."""

    return days_to_maturity(maturity, today) / DAYS_PER_YEAR


def maturity_bucket(years: float) -> str | None:
    if years < 0:
        return None
    return next(label for label, low, high in MATURITY_BUCKETS if low <= years < high)


def _text(raw: Any) -> str | None:
    value = str(raw).strip() if raw is not None else ""
    return None if value in ("", "null", "None", "N/A") else value


def _number(raw: Any) -> float | None:
    text = _text(raw)
    if text is None:
        return None
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        raise MalformedRow("MALFORMED_NUMBER") from None


def _date(raw: Any, *, required: bool = False) -> date | None:
    text = _text(raw)
    if text is None:
        if required:
            raise MalformedRow("MISSING_DATE")
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        raise MalformedRow("MALFORMED_DATE") from None


def _flag(raw: Any) -> bool | None:
    text = _text(raw)
    return None if text is None else {"yes": True, "no": False}.get(text.casefold())


@dataclass(frozen=True, slots=True)
class TreasuryAuction:
    """One auction's published facts. Rates are percent; prices are per 100 of par."""

    auction_date: date
    issue_date: date
    security_term: str | None
    reopening: bool
    dated_date: date | None = None
    high_yield: float | None = None
    high_discount_rate: float | None = None
    high_investment_rate: float | None = None
    high_discount_margin: float | None = None
    #: Price per 100 of par. For TIPS this is the inflation-ADJUSTED price (unadjusted × index ratio).
    high_price: float | None = None
    #: TIPS only: the real (unadjusted) price per 100 of par, the basis of the real auction yield.
    unadjusted_price: float | None = None
    accrued_interest_per100: float | None = None
    bid_to_cover: float | None = None
    offering_amount: float | None = None
    total_accepted: float | None = None
    direct_bidder_accepted: float | None = None
    indirect_bidder_accepted: float | None = None
    primary_dealer_accepted: float | None = None
    competitive_accepted: float | None = None
    index_ratio_on_issue_date: float | None = None
    ref_cpi_on_issue_date: float | None = None
    frn_index_rate: float | None = None

    @property
    def has_results(self) -> bool:
        return any(value is not None for value in (self.high_yield, self.high_discount_rate,
                                                   self.high_discount_margin, self.high_price))


@dataclass(frozen=True, slots=True)
class TreasurySecurity:
    cusip: str
    kind: str
    base_type: str | None
    original_term: str | None
    issue_date: date
    maturity_date: date
    coupon_pct: float | None
    frn_spread_pct: float | None
    payments_per_year: int | None
    dated_date: date | None
    callable: bool | None
    call_date: date | None
    series: str | None
    auctions: tuple[TreasuryAuction, ...]
    mspd_outstanding_musd: float | None
    source: str

    @property
    def tips(self) -> bool:
        return self.kind == TIPS

    @property
    def frn(self) -> bool:
        return self.kind == FRN

    @property
    def cmb(self) -> bool:
        return self.kind == CMB

    @property
    def reopened(self) -> bool:
        return any(auction.reopening for auction in self.auctions)

    @property
    def latest_auction(self) -> TreasuryAuction | None:
        completed = [auction for auction in self.auctions if auction.has_results]
        return completed[-1] if completed else None

    @property
    def description(self) -> str:
        month = f"{self.maturity_date:%b} {self.maturity_date.year}"
        if self.kind in (BILL, CMB):
            label = "Cash Management Bill" if self.kind == CMB else "Bill"
            return f"{ISSUER} {label} {self.maturity_date:%b} {self.maturity_date.day} {self.maturity_date.year}"
        if self.kind == FRN:
            return f"{ISSUER} FRN {month}"
        coupon = "" if self.coupon_pct is None else f" {format_coupon(self.coupon_pct)}%"
        return f"{ISSUER} {self.kind}{coupon} {month}"

    def outstanding_on(self, today: date) -> bool:
        return self.issue_date <= today < self.maturity_date


def format_coupon(value: float) -> str:
    text = f"{value:.3f}"
    return text[:-1] if text.endswith("0") else text


@dataclass(frozen=True, slots=True)
class TreasuryCatalog:
    securities: tuple[TreasurySecurity, ...]
    fetched_at: str
    mspd_record_date: date | None
    mspd_error: str | None
    rejected: dict[str, int] = field(default_factory=dict)
    announced: int = 0

    def outstanding(self, today: date) -> list[TreasurySecurity]:
        return [security for security in self.securities if security.outstanding_on(today)]


def _auction(row: dict[str, Any]) -> tuple[str, dict[str, Any], TreasuryAuction]:
    cusip = (_text(row.get("cusip")) or "").upper()
    if not cusip_valid(cusip):
        raise MalformedRow("INVALID_CUSIP")
    base = _BASE_TYPES.get(_text(row.get("security_type")) or "")
    if base is None:
        raise MalformedRow("UNKNOWN_SECURITY_TYPE")
    tips, frn, cmb = (_flag(row.get(key)) for key in ("inflation_index_security", "floating_rate", "cash_management_bill_cmb"))
    kind = CMB if cmb else TIPS if tips else FRN if frn else base
    maturity = _date(row.get("maturity_date"), required=True)
    issue = _date(row.get("issue_date"), required=True)
    auction_date = _date(row.get("auction_date"), required=True)
    assert maturity is not None and issue is not None and auction_date is not None
    if maturity <= issue:
        raise MalformedRow("MATURITY_NOT_AFTER_ISSUE")
    coupon = _number(row.get("int_rate"))
    if kind in (BILL, CMB):
        coupon = None  # Bills are discount instruments: a discount rate is never a coupon.
    frequency = _text(row.get("int_payment_frequency"))
    terms = {
        "kind": kind, "base_type": base, "maturity_date": maturity, "coupon_pct": coupon,
        "frn_spread_pct": _number(row.get("spread")) if kind == FRN else None,
        "payments_per_year": 0 if kind in (BILL, CMB) else _FREQUENCIES.get(frequency or ""),
        "original_term": _text(row.get("original_security_term")),
        "callable": _flag(row.get("callable")), "call_date": _date(row.get("call_date")),
        "series": _text(row.get("series")), "reopening": _flag(row.get("reopening")) is True,
    }
    auction = TreasuryAuction(
        auction_date=auction_date, issue_date=issue, security_term=_text(row.get("security_term")),
        reopening=terms["reopening"], dated_date=_date(row.get("dated_date")),
        high_yield=_number(row.get("high_yield")), high_discount_rate=_number(row.get("high_discnt_rate")),
        high_investment_rate=_number(row.get("high_investment_rate")),
        high_discount_margin=_number(row.get("high_discnt_margin")), high_price=_number(row.get("high_price")),
        unadjusted_price=_number(row.get("unadj_price")) if kind == TIPS else None,
        accrued_interest_per100=_number(row.get("accrued_int_per100")),
        bid_to_cover=_number(row.get("bid_to_cover_ratio")), offering_amount=_number(row.get("offering_amt")),
        total_accepted=_number(row.get("total_accepted")),
        direct_bidder_accepted=_number(row.get("direct_bidder_accepted")),
        indirect_bidder_accepted=_number(row.get("indirect_bidder_accepted")),
        primary_dealer_accepted=_number(row.get("primary_dealer_accepted")),
        competitive_accepted=_number(row.get("comp_accepted")),
        index_ratio_on_issue_date=_number(row.get("index_ratio_on_issue_date")),
        ref_cpi_on_issue_date=_number(row.get("ref_cpi_on_issue_date")),
        frn_index_rate=_number(row.get("frn_index_determination_rate")),
    )
    return cusip, terms, auction


_CONSISTENT = ("kind", "base_type", "maturity_date")


def _mspd_amounts(rows: Iterable[dict[str, Any]]) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    """Outstanding amount (USD millions) per CUSIP, and each CUSIP's first MSPD line."""

    amounts: dict[str, float] = {}
    lines: dict[str, dict[str, Any]] = {}
    for row in rows:
        cusip = (_text(row.get("security_class2_desc")) or "").upper()
        if not cusip_valid(cusip):
            continue  # subtotal and class lines carry no CUSIP
        lines.setdefault(cusip, row)
        try:
            amount = _number(row.get("outstanding_amt"))
        except MalformedRow:
            continue
        if amount is not None:
            amounts[cusip] = max(amount, amounts.get(cusip, amount))
    return amounts, lines


def _mspd_only(cusip: str, row: dict[str, Any], amount: float | None) -> TreasurySecurity | None:
    """A security MSPD lists as outstanding but the auction dataset does not cover."""

    kind = _MSPD_CLASSES.get(_text(row.get("security_class1_desc")) or "")
    try:
        issue, maturity = _date(row.get("issue_date"), required=True), _date(row.get("maturity_date"), required=True)
        coupon = _number(row.get("interest_rate_pct"))
    except MalformedRow:
        return None
    if kind is None or issue is None or maturity is None or maturity <= issue:
        return None
    # MSPD lists each coupon security's interest payment dates (MM/DD); bills are discount instruments.
    payments = 0 if kind in (BILL, CMB) else sum(1 for index in range(1, 5) if _text(row.get(f"interest_pay_date_{index}"))) or None
    return TreasurySecurity(
        cusip=cusip, kind=kind, base_type=kind if kind in (BILL, NOTE, BOND) else None, original_term=None,
        issue_date=issue, maturity_date=maturity, coupon_pct=None if kind in (BILL, CMB, FRN) else coupon,
        frn_spread_pct=None, payments_per_year=payments, dated_date=None, callable=None, call_date=None, series=None,
        auctions=(), mspd_outstanding_musd=amount, source=SOURCE_MSPD)


def build_catalog(auction_rows: Iterable[dict[str, Any]], mspd_rows: Iterable[dict[str, Any]] | None, *,
                  today: date, fetched_at: str, mspd_record_date: date | None = None,
                  mspd_error: str | None = None) -> TreasuryCatalog:
    """Reconcile auctions per CUSIP; malformed rows and conflicting terms fail closed."""

    rejected: Counter[str] = Counter()
    grouped: dict[str, list[tuple[dict[str, Any], TreasuryAuction]]] = defaultdict(list)
    for row in auction_rows:
        try:
            cusip, terms, auction = _auction(row)
        except MalformedRow as exc:
            rejected[str(exc)] += 1
            continue
        grouped[cusip].append((terms, auction))
    amounts, lines = _mspd_amounts(mspd_rows or ())
    securities: list[TreasurySecurity] = []
    announced = 0
    for cusip, entries in grouped.items():
        first = entries[0][0]
        coupons = {terms["coupon_pct"] for terms, _ in entries if terms["coupon_pct"] is not None}
        if any(terms[key] != first[key] for terms, _ in entries for key in _CONSISTENT) or len(coupons) > 1:
            rejected["CONFLICTING_TERMS"] += 1
            continue
        # One record per auction date: an exact duplicate row is the same auction.
        auctions = sorted({auction.auction_date: auction for _, auction in entries}.values(), key=lambda item: item.auction_date)
        issue_date = min(auction.issue_date for auction in auctions)
        if issue_date > today:
            announced += 1
            continue
        original_terms = next((terms for terms, auction in sorted(entries, key=lambda item: item[1].auction_date)
                               if not terms["reopening"]), sorted(entries, key=lambda item: item[1].auction_date)[0][0])
        original = next((auction for auction in auctions if not auction.reopening), auctions[0])
        securities.append(TreasurySecurity(
            cusip=cusip, kind=first["kind"], base_type=first["base_type"],
            original_term=original_terms["original_term"] or original.security_term,
            issue_date=issue_date, maturity_date=first["maturity_date"],
            coupon_pct=next(iter(coupons)) if coupons else None,
            frn_spread_pct=next((terms["frn_spread_pct"] for terms, _ in entries if terms["frn_spread_pct"] is not None), None),
            payments_per_year=original_terms["payments_per_year"], dated_date=original.dated_date,
            callable=original_terms["callable"], call_date=original_terms["call_date"], series=original_terms["series"],
            auctions=tuple(auctions), mspd_outstanding_musd=amounts.get(cusip), source=SOURCE_AUCTIONS))
    for cusip, row in lines.items():
        if cusip in grouped:
            continue
        security = _mspd_only(cusip, row, amounts.get(cusip))
        if security is not None:
            securities.append(security)
    securities.sort(key=lambda item: (item.maturity_date, item.cusip))
    return TreasuryCatalog(tuple(securities), fetched_at, mspd_record_date, mspd_error, dict(rejected), announced)


def _pages(get: Getter, url: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number in range(1, MAX_PAGES + 1):
        payload = get_json(get, f"{url}&page%5Bsize%5D={PAGE_SIZE}&page%5Bnumber%5D={number}")
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list) or not isinstance(payload.get("meta"), dict):
            raise FixedIncomeSourceError("MALFORMED_RESPONSE")
        rows.extend(item for item in payload["data"] if isinstance(item, dict))
        if number >= int(payload["meta"].get("total-pages") or 1):
            return rows
    raise FixedIncomeSourceError("RESPONSE_TOO_LARGE")


def fetch_auction_rows(get: Getter, today: date) -> list[dict[str, Any]]:
    """Every auction of a security maturing on or after today (bounded: ~900 rows)."""

    return _pages(get, f"{AUCTIONS_URL}?filter=maturity_date:gte:{today.isoformat()}")


def fetch_mspd_rows(get: Getter) -> tuple[date, list[dict[str, Any]]]:
    latest = get_json(get, f"{MSPD_MARKET_URL}?sort=-record_date&fields=record_date&page%5Bsize%5D=1")
    try:
        record = date.fromisoformat(str(latest["data"][0]["record_date"])[:10])
    except (KeyError, IndexError, TypeError, ValueError):
        raise FixedIncomeSourceError("MALFORMED_RESPONSE") from None
    return record, _pages(get, f"{MSPD_MARKET_URL}?filter=record_date:eq:{record.isoformat()}")


def load_treasury_catalog(*, today: date, fetched_at: str, get: Getter = http_get) -> TreasuryCatalog:
    """Auctions are required; a missing MSPD leaves amounts unavailable, not the catalog."""

    auctions = fetch_auction_rows(get, today)
    try:
        record, mspd = fetch_mspd_rows(get)
        error = None
    except FixedIncomeSourceError as exc:
        record, mspd, error = None, [], exc.code
    return build_catalog(auctions, mspd, today=today, fetched_at=fetched_at, mspd_record_date=record, mspd_error=error)
