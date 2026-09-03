"""PIT ticker → instrument_id. Do not join solely on the current ticker."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SymbolResolution:
    provider_symbol: str
    instrument_id: str
    venue_id: str
    asset_class: str
    listing_authority: str = ""
    quality_flags: tuple[str, ...] = ()


class SymbolMap:
    def __init__(self, records: tuple[dict[str, Any], ...]) -> None:
        self._records = records

    @classmethod
    def from_path(cls, path: Path) -> "SymbolMap":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("records") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("SYMBOL_MAP_INVALID")
        return cls(tuple(row for row in rows if isinstance(row, dict)))

    def resolve(self, provider_symbol: str, *, as_of: str) -> SymbolResolution:
        symbol = str(provider_symbol or "").strip().upper()
        if not symbol:
            return SymbolResolution("", "", "", "", ("IDENTITY_UNRESOLVED",))
        cutoff = as_of[:10] if as_of else ""
        for row in self._records:
            aliases = {str(row.get("provider_symbol") or "").upper()}
            aliases.update(str(item).upper() for item in (row.get("aliases") or ()))
            if symbol not in aliases:
                continue
            valid_from = str(row.get("valid_from") or "")
            valid_to = str(row.get("valid_to") or "")
            if valid_from and cutoff and cutoff < valid_from[:10]:
                continue
            if valid_to and cutoff and cutoff >= valid_to[:10]:
                continue
            return SymbolResolution(
                provider_symbol=symbol,
                instrument_id=str(row.get("instrument_id") or symbol),
                venue_id=str(row.get("venue_id") or "US_EQUITY"),
                asset_class=str(row.get("asset_class") or "EQUITY"),
                listing_authority=str(row.get("listing_authority") or ""),
            )
        return SymbolResolution(
            provider_symbol=symbol,
            instrument_id="",
            venue_id="",
            asset_class="",
            quality_flags=("IDENTITY_UNRESOLVED",),
        )
