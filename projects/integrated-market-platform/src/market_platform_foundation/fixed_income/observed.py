"""Dated analytics at an observed Treasury operation price (Screener S16).

Input: one ``OperationPrice`` (a Treasury buyback or a New York Fed outright
purchase) for one Treasury security. Output: the yield, accrued interest,
durations, DV01, and benchmark spread *at that operation's settlement date*,
each labeled DERIVED and carrying the operation date. Nothing here is a
current yield: the operation price is the weighted-average accepted price in
one operation, and the values age with it.

Conventions:

- settlement is the operation's published settlement date (the operation
  date only when none is published, which is flagged);
- notes, bonds: 31 CFR 356 Appendix B yield from the clean price
  (``analytics.yield_from_price``), then durations/DV01 at that yield;
- TIPS: the same math in real terms. Treasury buyback offers for TIPS are
  priced per 100 of *unadjusted* (real) principal, so the result is a real
  yield and the benchmark is the real par curve (checked live: every TIPS
  buyback yield lies within tens of basis points of the same-day real par
  curve, while an inflation-adjusted price would imply a yield several
  percent lower);
- bills: investment (coupon-equivalent) rate and bank-discount rate from the
  price, DV01 on the investment-rate basis (``analytics.bill_analytics``);
- FRNs: no yield — the coupon floats (``FRN_FLOATING_COUPON``);
- benchmark: the nominal (or real, for TIPS) par curve published on the
  operation date, linearly interpolated at the remaining maturity from
  settlement (``treasury_rates.interpolate_par``); spread = yield − par
  yield in basis points. The curve is an end-of-day publication and the
  operation is intraday, so the spread states both dates.
"""

from __future__ import annotations

from typing import Any

from . import analytics
from .nyfed import OperationPrice
from .treasury_catalog import BILL, CMB, FRN, TIPS, DAYS_PER_YEAR, TreasurySecurity
from .treasury_rates import REAL, TreasuryRates, interpolate_par, publication_on


def observed_measures(security: TreasurySecurity, observation: OperationPrice,
                      rates: TreasuryRates | None) -> dict[str, Any]:
    settlement = observation.settlement_date or observation.operation_date
    price = observation.price
    rate_quoted = observation.quote_basis == "DISCOUNT_RATE"
    if rate_quoted:
        # Bank-discount convention (actual/360): price = 100 x (1 - d x days / 360).
        price = None
        if security.kind in (BILL, CMB) and (security.maturity_date - settlement).days > 0:
            price = round(100.0 * (1.0 - observation.price / 100.0 * (security.maturity_date - settlement).days / 360.0), 6)
    result: dict[str, Any] = {
        "price": price, "price_basis": "REAL_PER_100_UNADJUSTED" if security.kind == TIPS
        else "PER_100_PAR_FROM_DISCOUNT_RATE" if rate_quoted else "PER_100_PAR",
        "quoted_discount_rate": observation.price if rate_quoted else None,
        "kind": observation.kind, "source": observation.source, "operation_type": observation.operation_type,
        "operation_date": observation.operation_date.isoformat(), "settlement_date": settlement.isoformat(),
        "settlement_published": observation.settlement_date is not None, "par_accepted": observation.par_accepted,
        "state": "DATED_OBSERVATION", "class": "OBSERVED",
        "yield": None, "yield_basis": None, "reason": None, "benchmark": None,
    }
    try:
        if price is None:
            raise analytics.FixedIncomeMathError("QUOTE_BASIS_MISMATCH")
        if security.kind == FRN:
            raise analytics.FixedIncomeMathError("FRN_FLOATING_COUPON")
        if security.kind in (BILL, CMB):
            days = (security.maturity_date - settlement).days
            bill = analytics.bill_analytics(price, days, settlement)
            result.update({"yield": round(bill.investment_rate_pct, 6), "yield_basis": "INVESTMENT_RATE",
                           "discount_rate": round(bill.discount_rate_pct, 6), "accrued": None,
                           "macaulay": round(bill.macaulay_years, 6), "modified": round(bill.modified_duration, 6),
                           "dv01": round(bill.dv01, 6)})
        else:
            ytm = analytics.yield_from_price(price, security.coupon_pct, security.payments_per_year, settlement,
                                             security.maturity_date, dated_date=security.dated_date)
            measures = analytics.fixed_coupon_analytics(ytm, security.coupon_pct, security.payments_per_year, settlement,
                                                        security.maturity_date, dated_date=security.dated_date)
            result.update({"yield": round(ytm, 6), "yield_basis": "REAL_YTM" if security.kind == TIPS else "YTM",
                           "accrued": round(measures.accrued, 6), "dirty_price": round(measures.dirty_price, 6),
                           "macaulay": round(measures.macaulay_years, 6), "modified": round(measures.modified_duration, 6),
                           "dv01": round(measures.dv01, 6),
                           "current_yield": round(measures.current_yield_pct, 6) if measures.current_yield_pct else None})
    except analytics.FixedIncomeMathError as exc:
        result["reason"] = exc.code
        return result
    publications = (rates.real if security.kind == TIPS else rates.nominal) if rates else ()
    curve = publication_on(publications, observation.operation_date)
    if curve is None:
        result["benchmark"] = {"state": "UNAVAILABLE", "reason": "NO_CURVE_ON_OPERATION_DATE"}
        return result
    years = (security.maturity_date - settlement).days / DAYS_PER_YEAR
    par = interpolate_par(years, curve)
    if par["state"] != "DERIVED":
        result["benchmark"] = par
        return result
    result["benchmark"] = {**par, "years": round(years, 4), "curve": "REAL_PAR" if curve.kind == REAL else "NOMINAL_PAR",
                           "spread_bp": round((result["yield"] - par["value"]) * 100, 1)}
    return result
