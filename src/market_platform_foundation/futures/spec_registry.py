"""Versioned futures contract spec registry (F1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..contracts.futures import FuturesContractSpec


@dataclass(frozen=True, slots=True)
class FuturesSpecEntry:
    instrument_family: str
    effective_from: date
    spec: FuturesContractSpec


_ES_CME_V1 = FuturesContractSpec(
    multiplier=Decimal("50"),
    tick_size=Decimal("0.25"),
    tick_value=Decimal("12.50"),
    point_value=Decimal("50"),
    spec_version="es_cme_v1",
    spec_effective_date="2020-01-01",
)

_REGISTRY: tuple[FuturesSpecEntry, ...] = (
    FuturesSpecEntry(instrument_family="ES", effective_from=date(2020, 1, 1), spec=_ES_CME_V1),
)

# Backward-compatible alias for tests and notional helpers
ES_CONTRACT_SPEC = _ES_CME_V1


def resolve_futures_spec(instrument_family: str, as_of: date) -> FuturesContractSpec | None:
    """Return the effective contract spec for a family at as_of — fail-closed when unknown."""
    family = instrument_family.strip().upper()
    candidates = [
        entry.spec
        for entry in _REGISTRY
        if entry.instrument_family == family and entry.effective_from <= as_of
    ]
    if not candidates:
        return None
    return candidates[-1]


__all__ = [
    "ES_CONTRACT_SPEC",
    "FuturesSpecEntry",
    "resolve_futures_spec",
]
