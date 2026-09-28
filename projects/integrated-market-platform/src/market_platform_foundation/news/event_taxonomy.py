"""Deterministic event categories for Screener news (S11).

Categories are DERIVED from headline/summary language with whole-word patterns;
they describe what a story is about, never how a price will react. Corporate and
regulatory keywords are the canonical ``CatalystRegistry`` entries; the macro
families are adapted from the Claude Code News donor's measured KEEP tables
(``news/live/focus.mjs``) and extended with rates/Treasury and crypto families
so Futures, Bonds, and Crypto have honest coverage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .catalysts import DEFAULT_CATALYST_REGISTRY

TAXONOMY_VERSION = "news/event-taxonomy/1.0.0"
METHOD = ("Keyword taxonomy: whole-word headline/summary patterns per category "
          f"({TAXONOMY_VERSION}); a story can carry several categories.")


@dataclass(frozen=True, slots=True)
class EventCategory:
    id: str
    label: str
    group: str  # CORPORATE | REGULATORY | MACRO | CRYPTO | FILING
    patterns: tuple[str, ...]

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "group": self.group}


def _words(*terms: str) -> tuple[str, ...]:
    return tuple(rf"\b{re.escape(term)}\b" for term in terms)


# Canonical catalyst keywords, grouped by the registry's own category. Generic
# single words that collide with ordinary prose ("approval", "executive",
# "merge", "forecast") stay only in their unambiguous multi-word forms.
_CATALYST_OVERRIDES: dict[str, tuple[str, ...]] = {
    "approval": ("fda approval", "regulatory approval", "wins approval", "receives approval"),
    "management": ("ceo", "cfo", "chief executive", "steps down", "resigns", "management change"),
    "merger": ("merger", "merger agreement", "to merge"),
    "guidance": ("guidance", "raises outlook", "cuts outlook", "lowers outlook", "full-year outlook"),
    "supply": ("supply disruption", "supply chain"),
}
_MACRO_CATALYSTS = frozenset({"rate_decision", "cpi", "payroll", "inventory", "opec", "central_bank", "production"})

_CORPORATE: list[EventCategory] = []
for _entry in DEFAULT_CATALYST_REGISTRY:
    if _entry.catalyst_id in _MACRO_CATALYSTS:
        continue  # replaced by the richer macro families below
    _terms = _CATALYST_OVERRIDES.get(_entry.catalyst_id, _entry.terms)
    _CORPORATE.append(EventCategory(f"catalyst.{_entry.catalyst_id}", _entry.display_name,
                                    "REGULATORY" if _entry.category == "REGULATORY" else "CORPORATE", _words(*_terms)))

MACRO: tuple[EventCategory, ...] = (
    EventCategory("macro.fed_policy", "Fed / monetary policy", "MACRO", _words(
        "fed", "federal reserve", "fomc", "powell", "rate hike", "rate hikes", "rate cut", "rate cuts",
        "interest rates", "basis points", "hawkish", "dovish", "monetary policy", "rate path", "fed funds",
        "waller", "williams", "kashkari", "bostic", "jefferson", "barr", "bowman", "goolsbee", "logan")),
    EventCategory("macro.inflation", "Inflation", "MACRO", _words(
        "inflation", "cpi", "consumer price index", "ppi", "producer price index", "pce", "core pce",
        "deflation", "disinflation", "stagflation")),
    EventCategory("macro.labor", "Labor market", "MACRO", _words(
        "payrolls", "nonfarm payrolls", "jobless claims", "unemployment", "jobs report", "adp", "jolts",
        "labor market", "wage growth")),
    EventCategory("macro.growth", "Growth / activity", "MACRO", _words(
        "gdp", "recession", "consumer confidence", "retail sales", "ism", "pmi", "industrial production",
        "consumer sentiment")),
    EventCategory("macro.rates_treasury", "Treasuries / rates", "MACRO", _words(
        "treasury", "treasuries", "treasury yields", "bond yields", "yields", "10-year", "2-year", "30-year",
        "yield curve", "bond market", "treasury auction", "note auction", "bond auction", "bill auction",
        "debt ceiling", "t-bills")),
    EventCategory("macro.dollar_fx", "Dollar / FX", "MACRO", _words(
        "dollar index", "dxy", "u.s. dollar", "greenback", "yen", "euro", "ecb", "boj", "bank of japan",
        "bank of england", "boe")),
    EventCategory("macro.energy", "Energy / oil & gas", "MACRO", _words(
        "oil", "crude", "wti", "brent", "opec", "opec+", "natural gas", "lng", "gasoline", "crude inventories",
        "eia", "refinery", "production cut", "hormuz")),
    EventCategory("macro.metals", "Metals", "MACRO", _words("gold", "silver", "copper", "platinum", "palladium")),
    EventCategory("macro.agriculture", "Agriculture / weather", "MACRO", _words(
        "corn", "soybeans", "wheat", "crop", "usda", "drought", "harvest", "hurricane", "el nino")),
    EventCategory("macro.trade_policy", "Trade policy", "MACRO", _words(
        "tariff", "tariffs", "trade war", "trade deal", "sanctions", "export controls", "import duties")),
    EventCategory("macro.geopolitical", "Geopolitical", "MACRO", _words(
        "war", "missile", "missiles", "ceasefire", "invasion", "airstrike", "airstrikes", "military strike",
        "escalation", "geopolitical")),
    EventCategory("macro.equity_index", "Index / broad market", "MACRO", _words(
        "s&p 500", "nasdaq", "dow jones", "russell 2000", "stock market", "wall street", "stock futures",
        "equity futures", "vix", "sell-off", "selloff", "record high")),
)

CRYPTO: tuple[EventCategory, ...] = (
    EventCategory("crypto.regulation", "Crypto regulation", "CRYPTO", _words(
        "sec", "cftc", "stablecoin bill", "crypto bill", "crypto regulation", "mica", "enforcement action",
        "wells notice", "genius act", "clarity act")),
    EventCategory("crypto.etf", "Crypto ETF / fund flows", "CRYPTO", _words(
        "spot bitcoin etf", "bitcoin etf", "ether etf", "ethereum etf", "solana etf", "etf inflows",
        "etf outflows", "grayscale", "ibit")),
    EventCategory("crypto.exchange", "Exchange / venue event", "CRYPTO", _words(
        "exchange hack", "hack", "hacked", "exploit", "outage", "delisting", "delists", "listing",
        "withdrawals halted", "insolvency", "kraken", "coinbase", "binance")),
    EventCategory("crypto.protocol", "Protocol / network", "CRYPTO", _words(
        "halving", "hard fork", "upgrade", "mainnet", "staking", "validator", "network upgrade", "layer 2")),
)

FILING = EventCategory("filing.sec", "SEC filing", "FILING", ())

CATEGORIES: tuple[EventCategory, ...] = (*_CORPORATE, *MACRO, *CRYPTO, FILING)
_BY_ID = {category.id: category for category in CATEGORIES}
_COMPILED = tuple((category, re.compile("|".join(category.patterns), re.IGNORECASE))
                  for category in CATEGORIES if category.patterns)


def category(category_id: str) -> EventCategory | None:
    return _BY_ID.get(category_id)


def classify_text(headline: str, summary: str = "", *, groups: frozenset[str] | None = None) -> tuple[EventCategory, ...]:
    """Categories whose whole-word patterns occur in the headline or summary."""

    text = f"{headline or ''}\n{summary or ''}"
    if not text.strip():
        return ()
    found = []
    for item, pattern in _COMPILED:
        if groups is not None and item.group not in groups:
            continue
        if pattern.search(text):
            found.append(item)
    return tuple(found)


__all__ = ["CATEGORIES", "CRYPTO", "EventCategory", "FILING", "MACRO", "METHOD", "TAXONOMY_VERSION",
           "category", "classify_text"]
