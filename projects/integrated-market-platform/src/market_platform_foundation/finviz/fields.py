"""Machine-readable Finviz field inventory and classification."""

from __future__ import annotations

from enum import Enum
from typing import Any

from .authority import authority_for_field


class FieldCategory(str, Enum):
    IDENTITY = "IDENTITY"
    PRICE = "PRICE"
    VOLUME = "VOLUME"
    FLOAT = "FLOAT"
    SHORT = "SHORT"
    FUNDAMENTAL = "FUNDAMENTAL"
    VALUATION = "VALUATION"
    GROWTH = "GROWTH"
    PROFITABILITY = "PROFITABILITY"
    BALANCE_SHEET = "BALANCE_SHEET"
    OWNERSHIP = "OWNERSHIP"
    ANALYST = "ANALYST"
    EARNINGS = "EARNINGS"
    TECHNICAL = "TECHNICAL"
    PERFORMANCE = "PERFORMANCE"
    NEWS = "NEWS"
    INSIDER = "INSIDER"
    OPTIONS = "OPTIONS"
    ETF = "ETF"
    GROUP = "GROUP"
    OTHER = "OTHER"


SCREENER_FIELD_MAP: dict[str, dict[str, Any]] = {
    "Ticker": {
        "category": FieldCategory.IDENTITY,
        "canonical": "instrument_id",
        "unit": "symbol",
        "pit_suitability": "CURRENT_ONLY",
        "lanes": ["DISCOVERY"],
    },
    "Company": {"category": FieldCategory.IDENTITY, "canonical": "company_name", "unit": "text"},
    "Sector": {"category": FieldCategory.GROUP, "canonical": "sector", "unit": "text", "lanes": ["MARKET_CONTEXT"]},
    "Industry": {"category": FieldCategory.GROUP, "canonical": "industry", "unit": "text", "lanes": ["MARKET_CONTEXT"]},
    "Price": {"category": FieldCategory.PRICE, "canonical": "price", "unit": "USD", "lanes": ["DISCOVERY"]},
    "Change": {"category": FieldCategory.PRICE, "canonical": "change_pct", "unit": "percent", "lanes": ["DISCOVERY"]},
    "Volume": {"category": FieldCategory.VOLUME, "canonical": "volume", "unit": "shares", "lanes": ["DISCOVERY"]},
    "Average Volume": {"category": FieldCategory.VOLUME, "canonical": "avg_volume", "unit": "shares"},
    "Relative Volume": {
        "category": FieldCategory.VOLUME,
        "canonical": "rel_volume",
        "unit": "ratio",
        "lanes": ["DISCOVERY", "SHORT_SQUEEZE"],
        "pit_suitability": "PROSPECTIVE_CAPTURE_REQUIRED",
    },
    "Market Cap.": {"category": FieldCategory.FUNDAMENTAL, "canonical": "market_cap", "unit": "USD"},
    "Shares Out.": {"category": FieldCategory.FLOAT, "canonical": "shares_outstanding", "unit": "shares"},
    "Shares Float": {
        "category": FieldCategory.FLOAT,
        "canonical": "float_shares",
        "unit": "shares",
        "lanes": ["SHORT_SQUEEZE", "SHORT_INTELLIGENCE"],
        "authority_note": "FINVIZ_SHORT_FLOAT",
    },
    "Short Float": {
        "category": FieldCategory.SHORT,
        "canonical": "short_float_pct",
        "unit": "percent",
        "lanes": ["SHORT_SQUEEZE", "DISCOVERY"],
        "authority_note": "FINVIZ_SHORT_FLOAT",
        "pit_suitability": "PROSPECTIVE_CAPTURE_REQUIRED",
    },
    "Short Ratio": {
        "category": FieldCategory.SHORT,
        "canonical": "short_ratio",
        "unit": "days",
        "lanes": ["SHORT_SQUEEZE"],
        "authority_note": "FINVIZ_SHORT_FLOAT",
    },
    "EPS ttm": {"category": FieldCategory.EARNINGS, "canonical": "eps_ttm", "unit": "USD"},
    "P/E": {"category": FieldCategory.VALUATION, "canonical": "pe", "unit": "ratio"},
    "Fwd P/E": {"category": FieldCategory.VALUATION, "canonical": "fwd_pe", "unit": "ratio"},
    "RSI (14)": {"category": FieldCategory.TECHNICAL, "canonical": "rsi_14", "unit": "index", "lanes": ["DISCOVERY"]},
    "Earnings": {"category": FieldCategory.EARNINGS, "canonical": "earnings_date", "unit": "date"},
    "Perf Week": {"category": FieldCategory.PERFORMANCE, "canonical": "perf_week", "unit": "percent"},
    "Recommendation": {"category": FieldCategory.ANALYST, "canonical": "recommendation", "unit": "text"},
}


OPTIONS_FIELD_HINTS: dict[str, FieldCategory] = {
    "contract": FieldCategory.OPTIONS,
    "strike": FieldCategory.OPTIONS,
    "expiry": FieldCategory.OPTIONS,
    "expiration": FieldCategory.OPTIONS,
    "bid": FieldCategory.OPTIONS,
    "ask": FieldCategory.OPTIONS,
    "volume": FieldCategory.VOLUME,
    "openint": FieldCategory.OPTIONS,
    "openinterest": FieldCategory.OPTIONS,
    "iv": FieldCategory.OPTIONS,
    "delta": FieldCategory.OPTIONS,
    "gamma": FieldCategory.OPTIONS,
    "theta": FieldCategory.OPTIONS,
    "vega": FieldCategory.OPTIONS,
    "type": FieldCategory.OPTIONS,
}


def classify_screener_columns(columns: list[str]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for name in columns:
        meta = SCREENER_FIELD_MAP.get(name, {"category": FieldCategory.OTHER, "canonical": None})
        category = meta.get("category", FieldCategory.OTHER)
        family = "short_float_discovery" if category == FieldCategory.SHORT else "broad_screening"
        auth = authority_for_field(family)
        inventory.append(
            {
                "finviz_field": name,
                "category": str(category.value if isinstance(category, FieldCategory) else category),
                "canonical_mapping": meta.get("canonical"),
                "unit": meta.get("unit"),
                "source_authority_label": auth.get("authority"),
                "research_lanes": meta.get("lanes", []),
                "pit_suitability": meta.get("pit_suitability", "CURRENT_ONLY"),
                "authority_note": meta.get("authority_note"),
            }
        )
    return inventory


def classify_options_columns(columns: list[str]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for name in columns:
        normalized = "".join(ch for ch in name.lower() if ch.isalnum())
        category = FieldCategory.OPTIONS
        for hint, cat in OPTIONS_FIELD_HINTS.items():
            if hint in normalized:
                category = cat
                break
        inventory.append(
            {
                "finviz_field": name,
                "category": category.value,
                "canonical_mapping": normalized,
                "provider_authority": "FINVIZ_ELITE",
                "pit_suitability": "CURRENT_ONLY",
            }
        )
    return inventory


def field_inventory_summary(columns: list[str]) -> dict[str, Any]:
    classified = classify_screener_columns(columns)
    categories: dict[str, int] = {}
    for row in classified:
        cat = row["category"]
        categories[cat] = categories.get(cat, 0) + 1
    return {
        "field_count": len(columns),
        "categories": categories,
        "fields": classified,
    }
