"""Federal Reserve Bank of New York Markets API: reference rates, SOMA holdings,
and Treasury outright-operation results (Screener S16).

Public JSON, no credential (``markets.newyorkfed.org/api``):

- ``/rates/all/latest.json`` — SOFR, EFFR, OBFR, TGCR, BGCR for their latest
  effective dates (policy context without a FRED key);
- ``/soma/asofdates/latest.json`` + ``/soma/{tsy,agency}/get/asof/<date>.json``
  — the System Open Market Account's holdings by CUSIP, weekly (a holdings
  fact: par held and, for Treasuries, the share of the issue outstanding);
- ``/tsy/all/results/details/search.json`` — outright Treasury operations and,
  per accepted CUSIP, the weighted-average accepted quote: a price per 100 of
  par for coupon securities, but a bank-discount *rate* (percent) for bill
  purchases, which the Desk conducts on a rate basis (``quote_basis``).

An operation price is a *dated transaction observation* at the operation's
date and settlement: never a current price or quote. SOMA agency MBS/CMBS
terms are free text in the feed and are not parsed into typed terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .http import FixedIncomeSourceError, Getter, get_json, http_get

API = "https://markets.newyorkfed.org/api"
SOURCE_RATES = "NY_FED_REFERENCE_RATES"
SOURCE_SOMA = "NY_FED_SOMA_HOLDINGS"
SOURCE_OPERATIONS = "NY_FED_TREASURY_OPERATIONS"
RATE_TYPES = ("SOFR", "EFFR", "OBFR", "TGCR", "BGCR")
RATE_LABELS = {"SOFR": "Secured Overnight Financing Rate", "EFFR": "Effective Federal Funds Rate",
               "OBFR": "Overnight Bank Funding Rate", "TGCR": "Tri-Party General Collateral Rate",
               "BGCR": "Broad General Collateral Rate"}
OPERATION_LOOKBACK_DAYS = 60


def _number(raw: Any) -> float | None:
    try:
        value = float(raw) if raw not in (None, "", "NA") else None
    except (TypeError, ValueError):
        return None
    return value if value is not None and value == value else None


def _day(raw: Any) -> date | None:
    try:
        return date.fromisoformat(str(raw or "")[:10])
    except ValueError:
        return None


def load_reference_rates(*, get: Getter = http_get) -> dict[str, Any]:
    payload = get_json(get, f"{API}/rates/all/latest.json")
    rows = payload.get("refRates") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise FixedIncomeSourceError("MALFORMED_RESPONSE")
    items = []
    for row in rows:
        if not isinstance(row, dict) or row.get("type") not in RATE_TYPES:
            continue
        effective = _day(row.get("effectiveDate"))
        value = _number(row.get("percentRate"))
        if effective is None or value is None:
            continue
        item = {"id": row["type"], "label": RATE_LABELS[row["type"]], "value": value, "unit": "percent",
                "effective_date": effective.isoformat(), "volume_billions": _number(row.get("volumeInBillions")),
                "p1": _number(row.get("percentPercentile1")), "p99": _number(row.get("percentPercentile99")),
                "class": "OBSERVED", "source": SOURCE_RATES}
        if row["type"] == "EFFR":
            item["target_from"], item["target_to"] = _number(row.get("targetRateFrom")), _number(row.get("targetRateTo"))
        items.append(item)
    items.sort(key=lambda item: RATE_TYPES.index(item["id"]))
    return {"source": SOURCE_RATES, "state": "PUBLICATION_CURRENT" if items else "UNAVAILABLE",
            "reason": None if items else "NO_RATES", "items": items}


@dataclass(frozen=True, slots=True)
class SomaHolding:
    cusip: str
    as_of: date
    security_type: str
    par_value: float | None
    percent_outstanding: float | None  # share of the issue, percent (Treasuries only)
    inflation_compensation: float | None
    issuer: str | None
    coupon: float | None
    maturity: date | None


@dataclass(frozen=True, slots=True)
class SomaHoldings:
    as_of: date
    holdings: dict[str, SomaHolding]
    counts: dict[str, int]

    def for_cusip(self, cusip: str) -> SomaHolding | None:
        return self.holdings.get(cusip)


def _holdings(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("soma", {}).get("holdings") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise FixedIncomeSourceError("MALFORMED_RESPONSE")
    return [row for row in rows if isinstance(row, dict)]


def load_soma(*, get: Getter = http_get) -> SomaHoldings:
    """The latest weekly SOMA holdings (Treasury and agency), keyed by CUSIP."""

    dates = get_json(get, f"{API}/soma/asofdates/latest.json")
    try:
        as_of = date.fromisoformat(str(dates["soma"]["asOfDates"][0])[:10])
    except (KeyError, IndexError, TypeError, ValueError):
        raise FixedIncomeSourceError("MALFORMED_RESPONSE") from None
    holdings: dict[str, SomaHolding] = {}
    counts: dict[str, int] = {}
    for market in ("tsy", "agency"):
        for row in _holdings(get_json(get, f"{API}/soma/{market}/get/asof/{as_of.isoformat()}.json")):
            cusip = str(row.get("cusip") or "").strip().upper()
            kind = str(row.get("securityType") or "").strip() or "Unknown"
            if len(cusip) != 9:
                continue
            counts[kind] = counts.get(kind, 0) + 1
            share = _number(row.get("percentOutstanding"))
            holdings[cusip] = SomaHolding(
                cusip=cusip, as_of=as_of, security_type=kind, par_value=_number(row.get("parValue")),
                # The feed states a fraction of the issue (0.06 = 6 %).
                percent_outstanding=round(share * 100, 4) if share is not None else None,
                inflation_compensation=_number(row.get("inflationCompensation")),
                issuer=str(row.get("issuer") or "").strip() or None, coupon=_number(row.get("coupon")),
                maturity=_day(row.get("maturityDate")))
    return SomaHoldings(as_of, holdings, counts)


@dataclass(frozen=True, slots=True)
class OperationPrice:
    """A weighted-average accepted quote in one dated Treasury operation.

    ``price`` is a price per 100 of par, except when ``quote_basis`` is
    ``DISCOUNT_RATE`` (Fed bill purchases): then it is the accepted bank-discount
    rate in percent, converted to a price only against the bill's maturity.
    """

    cusip: str
    price: float
    kind: str  # FED_BILL_PURCHASE | FED_COUPON_PURCHASE | TREASURY_BUYBACK
    source: str
    operation_date: date
    settlement_date: date | None
    par_accepted: float | None
    operation_type: str
    security_type: str | None = None
    operation_time: str | None = None
    quote_basis: str = "PRICE_PER_100"  # PRICE_PER_100 | DISCOUNT_RATE


def parse_operations(payload: Any) -> list[OperationPrice]:
    operations = payload.get("treasury", {}).get("auctions") if isinstance(payload, dict) else None
    if not isinstance(operations, list):
        raise FixedIncomeSourceError("MALFORMED_RESPONSE")
    prices = []
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("operationDirection") != "P":
            continue
        operation_date = _day(operation.get("operationDate"))
        if operation_date is None or str(operation.get("auctionStatus") or "").casefold() != "results":
            continue
        bill = "bill" in str(operation.get("operationType") or "").casefold()
        kind = "FED_BILL_PURCHASE" if bill else "FED_COUPON_PURCHASE"
        for detail in operation.get("details") or []:
            if not isinstance(detail, dict):
                continue
            price, par = _number(detail.get("weightedAvgAccptPrice")), _number(detail.get("parAmountAccepted"))
            cusip = str(detail.get("cusip") or "").strip().upper()
            # Bills are bought on a discount-rate basis (e.g. 3.932 = 3.932%); coupons on price per 100.
            if price is None or not par or len(cusip) != 9 or not (-1 < price < 25 if bill else 0 < price < 200):
                continue
            prices.append(OperationPrice(cusip, price, kind, SOURCE_OPERATIONS, operation_date,
                                         _day(operation.get("settlementDate")), par,
                                         str(operation.get("operationType") or ""),
                                         operation_time=str(operation.get("closeTime") or "") or None,
                                         quote_basis="DISCOUNT_RATE" if bill else "PRICE_PER_100"))
    return prices


def load_operation_prices(*, today: date, get: Getter = http_get) -> list[OperationPrice]:
    start = today - timedelta(days=OPERATION_LOOKBACK_DAYS)
    return parse_operations(get_json(get, f"{API}/tsy/all/results/details/search.json"
                                          f"?startDate={start.isoformat()}&endDate={today.isoformat()}"))
