"""Screener S13: deterministic universe admission for exchange-listed securities.

Every US Equities and ETF row answers "why is this in this universe?" from
recorded evidence, never from which provider endpoint returned it:

    provider catalog -> normalized security classification -> canonical XA-01
    identity -> universe admission decision -> rejection reason.

Two already-integrated sources are combined:

- Moomoo OpenD ``get_stock_basicinfo(US, ETF)`` supplies the ETF provider
  catalog and quote identity. Its ``ETF`` security type is a broad fund /
  trust bucket: it also returns equity REITs (EQIX, WY) and closed-end funds
  (AIO), and it carries no REIT, CEF, or ETN flag.
- The Finviz Elite export already loaded for US Equities supplies the
  reference ``sector`` / ``industry`` classification for every US listing,
  including the ``Exchange Traded Fund`` industry.

``US_ETFS`` admits a row only when both agree it is an exchange-traded fund
(fail-closed: an unresolved listing is rejected). ``US_EQUITIES`` admits every
Finviz US listing except the ones Finviz classifies as exchange-traded funds,
so the two universes are disjoint by construction. Categories (REIT,
closed-end fund, shell company) are recorded provenance inside a universe,
never new universes; the canonical asset classes stay XA-01 ``EQUITY`` and
``ETF_FUND``. See docs/engineering/SCREENER_S13_UNIVERSE_INTEGRITY.md.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .screener_universes import BONDS, CRYPTO, FUTURES, UNIVERSES, US_EQUITIES, US_ETFS

REFERENCE_SOURCE = "FINVIZ_ELITE"
PROVIDER_SOURCE = "MOOMOO_OPEND"

# Security categories. They describe a listing inside a universe; the XA-01
# asset class (EQUITY / ETF_FUND) remains the only structural taxonomy.
EXCHANGE_TRADED_FUND = "EXCHANGE_TRADED_FUND"
REIT = "REIT"
CLOSED_END_FUND = "CLOSED_END_FUND"
SHELL_COMPANY = "SHELL_COMPANY"
LISTED_EQUITY = "LISTED_EQUITY"
UNCLASSIFIED = "UNCLASSIFIED"

# Rejection reasons (deterministic; audit/debug metadata, not UI copy).
NOT_ETF = "NOT_ETF"
WRONG_MARKET = "WRONG_MARKET"
WRONG_PRODUCT_TYPE = "WRONG_PRODUCT_TYPE"
DELISTED = "DELISTED"
INVALID_SYMBOL = "INVALID_SYMBOL"
UNRESOLVED_SECURITY_TYPE = "UNRESOLVED_SECURITY_TYPE"
CLASSIFICATION_UNAVAILABLE = "CLASSIFICATION_UNAVAILABLE"
ETF_BELONGS_TO_US_ETFS = "ETF_BELONGS_TO_US_ETFS"
DUPLICATE_LISTING = "DUPLICATE_LISTING"

_ETF_INDUSTRY = "exchange traded fund"
_REIT_PREFIX = "reit"
_CEF_PREFIX = "closed-end fund"
_SHELL_INDUSTRY = "shell companies"


def listing_key(symbol: str) -> str:
    """One US listing across providers: Moomoo ``BRK.B`` and Finviz ``BRK-B`` are the same share class."""

    return str(symbol or "").strip().upper().replace("-", ".").replace("/", ".")


def reference_category(industry: str | None) -> str:
    """Finviz industry to a security category; an empty industry is never guessed."""

    text = str(industry or "").strip().casefold()
    if not text:
        return UNCLASSIFIED
    if text == _ETF_INDUSTRY:
        return EXCHANGE_TRADED_FUND
    if text.startswith(_REIT_PREFIX):
        return REIT
    if text.startswith(_CEF_PREFIX):
        return CLOSED_END_FUND
    if text == _SHELL_INDUSTRY:
        return SHELL_COMPANY
    return LISTED_EQUITY


@dataclass(frozen=True, slots=True)
class ReferenceEntry:
    symbol: str
    sector: str | None
    industry: str | None
    country: str | None

    @property
    def category(self) -> str:
        return reference_category(self.industry)

    def payload(self, as_of: str | None) -> dict[str, Any]:
        return {"source": REFERENCE_SOURCE, "symbol": self.symbol, "sector": self.sector,
                "industry": self.industry, "country": self.country, "as_of": as_of}


@dataclass(frozen=True, slots=True)
class ClassificationReference:
    """One Finviz export's classification of every US listing, keyed by listing."""

    as_of: str | None
    entries: Mapping[str, ReferenceEntry] = field(default_factory=dict)
    error: str | None = None
    #: Digest of every listing's category: an unchanged classification keeps page chains valid across refreshes.
    fingerprint: str = ""

    @property
    def available(self) -> bool:
        return self.as_of is not None

    def get(self, symbol: str) -> ReferenceEntry | None:
        return self.entries.get(listing_key(symbol))

    @classmethod
    def build(cls, rows: Iterable[Any], *, as_of: str, error: str | None = None) -> "ClassificationReference":
        entries: dict[str, ReferenceEntry] = {}
        for row in rows:
            symbol = str(getattr(row, "ticker", "") or "").strip().upper()
            if symbol:
                entries.setdefault(listing_key(symbol), ReferenceEntry(
                    symbol, getattr(row, "sector", None) or None, getattr(row, "industry", None) or None,
                    getattr(row, "country", None) or None))
        digest = hashlib.sha256("\n".join(f"{key}:{entry.category}" for key, entry in sorted(entries.items()))
                                .encode()).hexdigest()[:16]
        return cls(as_of, entries, error, digest)


UNAVAILABLE_REFERENCE = ClassificationReference(None, {}, "SOURCE_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class Admission:
    admitted: bool
    category: str
    reason: str | None
    classification: dict[str, Any]


def _provider_payload(source: Mapping[str, Any]) -> dict[str, Any]:
    """Every provider classification field kept verbatim before normalization."""

    keys = ("code", "stock_type", "stock_child_type", "exchange_type", "stock_owner", "listing_date", "delisting")
    return {"source": PROVIDER_SOURCE, **{key: source.get(key) for key in keys if key in source}}


def admit_etf(source: Mapping[str, Any], reference: ClassificationReference) -> Admission:
    """US_ETFS admission: provider ETF type AND reference ``Exchange Traded Fund`` industry."""

    provider = _provider_payload(source)
    code = str(source.get("code") or "")

    def decide(admitted: bool, category: str, reason: str | None, entry: ReferenceEntry | None = None,
               basis: str = "PROVIDER_SECURITY_TYPE") -> Admission:
        return Admission(admitted, category, reason, {
            "universe": US_ETFS, "category": category, "status": "ADMITTED" if admitted else "REJECTED",
            "reason": reason, "basis": basis, "provider": provider,
            "reference": entry.payload(reference.as_of) if entry else None})

    if not code.startswith("US."):
        return decide(False, UNCLASSIFIED, WRONG_MARKET)
    if source.get("stock_type") != "ETF":
        return decide(False, UNCLASSIFIED, WRONG_PRODUCT_TYPE)
    if source.get("delisting"):
        return decide(False, UNCLASSIFIED, DELISTED)
    symbol = code[3:].upper()
    if not symbol or not all(char.isalnum() or char in ".-" for char in symbol):
        return decide(False, UNCLASSIFIED, INVALID_SYMBOL)
    if not reference.available:
        # Fail closed: without the reference, a provider "ETF" may be a REIT or CEF.
        return decide(False, UNCLASSIFIED, CLASSIFICATION_UNAVAILABLE)
    entry = reference.get(symbol)
    basis = "PROVIDER_SECURITY_TYPE+REFERENCE_INDUSTRY"
    if entry is None:
        return decide(False, UNCLASSIFIED, UNRESOLVED_SECURITY_TYPE)
    category = entry.category
    if category == EXCHANGE_TRADED_FUND:
        return decide(True, category, None, entry, basis)
    if category == UNCLASSIFIED:
        return decide(False, category, UNRESOLVED_SECURITY_TYPE, entry, basis)
    return decide(False, category, category if category in (REIT, CLOSED_END_FUND) else NOT_ETF, entry, basis)


def admit_equity(row: Any, *, as_of: str | None) -> Admission:
    """US_EQUITIES admission over the Finviz ``geo_usa`` export: every listing except ETFs.

    REITs, closed-end funds, BDCs, royalty trusts, and SPAC shells are listed
    equity securities and stay here with their recorded category. An empty
    industry is admitted as ``UNCLASSIFIED``: the source is an equity export,
    and only the narrower ETF claim requires positive evidence.
    """

    entry = ReferenceEntry(str(getattr(row, "ticker", "") or "").upper(), getattr(row, "sector", None) or None,
                           getattr(row, "industry", None) or None, getattr(row, "country", None) or None)
    category = entry.category
    admitted = category != EXCHANGE_TRADED_FUND
    reason = None if admitted else ETF_BELONGS_TO_US_ETFS
    return Admission(admitted, category, reason, {
        "universe": US_EQUITIES, "category": category, "status": "ADMITTED" if admitted else "REJECTED",
        "reason": reason, "basis": "REFERENCE_INDUSTRY", "provider": None, "reference": entry.payload(as_of)})


def admission_summary(universe: str, decisions: Iterable[Admission], *, raw_count: int | None = None,
                      source: str | None = None, reference_as_of: str | None = None,
                      reference_error: str | None = None, duplicates: int = 0) -> dict[str, Any]:
    """Counts that expose the impact of admission instead of hiding it."""

    decisions = list(decisions)
    accepted = [item for item in decisions if item.admitted]
    rejected = Counter(item.reason for item in decisions if not item.admitted)
    return {
        "universe": universe, "source": source or UNIVERSES[universe].source,
        "provider_raw_count": len(decisions) if raw_count is None else raw_count,
        "accepted": len(accepted), "rejected": sum(rejected.values()), "duplicates": duplicates,
        "ambiguous": sum(1 for item in accepted if item.category == UNCLASSIFIED),
        "accepted_categories": dict(sorted(Counter(item.category for item in accepted).items())),
        "rejection_reasons": dict(rejected.most_common()),
        "reference": {"source": REFERENCE_SOURCE, "as_of": reference_as_of, "error": reference_error},
    }


# ----------------------------------------------------------------- invariants

#: Row-level contract per universe: XA-01 class/kind plus universe-specific product checks.
def _row_problems(universe: str, row: Mapping[str, Any]) -> list[str]:
    spec = UNIVERSES[universe]
    instrument = row.get("instrument") or {}
    problems: list[str] = []
    classes = spec.admitted_asset_classes or (spec.asset_class,)
    kinds = spec.admitted_instrument_kinds or (spec.instrument_kind,)
    if instrument.get("asset_class") not in classes:
        problems.append("WRONG_ASSET_CLASS")
    if instrument.get("instrument_kind") not in kinds:
        problems.append("WRONG_INSTRUMENT_KIND")
    classification = row.get("classification") or {}
    if universe == US_ETFS and (classification.get("category") != EXCHANGE_TRADED_FUND
                                or classification.get("status") != "ADMITTED"):
        problems.append(NOT_ETF)
    if universe == US_EQUITIES and classification.get("category") == EXCHANGE_TRADED_FUND:
        problems.append(ETF_BELONGS_TO_US_ETFS)
    if universe == FUTURES and not (row.get("root") and row.get("expiry") and row.get("lead")):
        problems.append("NOT_LEAD_FUTURE_CONTRACT")
    if universe == BONDS and not row.get("cusip"):
        problems.append("MISSING_CUSIP")
    if universe == CRYPTO and (row.get("product_type") != "SPOT" or not row.get("venue")):
        problems.append("NOT_VENUE_SPOT_PAIR")
    return problems


def integrity_report(catalogs: Mapping[str, list[Mapping[str, Any]]]) -> dict[str, Any]:
    """Row-contract violations and unexpected cross-universe duplicates.

    Two identities collide when they share an XA-01 instrument id, or when an
    exchange listing (US Equities / ETFs ticker) appears in both
    exchange-listed universes. Futures contract ids, CUSIPs, and venue pairs
    live in disjoint identity spaces and are compared by instrument id only.
    """

    violations: list[dict[str, Any]] = []
    owners: dict[str, set[str]] = {}
    listings: dict[str, set[str]] = {}
    for universe, rows in catalogs.items():
        for row in rows:
            identity = str((row.get("instrument") or {}).get("instrument_id") or "")
            for problem in _row_problems(universe, row):
                violations.append({"universe": universe, "symbol": row.get("symbol"), "problem": problem})
            owners.setdefault(identity, set()).add(universe)
            if universe in (US_EQUITIES, US_ETFS):
                listings.setdefault(listing_key(str(row.get("symbol") or "")), set()).add(universe)
    duplicates = [{"key": key, "kind": "INSTRUMENT_ID", "universes": sorted(found)}
                  for key, found in sorted(owners.items()) if len(found) > 1]
    duplicates += [{"key": key, "kind": "LISTING", "universes": sorted(found)}
                   for key, found in sorted(listings.items()) if len(found) > 1]
    return {"counts": {universe: len(rows) for universe, rows in catalogs.items()},
            "violations": violations, "cross_universe_duplicates": duplicates,
            "clean": not violations and not duplicates}
