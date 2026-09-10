"""Governed deterministic catalyst/keyword registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CatalystEntry:
    catalyst_id: str
    display_name: str
    terms: tuple[str, ...]
    asset_classes: tuple[str, ...] = ()
    enabled: bool = True
    category: str = "GENERAL"


DEFAULT_CATALYST_REGISTRY: tuple[CatalystEntry, ...] = (
    CatalystEntry("earnings", "Earnings", ("earnings", "eps", "quarterly results"), ("EQUITY",), category="CORPORATE"),
    CatalystEntry("guidance", "Guidance", ("guidance", "outlook", "forecast"), ("EQUITY",), category="CORPORATE"),
    CatalystEntry("partnership", "Partnership", ("partnership", "collaboration", "alliance"), ("EQUITY",), category="CORPORATE"),
    CatalystEntry("contract", "Contract", ("contract award", "wins contract", "contract win"), ("EQUITY",), category="CORPORATE"),
    CatalystEntry("acquisition", "Acquisition", ("acquisition", "acquires", "to acquire"), ("EQUITY",), category="CORPORATE"),
    CatalystEntry("merger", "Merger", ("merger", "merge", "combination"), ("EQUITY",), category="CORPORATE"),
    CatalystEntry("offering", "Offering", ("offering", "secondary offering", "public offering"), ("EQUITY",), category="CORPORATE"),
    CatalystEntry("financing", "Financing", ("financing", "raises capital", "debt offering"), ("EQUITY",), category="CORPORATE"),
    CatalystEntry("analyst", "Analyst", ("analyst upgrade", "analyst downgrade", "price target"), ("EQUITY",), category="CORPORATE"),
    CatalystEntry("bankruptcy", "Bankruptcy", ("bankruptcy", "chapter 11", "restructuring"), ("EQUITY",), category="CORPORATE"),
    CatalystEntry("management", "Management", ("ceo", "cfo", "management change", "executive"), ("EQUITY",), category="CORPORATE"),
    CatalystEntry("fda", "FDA", ("fda", "fda approval", "fda clearance"), ("EQUITY", "REGULATORY"), category="REGULATORY"),
    CatalystEntry("approval", "Approval", ("approval", "approved", "clearance"), ("EQUITY", "REGULATORY"), category="REGULATORY"),
    CatalystEntry("clinical", "Clinical", ("clinical trial", "phase 3", "phase 2"), ("EQUITY", "REGULATORY"), category="REGULATORY"),
    CatalystEntry("sec_filing", "SEC Filing", ("sec filing", "form 8-k", "form 10-k", "form 10-q"), ("EQUITY", "REGULATORY"), category="REGULATORY"),
    CatalystEntry("investigation", "Investigation", ("investigation", "probe", "subpoena"), ("EQUITY", "REGULATORY"), category="REGULATORY"),
    CatalystEntry("rate_decision", "Rate Decision", ("rate decision", "fomc", "fed decision"), ("MACRO", "FUTURES", "FX"), category="MACRO"),
    CatalystEntry("cpi", "CPI", ("cpi", "consumer price index", "inflation"), ("MACRO", "FUTURES"), category="MACRO"),
    CatalystEntry("payroll", "Payroll", ("payroll", "nonfarm payrolls", "jobs report"), ("MACRO", "FUTURES"), category="MACRO"),
    CatalystEntry("inventory", "Inventory", ("inventory", "crude inventories", "eia report"), ("COMMODITY", "FUTURES"), category="MACRO"),
    CatalystEntry("opec", "OPEC", ("opec", "opec+", "production cut"), ("COMMODITY", "FUTURES"), category="MACRO"),
    CatalystEntry("central_bank", "Central Bank", ("central bank", "ecb", "boj", "boe"), ("MACRO", "FX"), category="MACRO"),
    CatalystEntry("supply", "Supply", ("supply disruption", "supply chain"), ("COMMODITY", "EQUITY"), category="MACRO"),
    CatalystEntry("production", "Production", ("production increase", "production cut"), ("COMMODITY",), category="MACRO"),
)


class CatalystRegistry:
    VERSION = "news/catalysts/1.0.0"

    def __init__(self, entries: tuple[CatalystEntry, ...] | None = None) -> None:
        self._entries = entries or DEFAULT_CATALYST_REGISTRY
        self._by_id = {entry.catalyst_id: entry for entry in self._entries}

    def match(
        self,
        text: str,
        *,
        enabled_catalyst_ids: frozenset[str],
        asset_classes: tuple[str, ...] = (),
    ) -> tuple[str, ...]:
        haystack = _normalize_text(text)
        if not haystack:
            return ()
        matched: list[str] = []
        for entry in self._entries:
            if not entry.enabled:
                continue
            if enabled_catalyst_ids and entry.catalyst_id not in enabled_catalyst_ids:
                continue
            if asset_classes and entry.asset_classes:
                if not any(ac in entry.asset_classes for ac in asset_classes):
                    continue
            for term in entry.terms:
                if _term_matches(haystack, term):
                    matched.append(entry.catalyst_id)
                    break
        return tuple(dict.fromkeys(matched))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "entries": [
                {
                    "catalyst_id": entry.catalyst_id,
                    "display_name": entry.display_name,
                    "category": entry.category,
                    "enabled": entry.enabled,
                }
                for entry in self._entries
            ],
        }


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _term_matches(haystack: str, term: str) -> bool:
    needle = _normalize_text(term)
    if not needle:
        return False
    if " " in needle:
        return needle in haystack
    return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None


__all__ = [
    "CatalystEntry",
    "CatalystRegistry",
    "DEFAULT_CATALYST_REGISTRY",
]
