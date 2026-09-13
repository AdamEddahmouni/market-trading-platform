"""Provisional US equity security identity helpers (PIT lane).

Not a security master — binds a normalized ticker to ``InstrumentIdentity`` for
research exports and opportunity linkage until durable PIT master data lands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..providers.identity import InstrumentIdentity

_US_EQUITY_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")

# Canonical frozen fingerprint for sibling campaign; integrity tooling asserts unchanged.
FTEP_V1_001_MANIFEST_FINGERPRINT = (
    "69C36BA23813C009C27EE83924834D46F5804D0A0FA037E37ADB133F8BFEA99C"
)


@dataclass(frozen=True, slots=True)
class SecurityIdentity:
    """Minimal security row for research / news linkage (provisional)."""

    ticker: str
    asset_class: str
    currency: str
    instrument: InstrumentIdentity

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_class": self.asset_class,
            "currency": self.currency,
            "instrument": self.instrument.to_dict(),
            "provisional": True,
            "ticker": self.ticker,
        }


def normalize_us_equity_ticker(raw: str) -> str:
    text = str(raw).strip().upper()
    if not text or not _US_EQUITY_TICKER.fullmatch(text):
        raise ValueError("US_EQUITY_TICKER_INVALID")
    return text


def resolve_us_equity_ticker(
    raw: str,
    *,
    venue_id: str = "UNKNOWN",
    namespace: str = "ftep.provisional",
) -> SecurityIdentity:
    """Map a provider symbol to a namespaced ``InstrumentIdentity`` (venue optional)."""

    ticker = normalize_us_equity_ticker(raw)
    instrument = InstrumentIdentity(
        namespace=namespace,
        instrument_id=ticker,
        asset_class="equity",
        venue_id=venue_id,
        currency="USD",
    )
    return SecurityIdentity(
        ticker=ticker,
        asset_class="equity",
        currency="USD",
        instrument=instrument,
    )


__all__ = [
    "FTEP_V1_001_MANIFEST_FINGERPRINT",
    "SecurityIdentity",
    "normalize_us_equity_ticker",
    "resolve_us_equity_ticker",
]
