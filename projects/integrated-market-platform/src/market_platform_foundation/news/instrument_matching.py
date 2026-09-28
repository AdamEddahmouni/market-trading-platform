"""Cross-universe news-to-instrument association with an explicit match basis (S11).

Each universe matches by the identity it actually has — no Equity ticker
heuristic is applied universally:

* US Equities: provider ticker tags, cashtags / exchange-qualified tickers,
  company name (entity), SEC CIK for official filings.
* ETFs: provider ticker tags, fund name, and a small explicit underlying-theme
  map (context only).
* Futures: contract root → underlying concept (index, energy, metals, rates,
  FX, grains, crypto) plus macro-category context.
* Bonds: CUSIP, then issuer-level Treasury / rates / Fed context. Issuer
  relevance is never promoted to instrument-specific materiality.
* Crypto: asset name, pair notation, cashtag, provider tags, and the venue.
  Bare symbols such as ``SOL`` collide with ordinary words and other tickers
  and are only ever ``AMBIGUOUS``.

Confidence is ``EXACT`` (identity evidence), ``CONTEXT`` (topic/underlying/
issuer relevance), or ``AMBIGUOUS`` (collision-prone evidence). Ambiguous
evidence never makes a story "news for this instrument" on its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

MATCHING_VERSION = "news/instrument-matching/1.0.0"

EXACT = "EXACT"
CONTEXT = "CONTEXT"
AMBIGUOUS = "AMBIGUOUS"
_RANK = {EXACT: 0, CONTEXT: 1, AMBIGUOUS: 2}

US_EQUITIES, US_ETFS, FUTURES, BONDS, CRYPTO = "US_EQUITIES", "US_ETFS", "FUTURES", "BONDS", "CRYPTO"


@dataclass(frozen=True, slots=True)
class MatchResult:
    instrument_id: str | None
    symbol: str
    basis: str
    confidence: str
    term: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"instrument_id": self.instrument_id, "symbol": self.symbol, "basis": self.basis,
                "confidence": self.confidence, "term": self.term}


@dataclass(frozen=True, slots=True)
class _Rule:
    pattern: re.Pattern[str]
    basis: str
    confidence: str
    term: str
    case_sensitive: bool = False


@dataclass(frozen=True, slots=True)
class InstrumentProfile:
    """How one instrument is recognised in news. ``terms`` is shown to the operator."""

    universe: str
    instrument_id: str
    symbol: str
    label: str
    provider_tickers: frozenset[str] = frozenset()
    rules: tuple[_Rule, ...] = ()
    context_categories: frozenset[str] = frozenset()
    category_basis: str = "MACRO_CONTEXT"
    cik: str | None = None
    capability: str = "SUPPORTED"
    capability_reason: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def match_bases(self) -> list[str]:
        bases = {rule.basis for rule in self.rules}
        if self.provider_tickers:
            bases.add("PROVIDER_TICKER")
        if self.context_categories:
            bases.add(self.category_basis)
        if self.cik:
            bases.add("EXACT_ENTITY")
        return sorted(bases)

    @property
    def terms(self) -> list[str]:
        return sorted({rule.term for rule in self.rules} | set(self.provider_tickers))


def _word(term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w$]){re.escape(term)}(?![\w])", re.IGNORECASE)


def _exact_ticker_rules(symbol: str) -> list[_Rule]:
    ticker = re.escape(symbol.upper())
    rules = [
        _Rule(re.compile(rf"\${ticker}\b"), "EXACT_TICKER", EXACT, f"${symbol.upper()}", True),
        _Rule(re.compile(rf"\((?:(?:NASDAQ|NYSE|NYSEARCA|NYSE ARCA|AMEX|NYSEAMERICAN|CBOE|BATS)\s*:\s*)?{ticker}\)"),
              "EXACT_TICKER", EXACT, f"({symbol.upper()})", True),
        _Rule(re.compile(rf"\b(?:NASDAQ|NYSE|NYSEARCA|AMEX|CBOE)\s*:\s*{ticker}\b"), "EXACT_TICKER", EXACT,
              f"exchange:{symbol.upper()}", True),
    ]
    if len(symbol) >= 2:
        # A bare uppercase ticker is collision-prone (e.g. "ALL", "IT", "ON").
        rules.append(_Rule(re.compile(rf"(?<![\w$]){ticker}(?![\w])"), "AMBIGUOUS", AMBIGUOUS, symbol.upper(), True))
    return rules


_CORPORATE_SUFFIX = re.compile(
    r"[,.]?\s+(?:inc|incorporated|corp|corporation|co|company|ltd|limited|plc|holdings?|group|class [a-z]|"
    r"n\.?v|s\.?a|ag|se|lp|l\.?p|llc|the)\.?$", re.IGNORECASE)
_GENERIC_NAMES = frozenset({"target", "block", "general", "american", "united", "first",
                            "global", "international", "national", "energy", "capital", "financial", "digital"})


def entity_name(company: str | None) -> str | None:
    """Company name stripped of corporate suffixes; None when too generic to identify alone."""

    name = (company or "").strip()
    if not name:
        return None
    previous = None
    while previous != name:
        previous = name
        name = _CORPORATE_SUFFIX.sub("", name).strip()
    return name or None


def _entity_rules(company: str | None) -> list[_Rule]:
    name = entity_name(company)
    if not name or len(name) < 3:
        return []
    words = name.split()
    # One common word ("Apple", "Target") is a real-world collision: context-level only.
    confidence = EXACT if len(words) >= 2 or (len(name) >= 5 and name.lower() not in _GENERIC_NAMES) else AMBIGUOUS
    basis = "EXACT_ENTITY" if confidence == EXACT else "AMBIGUOUS"
    rules = [_Rule(_word(name), basis, confidence, name)]
    if len(words) >= 2 and words[0].lower() not in _GENERIC_NAMES and len(words[0]) >= 5:
        # "Nvidia" for "NVIDIA Corp" is caught above; "Tesla" for "Tesla Motors" here — context only.
        rules.append(_Rule(_word(words[0]), "EXACT_ENTITY", CONTEXT, words[0]))
    return rules


# ETFs: explicit, auditable underlying themes for widely held funds only.
ETF_THEMES: dict[str, tuple[str, ...]] = {
    "SPY": ("s&p 500",), "IVV": ("s&p 500",), "VOO": ("s&p 500",), "SPLG": ("s&p 500",),
    "QQQ": ("nasdaq 100", "nasdaq-100"), "QQQM": ("nasdaq 100", "nasdaq-100"),
    "DIA": ("dow jones industrial average", "dow jones"), "IWM": ("russell 2000",),
    "TLT": ("treasury", "treasuries", "30-year", "long bond"), "IEF": ("treasury", "treasuries", "10-year"),
    "SHY": ("treasury", "treasuries", "2-year"), "GOVT": ("treasury", "treasuries"),
    "GLD": ("gold",), "IAU": ("gold",), "SLV": ("silver",), "USO": ("crude", "oil"), "UNG": ("natural gas",),
    "XLE": ("energy stocks", "oil"), "XLF": ("bank stocks", "banks"), "SMH": ("semiconductor", "chip stocks"),
    "IBIT": ("bitcoin",), "FBTC": ("bitcoin",), "GBTC": ("bitcoin",), "ETHA": ("ether", "ethereum"),
    "HYG": ("high-yield", "junk bond"), "LQD": ("investment-grade", "corporate bond"),
}
ETF_THEME_CATEGORIES: dict[str, frozenset[str]] = {
    "TLT": frozenset({"macro.rates_treasury", "macro.fed_policy", "macro.inflation"}),
    "IEF": frozenset({"macro.rates_treasury", "macro.fed_policy", "macro.inflation"}),
    "SHY": frozenset({"macro.rates_treasury", "macro.fed_policy"}),
    "GOVT": frozenset({"macro.rates_treasury", "macro.fed_policy"}),
    "SPY": frozenset({"macro.equity_index"}), "IVV": frozenset({"macro.equity_index"}), "VOO": frozenset({"macro.equity_index"}),
    "QQQ": frozenset({"macro.equity_index"}), "DIA": frozenset({"macro.equity_index"}), "IWM": frozenset({"macro.equity_index"}),
    "GLD": frozenset({"macro.metals"}), "IAU": frozenset({"macro.metals"}), "SLV": frozenset({"macro.metals"}),
    "USO": frozenset({"macro.energy"}), "UNG": frozenset({"macro.energy"}),
}

# Futures: root → (underlying terms, macro categories that are context for it).
FUTURES_UNDERLYINGS: dict[str, tuple[tuple[str, ...], frozenset[str]]] = {}
_EQUITY_MACRO = frozenset({"macro.fed_policy", "macro.inflation", "macro.labor", "macro.growth", "macro.equity_index",
                           "macro.trade_policy", "macro.geopolitical"})
_RATES_MACRO = frozenset({"macro.fed_policy", "macro.inflation", "macro.labor", "macro.rates_treasury", "macro.growth"})
_ENERGY_MACRO = frozenset({"macro.energy", "macro.geopolitical"})
for _roots, _terms, _cats in (
    (("ES", "MES"), ("s&p 500", "s&p", "stock futures", "equity futures"), _EQUITY_MACRO),
    (("NQ", "MNQ"), ("nasdaq 100", "nasdaq-100", "nasdaq", "tech stocks"), _EQUITY_MACRO),
    (("YM", "MYM"), ("dow jones", "the dow", "dow futures"), _EQUITY_MACRO),
    (("RTY", "M2K"), ("russell 2000", "small caps", "small-cap"), _EQUITY_MACRO),
    (("CL", "MCL", "QM"), ("crude", "oil", "wti", "opec", "opec+", "crude inventories"), _ENERGY_MACRO),
    (("BZ",), ("brent", "crude", "oil", "opec"), _ENERGY_MACRO),
    (("NG", "QG"), ("natural gas", "lng"), frozenset({"macro.energy"})),
    (("RB",), ("gasoline", "refinery"), frozenset({"macro.energy"})),
    (("HO",), ("heating oil", "diesel", "distillate"), frozenset({"macro.energy"})),
    (("GC", "MGC"), ("gold",), frozenset({"macro.metals", "macro.fed_policy", "macro.dollar_fx", "macro.geopolitical"})),
    (("SI", "SIL"), ("silver",), frozenset({"macro.metals"})),
    (("HG", "MHG"), ("copper",), frozenset({"macro.metals", "macro.growth"})),
    (("PL",), ("platinum",), frozenset({"macro.metals"})),
    (("PA",), ("palladium",), frozenset({"macro.metals"})),
    (("ZN", "TN"), ("10-year", "treasury", "treasuries", "treasury yields", "note auction"), _RATES_MACRO),
    (("ZB", "UB"), ("30-year", "long bond", "treasury", "treasuries", "bond auction"), _RATES_MACRO),
    (("ZF",), ("5-year", "treasury", "treasuries"), _RATES_MACRO),
    (("ZT",), ("2-year", "treasury", "treasuries"), _RATES_MACRO),
    (("SR3", "ZQ"), ("fed funds", "sofr", "rate cut", "rate hike"), _RATES_MACRO),
    (("6E", "M6E"), ("euro", "ecb", "eurozone"), frozenset({"macro.dollar_fx"})),
    (("6J",), ("yen", "boj", "bank of japan"), frozenset({"macro.dollar_fx"})),
    (("6B",), ("pound", "sterling", "bank of england", "boe"), frozenset({"macro.dollar_fx"})),
    (("6C",), ("canadian dollar", "loonie", "bank of canada"), frozenset({"macro.dollar_fx"})),
    (("6A",), ("australian dollar", "rba"), frozenset({"macro.dollar_fx"})),
    (("DX",), ("dollar index", "dxy", "u.s. dollar"), frozenset({"macro.dollar_fx", "macro.fed_policy"})),
    (("ZC", "XC"), ("corn",), frozenset({"macro.agriculture"})),
    (("ZS", "XK"), ("soybeans", "soybean"), frozenset({"macro.agriculture"})),
    (("ZW", "XW"), ("wheat",), frozenset({"macro.agriculture"})),
    (("LE",), ("live cattle", "cattle"), frozenset({"macro.agriculture"})),
    (("HE",), ("lean hogs", "hogs"), frozenset({"macro.agriculture"})),
    (("BTC", "MBT", "BFF"), ("bitcoin",), frozenset({"crypto.regulation", "crypto.etf"})),
    (("ETH", "MET"), ("ether", "ethereum"), frozenset({"crypto.regulation", "crypto.etf"})),
    (("VX", "VXM"), ("vix", "volatility index"), frozenset({"macro.equity_index"})),
):
    for _root in _roots:
        FUTURES_UNDERLYINGS[_root] = (_terms, _cats)

# Crypto: base asset → names. Only assets with an unambiguous public name.
CRYPTO_ASSET_NAMES: dict[str, tuple[str, ...]] = {
    "BTC": ("bitcoin",), "XBT": ("bitcoin",), "ETH": ("ethereum", "ether"), "SOL": ("solana",),
    "XRP": ("xrp", "ripple"), "ADA": ("cardano",), "DOGE": ("dogecoin",), "XDG": ("dogecoin",),
    "DOT": ("polkadot",), "LTC": ("litecoin",), "AVAX": ("avalanche",), "LINK": ("chainlink",),
    "USDT": ("tether",), "USDC": ("usd coin", "usdc"), "POL": ("polygon",), "MATIC": ("polygon",),
    "TRX": ("tron",), "BCH": ("bitcoin cash",), "XLM": ("stellar",), "ATOM": ("cosmos",),
    "UNI": ("uniswap",), "SHIB": ("shiba inu",), "XMR": ("monero",), "ETC": ("ethereum classic",),
    "FIL": ("filecoin",), "NEAR": ("near protocol",), "APT": ("aptos",), "ARB": ("arbitrum",),
    "OP": ("optimism",), "SUI": ("sui",), "TON": ("toncoin",), "PEPE": ("pepe",), "AAVE": ("aave",),
    "ALGO": ("algorand",), "HBAR": ("hedera",), "ICP": ("internet computer",), "XTZ": ("tezos",),
}
# Longer names that contain a shorter asset's name ("bitcoin cash" ⊃ "bitcoin").
_CRYPTO_SUPERSTRINGS: dict[str, tuple[str, ...]] = {
    "bitcoin": ("bitcoin cash", "bitcoin sv"), "ethereum": ("ethereum classic",), "ether": ("ethereum",),
}
CRYPTO_SECTOR_TERMS = ("crypto", "cryptocurrency", "cryptocurrencies", "digital assets", "digital asset",
                       "stablecoin", "stablecoins", "defi")
# Sector-wide categories only: ETF-flow stories name a specific asset and are matched by name, never by category.
CRYPTO_CONTEXT_CATEGORIES = frozenset({"crypto.regulation", "crypto.exchange"})
TREASURY_TERMS = ("treasury", "treasuries", "t-bill", "t-bills", "treasury auction", "u.s. government debt",
                  "treasury yields", "treasury market")
BOND_CONTEXT_CATEGORIES = frozenset({"macro.rates_treasury", "macro.fed_policy", "macro.inflation"})


def _name_rule(name: str, basis: str, confidence: str) -> _Rule:
    blockers = _CRYPTO_SUPERSTRINGS.get(name.lower(), ())
    lookahead = "".join(rf"(?!{re.escape(blocker[len(name):])})" for blocker in blockers if blocker.startswith(name.lower()))
    pattern = re.compile(rf"(?<![\w$]){re.escape(name)}(?![\w]){lookahead}", re.IGNORECASE)
    return _Rule(pattern, basis, confidence, name)


def profile_for_row(universe: str, row: dict[str, Any]) -> InstrumentProfile:
    instrument = row.get("instrument") or {}
    instrument_id = str(instrument.get("instrument_id") or row.get("instrument_id") or "")
    symbol = str(row.get("symbol") or "")
    label = str(row.get("company") or row.get("description") or symbol)
    if universe == US_EQUITIES:
        rules = [*_exact_ticker_rules(symbol), *_entity_rules(row.get("company"))]
        return InstrumentProfile(universe, instrument_id, symbol, label, frozenset({symbol.upper()}), tuple(rules),
                                 cik=str(row.get("cik")) if row.get("cik") else None)
    if universe == US_ETFS:
        rules = [*_exact_ticker_rules(symbol), *_entity_rules(row.get("company"))]
        rules += [_Rule(_word(term), "UNDERLYING_MATCH", CONTEXT, term) for term in ETF_THEMES.get(symbol.upper(), ())]
        return InstrumentProfile(universe, instrument_id, symbol, label, frozenset({symbol.upper()}), tuple(rules),
                                 context_categories=ETF_THEME_CATEGORIES.get(symbol.upper(), frozenset()),
                                 category_basis="UNDERLYING_MATCH")
    if universe == FUTURES:
        root = str(row.get("root") or "").upper()
        terms, categories = FUTURES_UNDERLYINGS.get(root, ((), frozenset()))
        rules = [_Rule(_word(term), "UNDERLYING_MATCH", CONTEXT, term) for term in terms]
        rules.append(_Rule(re.compile(rf"(?<![\w$]){re.escape(symbol)}(?![\w])"), "EXACT_TICKER", EXACT, symbol, True))
        capability, reason = ("SUPPORTED", None) if terms else ("PARTIAL", "UNDERLYING_NOT_MAPPED")
        return InstrumentProfile(universe, instrument_id, symbol, label, frozenset(), tuple(rules),
                                 context_categories=categories, capability=capability, capability_reason=reason,
                                 notes=("Futures news is underlying/macro context, not contract-specific reporting.",))
    if universe == BONDS:
        cusip = str(row.get("cusip") or instrument.get("cusip") or "").upper()
        rules = [_Rule(re.compile(rf"\b{re.escape(cusip)}\b"), "EXACT_CUSIP", EXACT, cusip, True)] if cusip else []
        rules += [_Rule(_word(term), "ISSUER_MATCH", CONTEXT, term) for term in TREASURY_TERMS]
        term = str(row.get("term") or "")
        tenor = re.match(r"(\d+)-(Year|Week)", term)
        if tenor:
            text = f"{tenor.group(1)}-{tenor.group(2).lower()}"
            rules.append(_Rule(_word(text), "ISSUER_MATCH", CONTEXT, text))
        return InstrumentProfile(universe, instrument_id, symbol, label, frozenset(), tuple(rules),
                                 context_categories=BOND_CONTEXT_CATEGORIES, capability="PARTIAL",
                                 capability_reason="ISSUER_LEVEL_CONTEXT_ONLY",
                                 notes=("Treasury news is issuer/rates context; it is not evidence about this CUSIP.",))
    if universe == CRYPTO:
        base = str(row.get("base_asset") or "").upper()
        quote = str(row.get("quote_asset") or "").upper()
        venue = str(row.get("venue") or "")
        rules: list[_Rule] = []
        for name in CRYPTO_ASSET_NAMES.get(base, ()):
            rules.append(_name_rule(name, "ASSET_MATCH", EXACT if len(name) >= 5 else CONTEXT))
        rules.append(_Rule(re.compile(rf"\${re.escape(base)}\b"), "EXACT_TICKER", EXACT, f"${base}", True))
        rules.append(_Rule(re.compile(rf"\b{re.escape(base)}\s*[/-]\s*{re.escape(quote)}\b|\b{re.escape(base + quote)}\b",
                                      re.IGNORECASE), "PAIR_MATCH", EXACT, f"{base}/{quote}"))
        if len(base) >= 2:
            rules.append(_Rule(re.compile(rf"(?<![\w$/-]){re.escape(base)}(?![\w/-])"), "AMBIGUOUS", AMBIGUOUS, base, True))
        if venue:
            rules.append(_Rule(_word(venue.split("_")[0].title()), "VENUE_MATCH", CONTEXT, venue.split("_")[0].title()))
        rules += [_Rule(_word(term), "MACRO_CONTEXT", CONTEXT, term) for term in CRYPTO_SECTOR_TERMS]
        # Provider tags in crypto notation; the bare base symbol is never a tag match on its own.
        tags = frozenset({f"{base}USD", f"{base}-USD", f"CRYPTO:{base}", f"{base}{quote}", f"{base}-{quote}"})
        capability, reason = ("SUPPORTED", None) if CRYPTO_ASSET_NAMES.get(base) else ("PARTIAL", "ASSET_NAME_NOT_MAPPED")
        return InstrumentProfile(universe, instrument_id, symbol, label, tags, tuple(rules),
                                 context_categories=CRYPTO_CONTEXT_CATEGORIES, capability=capability,
                                 capability_reason=reason,
                                 notes=("Venue and sector news is context for the pair, not pair-specific reporting.",))
    raise ValueError(f"UNKNOWN_UNIVERSE:{universe}")


def match_profile(profile: InstrumentProfile, *, headline: str, summary: str = "", tickers: Iterable[str] = (),
                  categories: Iterable[str] = (), cik: str | None = None) -> list[MatchResult]:
    """All evidence linking one story to one instrument, strongest first (one result per basis)."""

    text = f"{headline or ''}\n{summary or ''}"
    found: dict[str, MatchResult] = {}

    def add(result: MatchResult) -> None:
        current = found.get(result.basis)
        if current is None or _RANK[result.confidence] < _RANK[current.confidence]:
            found[result.basis] = result

    tagged = {str(item).strip().upper() for item in tickers if str(item).strip()}
    for ticker in sorted(profile.provider_tickers & tagged):
        add(MatchResult(profile.instrument_id, profile.symbol, "PROVIDER_TICKER", EXACT, ticker))
    if cik and profile.cik and cik.lstrip("0") == profile.cik.lstrip("0"):
        add(MatchResult(profile.instrument_id, profile.symbol, "EXACT_ENTITY", EXACT, f"CIK {profile.cik}"))
    for rule in profile.rules:
        if rule.pattern.search(text):
            add(MatchResult(profile.instrument_id, profile.symbol, rule.basis, rule.confidence, rule.term))
    story_categories = set(categories)
    shared = sorted(story_categories & profile.context_categories)
    if shared:
        add(MatchResult(profile.instrument_id, profile.symbol, profile.category_basis, CONTEXT, shared[0]))
    return sorted(found.values(), key=lambda item: (_RANK[item.confidence], item.basis))


def is_relevant(matches: Iterable[MatchResult], *, include_context: bool = True) -> bool:
    """A story belongs to an instrument on EXACT evidence, or CONTEXT when requested; never AMBIGUOUS alone."""

    confidences = {match.confidence for match in matches}
    return EXACT in confidences or (include_context and CONTEXT in confidences)


def strongest(matches: Iterable[MatchResult]) -> str | None:
    ranked = sorted(matches, key=lambda item: _RANK[item.confidence])
    return ranked[0].confidence if ranked else None


__all__ = ["AMBIGUOUS", "BOND_CONTEXT_CATEGORIES", "CONTEXT", "CRYPTO_ASSET_NAMES", "ETF_THEMES", "EXACT",
           "FUTURES_UNDERLYINGS", "InstrumentProfile", "MATCHING_VERSION", "MatchResult", "entity_name", "is_relevant",
           "match_profile", "profile_for_row", "strongest"]
