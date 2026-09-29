"""U.S. Treasury daily interest-rate publications and curve-derived context.

Official structured XML feeds (Treasury Resource Center):

- Daily Treasury Par Yield Curve Rates (nominal, 1M–30Y).
- Daily Treasury Par Real Yield Curve Rates (5Y–30Y).
- Daily Treasury Bill Rates: indicative closing bank-discount and
  coupon-equivalent rates for the most recently auctioned bill of each term,
  with that bill's CUSIP.

Par curve points are *reference observations* on an interpolated curve built
from indicative bid-side prices of on-the-run securities. A curve point is
never a specific security's yield, and a CUSIP is never a curve tenor. The
bill-rate feed names its CUSIPs, so those quotes attach to exactly those
bills and no others.

Derived values (spreads, shape, breakevens, nearest-tenor reference) are
computed from one publication date and say so.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from .http import FixedIncomeSourceError, Getter, failure_code, http_get

RATES_XML_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
NOMINAL, REAL, BILLS = "NOMINAL_PAR", "REAL_PAR", "BILL_RATES"
FEEDS = {NOMINAL: "daily_treasury_yield_curve", REAL: "daily_treasury_real_yield_curve", BILLS: "daily_treasury_bill_rates"}
SOURCE = "US_TREASURY_DAILY_RATES"
#: A publication older than this many calendar days is STALE (covers a weekend plus a holiday Monday).
STALE_AFTER_DAYS = 4
#: A nearest-tenor reference is withheld when maturity lies this far (years) outside the published tenor range.
REFERENCE_RANGE_TOLERANCE_YEARS = 1.0
_NS = {"m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
       "d": "http://schemas.microsoft.com/ado/2007/08/dataservices"}

NOMINAL_TENORS: tuple[tuple[str, str, float], ...] = (
    ("1M", "BC_1MONTH", 1 / 12), ("1.5M", "BC_1_5MONTH", 1.5 / 12), ("2M", "BC_2MONTH", 2 / 12),
    ("3M", "BC_3MONTH", 0.25), ("4M", "BC_4MONTH", 4 / 12), ("6M", "BC_6MONTH", 0.5),
    ("1Y", "BC_1YEAR", 1.0), ("2Y", "BC_2YEAR", 2.0), ("3Y", "BC_3YEAR", 3.0), ("5Y", "BC_5YEAR", 5.0),
    ("7Y", "BC_7YEAR", 7.0), ("10Y", "BC_10YEAR", 10.0), ("20Y", "BC_20YEAR", 20.0), ("30Y", "BC_30YEAR", 30.0),
)
REAL_TENORS: tuple[tuple[str, str, float], ...] = (
    ("5Y", "TC_5YEAR", 5.0), ("7Y", "TC_7YEAR", 7.0), ("10Y", "TC_10YEAR", 10.0),
    ("20Y", "TC_20YEAR", 20.0), ("30Y", "TC_30YEAR", 30.0),
)
BILL_TERMS: tuple[tuple[str, str], ...] = (("4W", "4WK"), ("6W", "6WK"), ("8W", "8WK"), ("13W", "13WK"),
                                           ("17W", "17WK"), ("26W", "26WK"), ("52W", "52WK"))
#: (id, long tenor, short tenor): value = long − short, in basis points.
SPREADS: tuple[tuple[str, str, str], ...] = (("2s10s", "10Y", "2Y"), ("3m10y", "10Y", "3M"),
                                             ("5s30s", "30Y", "5Y"), ("10s30s", "30Y", "10Y"))
#: Curve shape thresholds in basis points (see ``curve_shape``).
SHAPE_THRESHOLD_BP = 10.0


@dataclass(frozen=True, slots=True)
class CurvePoint:
    tenor: str
    years: float
    value: float  # percent


@dataclass(frozen=True, slots=True)
class CurvePublication:
    kind: str
    date: date
    points: tuple[CurvePoint, ...]

    def value(self, tenor: str) -> float | None:
        return next((point.value for point in self.points if point.tenor == tenor), None)


@dataclass(frozen=True, slots=True)
class BillQuote:
    term: str
    cusip: str | None
    maturity_date: date | None
    discount_rate: float | None  # bank-discount basis, percent
    coupon_equivalent: float | None  # coupon-equivalent (investment) yield, percent


@dataclass(frozen=True, slots=True)
class BillPublication:
    date: date
    quotes: tuple[BillQuote, ...]

    def for_cusip(self, cusip: str) -> BillQuote | None:
        return next((quote for quote in self.quotes if quote.cusip == cusip), None)


@dataclass(frozen=True, slots=True)
class TreasuryRates:
    nominal: tuple[CurvePublication, ...]
    real: tuple[CurvePublication, ...]
    bills: tuple[BillPublication, ...]
    errors: dict[str, str]
    fetched_at: str

    @staticmethod
    def _latest(items: tuple[Any, ...]) -> Any | None:
        return items[-1] if items else None

    @property
    def latest_nominal(self) -> CurvePublication | None:
        return self._latest(self.nominal)

    @property
    def latest_real(self) -> CurvePublication | None:
        return self._latest(self.real)

    @property
    def latest_bills(self) -> BillPublication | None:
        return self._latest(self.bills)


def publication_state(published: date | None, today: date) -> str:
    if published is None:
        return "UNAVAILABLE"
    return "PUBLICATION_CURRENT" if (today - published).days <= STALE_AFTER_DAYS else "STALE"


def _properties(xml: bytes) -> list[dict[str, str]]:
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        raise FixedIncomeSourceError("MALFORMED_RESPONSE") from None
    entries = []
    for properties in root.iter(f"{{{_NS['m']}}}properties"):
        entries.append({child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in properties})
    return entries


def _rate(raw: str | None) -> float | None:
    try:
        value = float(raw) if raw not in (None, "") else None
    except ValueError:
        return None
    return value if value is not None and -20.0 < value < 50.0 else None


def _day(raw: str | None) -> date | None:
    try:
        return date.fromisoformat((raw or "")[:10])
    except ValueError:
        return None


def parse_curve(xml: bytes, kind: str) -> list[CurvePublication]:
    tenors = NOMINAL_TENORS if kind == NOMINAL else REAL_TENORS
    publications = []
    for entry in _properties(xml):
        day = _day(entry.get("NEW_DATE"))
        if day is None:
            continue
        points = tuple(CurvePoint(tenor, years, value) for tenor, key, years in tenors
                       if (value := _rate(entry.get(key))) is not None)
        if points:
            publications.append(CurvePublication(kind, day, points))
    return publications


def parse_bills(xml: bytes) -> list[BillPublication]:
    publications = []
    for entry in _properties(xml):
        day = _day(entry.get("INDEX_DATE"))
        if day is None:
            continue
        quotes = tuple(BillQuote(term, (entry.get(f"CUSIP_{key}") or "").upper() or None,
                                 _day(entry.get(f"MATURITY_DATE_{key}")),
                                 _rate(entry.get(f"ROUND_B1_CLOSE_{key}_2")), _rate(entry.get(f"ROUND_B1_YIELD_{key}_2")))
                       for term, key in BILL_TERMS)
        publications.append(BillPublication(day, tuple(quote for quote in quotes
                                                       if quote.discount_rate is not None or quote.coupon_equivalent is not None)))
    return publications


def _months(today: date) -> tuple[str, str]:
    previous = date(today.year - 1, 12, 1) if today.month == 1 else date(today.year, today.month - 1, 1)
    return f"{previous:%Y%m}", f"{today:%Y%m}"


def _merge(items: Iterable[Any]) -> tuple[Any, ...]:
    return tuple(sorted({item.date: item for item in items}.values(), key=lambda item: item.date))


def fetch_rates(*, today: date, fetched_at: str, get: Getter = http_get) -> TreasuryRates:
    """Current and previous month of each feed (six bounded requests, three at a time)."""

    jobs = [(kind, month) for kind in FEEDS for month in _months(today)]

    def run(job: tuple[str, str]) -> tuple[str, list[Any] | str]:
        kind, month = job
        try:
            body = get(f"{RATES_XML_URL}?data={FEEDS[kind]}&field_tdr_date_value_month={month}", 20.0)
            return kind, parse_bills(body) if kind == BILLS else parse_curve(body, kind)
        except Exception as exc:  # noqa: BLE001 — classified per feed
            return kind, failure_code(exc)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run, jobs))
    collected: dict[str, list[Any]] = {kind: [] for kind in FEEDS}
    errors: dict[str, str] = {}
    for kind, result in results:
        if isinstance(result, str):
            errors[kind] = result
        else:
            collected[kind].extend(result)
    for kind in FEEDS:
        if collected[kind]:
            errors.pop(kind, None)  # one month failing while the other succeeded is not a feed failure
        elif kind not in errors:
            errors[kind] = "NO_PUBLICATION"
    return TreasuryRates(_merge(collected[NOMINAL]), _merge(collected[REAL]), _merge(collected[BILLS]), errors, fetched_at)


# ------------------------------------------------------------------ derived context
def curve_spreads(publication: CurvePublication | None) -> list[dict[str, Any]]:
    """Deterministic spreads from one publication, in basis points."""

    result = []
    for spread_id, long, short in SPREADS:
        left = publication.value(long) if publication else None
        right = publication.value(short) if publication else None
        result.append({"id": spread_id, "long_tenor": long, "short_tenor": short, "formula": f"{long} − {short}",
                       "value_bp": round((left - right) * 100, 1) if left is not None and right is not None else None,
                       "publication_date": publication.date.isoformat() if publication else None, "class": "DERIVED"})
    return result


def curve_shape(publication: CurvePublication | None) -> dict[str, Any]:
    """UPWARD_SLOPING when 3m10y and 2s10s are both ≥ +10 bp; INVERTED when both ≤ −10 bp;
    otherwise FLAT_OR_MIXED. A description of today's curve, never a forecast."""

    rule = f"UPWARD_SLOPING if 3m10y and 2s10s ≥ +{SHAPE_THRESHOLD_BP:g} bp; INVERTED if both ≤ −{SHAPE_THRESHOLD_BP:g} bp; else FLAT_OR_MIXED"
    spreads = {item["id"]: item["value_bp"] for item in curve_spreads(publication)}
    front, belly = spreads.get("3m10y"), spreads.get("2s10s")
    if front is None or belly is None:
        return {"state": "UNAVAILABLE", "rule": rule, "publication_date": None}
    state = ("UPWARD_SLOPING" if front >= SHAPE_THRESHOLD_BP and belly >= SHAPE_THRESHOLD_BP else
             "INVERTED" if front <= -SHAPE_THRESHOLD_BP and belly <= -SHAPE_THRESHOLD_BP else "FLAT_OR_MIXED")
    return {"state": state, "rule": rule, "publication_date": publication.date.isoformat() if publication else None,
            "class": "DERIVED"}


def breakevens(nominal: CurvePublication | None, real: CurvePublication | None) -> dict[str, Any]:
    """Nominal par yield − real par yield at the same tenor and publication date."""

    if nominal is None or real is None:
        return {"state": "UNAVAILABLE", "reason": "CURVE_UNAVAILABLE", "items": []}
    if nominal.date != real.date:
        return {"state": "UNAVAILABLE", "reason": "PUBLICATION_DATE_MISMATCH", "items": []}
    items = [{"tenor": point.tenor, "nominal": nominal.value(point.tenor), "real": point.value,
              "value": round(nominal.value(point.tenor) - point.value, 4)}  # type: ignore[operator]
             for point in real.points if nominal.value(point.tenor) is not None]
    return {"state": "DERIVED", "reason": None, "publication_date": nominal.date.isoformat(), "items": items,
            "method": "Par-curve breakeven: nominal par yield minus real par yield at the same tenor; an approximation, not a traded breakeven."}


def match_reference(years: float, publication: CurvePublication | None) -> dict[str, Any]:
    """Nearest published tenor by remaining maturity (ties → shorter tenor).

    Withheld when the maturity lies more than ``REFERENCE_RANGE_TOLERANCE_YEARS``
    outside the published tenor range; never interpolated.
    """

    if publication is None or not publication.points:
        return {"state": "UNAVAILABLE", "reason": "CURVE_UNAVAILABLE"}
    shortest, longest = publication.points[0].years, publication.points[-1].years
    if years < shortest - REFERENCE_RANGE_TOLERANCE_YEARS or years > longest + REFERENCE_RANGE_TOLERANCE_YEARS:
        return {"state": "UNAVAILABLE", "reason": "OUTSIDE_CURVE_RANGE"}
    point = min(publication.points, key=lambda item: (abs(item.years - years), item.years))
    return {"state": "REFERENCE", "reason": None, "tenor": point.tenor, "tenor_years": point.years,
            "value": point.value, "distance_years": round(abs(point.years - years), 4),
            "curve": publication.kind, "publication_date": publication.date.isoformat(),
            "method": "NEAREST_PUBLISHED_TENOR"}


def interpolate_par(years: float, publication: CurvePublication | None) -> dict[str, Any]:
    """Par yield at ``years`` by linear interpolation between the two bracketing published tenors.

    Never extrapolated: a maturity shorter than the first or longer than the last
    published tenor has no benchmark. A par yield is a curve reference on one
    publication date, not any security's own yield.
    """

    if publication is None or not publication.points:
        return {"state": "UNAVAILABLE", "reason": "CURVE_UNAVAILABLE"}
    points = sorted(publication.points, key=lambda point: point.years)
    if years < points[0].years or years > points[-1].years:
        return {"state": "UNAVAILABLE", "reason": "OUTSIDE_CURVE_RANGE"}
    for low, high in zip(points, points[1:] or points):
        if low.years <= years <= high.years:
            weight = 0.0 if high.years == low.years else (years - low.years) / (high.years - low.years)
            value = low.value + weight * (high.value - low.value)
            return {"state": "DERIVED", "reason": None, "value": round(value, 6), "curve": publication.kind,
                    "publication_date": publication.date.isoformat(), "lower_tenor": low.tenor, "upper_tenor": high.tenor,
                    "weight": round(weight, 6), "method": "LINEAR_BETWEEN_PUBLISHED_TENORS"}
    return {"state": "UNAVAILABLE", "reason": "OUTSIDE_CURVE_RANGE"}  # single-point curve


def publication_on(publications: tuple[CurvePublication, ...], day: date) -> CurvePublication | None:
    return next((item for item in publications if item.date == day), None)
