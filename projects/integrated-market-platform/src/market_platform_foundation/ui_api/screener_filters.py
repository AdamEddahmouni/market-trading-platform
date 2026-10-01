"""Provider-neutral, universe-scoped Screener fields and predicates."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Callable

from ..discovery.screens import SCREEN_LIBRARY
from .screener_universes import BONDS, CRYPTO, FUTURES, US_EQUITIES, US_ETFS, universe_spec

NUMERIC_OPERATORS = ("eq", "ne", "gt", "gte", "lt", "lte", "between")
TEXT_OPERATORS = ("eq", "ne", "in", "not_in", "contains")

_FIELDS: tuple[tuple[str, str, str, str, str], ...] = (
    ("symbol", "Symbol", "Identity", "text", "text"),
    ("company", "Company", "Identity", "text", "text"),
    ("sector", "Sector", "Identity", "text", "text"),
    ("industry", "Industry", "Identity", "text", "text"),
    ("country", "Country", "Identity", "text", "text"),
    ("price", "Price", "Price & Movement", "number", "USD"),
    ("change_pct", "Change %", "Price & Movement", "number", "percent"),
    ("volume", "Volume", "Volume & Liquidity", "number", "shares"),
    ("avg_volume", "Average Volume", "Volume & Liquidity", "number", "shares"),
    ("rel_volume", "Relative Volume", "Volume & Liquidity", "number", "ratio"),
    ("float_shares", "Float", "Size & Shares", "number", "shares"),
    ("shares_outstanding", "Shares Outstanding", "Size & Shares", "number", "shares"),
    ("market_cap", "Market Cap", "Size & Shares", "number", "USD"),
    ("short_float_pct", "Short Float %", "Short Interest", "number", "percent"),
    ("short_ratio", "Short Ratio", "Short Interest", "number", "days"),
    ("eps_ttm", "EPS TTM", "Fundamentals", "number", "USD"),
    ("pe", "P/E", "Fundamentals", "number", "ratio"),
    ("fwd_pe", "Forward P/E", "Fundamentals", "number", "ratio"),
    ("recommendation", "Recommendation", "Fundamentals", "text", "text"),
    ("rsi_14", "RSI (14)", "Technical", "number", "index"),
    ("perf_week", "Weekly Performance", "Price & Movement", "number", "percent"),
    ("bid", "Bid", "Price & Movement", "number", "USD"),
    ("ask", "Ask", "Price & Movement", "number", "USD"),
    ("spread_pct", "Spread %", "Volume & Liquidity", "number", "percent"),
)
_CATALOG = {
    field: {"field": field, "label": label, "category": category, "type": kind,
            "unit": unit, "operators": list(NUMERIC_OPERATORS if kind == "number" else TEXT_OPERATORS),
            "universes": ["US_EQUITIES"], "availability": "SNAPSHOT"}
    for field, label, category, kind, unit in _FIELDS
}
for field in ("symbol", "company"):
    _CATALOG[field]["universes"] = [US_EQUITIES, FUTURES, US_ETFS]
# ETF market fields filter only through the universe-wide OpenD market snapshot
# (S6); equities take bid/ask/spread from the same kind of snapshot (Finviz has none).
for field in ("price", "change_pct", "volume"):
    _CATALOG[field]["universes"] = [US_EQUITIES, US_ETFS]
for field in ("bid", "ask", "spread_pct"):
    _CATALOG[field]["universes"] = [US_EQUITIES, US_ETFS, CRYPTO]
for field in ("symbol", "price", "change_pct"):
    _CATALOG[field]["universes"].append(CRYPTO)
_CATALOG.update({
    field: {"field": field, "label": label, "category": category, "type": kind,
            "unit": unit, "operators": list(NUMERIC_OPERATORS if kind == "number" else TEXT_OPERATORS),
            "universes": [CRYPTO], "availability": "CURRENT_SPOT"}
    for field, label, category, kind, unit in (
        ("base_asset", "Base Asset", "Identity", "text", "text"),
        ("quote_asset", "Quote Asset", "Identity", "text", "text"),
        ("venue", "Venue", "Identity", "text", "text"),
        ("status", "Status", "Identity", "text", "text"),
        ("base_volume", "24h Base Volume", "Volume & Liquidity", "number", "BASE_UNITS"),
        ("quote_volume", "24h Quote Volume", "Volume & Liquidity", "number", "QUOTE_UNITS"),
        ("high_24h", "24h High", "Price & Movement", "number", "QUOTE_UNITS"),
        ("low_24h", "24h Low", "Price & Movement", "number", "QUOTE_UNITS"),
        ("trade_count", "24h Trades", "Volume & Liquidity", "number", "count"),
    )
})
_CATALOG.update({
    field: {"field": field, "label": label, "category": category, "type": kind,
            "unit": unit, "operators": list(NUMERIC_OPERATORS if kind == "number" else TEXT_OPERATORS),
            "universes": universes, "availability": "CURRENT_METADATA"}
    for field, label, category, kind, unit, universes in (
        ("root", "Root", "Contract", "text", "text", [FUTURES]),
        ("exchange", "Exchange", "Identity", "text", "text", [FUTURES, US_ETFS]),
        ("contract_month", "Contract Month", "Contract", "text", "text", [FUTURES]),
        ("dte", "Days to Expiry", "Contract", "number", "days", [FUTURES]),
        ("lead", "Lead Contract", "Contract", "number", "boolean", [FUTURES]),
    )
})
# S9: Bond terms, maturity, and auction facts are complete for every catalog
# row. No price, yield-to-maturity, spread, rating, or trade-activity filter
# exists because no universe-wide source supplies them. S16 adds the category
# and fund-reported (Form N-PORT) terms and holdings; Treasury rows have no
# fund-held values, so a fund-holdings filter excludes them.
_CATALOG.update({
    field: {"field": field, "label": label, "category": category, "type": kind,
            "unit": unit, "operators": list(NUMERIC_OPERATORS if kind == "number" else TEXT_OPERATORS),
            "universes": [BONDS], "availability": "CURRENT_METADATA"}
    for field, label, category, kind, unit in (
        ("security_type", "Security Type", "Terms", "text", "text"),
        ("issuer", "Issuer", "Identity", "text", "text"),
        ("term", "Original Term", "Terms", "text", "text"),
        ("tips", "TIPS", "Terms", "text", "text"),
        ("frn", "Floating Rate (FRN)", "Terms", "text", "text"),
        ("callable", "Callable", "Terms", "text", "text"),
        ("coupon", "Coupon", "Terms", "number", "percent"),
        ("maturity_bucket", "Maturity Bucket", "Maturity", "text", "text"),
        ("years_to_maturity", "Years to Maturity", "Maturity", "number", "years"),
        ("days_to_maturity", "Days to Maturity", "Maturity", "number", "days"),
        ("maturity_year", "Maturity Year", "Maturity", "number", "year"),
        ("outstanding", "Amount Outstanding", "Size", "number", "USD_BILLIONS"),
        ("auction_yield", "Auction Yield (latest)", "Auction", "number", "percent"),
        ("auction_real_yield", "Auction Real Yield (TIPS)", "Auction", "number", "percent"),
        ("bid_to_cover", "Bid-to-Cover (latest auction)", "Auction", "number", "ratio"),
        ("category", "Category", "Identity", "text", "text"),
        ("isin", "ISIN", "Identity", "text", "text"),
        ("coupon_type", "Coupon Type", "Terms", "text", "text"),
        ("in_default", "In Default (fund-reported)", "Credit", "text", "text"),
        ("convertible", "Convertible", "Terms", "text", "text"),
        ("pik", "Paid in Kind", "Terms", "text", "text"),
        ("fund_count", "Reporting Funds", "Fund Holdings", "number", "count"),
        ("fund_par_held", "Par Held by Funds", "Fund Holdings", "number", "USD_MILLIONS"),
        ("fund_value_pct", "Fund Value (% of par, stale)", "Fund Holdings", "number", "per_100_par"),
    )
})


def filter_catalog(universe: str | None = US_EQUITIES) -> list[dict[str, Any]]:
    if universe is not None:
        universe_spec(universe)
    entries = deepcopy([entry for entry in _CATALOG.values()
                        if universe is None or universe in entry["universes"]])
    if universe == CRYPTO:
        # Pair prices are in the quote asset, and Kraken's open is the midnight-UTC
        # open: the change is a UTC-day change, never a rolling 24h change.
        units = {"price": "QUOTE_UNITS", "bid": "QUOTE_UNITS", "ask": "QUOTE_UNITS",
                 "change_pct": "UTC_DAY_PERCENT"}
        labels = {"symbol": "Pair", "price": "Last", "change_pct": "UTC Day Change %"}
        for entry in entries:
            if entry["field"] in units:
                entry["unit"] = units[entry["field"]]
            if entry["field"] in labels:
                entry["label"] = labels[entry["field"]]
    return entries


def validate_filters(raw: Any, *, universe: str = US_EQUITIES) -> list[dict[str, Any]]:
    universe_spec(universe)
    if not isinstance(raw, list) or len(raw) > 32:
        raise ValueError("INVALID_FILTER_LIST")
    validated: list[dict[str, Any]] = []
    ids: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("INVALID_FILTER")
        field, operator, identity = item.get("field"), item.get("operator"), item.get("id")
        if field not in _CATALOG:
            raise ValueError("UNKNOWN_FILTER_FIELD")
        if universe not in _CATALOG[field]["universes"]:
            raise ValueError("FILTER_UNIVERSE_MISMATCH")
        if operator not in _CATALOG[field]["operators"]:
            raise ValueError("UNSUPPORTED_FILTER_OPERATOR")
        if not isinstance(identity, str) or not identity or len(identity) > 80 or identity in ids:
            raise ValueError("INVALID_FILTER_ID")
        ids.add(identity)
        value = item.get("value")
        if _CATALOG[field]["type"] == "number":
            values = value if operator == "between" else [value]
            if not isinstance(values, list) or len(values) != (2 if operator == "between" else 1) or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values
            ):
                raise ValueError("INVALID_NUMERIC_FILTER_VALUE")
            if operator == "between" and values[0] > values[1]:
                raise ValueError("INVALID_FILTER_RANGE")
        else:
            values = value if operator in ("in", "not_in") else [value]
            if not isinstance(values, list) or not values or len(values) > 50 or any(
                not isinstance(v, str) or not v.strip() or len(v) > 160 for v in values
            ):
                raise ValueError("INVALID_TEXT_FILTER_VALUE")
        validated.append({"id": identity, "field": field, "operator": operator, "value": value})
    return validated


Observe = Callable[[dict[str, Any], str], Any]


def field_value(row: dict[str, Any], field: str) -> Any:
    """A row's own value: text from the row, numbers from its field envelope."""

    return row.get(field) if _CATALOG.get(field, {}).get("type") == "text" or field not in row.get("fields", {})         else row["fields"][field]["value"]


def _matches(row: dict[str, Any], rule: dict[str, Any], observe: Observe = field_value) -> bool:
    field, operator, wanted = rule["field"], rule["operator"], rule["value"]
    observed = observe(row, field)
    if observed is None:
        return False
    if _CATALOG[field]["type"] == "text":
        observed = str(observed).casefold()
        wanted = [v.casefold() for v in wanted] if operator in ("in", "not_in") else wanted.casefold()
        return {"eq": lambda: observed == wanted, "ne": lambda: observed != wanted,
                "in": lambda: observed in wanted, "not_in": lambda: observed not in wanted,
                "contains": lambda: wanted in observed}[operator]()
    if not isinstance(observed, (int, float)) or not math.isfinite(observed):
        return False
    return {"eq": lambda: observed == wanted, "ne": lambda: observed != wanted,
            "gt": lambda: observed > wanted, "gte": lambda: observed >= wanted,
            "lt": lambda: observed < wanted, "lte": lambda: observed <= wanted,
            "between": lambda: wanted[0] <= observed <= wanted[1]}[operator]()


def apply_filters(rows: list[dict[str, Any]], rules: list[dict[str, Any]],
                  observe: Observe = field_value) -> list[dict[str, Any]]:
    return [row for row in rows if all(_matches(row, rule, observe) for rule in rules)]


def rule_matches(row: dict[str, Any], rule: dict[str, Any]) -> bool:
    """The exact per-rule predicate used by ``apply_filters`` (validated rules only)."""

    return _matches(row, rule)


def catalog_entry(field: str) -> dict[str, Any]:
    return deepcopy(_CATALOG[field])


# Exact, reviewed translations from the immutable discovery definitions. A
# provider-only condition is reported as unsupported until the snapshot can
# actually evaluate it; it is never silently replaced by a different rule.
_TRANSLATIONS: dict[str, tuple[tuple[str, str, Any], ...] | None] = {
    "SHORT_SQUEEZE_DISCOVERY": (("float_shares", "lt", 50_000_000), ("price", "lt", 50),
                                ("short_float_pct", "gt", 20), ("rel_volume", "gt", 1.5)),
    "UNUSUAL_VOLUME_DISCOVERY": (("rel_volume", "gt", 2),),
    "MOMENTUM_IGNITION_DISCOVERY": (("change_pct", "gt", 10), ("rel_volume", "gt", 1.5)),
    "GAP_CATALYST_DISCOVERY": None,
    "EARNINGS_MOVER_DISCOVERY": None,
    "ANALYST_EVENT_DISCOVERY": None,
    "INSIDER_ACTIVITY_DISCOVERY": None,
    "TECHNICAL_BREAKOUT_DISCOVERY": None,
}
_PRESET_NAMES = {
    "SHORT_SQUEEZE_DISCOVERY": "Short Squeeze Discovery",
    "UNUSUAL_VOLUME_DISCOVERY": "Unusual Volume",
    "MOMENTUM_IGNITION_DISCOVERY": "Momentum Ignition",
    "GAP_CATALYST_DISCOVERY": "Gap / Catalyst",
    "EARNINGS_MOVER_DISCOVERY": "Earnings Movers",
    "ANALYST_EVENT_DISCOVERY": "Analyst Events",
    "INSIDER_ACTIVITY_DISCOVERY": "Insider Activity",
    "TECHNICAL_BREAKOUT_DISCOVERY": "Technical Breakouts",
}


def builtin_presets() -> list[dict[str, Any]]:
    result = []
    for screen_id, screen in SCREEN_LIBRARY.items():
        mapping = _TRANSLATIONS[screen_id]
        result.append({
            "id": screen_id, "name": _PRESET_NAMES[screen_id],
            "universe": US_EQUITIES,
            "version": screen.version, "status": "SUPPORTED" if mapping is not None else "UNSUPPORTED",
            "reason": None if mapping is not None else "Existing discovery condition is absent from the current broad Screener contract",
            "filters": [{"id": f"{screen_id.lower()}-{index}", "field": field, "operator": operator, "value": value}
                        for index, (field, operator, value) in enumerate(mapping or ())],
        })
    return result
