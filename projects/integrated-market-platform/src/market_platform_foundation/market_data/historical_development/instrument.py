"""US equity instrument identity for historical development pulls."""

from __future__ import annotations

_DEFAULT_MIC = "XNAS"


def resolve_us_equity_instrument_id(symbol: str, *, mic: str = _DEFAULT_MIC) -> str:
    """Map operator ticker or canonical id to ``canonical:EQUITY:<MIC>:<SYMBOL>``."""

    text = str(symbol or "").strip()
    if not text:
        raise ValueError("INSTRUMENT_REQUIRED")
    if text.startswith("canonical:"):
        return text
    ticker = text.upper().split(":")[-1]
    venue = str(mic or _DEFAULT_MIC).strip().upper() or _DEFAULT_MIC
    return f"canonical:EQUITY:{venue}:{ticker}"


def symbol_from_instrument_id(instrument_id: str) -> str:
    """Extract bare US ticker from canonical instrument id."""

    parts = str(instrument_id or "").strip().split(":")
    if len(parts) >= 4 and parts[0] == "canonical" and parts[1] == "EQUITY":
        return parts[-1].upper()
    return str(instrument_id or "").strip().upper()


__all__ = ["resolve_us_equity_instrument_id", "symbol_from_instrument_id"]
