"""Heuristic provider-symbol linkage quality — warn without rewriting provider truth.

Semantics
---------
Flags and linkage ``confidence`` are **operator-visible suspicion / evidence-quality
signals**. They do **not**:

- declare provider metadata false as fact
- replace, drop, or invent tickers
- reject events by themselves
- change LIVE_OBSERVED vs HISTORICAL_RECONSTRUCTED gates

Unknown assessment stays ``UNKNOWN``. Missing URL is a quality signal only.

Company-name corroboration uses **headline/summary surface forms** (no issuer
directory). Ordinary English words are never treated as rival tickers.
``PROVIDER_LINKAGE_ALTERNATE_ENTITY_PROMINENT`` is reserved for prominent
company-like spans that are **not** letter-consistent with the provider symbol.
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
        "fed",
        "new",
        "lineup",
    }
)

# CamelCase compounds (MillerKnoll), Title Case words (Apple), and ALL-CAPS
# issuer tokens (NVIDIA) — never treat ordinary lowercase English as tickers.
_CAMEL_ENTITY = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")
_TITLE_WORD = re.compile(r"\b([A-Z][a-z]{3,})\b")
_ALLCAPS_WORD = re.compile(r"\b([A-Z]{4,})\b")


@dataclass(frozen=True, slots=True)
class ProviderLinkageQualityAssessment:
    """Assessment attached alongside preserved provider linkages."""

    linkages: tuple[InstrumentLinkage, ...]
    quality_flags: tuple[str, ...]


def _normalize_haystack(text: str) -> str:
    return " ".join(str(text or "").upper().split())


def _symbol_token(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _letters_only(text: str) -> str:
    return "".join(ch for ch in str(text or "").upper() if "A" <= ch <= "Z")


def _ticker_lexically_present(symbol: str, haystack_upper: str) -> bool:
    token = _symbol_token(symbol)
    if not token or not haystack_upper:
        return False
    bare = token.split(".")[-1]
    pattern = rf"(?<![A-Z0-9])\$?(?:[A-Z]{{1,5}}\.)?{re.escape(bare)}(?![A-Z0-9])"
    return re.search(pattern, haystack_upper) is not None


def _ordered_subsequence(needle: str, haystack: str) -> bool:
    if not needle or not haystack:
        return False
    index = 0
    for ch in haystack:
        if index < len(needle) and ch == needle[index]:
            index += 1
    return index == len(needle)


def _ticker_consistent_with_name(symbol: str, name: str) -> bool:
    """Heuristic issuer support: ticker letters align with a company-like name.

    No issuer directory. Ordered subsequence preferred; unique-letter containment
    is a fallback for forms like AAPL/APPLE. This is corroboration, not identity.
    """

    ticker = _letters_only(_symbol_token(symbol).split(".")[-1])
    company = _letters_only(name)
    if len(ticker) < 2 or len(company) < 4:
        return False
    if _ordered_subsequence(ticker, company):
        return True
    # Unique-letter containment (AAPL ⊆ APPLE) — ticker must be meaningful length.
    if len(ticker) >= 3 and set(ticker) <= set(company):
        return True
    return False


def _extract_company_like_spans(headline: str) -> tuple[str, ...]:
    """Surface company-like spans from headline text alone."""

    text = str(headline or "").strip()
    if not text:
        return ()
    spans: list[str] = []
    for match in _CAMEL_ENTITY.finditer(text):
        entity = match.group(1)
        if entity.lower() in _STOP_TITLE_TOKENS:
            continue
        spans.append(entity)
    for match in _TITLE_WORD.finditer(text):
        word = match.group(1)
        if word.lower() in _STOP_TITLE_TOKENS:
            continue
        spans.append(word)
    for match in _ALLCAPS_WORD.finditer(text):
        word = match.group(1)
        if word.lower() in _STOP_TITLE_TOKENS:
            continue
        # Skip pure ticker-length tokens here; lexical ticker match covers those.
        if len(word) <= 5:
            continue
        spans.append(word)
    # Multi-word Title Case pairs (e.g. "Miller Knoll") as one span.
    title_words = [
        m.group(1)
        for m in _TITLE_WORD.finditer(text)
        if m.group(1).lower() not in _STOP_TITLE_TOKENS
    ]
    for left, right in zip(title_words, title_words[1:]):
        spans.append(f"{left} {right}")
    return tuple(dict.fromkeys(spans))


def _inconsistent_camel_entities(*, headline: str, symbol: str) -> tuple[str, ...]:
    """CamelCase compounds that are not letter-consistent with the provider symbol."""

    text = str(headline or "").strip()
    if not text:
        return ()
    inconsistent: list[str] = []
    for match in _CAMEL_ENTITY.finditer(text):
        entity = match.group(1)
        if entity.lower() in _STOP_TITLE_TOKENS:
            continue
        if _ticker_consistent_with_name(symbol, entity):
            continue
        inconsistent.append(entity)
    return tuple(inconsistent)


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

    Corroboration prefers ticker-token presence, then company-like spans extracted
    from the headline/summary (optional raw ``company_names`` are supplemental only).
    """

    links = tuple(linkages)
    provider_links = [
        link
        for link in links
        if str(link.linkage_method or "").upper() == "PROVIDER_SYMBOL"
        and _symbol_token(link.provider_symbol or link.instrument_id)
    ]
    flags: list[str] = []

    url_text = str(url or "").strip()
    if not url_text:
        flags.append(FLAG_SOURCE_URL_MISSING)

    haystack = _normalize_haystack(f"{headline} {summary}")
    has_assessable_text = bool(haystack)
    headline_spans = _extract_company_like_spans(headline)
    summary_spans = _extract_company_like_spans(summary)
    supplemental = tuple(
        str(name).strip() for name in (company_names or ()) if str(name or "").strip()
    )
    company_spans = tuple(dict.fromkeys((*headline_spans, *summary_spans, *supplemental)))

    if not provider_links:
        return ProviderLinkageQualityAssessment(
            linkages=links,
            quality_flags=tuple(dict.fromkeys(flags)),
        )

    provider_symbols = {
        _symbol_token(link.provider_symbol or link.instrument_id) for link in provider_links
    }

    if not has_assessable_text:
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
        return ProviderLinkageQualityAssessment(
            linkages=adjusted,
            quality_flags=tuple(dict.fromkeys(flags)),
        )

    corroboration: dict[str, bool] = {}
    alternate_for_symbol: dict[str, bool] = {}
    for symbol in provider_symbols:
        lexical = _ticker_lexically_present(symbol, haystack)
        name_hit = any(_ticker_consistent_with_name(symbol, span) for span in company_spans)
        corroboration[symbol] = lexical or name_hit
        # Alternate-entity only from CamelCase compounds inconsistent with this symbol.
        # Do not escalate from ordinary Title Case / English tokens (false Apple/Fed cases).
        alternate_for_symbol[symbol] = bool(
            _inconsistent_camel_entities(headline=headline, symbol=symbol)
        ) and not corroboration[symbol]

    any_corroborated = any(corroboration.values())
    any_uncorroborated = any(not ok for ok in corroboration.values())
    any_alternate = any(alternate_for_symbol.values())

    if any_uncorroborated:
        flags.append(FLAG_TICKER_NOT_IN_TEXT)

    if any_alternate:
        flags.append(FLAG_ALTERNATE_ENTITY_PROMINENT)

    # Mixed corroboration across multiple provider symbols — not "all weak".
    if len(provider_symbols) > 1 and any_corroborated and any_uncorroborated:
        flags.append(FLAG_MULTIPLE_CONTRADICTORY)

    # Strong suspicion only: alternate entity (optionally compounded by missing URL).
    if FLAG_ALTERNATE_ENTITY_PROMINENT in flags:
        flags.append(FLAG_LOW_CONTEXTUAL_CONFIDENCE)

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

    return ProviderLinkageQualityAssessment(
        linkages=tuple(adjusted_links),
        quality_flags=tuple(dict.fromkeys(flags)),
    )


def company_names_from_raw(item: dict[str, Any]) -> tuple[str, ...]:
    """Optional raw company/issuer labels — supplemental; Finviz may omit these."""

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
