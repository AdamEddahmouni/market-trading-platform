"""S15: an explicit CFTC coverage decision for every Screener Futures root.

Every root the Futures catalog lists resolves to exactly one decision:

* ``MAPPED`` — one CFTC contract market in ``POSITIONING_MARKETS`` (code-exact, with
  its evidence basis);
* ``NO_CFTC_REPORT`` — no COT market exists for the product (``PRODUCT_NOT_COVERED``:
  single-stock futures are not in any COT report) or for this particular contract
  (``NO_CFTC_MARKET_FOUND``: e.g. a micro contract whose full-size parent is reported);
* ``AMBIGUOUS`` — a candidate market exists but its identity does not establish that it
  reports this contract; never fed as positioning;
* ``UNCLASSIFIED`` — a root the registry has never decided (a new provider listing).
  It is reported, never silently assigned to a nearby market.

A mapped root whose provider venue contradicts the CFTC market's exchange is
``AMBIGUOUS`` / ``EXCHANGE_MISMATCH`` at runtime. Nothing here matches by name
similarity; decisions were made once, from official CFTC Public Reporting data, and
are recorded with their evidence (docs/engineering/SCREENER_S15_CFTC_COVERAGE.md).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from .screener_positioning import POSITIONING_MARKETS, PositioningMarket

#: When the decisions below were verified: CFTC report of 2026-09-22 (all COT datasets,
#: codes since 2012) against the Moomoo OpenD Futures catalog of 2026-09-29 (178 roots).
REGISTRY_VERIFIED = "2026-09-29"


class CoverageStatus(StrEnum):
    MAPPED = "MAPPED"
    NO_CFTC_REPORT = "NO_CFTC_REPORT"
    AMBIGUOUS = "AMBIGUOUS"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True, slots=True)
class Unmapped:
    status: CoverageStatus
    reason: str
    note: str
    candidate_code: str | None = None  # a considered CFTC market that was rejected or is ambiguous


def _no_market(note: str) -> Unmapped:
    return Unmapped(CoverageStatus.NO_CFTC_REPORT, "NO_CFTC_MARKET_FOUND", note)


_STOCK_NOTE = ("Single-stock future. No COT report (Legacy, TFF, or Disaggregated, 2012 onward) "
               "contains a single-stock market, so no CFTC positioning series exists for it.")
#: Single-stock futures in the catalog (``S…`` full-size, ``X…`` micro), listed explicitly:
#: a new stock root must be decided, never inferred from its spelling.
SINGLE_STOCK_ROOTS: tuple[str, ...] = (
    "SAAPL", "SABBV", "SADBE", "SAMAT", "SAMD0", "SAMGN", "SAMZN", "SAVGO", "SBA00", "SBAC0", "SBKNG", "SBRKB",
    "SCAT0", "SCMCS", "SCOP0", "SCOST", "SCRM0", "SCSCO", "SCVX0", "SDIS0", "SGOOG", "SHD00", "SIBM0", "SINTC",
    "SJNJ0", "SJPM0", "SKO00", "SLLY0", "SLMT0", "SMA00", "SMCD0", "SMETA", "SMRK0", "SMSFT", "SMU00", "SNEM0",
    "SNFLX", "SNVDA", "SORCL", "SPANW", "SPEP0", "SPFE0", "SPG00", "SPLD0", "SPLTR", "SQCOM", "SSBUX", "SSPCX",
    "STSLA", "STXN0", "SUNH0", "SV000", "SVZ00", "SWMT0", "SXOM0",
    "XAAPL", "XAMD0", "XAMZN", "XAVGO", "XBA00", "XBAC0", "XCSCO", "XGOOG", "XINTC", "XJPM0", "XMETA", "XMSFT",
    "XMU00", "XNEM0", "XNFLX", "XNVDA", "XPFE0", "XPLTR", "XSPCX", "XTSLA", "XWMT0", "XXOM0",
)

_MICRO_FX = "CFTC reports the full-size {parent} market only; there is no micro market, and micro positions are never merged into the parent."
#: Roots with a recorded decision other than MAPPED. Evidence: a search of every COT market code
#: reported since 2012 (docs/engineering/SCREENER_S15_CFTC_COVERAGE.md#unmapped-roots).
UNMAPPED_ROOTS: dict[str, Unmapped] = {
    **{root: Unmapped(CoverageStatus.NO_CFTC_REPORT, "PRODUCT_NOT_COVERED", _STOCK_NOTE) for root in SINGLE_STOCK_ROOTS},
    "1OZ": Unmapped(CoverageStatus.NO_CFTC_REPORT, "NO_CFTC_MARKET_FOUND",
                    "No 1-ounce gold market on CME Group. The similarly named GOLD -1 TROY OUNCE is a Coinbase "
                    "Derivatives market (a different exchange) and is rejected.", candidate_code="088LM1"),
    "2YY": _no_market("CFTC reports MICRO 10 YEAR YIELD only; there is no 2-year yield market."),
    "5YY": _no_market("CFTC reports MICRO 10 YEAR YIELD only; there is no 5-year yield market."),
    "30Y": _no_market("CFTC reports MICRO 10 YEAR YIELD only; there is no 30-year yield market."),
    "M6A": _no_market(_MICRO_FX.format(parent="AUSTRALIAN DOLLAR")),
    "M6B": _no_market(_MICRO_FX.format(parent="BRITISH POUND")),
    "M6E": _no_market(_MICRO_FX.format(parent="EURO FX")),
    "MCD": _no_market(_MICRO_FX.format(parent="CANADIAN DOLLAR")),
    "MJY": _no_market(_MICRO_FX.format(parent="JAPANESE YEN")),
    "MSF": _no_market(_MICRO_FX.format(parent="SWISS FRANC")),
    "MIR": _no_market("No Indian rupee market in any COT report."),
    "SIR": _no_market("No Indian rupee market in any COT report."),
    "PJY": _no_market("No British pound / Japanese yen cross-rate market; CFTC reports only the EUR/GBP and EUR/JPY cross rates."),
    "MCL": _no_market("No micro WTI market; WTI-PHYSICAL is the full-size contract and is never used for the micro."),
    "QM": _no_market("No E-mini crude oil market; WTI-PHYSICAL is the full-size contract."),
    "MNG": _no_market("No micro Henry Hub market; E-MINI NATURAL GAS is the QG contract, not this one."),
    "QC": _no_market("No E-mini copper market; COPPER- #1 is the full-size contract."),
    "QI": _no_market("No E-mini silver market; SILVER is the full-size contract."),
    "QO": _no_market("No E-mini gold market; GOLD is the full-size contract."),
    "SIC": _no_market("No 100-ounce silver market; SILVER (5,000 oz) and MICRO SILVER (1,000 oz) are other contracts."),
    "SGU": _no_market("No Shanghai gold market in any COT report."),
    "MNI": _no_market("No micro Nikkei market; CFTC reports the full-size yen- and dollar-denominated Nikkei only."),
    "MNK": _no_market("No micro Nikkei market; CFTC reports the full-size yen- and dollar-denominated Nikkei only."),
    "TPD": _no_market("No TOPIX market in any COT report."),
    "MTN": _no_market("No micro Ultra 10-year market; ULTRA UST 10Y is the full-size contract."),
    "MWN": _no_market("No micro Ultra bond market; ULTRA UST BOND is the full-size contract."),
    "MZC": _no_market("No micro corn market; CORN is the full-size contract."),
    "MZL": _no_market("No micro soybean oil market; SOYBEAN OIL is the full-size contract."),
    "MZM": _no_market("No micro soybean meal market; SOYBEAN MEAL is the full-size contract."),
    "MZS": _no_market("No micro soybean market; SOYBEANS and MINI SOYBEANS are other contracts."),
    "MZW": _no_market("No micro wheat market; WHEAT-SRW is the full-size contract."),
    "XC": _no_market("No mini-sized corn market; MINI SOYBEANS is the only mini grain market CFTC reports."),
    "XW": _no_market("No mini-sized wheat market; MINI SOYBEANS is the only mini grain market CFTC reports."),
    "VXM": Unmapped(CoverageStatus.AMBIGUOUS, "AMBIGUOUS_MAPPING",
                    "CFTC publishes one VIX FUTURES market; its identity does not state whether Mini VIX positions "
                    "are included, so it is not shown as Mini VIX positioning.", candidate_code="1170E1"),
}

#: CFTC exchange (the suffix of the official market name) → the provider venue it is listed on.
EXCHANGE_VENUES: dict[str, str] = {
    "CHICAGO MERCANTILE EXCHANGE": "US_CME",
    "CHICAGO BOARD OF TRADE": "US_CBOT",
    "NEW YORK MERCANTILE EXCHANGE": "US_NYMEX",
    "COMMODITY EXCHANGE INC.": "US_COMEX",
    "CBOE FUTURES EXCHANGE": "US_CBOE",
}


#: Short display label per decision reason (the ``note`` carries the root-specific explanation).
REASON_LABELS: dict[str | None, str] = {
    None: "Mapped to a CFTC market",
    "PRODUCT_NOT_COVERED": "Single-stock future · no COT market",
    "NO_CFTC_MARKET_FOUND": "No CFTC market",
    "AMBIGUOUS_MAPPING": "Ambiguous CFTC market",
    "EXCHANGE_MISMATCH": "Exchange mismatch",
    "ROOT_NOT_IN_COVERAGE_REGISTRY": "Unclassified root",
}


def cftc_exchange(market: PositioningMarket) -> str:
    return market.market_name.rsplit(" - ", 1)[-1].strip()


def expected_venue(market: PositioningMarket) -> str | None:
    return EXCHANGE_VENUES.get(cftc_exchange(market))


def market_payload(market: PositioningMarket) -> dict[str, Any]:
    return {"cftc_contract_market_code": market.code, "market_name": market.market_name, "report": market.report.value,
            "cftc_exchange": cftc_exchange(market), "basis": market.basis, "confidence": market.confidence,
            "note": market.note or None, "former_names": list(market.former_names)}


def classify_root(root: str, *, exchange: str | None = None) -> dict[str, Any]:
    """The coverage decision for one root; ``exchange`` is the provider venue when known."""

    key = (root or "").strip().upper()
    venue_in = (exchange or "").strip().upper() or None

    def decided(status: CoverageStatus, reason: str | None, note: str | None, *, market: dict[str, Any] | None = None,
                candidate: str | None = None) -> dict[str, Any]:
        return {"root": key, "status": status.value, "reason": reason, "label": REASON_LABELS[reason], "note": note,
                "provider_exchange": venue_in, "market": market, "candidate_code": candidate}

    market = POSITIONING_MARKETS.get(key)
    if market is not None:
        venue = expected_venue(market)
        if venue_in and venue and venue_in != venue:
            return decided(CoverageStatus.AMBIGUOUS, "EXCHANGE_MISMATCH",
                           f"Provider venue {venue_in} is not the CFTC market's exchange ({cftc_exchange(market)}).",
                           candidate=market.code)
        return decided(CoverageStatus.MAPPED, None, market.note or None, market=market_payload(market))
    decision = UNMAPPED_ROOTS.get(key)
    if decision is None:
        return decided(CoverageStatus.UNCLASSIFIED, "ROOT_NOT_IN_COVERAGE_REGISTRY",
                       "This root has no recorded CFTC coverage decision yet; it is not mapped to any market.")
    return decided(decision.status, decision.reason, decision.note, candidate=decision.candidate_code)


def coverage_summary(roots: Iterable[tuple[str, str | None]]) -> dict[str, Any]:
    """Counts by status and reason for ``(root, provider venue)`` pairs, plus every non-mapped decision."""

    decisions = [classify_root(root, exchange=exchange) for root, exchange in sorted(set(roots))]
    statuses = Counter(item["status"] for item in decisions)
    reasons = Counter(item["reason"] for item in decisions if item["reason"])
    total = len(decisions)
    mapped = statuses.get(CoverageStatus.MAPPED.value, 0)
    return {
        "universe_roots": total,
        "mapped_roots": mapped,
        "mapped_percent": round(100.0 * mapped / total, 1) if total else None,
        "by_status": {status.value: statuses.get(status.value, 0) for status in CoverageStatus},
        "by_reason": dict(sorted(reasons.items())),
        # Display order: mapped, then each non-mapped reason with its label (counts only; never a score).
        "breakdown": [{"id": CoverageStatus.MAPPED.value, "label": REASON_LABELS[None], "count": mapped},
                      *({"id": reason, "label": REASON_LABELS.get(reason, reason), "count": reasons.get(reason, 0)}
                        for reason in REASON_LABELS if reason and reasons.get(reason))],
        "unmapped": [item for item in decisions if item["status"] != CoverageStatus.MAPPED.value],
        "registry_verified": REGISTRY_VERIFIED,
    }


__all__ = ["CoverageStatus", "EXCHANGE_VENUES", "REASON_LABELS", "REGISTRY_VERIFIED", "SINGLE_STOCK_ROOTS", "UNMAPPED_ROOTS",
           "Unmapped",
           "cftc_exchange", "classify_root", "coverage_summary", "expected_venue", "market_payload"]
