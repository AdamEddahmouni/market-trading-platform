"""Security-level Treasury publications beyond terms and auctions (Screener S16).

Official, public, per-CUSIP sources:

- **TIPS CPI data** (Fiscal Data ``tips_cpi_data_detail``): the daily index
  ratio and reference CPI for every TIPS, published ahead of the index date.
- **FRN daily indexes** (Fiscal Data ``frn_daily_indexes``): each FRN's daily
  index (the 13-week bill high rate), spread, daily accrual rate, and accrued
  interest per 100 for the current payment period.
- **Treasury buybacks** (Fiscal Data ``buybacks_security_details`` joined to
  ``buybacks_operations``): the weighted-average accepted price per 100 of
  par for each CUSIP Treasury bought back, with the operation's settlement.
- **New York Fed outright purchases** (``nyfed.load_operation_prices``): the
  weighted-average accepted price per CUSIP in each Desk operation.

Buyback and Fed-operation prices are dated *transaction observations*: the
average price accepted in one operation on one date. They are never shown as
current prices, and anything computed from them (yield, duration, spread)
carries the operation date.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable

from .http import FixedIncomeSourceError, Getter, failure_code, get_json, http_get
from .nyfed import OPERATION_LOOKBACK_DAYS, OperationPrice, load_operation_prices
from .treasury_catalog import FISCAL_DATA

TIPS_URL = f"{FISCAL_DATA}/v1/accounting/od/tips_cpi_data_detail"
FRN_URL = f"{FISCAL_DATA}/v1/accounting/od/frn_daily_indexes"
BUYBACK_DETAILS_URL = f"{FISCAL_DATA}/v1/accounting/od/buybacks_security_details"
BUYBACK_OPERATIONS_URL = f"{FISCAL_DATA}/v1/accounting/od/buybacks_operations"
SOURCE_TIPS = "US_TREASURY_FISCAL_DATA_TIPS_CPI"
SOURCE_FRN = "US_TREASURY_FISCAL_DATA_FRN_INDEXES"
SOURCE_BUYBACKS = "US_TREASURY_FISCAL_DATA_BUYBACKS"
TIPS, FRN_FEED, BUYBACKS, FED_OPERATIONS = "TIPS_INDEX", "FRN_INDEX", "BUYBACKS", "FED_OPERATIONS"


def _text(raw: Any) -> str | None:
    value = str(raw).strip() if raw is not None else ""
    return None if value in ("", "null", "None", "N/A", "NA") else value


def _number(raw: Any) -> float | None:
    text = _text(raw)
    try:
        return float(text) if text is not None else None
    except ValueError:
        return None


def _day(raw: Any) -> date | None:
    try:
        return date.fromisoformat((_text(raw) or "")[:10])
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class TipsIndex:
    cusip: str
    index_date: date
    index_ratio: float
    ref_cpi: float | None


@dataclass(frozen=True, slots=True)
class FrnIndex:
    cusip: str
    record_date: date
    spread: float | None  # percent
    daily_index: float | None  # percent: the 13-week bill high rate in force
    accrual_rate: float | None  # percent: index + spread (floored at zero by the FRN terms)
    daily_accrued_per100: float | None
    period_accrued_per100: float | None
    accrual_start: date | None
    accrual_end: date | None


@dataclass(frozen=True, slots=True)
class TreasuryMarketData:
    tips: dict[str, TipsIndex]
    frn: dict[str, FrnIndex]
    prices: dict[str, OperationPrice]  # latest observation per CUSIP across buybacks and Fed operations
    errors: dict[str, str]
    fetched_at: str
    counts: dict[str, int] = field(default_factory=dict)


def _data(get: Getter, url: str) -> list[dict[str, Any]]:
    payload = get_json(get, url)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise FixedIncomeSourceError("MALFORMED_RESPONSE")
    return [row for row in payload["data"] if isinstance(row, dict)]


def load_tips_index(get: Getter, today: date) -> dict[str, TipsIndex]:
    """Each TIPS's index ratio for the latest index date on or before today."""

    rows = _data(get, f"{TIPS_URL}?filter=index_date:lte:{today.isoformat()}&sort=-index_date&page%5Bsize%5D=400")
    result: dict[str, TipsIndex] = {}
    for row in rows:
        cusip, day, ratio = (_text(row.get("cusip")) or "").upper(), _day(row.get("index_date")), _number(row.get("index_ratio"))
        if len(cusip) == 9 and day is not None and ratio is not None and 0.5 < ratio < 10 and cusip not in result:
            result[cusip] = TipsIndex(cusip, day, ratio, _number(row.get("ref_cpi")))
    return result


def load_frn_index(get: Getter, today: date) -> dict[str, FrnIndex]:
    rows = _data(get, f"{FRN_URL}?filter=record_date:lte:{today.isoformat()}&sort=-record_date&page%5Bsize%5D=200")
    result: dict[str, FrnIndex] = {}
    for row in rows:
        cusip, day = (_text(row.get("cusip")) or "").upper(), _day(row.get("record_date"))
        if len(cusip) != 9 or day is None or cusip in result:
            continue
        result[cusip] = FrnIndex(cusip, day, _number(row.get("spread")), _number(row.get("daily_index")),
                                 _number(row.get("daily_int_accrual_rate")), _number(row.get("daily_accrued_int_per100")),
                                 _number(row.get("accr_int_per100_pmt_period")), _day(row.get("start_of_accrual_period")),
                                 _day(row.get("end_of_accrual_period")))
    return result


def load_buyback_prices(get: Getter, today: date) -> list[OperationPrice]:
    start = (today - timedelta(days=OPERATION_LOOKBACK_DAYS)).isoformat()
    operations = {(_text(row.get("operation_date")), _text(row.get("operation_start_time_est"))): row
                  for row in _data(get, f"{BUYBACK_OPERATIONS_URL}?filter=operation_date:gte:{start}&page%5Bsize%5D=1000")}
    prices = []
    for row in _data(get, f"{BUYBACK_DETAILS_URL}?filter=operation_date:gte:{start}&page%5Bsize%5D=10000"):
        cusip, day = (_text(row.get("cusip_nbr")) or "").upper(), _day(row.get("operation_date"))
        price, par = _number(row.get("weighted_avg_accepted_price")), _number(row.get("par_amt_accepted"))
        operation = operations.get((_text(row.get("operation_date")), _text(row.get("operation_start_time_est"))))
        if len(cusip) != 9 or day is None or price is None or not par or not 0 < price < 200 or operation is None:
            continue  # an issue with no accepted amount has no price; an unmatched operation has no settlement
        prices.append(OperationPrice(cusip, price, "TREASURY_BUYBACK", SOURCE_BUYBACKS, day,
                                     _day(operation.get("settlement_date")), par,
                                     _text(operation.get("operation_type")) or "Buyback",
                                     security_type=_text(operation.get("security_type")),
                                     operation_time=_text(row.get("operation_start_time_est"))))
    return prices


def latest_prices(observations: list[OperationPrice]) -> dict[str, OperationPrice]:
    """The most recent observation per CUSIP (ties: later operation time, then larger accepted par)."""

    def key(item: OperationPrice) -> tuple[Any, ...]:
        return (item.operation_date, item.operation_time or "", item.par_accepted or 0.0)

    latest: dict[str, OperationPrice] = {}
    for item in observations:
        if item.cusip not in latest or key(item) > key(latest[item.cusip]):
            latest[item.cusip] = item
    return latest


def fetch_market_data(*, today: date, fetched_at: str, get: Getter = http_get,
                      operations_loader: Callable[..., list[OperationPrice]] = load_operation_prices) -> TreasuryMarketData:
    """Four independent feeds, two at a time; one failing feed never hides the others."""

    jobs: dict[str, Callable[[], Any]] = {
        TIPS: lambda: load_tips_index(get, today), FRN_FEED: lambda: load_frn_index(get, today),
        BUYBACKS: lambda: load_buyback_prices(get, today), FED_OPERATIONS: lambda: operations_loader(today=today, get=get),
    }

    def run(name: str) -> tuple[str, Any]:
        try:
            return name, jobs[name]()
        except Exception as exc:  # noqa: BLE001 — classified per feed
            return name, FixedIncomeSourceError(failure_code(exc))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = dict(pool.map(run, list(jobs)))
    errors = {name: value.code for name, value in results.items() if isinstance(value, FixedIncomeSourceError)}
    ok = {name: value for name, value in results.items() if not isinstance(value, FixedIncomeSourceError)}
    observations = [*ok.get(BUYBACKS, []), *ok.get(FED_OPERATIONS, [])]
    prices = latest_prices(observations)
    counts = {"tips": len(ok.get(TIPS, {})), "frn": len(ok.get(FRN_FEED, {})),
              "buyback_observations": len(ok.get(BUYBACKS, [])), "fed_observations": len(ok.get(FED_OPERATIONS, [])),
              "priced_cusips": len(prices)}
    return TreasuryMarketData(ok.get(TIPS, {}), ok.get(FRN_FEED, {}), prices, errors, fetched_at, counts)
