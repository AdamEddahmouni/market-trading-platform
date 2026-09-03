"""Strict adapter from SHARED P4 decompositions to the universal sidecar."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..contracts.common import ContractReference, IntelligenceScope
from .economic_assessment import (
    EconomicAssumptionsV1,
    MoneyMinorUnits,
    UniversalEconomicAssessmentV1,
)


def _unit_spec(units: Mapping[str, Any], key: str) -> tuple[str, str, int]:
    raw = units.get(key)
    if isinstance(raw, str):
        parts = raw.split(":")
        if len(parts) != 3:
            raise ValueError(f"P4_UNIT_SPEC_INVALID:{key}")
        currency, unit, scale = parts
        try:
            return currency, unit, int(scale)
        except ValueError as exc:
            raise ValueError(f"P4_UNIT_SPEC_INVALID:{key}") from exc
    if isinstance(raw, Mapping):
        try:
            return str(raw["currency"]), str(raw["unit"]), int(raw["scale"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"P4_UNIT_SPEC_INVALID:{key}") from exc
    raise ValueError(f"P4_UNIT_REQUIRED:{key}")


def _money(
    decomposition: Mapping[str, Any],
    units: Mapping[str, Any],
    key: str,
    *,
    nested_key: tuple[str, str] | None = None,
) -> MoneyMinorUnits | None:
    value = decomposition.get(key)
    unit_key = key
    if nested_key is not None:
        nested = decomposition.get(nested_key[0])
        if isinstance(nested, Mapping):
            value = nested.get(nested_key[1])
            unit_key = f"{nested_key[0]}.{nested_key[1]}"
    if value is None:
        return None
    currency, unit, scale = _unit_spec(units, unit_key)
    if unit != "minor_units":
        raise ValueError(f"P4_MONEY_UNIT_INVALID:{unit_key}")
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"P4_MONEY_VALUE_NOT_INTEGER:{unit_key}")
    return MoneyMinorUnits(value, currency, scale)


def _reject_undeclared_numeric_values(
    value: Any,
    units: Mapping[str, Any],
    *,
    path: str = "",
) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        if path not in units:
            raise ValueError(f"P4_AMBIGUOUS_UNTYPED_VALUE:{path}")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "units" and not path:
                continue
            child_path = f"{path}.{key}" if path else str(key)
            _reject_undeclared_numeric_values(child, units, path=child_path)
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_undeclared_numeric_values(child, units, path=f"{path}[{index}]")


def adapt_shared_p4_decomposition(
    decomposition: Mapping[str, Any],
    *,
    scope: IntelligenceScope,
    account_id: str,
    mode: str,
    assessed_at_ns: int,
    assumptions: EconomicAssumptionsV1,
    source_refs: tuple[ContractReference, ...] = (),
) -> UniversalEconomicAssessmentV1:
    """Adapt only P4 values carrying an explicit, per-dimension unit declaration.

    Existing P4 snapshots intentionally contain lane-native floats. Accepting
    those floats here would silently compare dollars, probability, and bps.
    """
    if not isinstance(decomposition, Mapping):
        raise ValueError("P4_DECOMPOSITION_MUST_BE_MAPPING")
    if any(key in decomposition for key in ("universal_score", "opaque_score", "economic_score")):
        raise ValueError("OPAQUE_ECONOMIC_SCORE_FORBIDDEN")
    units = decomposition.get("units")
    if not isinstance(units, Mapping):
        raise ValueError("P4_AMBIGUOUS_UNTYPED_VALUES")
    _reject_undeclared_numeric_values(decomposition, units)

    gross = _money(decomposition, units, "expected_gross_pnl", nested_key=("payoff", "expected_pnl"))
    net = _money(decomposition, units, "expected_net_pnl", nested_key=("payoff", "net_expected_pnl"))
    capital = _money(decomposition, units, "capital_required")
    if gross is None:
        raise ValueError("P4_EXPECTED_GROSS_PNL_REQUIRED")

    expected_return = decomposition.get("expected_return_bps")
    if expected_return is not None:
        _, unit, _ = _unit_spec(units, "expected_return_bps")
        if unit != "bps":
            raise ValueError("P4_RETURN_UNIT_INVALID")

    kwargs: dict[str, Any] = {
        "expected_gross_pnl": gross,
        "expected_net_pnl": net,
        "capital_required": capital,
        "expected_return_bps": expected_return,
        "source_refs": source_refs,
        "metadata": {"adapter": "shared_p4", "adapter_version": "1"},
    }
    return UniversalEconomicAssessmentV1.create(
        scope=scope,
        account_id=account_id,
        mode=mode,
        assessed_at_ns=assessed_at_ns,
        assumptions=assumptions,
        **kwargs,
    )


universal_economic_assessment_from_shared_p4 = adapt_shared_p4_decomposition

__all__ = [
    "adapt_shared_p4_decomposition",
    "universal_economic_assessment_from_shared_p4",
]
