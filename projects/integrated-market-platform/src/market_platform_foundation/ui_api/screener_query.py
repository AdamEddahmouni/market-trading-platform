"""Canonical, provider-neutral Screener query (S6).

One typed query drives server-side filtering, sorting, and bounded pages for
every universe. Each field declares how the server can evaluate it:

- ``CATALOG``: complete universe metadata the server holds.
- ``SNAPSHOT``: one universe-wide market snapshot taken at a known time.
- ``LIVE_WINDOW``: current quotes for visible/selected rows only.
- ``REFERENCE``: publication context attached to a row (a Treasury curve
  point for the matched tenor, or an on-the-run bill's daily closing bid);
  it describes a benchmark or a subset of rows, so it is display-only.
- ``UNAVAILABLE``: no evaluation source.

Only ``CATALOG`` and ``SNAPSHOT`` fields may filter or sort a universe. A
``LIVE_WINDOW`` value may be displayed for the rows that have it, but ordering
or filtering by it would describe the visible rows, not the universe.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .screener_filters import filter_catalog, validate_filters
from .screener_universes import BONDS, CRYPTO, FUTURES, UNIVERSES, US_EQUITIES, US_ETFS, universe_spec

CATALOG = "CATALOG"
SNAPSHOT = "SNAPSHOT"
LIVE_WINDOW = "LIVE_WINDOW"
REFERENCE = "REFERENCE"
UNAVAILABLE = "UNAVAILABLE"

# Measured on the real 6,306-row ETF catalog (docs/engineering/SCREENER_S6.md).
DEFAULT_PAGE_LIMIT = 200
MAX_PAGE_LIMIT = 500
MAX_SEARCH_LENGTH = 80

_EQUITY_SNAPSHOT = ("price", "change_pct", "volume", "rel_volume", "float_shares", "market_cap",
                    "short_float_pct", "rsi_14", "avg_volume", "shares_outstanding", "short_ratio",
                    "eps_ttm", "pe", "fwd_pe", "perf_week")
_QUOTE_WINDOW = ("bid", "ask", "spread_pct")
# Descriptive text columns are displayed and filtered but were never sortable (S2).
_UNSORTED_TEXT = frozenset(("sector", "industry", "country", "earnings_date", "recommendation"))

FIELD_EXECUTION: dict[str, dict[str, str]] = {
    US_EQUITIES: {
        **{field: CATALOG for field in ("symbol", "company", *_UNSORTED_TEXT)},
        **{field: SNAPSHOT for field in _EQUITY_SNAPSHOT},  # one Finviz universe export
        **{field: LIVE_WINDOW for field in _QUOTE_WINDOW},
    },
    FUTURES: {
        **{field: CATALOG for field in ("symbol", "company", "root", "exchange", "contract_month",
                                         "expiry", "dte", "lead", "tick_size", "multiplier")},
        # Quote entitlement is absent; values appear only for visible rows if granted.
        **{field: LIVE_WINDOW for field in ("price", "change_pct", "volume", "open_interest", *_QUOTE_WINDOW)},
    },
    US_ETFS: {
        **{field: CATALOG for field in ("symbol", "company", "exchange")},
        **{field: SNAPSHOT for field in ("price", "change_pct", "volume", *_QUOTE_WINDOW)},
    },
    # S9: terms and auction facts are complete for every outstanding security.
    # There is no universe-wide bond price, yield, spread, or trade source.
    # S16: category and fund-reported terms/holdings are catalog facts; observed
    # operation prices exist for a few CUSIPs on dated operations, so they are
    # shown per visible row but never filter or sort the universe.
    BONDS: {
        **{field: CATALOG for field in ("symbol", "company", "issuer", "security_type", "term", "issue_date",
                                         "maturity", "maturity_bucket", "tips", "frn", "callable", "coupon",
                                         "years_to_maturity", "days_to_maturity", "maturity_year", "outstanding",
                                         "auction_date", "auction_yield", "auction_real_yield",
                                         "auction_discount_margin", "bid_to_cover",
                                         "category", "isin", "coupon_type", "in_default", "convertible", "pik",
                                         "fund_count", "fund_par_held", "fund_value_pct", "report_date")},
        **{field: REFERENCE for field in ("reference_tenor", "reference_rate", "indicative_rate",
                                          "observed_price", "observed_yield", "benchmark_spread", "observed_date")},
    },
    CRYPTO: {
        **{field: CATALOG for field in ("symbol", "base_asset", "quote_asset", "venue", "status")},
        **{field: SNAPSHOT for field in ("price", "change_pct", "base_volume", "quote_volume", "bid", "ask",
                                          "spread_pct", "high_24h", "low_24h", "trade_count")},
    },
}


def field_execution(universe: str, field: str) -> str:
    return FIELD_EXECUTION[universe_spec(universe).id].get(field, UNAVAILABLE)


def is_sortable(universe: str, field: str) -> bool:
    return field in universe_spec(universe).columns and field not in _UNSORTED_TEXT and \
        field_execution(universe, field) in (CATALOG, SNAPSHOT)


def snapshot_fields(universe: str) -> frozenset[str]:
    return frozenset(field for field, mode in FIELD_EXECUTION[universe].items() if mode == SNAPSHOT)


def field_capabilities(universe: str) -> dict[str, dict[str, Any]]:
    """Per displayed column: its execution source and whether it sorts/filters the universe."""

    catalog = {entry["field"]: entry for entry in filter_catalog(universe)}
    shared = {entry["field"]: entry for entry in filter_catalog(None)}

    def own(field: str) -> dict[str, str]:
        # A universe may name or measure a shared field its own way (Crypto: "UTC Day
        # Change %" in UTC_DAY_PERCENT); only such overrides travel here.
        entry, base = catalog.get(field), shared.get(field)
        if entry is None or base is None or (entry["label"], entry["unit"]) == (base["label"], base["unit"]):
            return {}
        return {"label": entry["label"], "unit": entry["unit"]}

    return {field: {"execution": field_execution(universe, field), "sortable": is_sortable(universe, field),
                    "filterable": field in catalog, **own(field)}
            for field in sorted(universe_spec(universe).columns | set(catalog))}


@dataclass(frozen=True, slots=True)
class ScreenerQuery:
    universe: str
    filters: tuple[dict[str, Any], ...]
    search: str
    sort: str
    descending: bool
    offset: int
    limit: int
    result_set: str | None = None
    selected: str | None = None

    @property
    def identity(self) -> str:
        """Everything that defines the ordered result set; never the page window."""

        return json.dumps([self.universe, list(self.filters), self.search.casefold(), self.sort, self.descending],
                          sort_keys=True, separators=(",", ":"))

    @property
    def uses_snapshot(self) -> bool:
        fields = snapshot_fields(self.universe) if self.universe != US_EQUITIES else frozenset()
        return self.sort in fields or any(rule["field"] in fields for rule in self.filters)


def parse_query(*, universe: str, search: str = "", sort: str | None = None, descending: bool = True,
                offset: int = 0, limit: int = DEFAULT_PAGE_LIMIT, filters: Any = None,
                result_set: str | None = None, selected: str | None = None) -> ScreenerQuery:
    spec = universe_spec(universe)
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("INVALID_RESULT_WINDOW")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PAGE_LIMIT:
        raise ValueError("INVALID_RESULT_WINDOW")
    if not isinstance(search, str) or len(search) > MAX_SEARCH_LENGTH:
        raise ValueError("INVALID_SEARCH")
    chosen = sort or spec.default_sort
    if not is_sortable(universe, chosen):
        raise ValueError("UNSUPPORTED_SORT")
    rules = validate_filters([] if filters is None else filters, universe=universe)
    for rule in rules:
        if field_execution(universe, rule["field"]) not in (CATALOG, SNAPSHOT):
            raise ValueError("FILTER_NOT_UNIVERSE_EVALUABLE")
    for value in (result_set, selected):
        if value is not None and (not isinstance(value, str) or not value or len(value) > 200):
            raise ValueError("INVALID_RESULT_WINDOW")
    return ScreenerQuery(universe, tuple(rules), search.strip(), chosen, bool(descending),
                         offset, limit, result_set, selected)


def order_rows(rows: Iterable[dict[str, Any]], sort: str, descending: bool,
               value_of: Callable[[dict[str, Any], str], Any]) -> list[dict[str, Any]]:
    """The one Screener ordering: present values by direction, missing values last in
    both directions, ties broken by canonical instrument id ascending."""

    present: list[tuple[Any, str, dict[str, Any]]] = []
    missing: list[tuple[str, dict[str, Any]]] = []
    for row in rows:
        value = value_of(row, sort)
        identity = row["instrument"]["instrument_id"]
        if value is None or value == "":
            missing.append((identity, row))
        else:
            present.append((value.casefold() if isinstance(value, str) else value, identity, row))
    # Two stable passes: identity ascending, then value by direction.
    present.sort(key=lambda item: item[1])
    present.sort(key=lambda item: item[0], reverse=descending)
    missing.sort(key=lambda item: item[0])
    return [item[2] for item in present] + [item[1] for item in missing]


def exact_matches_first(ordered: list[dict[str, Any]], needle: str,
                        keys: Iterable[str] = ("symbol",)) -> list[dict[str, Any]]:
    """A search for a ticker lists that ticker first.

    Searching SPY in the ETF universe matched SPY, SPYG, SPYV... and the volume (or symbol
    descending) sort put SPY far down. Rows whose key equals the search, ignoring case, move
    to the top; every other row, and the exact matches among themselves, keep the requested order.
    """
    if not needle:
        return ordered
    target = needle.casefold()
    names = tuple(keys)
    exact = [row for row in ordered if any(str(row.get(key) or "").casefold() == target for key in names)]
    if not exact:
        return ordered
    chosen = {id(row) for row in exact}
    return exact + [row for row in ordered if id(row) not in chosen]


def page_payload(query: ScreenerQuery, ordered: list[dict[str, Any]]) -> dict[str, Any]:
    """Page window, truthful counts, and the position of a requested selection."""

    rows = ordered[query.offset:query.offset + query.limit]
    selected_index = None
    if query.selected is not None:
        selected_index = next((index for index, row in enumerate(ordered)
                               if row["instrument"]["instrument_id"] == query.selected), None)
    return {"result_count": len(ordered), "offset": query.offset, "limit": query.limit,
            "returned": len(rows), "has_more": query.offset + len(rows) < len(ordered),
            "query_id": query.identity, "selected_id": query.selected, "selected_index": selected_index,
            "rows": rows}


def universe_capabilities() -> dict[str, dict[str, dict[str, Any]]]:
    return {universe: field_capabilities(universe) for universe in UNIVERSES}
