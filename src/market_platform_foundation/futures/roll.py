"""Futures roll engine — lead contract selection and roll state semantics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from ..contracts.futures import RollState
from ..donor_patterns.futures_lane import get_third_friday


@dataclass(frozen=True, slots=True)
class ContractLiquidity:
    """Per-contract liquidity metrics for lead selection."""

    contract_id: str
    expiration: str
    volume: int
    open_interest: int
    days_to_expiration: int


@dataclass(frozen=True, slots=True)
class LeadContractSelection:
    """Deterministic lead-contract selection result with documented rule version."""

    lead_contract_id: str
    nearest_expiry_id: str
    highest_volume_id: str
    highest_oi_id: str
    roll_state: RollState
    rule_version: str
    execution_contract_id: str


LEAD_SELECTION_RULE_V1 = "volume_oi_dte_v1"


def days_between(today: date, expiration: date) -> int:
    return (expiration - today).days


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def select_lead_contract(
    contracts: list[ContractLiquidity],
    *,
    today: date | None = None,
    roll_window_days: int = 5,
    min_dte: int = 2,
) -> LeadContractSelection | None:
    """Select lead contract using volume + OI + DTE rule (v1).

    Does not simply choose nearest expiration. Uses highest combined liquidity
    among contracts with DTE >= min_dte, with roll window awareness.
    """
    if not contracts:
        return None
    today = today or date.today()
    eligible = [c for c in contracts if c.days_to_expiration >= min_dte]
    if not eligible:
        eligible = list(contracts)

    nearest = min(eligible, key=lambda c: c.days_to_expiration)
    highest_volume = max(eligible, key=lambda c: c.volume)
    highest_oi = max(eligible, key=lambda c: c.open_interest)

    # Combined score: prioritize OI then volume for financial futures convention
    def liquidity_score(c: ContractLiquidity) -> tuple[int, int, int]:
        return (c.open_interest, c.volume, -c.days_to_expiration)

    lead = max(eligible, key=liquidity_score)

    roll_state = RollState.POST_ROLL
    if nearest.days_to_expiration <= roll_window_days:
        if lead.contract_id != nearest.contract_id:
            roll_state = RollState.ROLLING
        else:
            roll_state = RollState.EXPIRING
    elif nearest.days_to_expiration <= roll_window_days + 7:
        roll_state = RollState.PRE_ROLL

    return LeadContractSelection(
        lead_contract_id=lead.contract_id,
        nearest_expiry_id=nearest.contract_id,
        highest_volume_id=highest_volume.contract_id,
        highest_oi_id=highest_oi.contract_id,
        roll_state=roll_state,
        rule_version=LEAD_SELECTION_RULE_V1,
        execution_contract_id=lead.contract_id,
    )


def es_quarterly_expiration(year: int, quarter_month: int) -> date:
    """Third Friday of Mar/Jun/Sep/Dec for ES-style quarterly contracts."""
    return get_third_friday(year, quarter_month)


def contract_liquidity_from_dict(row: dict[str, Any], today: date | None = None) -> ContractLiquidity | None:
    contract_id = str(row.get("contract_id", ""))
    expiration = str(row.get("expiration", ""))
    if not contract_id or not expiration:
        return None
    today = today or date.today()
    exp_date = parse_iso_date(expiration)
    return ContractLiquidity(
        contract_id=contract_id,
        expiration=expiration,
        volume=int(row.get("volume", 0) or 0),
        open_interest=int(row.get("open_interest", 0) or 0),
        days_to_expiration=days_between(today, exp_date),
    )
