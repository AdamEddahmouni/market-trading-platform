"""Fail-closed Paper commission/fee resolution.

Missing costs are unset, not zero. Explicit ``0`` on the fill or policy is a
declared ZERO_FEES model, not an invented fill.
"""

from __future__ import annotations

from typing import Any, Mapping

COST_FRICTION_UNSET = "COST_FRICTION_UNSET"


class PaperCostFrictionUnset(ValueError):
    """Commission/fees were neither stamped on the fill nor declared on policy."""

    def __init__(self) -> None:
        super().__init__(COST_FRICTION_UNSET)


def resolve_paper_cost_friction(
    *,
    fill: Mapping[str, Any],
    policy: Mapping[str, Any],
    quantity: int,
) -> tuple[int, int]:
    """Return ``(commission_minor, fees_minor)`` or raise if costs are unset.

    Both fields must come from the same source: either both stamped on the fill,
    or both declared on the policy. Mixing a partial fill stamp with a policy
    default is fail-closed.
    """
    fill_has_commission = "commission_minor" in fill
    fill_has_fees = "fees_minor" in fill
    if fill_has_commission and fill_has_fees:
        return int(fill["commission_minor"]), int(fill["fees_minor"])
    if fill_has_commission or fill_has_fees:
        raise PaperCostFrictionUnset()
    if "commission_minor_per_share" not in policy or "fee_minor_per_order" not in policy:
        raise PaperCostFrictionUnset()
    commission = int(quantity) * int(policy["commission_minor_per_share"])
    fees = int(policy["fee_minor_per_order"])
    return commission, fees


__all__ = [
    "COST_FRICTION_UNSET",
    "PaperCostFrictionUnset",
    "resolve_paper_cost_friction",
]
