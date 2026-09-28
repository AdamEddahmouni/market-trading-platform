"""Provider-neutral filters for the current US-equity Screener snapshot."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from ..discovery.screens import SCREEN_LIBRARY

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
)
_CATALOG = {
    field: {"field": field, "label": label, "category": category, "type": kind,
            "unit": unit, "operators": list(NUMERIC_OPERATORS if kind == "number" else TEXT_OPERATORS),
            "universes": ["US_EQUITIES"], "availability": "SNAPSHOT"}
    for field, label, category, kind, unit in _FIELDS
}


def filter_catalog() -> list[dict[str, Any]]:
    return deepcopy(list(_CATALOG.values()))


def validate_filters(raw: Any) -> list[dict[str, Any]]:
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


def _matches(row: dict[str, Any], rule: dict[str, Any]) -> bool:
    field, operator, wanted = rule["field"], rule["operator"], rule["value"]
    observed = row.get(field) if _CATALOG[field]["type"] == "text" else row.get("fields", {}).get(field, {}).get("value")
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


def apply_filters(rows: list[dict[str, Any]], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if all(_matches(row, rule) for rule in rules)]


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
            "version": screen.version, "status": "SUPPORTED" if mapping is not None else "UNSUPPORTED",
            "reason": None if mapping is not None else "Existing discovery condition is absent from the current broad Screener contract",
            "filters": [{"id": f"{screen_id.lower()}-{index}", "field": field, "operator": operator, "value": value}
                        for index, (field, operator, value) in enumerate(mapping or ())],
        })
    return result
