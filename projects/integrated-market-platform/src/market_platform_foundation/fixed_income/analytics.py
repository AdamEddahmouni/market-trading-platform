"""Deterministic fixed-income math with explicit conventions and failure codes.

Units: rates and yields are percent (4.125 means 4.125 %); prices are per 100
of par (``BondPriceBasis.PAR_PERCENT``); time is in years; DV01 is the price
change per 100 of par for a one-basis-point yield change.

Fixed-coupon securities (Treasury notes, bonds, and TIPS in real terms):

- Coupons are paid ``frequency`` times a year on the maturity day of month,
  with the end-of-month rule when maturity is a month end.
- Price from yield uses the Treasury formula (31 CFR Part 356, Appendix B)
  for a regular period: with ``v = 1 / (1 + y/f)``, ``w = DSC / E`` (days
  settlement→next coupon over days in the current period, actual/actual),
  and ``n`` full periods from the next coupon to maturity,
  ``dirty = (C/f + (C/f)·Σ_{k=1..n} v^k + 100·v^n) / (1 + w·y/f)`` — the
  fractional period is discounted at simple interest. Validated against 639
  published nominal auction prices and 133 TIPS unadjusted prices.
- Accrued interest = ``(C/f) · (E − DSC) / E``; clean = dirty − accrued.
- Modified duration = ``−(dP/dy) / P`` on the dirty price by a central
  difference of ±1 bp under the same formula; Macaulay = modified · (1 + y/f);
  DV01 = ``(P(y − 1 bp) − P(y + 1 bp)) / 2``.
- An irregular first coupon period (dated date not on the regular schedule)
  fails closed rather than being approximated.

Bills are discount instruments (no coupon): price = 100 · (1 − d·t/360); the
investment rate follows the Treasury coupon-equivalent formulas (simple for
t ≤ 182 days, the quadratic form beyond). Inverting those formulas gives a
bill's price at an investment rate — ``100 / (1 + t·y)`` for the simple form
and ``100 / ((1 + y/2)(1 + (t − ½)·y))`` for the quadratic form, t = days /
year basis — so bill DV01 and modified duration use the same ±1 bp central
difference as coupon securities (S16). TIPS math is in real terms on the
unadjusted price. FRN coupons float, so fixed-rate formulas are refused.
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from datetime import date


class FixedIncomeMathError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class CouponPeriod:
    previous: date
    next: date
    remaining: tuple[date, ...]  # coupon dates after settlement, ending at maturity

    @property
    def days_in_period(self) -> int:
        return (self.next - self.previous).days


def _is_month_end(day: date) -> bool:
    return day.day == calendar.monthrange(day.year, day.month)[1]


def _shift(day: date, months: int, month_end: bool) -> date:
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    last = calendar.monthrange(year, month + 1)[1]
    return date(year, month + 1, last if month_end else min(day.day, last))


def coupon_period(settlement: date, maturity: date, frequency: int) -> CouponPeriod:
    if frequency not in (1, 2, 4, 12):
        raise FixedIncomeMathError("UNSUPPORTED_FREQUENCY")
    if settlement >= maturity:
        raise FixedIncomeMathError("MATURED")
    step, month_end = 12 // frequency, _is_month_end(maturity)
    dates = [maturity]
    while dates[-1] > settlement:
        dates.append(_shift(maturity, -step * len(dates), month_end))
    previous = dates[-1]
    remaining = tuple(reversed(dates[:-1]))
    return CouponPeriod(previous, remaining[0], remaining)


def _check_fixed(coupon_pct: float | None, frequency: int | None, *, floating: bool, dated_date: date | None,
                 settlement: date, maturity: date) -> tuple[float, int, CouponPeriod]:
    if floating:
        raise FixedIncomeMathError("FRN_FLOATING_COUPON")
    if coupon_pct is None or frequency is None or frequency <= 0 or coupon_pct < 0:
        raise FixedIncomeMathError("MISSING_TERMS")
    period = coupon_period(settlement, maturity, frequency)
    if dated_date is not None and dated_date > settlement:
        raise FixedIncomeMathError("NOT_YET_DATED")
    if dated_date is not None and not _on_schedule(dated_date, maturity, frequency) and \
            settlement < _shift(dated_date, 2 * (12 // frequency), False):
        # A short or long first coupon is not approximated by the regular schedule.
        raise FixedIncomeMathError("IRREGULAR_FIRST_PERIOD")
    return coupon_pct, frequency, period


def _on_schedule(day: date, maturity: date, frequency: int) -> bool:
    step, month_end = 12 // frequency, _is_month_end(maturity)
    months = (maturity.year - day.year) * 12 + maturity.month - day.month
    return months % step == 0 and _shift(maturity, -months, month_end) == day


def accrued_interest(coupon_pct: float | None, frequency: int | None, settlement: date, maturity: date, *,
                     floating: bool = False, dated_date: date | None = None) -> float:
    """Accrued interest per 100 of par at ``settlement`` (actual/actual in period)."""

    coupon, freq, period = _check_fixed(coupon_pct, frequency, floating=floating, dated_date=dated_date,
                                        settlement=settlement, maturity=maturity)
    return coupon / freq * (settlement - period.previous).days / period.days_in_period


def _dirty(yield_pct: float, coupon: float, freq: int, period: CouponPeriod, settlement: date) -> float:
    y = yield_pct / 100.0
    if 1 + y / freq <= 0:
        raise FixedIncomeMathError("INVALID_YIELD")
    w = (period.next - settlement).days / period.days_in_period
    n = len(period.remaining) - 1  # full periods after the next coupon
    v = 1 / (1 + y / freq)
    at_next_coupon = coupon / freq + coupon / freq * sum(v ** k for k in range(1, n + 1)) + 100.0 * v ** n
    return at_next_coupon / (1 + w * y / freq)


@dataclass(frozen=True, slots=True)
class FixedCouponAnalytics:
    yield_pct: float
    clean_price: float
    accrued: float
    dirty_price: float
    macaulay_years: float
    modified_duration: float
    dv01: float  # per 100 par
    current_yield_pct: float | None


def price_from_yield(yield_pct: float, coupon_pct: float | None, frequency: int | None, settlement: date,
                     maturity: date, *, floating: bool = False, dated_date: date | None = None) -> float:
    """Clean price per 100 of par."""

    coupon, freq, period = _check_fixed(coupon_pct, frequency, floating=floating, dated_date=dated_date,
                                        settlement=settlement, maturity=maturity)
    return _dirty(yield_pct, coupon, freq, period, settlement) - coupon / freq * (settlement - period.previous).days / period.days_in_period


def yield_from_price(clean_price: float, coupon_pct: float | None, frequency: int | None, settlement: date,
                     maturity: date, *, floating: bool = False, dated_date: date | None = None) -> float:
    """Yield (percent) whose street price equals ``clean_price``, by bisection."""

    if not math.isfinite(clean_price) or clean_price <= 0:
        raise FixedIncomeMathError("NON_POSITIVE_PRICE")
    coupon, freq, period = _check_fixed(coupon_pct, frequency, floating=floating, dated_date=dated_date,
                                        settlement=settlement, maturity=maturity)
    accrued = coupon / freq * (settlement - period.previous).days / period.days_in_period
    target = clean_price + accrued
    low, high = -50.0 * freq / 2 + 0.01, 100.0
    f_low = _dirty(low, coupon, freq, period, settlement) - target
    f_high = _dirty(high, coupon, freq, period, settlement) - target
    if f_low * f_high > 0:
        raise FixedIncomeMathError("YIELD_NOT_BRACKETED")
    for _ in range(200):
        mid = (low + high) / 2
        f_mid = _dirty(mid, coupon, freq, period, settlement) - target
        if abs(f_mid) < 1e-11 or high - low < 1e-12:
            return mid
        if f_low * f_mid <= 0:
            high = mid
        else:
            low, f_low = mid, f_mid
    raise FixedIncomeMathError("YIELD_NOT_CONVERGED")


def fixed_coupon_analytics(yield_pct: float, coupon_pct: float | None, frequency: int | None, settlement: date,
                           maturity: date, *, floating: bool = False, dated_date: date | None = None) -> FixedCouponAnalytics:
    """Price, accrued, durations, and DV01 at ``yield_pct`` on ``settlement``."""

    coupon, freq, period = _check_fixed(coupon_pct, frequency, floating=floating, dated_date=dated_date,
                                        settlement=settlement, maturity=maturity)
    dirty = _dirty(yield_pct, coupon, freq, period, settlement)
    accrued = coupon / freq * (settlement - period.previous).days / period.days_in_period
    down = _dirty(yield_pct - 0.01, coupon, freq, period, settlement)
    up = _dirty(yield_pct + 0.01, coupon, freq, period, settlement)
    dv01 = (down - up) / 2
    modified = dv01 / dirty * 1e4
    clean = dirty - accrued
    return FixedCouponAnalytics(yield_pct=yield_pct, clean_price=clean, accrued=accrued, dirty_price=dirty,
                                macaulay_years=modified * (1 + yield_pct / 100.0 / freq), modified_duration=modified,
                                dv01=dv01, current_yield_pct=coupon / clean * 100 if clean > 0 else None)


def current_yield(coupon_pct: float | None, clean_price: float | None) -> float:
    """Annual coupon / clean price, percent. Not a yield to maturity."""

    if coupon_pct is None or clean_price is None:
        raise FixedIncomeMathError("MISSING_TERMS")
    if clean_price <= 0:
        raise FixedIncomeMathError("NON_POSITIVE_PRICE")
    return coupon_pct / clean_price * 100


# ----------------------------------------------------------------------- bills
def bill_price_from_discount(discount_pct: float, days: int) -> float:
    if days <= 0:
        raise FixedIncomeMathError("MATURED")
    return 100.0 * (1 - discount_pct / 100.0 * days / 360.0)


def _year_basis(start: date, days: int) -> int:
    """366 when the year following ``start`` contains February 29, else 365."""

    end = date.fromordinal(start.toordinal() + 365)
    for year in range(start.year, end.year + 1):
        if calendar.isleap(year) and start < date(year, 2, 29) <= end:
            return 366
    return 365


def bill_investment_rate(price: float, days: int, start: date) -> float:
    """Coupon-equivalent (investment) rate, percent, from a price per 100."""

    if days <= 0:
        raise FixedIncomeMathError("MATURED")
    if not math.isfinite(price) or not 0 < price < 100.0 + 1e-9:
        raise FixedIncomeMathError("NON_POSITIVE_PRICE" if price <= 0 else "INVALID_PRICE")
    basis = _year_basis(start, days)
    if days <= basis / 2:
        return (100.0 - price) / price * basis / days * 100
    t = days / basis
    a = t / 2 - 0.25
    b = t
    c = (price - 100.0) / price
    return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a) * 100


def bill_macaulay_years(days: int, start: date) -> float:
    """A zero-coupon instrument's Macaulay duration is its time to maturity."""

    if days <= 0:
        raise FixedIncomeMathError("MATURED")
    return days / _year_basis(start, days)


def bill_price_from_investment_rate(rate_pct: float, days: int, start: date) -> float:
    """Price per 100 at a coupon-equivalent (investment) rate: the inverse of ``bill_investment_rate``."""

    if days <= 0:
        raise FixedIncomeMathError("MATURED")
    basis = _year_basis(start, days)
    t, y = days / basis, rate_pct / 100.0
    denominator = 1 + t * y if days <= basis / 2 else (1 + y / 2) * (1 + (t - 0.5) * y)
    if denominator <= 0:
        raise FixedIncomeMathError("INVALID_YIELD")
    return 100.0 / denominator


@dataclass(frozen=True, slots=True)
class BillAnalytics:
    price: float
    investment_rate_pct: float
    discount_rate_pct: float
    macaulay_years: float
    modified_duration: float
    dv01: float  # per 100 par


def bill_analytics(price: float, days: int, start: date) -> BillAnalytics:
    """Investment and discount rates at ``price``, with DV01 on the investment-rate basis."""

    rate = bill_investment_rate(price, days, start)
    down = bill_price_from_investment_rate(rate - 0.01, days, start)
    up = bill_price_from_investment_rate(rate + 0.01, days, start)
    dv01 = (down - up) / 2
    return BillAnalytics(price=price, investment_rate_pct=rate,
                         discount_rate_pct=(100.0 - price) / 100.0 * 360.0 / days * 100,
                         macaulay_years=bill_macaulay_years(days, start), modified_duration=dv01 / price * 1e4, dv01=dv01)
