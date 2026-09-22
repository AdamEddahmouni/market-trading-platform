"""Heuristic provider-symbol linkage quality — warn without rewriting provider truth.

Semantics
---------
Flags and confidence tokens are **operator-visible suspicion / evidence-quality
signals**. They do **not**:

- declare provider metadata false as fact
- replace, drop, or invent tickers
- reject events by themselves
- change LIVE_OBSERVED vs HISTORICAL_RECONSTRUCTED gates

Unknown assessment stays ``UNKNOWN``. Missing URL is a quality signal only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .contracts import InstrumentLinkage

# Reuse NewsArticleEvent.quality_flags — same operator-visible channel as
# PUBLICATION_TIME_*. Additive tokens; not a platform-wide schema invention.
FLAG_TICKER_NOT_IN_TEXT = "PROVIDER_LINKAGE_TICKER_NOT_IN_TEXT"
FLAG_ALTERNATE_ENTITY_PROMINENT = "PROVIDER_LINKAGE_ALTERNATE_ENTITY_PROMINENT"
FLAG_SOURCE_URL_MISSING = "PROVIDER_LINKAGE_SOURCE_URL_MISSING"
FLAG_MULTIPLE_CONTRADICTORY = "PROVIDER_LINKAGE_MULTIPLE_CONTRADICTORY"
FLAG_LOW_CONTEXTUAL_CONFIDENCE = "PROVIDER_LINKAGE_LOW_CONTEXTUAL_CONFIDENCE"

CONFIDENCE_EXPLICIT = "EXPLICIT"
CONFIDENCE_PROVIDER_UNCORROBORATED = "PROVIDER_UNCORROBORATED"
CONFIDENCE_UNKNOWN = "UNKNOWN"

_STOP_TITLE_TOKENS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "for",
        "to",
        "in",
        "on",
        "at",
        "by",
        "from",
        "with",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "this",
        "that",
        "these",
        "those",
        "its",
        "their",
        "his",
        "her",
        "our",
        "your",
        "stock",
        "stocks",
        "share",
        "shares",
        "market",
        "markets",
        "earnings",
        "revenue",
        "profit",
        "loss",
        "quarter",
        "quarterly",
        "annual",
        "report",
        "reports",
        "reported",
        "update",
        "updates",
        "news",
        "today",
        "yesterday",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "inc",
        "corp",
        "ltd",
        "llc",
        "co",
        "company",
        "group",
        "holdings",
        "plc",
        "usa",
        "us",
        "nyse",
        "nasdaq",
    }
)

_CAMEL_ENTITY = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")
_TITLE_WORD = re.compile(r"\b([A-Z][a-z]{2,})\b")
_TICKER_TOKEN = re.compile(r"\b([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b")


@dataclass(frozen=True, slots=True)
class ProviderLinkageQualityAssessment:
    """Assessment attached alongside preserved provider linkages."""

    linkages: tuple[InstrumentLinkage, ...]
    quality_flags: tuple[str, ...]
    reasons: tuple[str, ...]
    association_confidence: str


def _normalize_haystack(text: str) -> str:
    return " ".join(str(text or "").upper().split())


def _symbol_token(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _ticker_lexically_present(symbol: str, haystack_upper: str) -> bool:
    token = _symbol_token(symbol)
    if not token or not haystack_upper:
        return False
    # Word-boundary match; allow optional leading $ and exchange prefix (US.NVDA).
    bare = token.split(".")[-1]
    pattern = rf"(?<![A-Z0-9])\$?(?:[A-Z]{{1,5}}\.)?{re.escape(bare)}(?![A-Z0-9])"
    return re.search(pattern, haystack_upper) is not None


def _company_name_present(name: str, haystack_upper: str) -> bool:
    cleaned = " ".join(str(name or "").upper().split())
    if len(cleaned) < 3 or not haystack_upper:
        return False
    return cleaned in haystack_upper


def _extract_company_names(raw_company_names: Iterable[str] | None) -> tuple[str, ...]:
    names: list[str] = []
    for value in raw_company_names or ():
        text = str(value or "").strip()
        if text:
            names.append(text)
    return tuple(names)


def _alternate_entity_prominent(*, headline: str, provider_symbols: set[str]) -> bool:
    """Heuristic: headline prominently names a non-ticker entity while lacking provider tickers.

    Does **not** assert identity of that entity. CamelCase or multi-word Title Case
    spans are treated as company-like surface forms only.
    """

    text = str(headline or "").strip()
    if not text:
        return False
    provider_bare = {s.split(".")[-1] for s in provider_symbols if s}

    for match in _CAMEL_ENTITY.finditer(text):
        entity = match.group(1)
        if entity.upper() in provider_bare:
            continue
        if entity.lower() in _STOP_TITLE_TOKENS:
            continue
        return True

    title_words = [m.group(1) for m in _TITLE_WORD.finditer(text)]
    kept: list[str] = []
    for word in title_words:
        if word.lower() in _STOP_TITLE_TOKENS:
            continue
        if word.upper() in provider_bare:
            continue
        kept.append(word)
    # Multi-word Title Case span (e.g. "Miller Knoll") is stronger than a lone word.
    if len(kept) >= 2:
        return True
    return False


def _headline_mentions_other_tickers(*, headline: str, provider_symbols: set[str]) -> bool:
    text = str(headline or "").upper()
    if not text:
        return False
    provider_bare = {s.split(".")[-1] for s in provider_symbols if s}
    for match in _TICKER_TOKEN.finditer(text):
        token = match.group(1)
        bare = token.split(".")[-1]
        if bare in provider_bare:
            continue
        # Ignore ultra-common short English tokens that look like tickers.
        if bare in {"A", "I", "AM", "PM", "CEO", "CFO", "CTO", "USA", "USD", "ETF"}:
            continue
        if len(bare) < 2:
            continue
        return True
    return False


def assess_provider_linkage_quality(
    *,
    headline: str,
    summary: str = "",
    url: str = "",
    linkages: tuple[InstrumentLinkage, ...] | list[InstrumentLinkage],
    company_names: Iterable[str] | None = None,
) -> ProviderLinkageQualityAssessment:
    """Assess provider linkages against available text without mutating symbols.

    Returns a new linkage tuple that may only change ``confidence``. Provider
    ``provider_symbol``, ``instrument_id``, and ``linkage_method`` are preserved.
    """

    links = tuple(linkages)
    provider_links = [
        link
        for link in links
        if str(link.linkage_method or "").upper() == "PROVIDER_SYMBOL"
        and _symbol_token(link.provider_symbol or link.instrument_id)
    ]
    flags: list[str] = []
    reasons: list[str] = []

    url_text = str(url or "").strip()
    if not url_text:
        flags.append(FLAG_SOURCE_URL_MISSING)
        reasons.append("source_url_missing:no_independent_verify_path")

    names = _extract_company_names(company_names)
    haystack = _normalize_haystack(f"{headline} {summary}")
    has_assessable_text = bool(haystack)

    if not provider_links:
        # No provider-symbol linkage to score — leave linkages untouched.
        confidence = CONFIDENCE_UNKNOWN if not has_assessable_text else CONFIDENCE_EXPLICIT
        return ProviderLinkageQualityAssessment(
            linkages=links,
            quality_flags=tuple(dict.fromkeys(flags)),
            reasons=tuple(reasons),
            association_confidence=confidence,
        )

    provider_symbols = {
        _symbol_token(link.provider_symbol or link.instrument_id) for link in provider_links
    }

    if not has_assessable_text:
        # Cannot corroborate or contradict — unknown stays unknown.
        adjusted = tuple(
            InstrumentLinkage(
                instrument_id=link.instrument_id,
                provider_symbol=link.provider_symbol,
                asset_class=link.asset_class,
                linkage_method=link.linkage_method,
                confidence=CONFIDENCE_UNKNOWN
                if str(link.linkage_method or "").upper() == "PROVIDER_SYMBOL"
                else link.confidence,
            )
            for link in links
        )
        reasons.append("association_confidence:UNKNOWN:no_assessable_text")
        return ProviderLinkageQualityAssessment(
            linkages=adjusted,
            quality_flags=tuple(dict.fromkeys(flags)),
            reasons=tuple(reasons),
            association_confidence=CONFIDENCE_UNKNOWN,
        )

    corroboration: dict[str, bool] = {}
    for symbol in provider_symbols:
        lexical = _ticker_lexically_present(symbol, haystack)
        name_hit = any(_company_name_present(name, haystack) for name in names)
        corroboration[symbol] = lexical or name_hit

    any_corroborated = any(corroboration.values())
    any_uncorroborated = any(not ok for ok in corroboration.values())

    if any_uncorroborated:
        flags.append(FLAG_TICKER_NOT_IN_TEXT)
        missing = sorted(sym for sym, ok in corroboration.items() if not ok)
        reasons.append(f"ticker_not_in_text:{','.join(missing)}")

    alternate = _alternate_entity_prominent(headline=headline, provider_symbols=provider_symbols)
    other_ticker = _headline_mentions_other_tickers(
        headline=headline, provider_symbols=provider_symbols
    )
    if (alternate or other_ticker) and any_uncorroborated:
        flags.append(FLAG_ALTERNATE_ENTITY_PROMINENT)
        if alternate:
            reasons.append("alternate_entity_prominent:company_like_span")
        if other_ticker:
            reasons.append("alternate_entity_prominent:other_ticker_token")

    if len(provider_symbols) > 1 and (
        (any_corroborated and any_uncorroborated) or not any_corroborated
    ):
        flags.append(FLAG_MULTIPLE_CONTRADICTORY)
        reasons.append(
            "multiple_provider_symbols:"
            + ",".join(sorted(provider_symbols))
            + ":corroboration_conflict_or_none"
        )

    if FLAG_TICKER_NOT_IN_TEXT in flags or FLAG_ALTERNATE_ENTITY_PROMINENT in flags:
        if FLAG_SOURCE_URL_MISSING in flags or FLAG_ALTERNATE_ENTITY_PROMINENT in flags:
            flags.append(FLAG_LOW_CONTEXTUAL_CONFIDENCE)
            reasons.append("low_contextual_confidence:uncorroborated_provider_linkage")

    adjusted_links: list[InstrumentLinkage] = []
    for link in links:
        symbol = _symbol_token(link.provider_symbol or link.instrument_id)
        is_provider = str(link.linkage_method or "").upper() == "PROVIDER_SYMBOL" and bool(symbol)
        if not is_provider:
            adjusted_links.append(link)
            continue
        if corroboration.get(symbol, False):
            confidence = CONFIDENCE_EXPLICIT
        else:
            confidence = CONFIDENCE_PROVIDER_UNCORROBORATED
        adjusted_links.append(
            InstrumentLinkage(
                instrument_id=link.instrument_id,
                provider_symbol=link.provider_symbol,
                asset_class=link.asset_class,
                linkage_method=link.linkage_method,
                confidence=confidence,
            )
        )

    if any_corroborated and not any_uncorroborated:
        association = CONFIDENCE_EXPLICIT
    elif any_uncorroborated:
        association = CONFIDENCE_PROVIDER_UNCORROBORATED
    else:
        association = CONFIDENCE_UNKNOWN

    return ProviderLinkageQualityAssessment(
        linkages=tuple(adjusted_links),
        quality_flags=tuple(dict.fromkeys(flags)),
        reasons=tuple(reasons),
        association_confidence=association,
    )


def company_names_from_raw(item: dict[str, Any]) -> tuple[str, ...]:
    """Pull optional company/issuer labels from raw provider payloads when present."""

    names: list[str] = []
    for key in ("company_name", "company", "issuer_name", "issuer"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            names.append(value.strip())
    multi = item.get("company_names") or item.get("companies") or []
    if isinstance(multi, list):
        for value in multi:
            if isinstance(value, str) and value.strip():
                names.append(value.strip())
    return tuple(dict.fromkeys(names))


__all__ = [
    "CONFIDENCE_EXPLICIT",
    "CONFIDENCE_PROVIDER_UNCORROBORATED",
    "CONFIDENCE_UNKNOWN",
    "FLAG_ALTERNATE_ENTITY_PROMINENT",
    "FLAG_LOW_CONTEXTUAL_CONFIDENCE",
    "FLAG_MULTIPLE_CONTRADICTORY",
    "FLAG_SOURCE_URL_MISSING",
    "FLAG_TICKER_NOT_IN_TEXT",
    "ProviderLinkageQualityAssessment",
    "assess_provider_linkage_quality",
    "company_names_from_raw",
]
