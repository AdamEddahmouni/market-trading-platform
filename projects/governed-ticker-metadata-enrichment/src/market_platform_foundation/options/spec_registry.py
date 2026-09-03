"""Versioned option product spec registry (O1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..contracts.options import DeliverableSpec, ExerciseStyle, SettlementStyle


@dataclass(frozen=True, slots=True)
class OptionProductSpec:
    underlying_id: str
    multiplier: Decimal
    shares_per_contract: Decimal
    exercise_style: ExerciseStyle
    settlement_style: SettlementStyle
    symbology_version: str
    effective_from: date

    def deliverable(self) -> DeliverableSpec:
        return DeliverableSpec(
            shares_per_contract=self.shares_per_contract,
            description=f"{self.underlying_id}:{self.symbology_version}",
        )


_STANDARD_EQUITY = {
    "multiplier": Decimal("100"),
    "shares_per_contract": Decimal("100"),
    "exercise_style": "american",
    "settlement_style": "physical",
    "symbology_version": "occ_equity_v1",
}

_REGISTRY: tuple[OptionProductSpec, ...] = tuple(
    OptionProductSpec(
        underlying_id=symbol,
        effective_from=date(2020, 1, 1),
        **values,
    )
    for symbol, values in (
        ("BIYA", _STANDARD_EQUITY),
        ("BIYA_ADJ", _STANDARD_EQUITY),
        ("NVDA", _STANDARD_EQUITY),
    )
)


def resolve_option_spec(underlying_id: str, as_of: date) -> OptionProductSpec | None:
    """Return effective product spec for underlying at as_of — fail-closed when unknown."""
    symbol = underlying_id.strip().upper()
    candidates = [
        entry
        for entry in _REGISTRY
        if entry.underlying_id == symbol and entry.effective_from <= as_of
    ]
    if not candidates:
        return None
    return candidates[-1]


__all__ = [
    "OptionProductSpec",
    "resolve_option_spec",
]
