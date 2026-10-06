"""OCT1-09 Paper portfolio experiment contract (PaperPortfolioExperimentV1).

An experiment is one explicit, versioned, fake-money portfolio account. Its
identity, starting capital and frozen risk / fill / cost policy identities are
written once at creation; cash, positions and P&L are always derived from the
existing ``PaperExecutionLedger`` event log, never stored here.

The capital is simulated. Execution is the internal Paper simulator. Market
data mode is recorded independently and never implies live-capital execution.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..execution.simulator import SIMULATOR_VERSION, SOURCE_CAPABILITY, BarConservativeSimulator
from ..risk.policy import build_risk_policy

EXPERIMENT_SCHEMA_VERSION = "paper-portfolio-experiment/1.0.0"
EXPERIMENT_INITIAL_CAPITAL_MINOR = 10_000_000  # $100,000.00 at 100 minor units per dollar
EXPERIMENT_CURRENCY = "USD"
EXPERIMENT_EXECUTION_MODE = "INTERNAL_SIMULATION"
EXPERIMENT_SEED_INSTRUMENT = "PORTFOLIO"

STATUS_ACTIVE = "ACTIVE"
STATUS_CLOSED = "CLOSED"
STATUSES = (STATUS_ACTIVE, STATUS_CLOSED)

SLIPPAGE_MODEL = "NOT_SEPARATELY_MODELED"
SLIPPAGE_STATEMENT = (
    "No separate slippage term. Adverse execution is embedded in the conservative bar fill: "
    "buys fill at the bar high and sells at the bar low of the first bar strictly after the "
    "order, capped by a share of that bar's volume."
)
NOT_A_PROFITABILITY_CLAIM = (
    "Paper P&L is accounting of simulated fills against observed prices. "
    "It is not evidence of a profitable strategy or a predictive edge."
)

EVIDENCE_PROSPECTIVE = "PROSPECTIVE_PAPER_WITH_LIVE_OBSERVATIONAL_DATA"
EVIDENCE_CONTROLLED = "SOFTWARE_CONTROLLED"
EVIDENCE_REPLAY = "HISTORICAL_REPLAY"


def build_experiment_policy() -> dict[str, Any]:
    """The experiment's frozen risk policy: canonical limits, $100,000 cash."""

    return build_risk_policy(
        initial_cash_minor=EXPERIMENT_INITIAL_CAPITAL_MINOR,
        currency=EXPERIMENT_CURRENCY,
    )


def fill_model_identity() -> dict[str, Any]:
    return {
        "fill_model_id": f"{BarConservativeSimulator.registry_id}@{SIMULATOR_VERSION}",
        "registry_id": BarConservativeSimulator.registry_id,
        "simulator_version": SIMULATOR_VERSION,
        "source_capability": SOURCE_CAPABILITY,
    }


def cost_policy(policy: dict[str, Any]) -> dict[str, Any]:
    body = {
        "commission_minor_per_share": int(policy["commission_minor_per_share"]),
        "fee_minor_per_order": int(policy["fee_minor_per_order"]),
        "fill_model_id": fill_model_identity()["fill_model_id"],
        "participation_cap_denominator": int(policy["participation_cap_denominator"]),
        "participation_cap_numerator": int(policy["participation_cap_numerator"]),
        "slippage_model": SLIPPAGE_MODEL,
    }
    return {**body, "cost_policy_id": "PCP-" + sha256_bytes(canonical_bytes(body))[:32]}


def evidence_class_for(data_mode: str) -> str:
    mode = str(data_mode).upper()
    if mode == "LIVE_OBSERVATIONAL":
        return EVIDENCE_PROSPECTIVE
    if mode == "HISTORICAL_CAPTURE":
        return EVIDENCE_REPLAY
    return EVIDENCE_CONTROLLED


def new_experiment_id(*, name: str, created_at_ns: int) -> str:
    body = {"created_at_ns": created_at_ns, "name": name, "nonce": uuid.uuid4().hex}
    return "PPE-" + sha256_bytes(canonical_bytes(body))[:32]


def build_experiment_record(
    *,
    experiment_id: str,
    name: str,
    created_at_ns: int,
    paper_account_id: str,
    paper_session_id: str,
    policy: dict[str, Any],
    data_mode: str,
    data_providers: list[str],
    execution_provider: str,
    execution_authority: str,
    source_scope: str,
    notes: str = "",
) -> dict[str, Any]:
    """Immutable creation record. Status and close facts are stored beside it."""

    if int(policy["initial_cash_minor"]) != EXPERIMENT_INITIAL_CAPITAL_MINOR:
        raise ValueError("EXPERIMENT_CAPITAL_INVALID")
    costs = cost_policy(policy)
    return {
        "capital_kind": "SIMULATED",
        "cost_policy": costs,
        "cost_policy_id": costs["cost_policy_id"],
        "created_at_ns": created_at_ns,
        "currency": str(policy["currency"]),
        "data_mode": data_mode,
        "data_providers": list(data_providers),
        "evidence_class": evidence_class_for(data_mode),
        "execution_authority": execution_authority,
        "execution_mode": EXPERIMENT_EXECUTION_MODE,
        "execution_provider": execution_provider,
        "experiment_id": experiment_id,
        "fill_model": fill_model_identity(),
        "fill_model_id": fill_model_identity()["fill_model_id"],
        "initial_capital_minor": int(policy["initial_cash_minor"]),
        "live_capital": False,
        "name": name,
        "notes": notes,
        "paper_account_id": paper_account_id,
        "paper_session_id": paper_session_id,
        "risk_policy": dict(policy),
        "risk_policy_id": str(policy["risk_policy_identity_hash"]),
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "slippage_model": SLIPPAGE_MODEL,
        "slippage_statement": SLIPPAGE_STATEMENT,
        "source_scope": source_scope,
        "started_at_ns": created_at_ns,
    }
