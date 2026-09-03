"""Finviz symbol ↔ IMP canonical instrument mapping."""

from __future__ import annotations

from ..providers.contracts import SymbolMapping


def finviz_to_canonical(finviz_symbol: str) -> SymbolMapping:
    code = str(finviz_symbol).strip().upper()
    if not code:
        raise ValueError("EMPTY_FINVIZ_SYMBOL")
    return SymbolMapping(provider_symbol=code, instrument_id=code, venue_id="US_EQUITY")


def canonical_to_moomoo(instrument_id: str) -> str:
    code = str(instrument_id).strip().upper()
    return f"US.{code}"
