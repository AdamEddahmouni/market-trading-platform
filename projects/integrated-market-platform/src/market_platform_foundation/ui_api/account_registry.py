"""Operational account discovery and context resolution for UI API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..operational_identity import (
    OperationalIdentity,
    OperationalIdentityError,
    derive_demo_identity,
    derive_live_canary_identity,
    derive_paper_identity,
)
from ..paper.ledger import PaperExecutionLedger
from .store import ReplayStore

AUTHORITY_BOUNDARY = "OPERATIONAL_ACCOUNT_DISCOVERY"


class UnknownOperationalAccountError(OperationalIdentityError):
    """Raised when a requested account_id is not registered for the current runtime."""


@dataclass(frozen=True)
class OperationalAccountDescriptor:
    """Discoverable account metadata — no secrets or wire tokens."""

    identity: OperationalIdentity
    display_label: str
    available: bool
    capability_state: str
    reason_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity.to_dict(),
            "display_label": self.display_label,
            "available": self.available,
            "capability_state": self.capability_state,
            "reason_code": self.reason_code,
        }


def _paper_broker_display(ledger: PaperExecutionLedger) -> str:
    if ledger.data_mode == "LIVE_OBSERVATIONAL":
        return "Moomoo (observational marks)"
    if ledger.execution_mode == "BROKER_PAPER":
        return str(ledger.execution_provider or "Broker paper")
    return "Internal simulation"


def list_operational_accounts(store: ReplayStore) -> list[OperationalAccountDescriptor]:
    ledger = store.paper_ledger
    accounts: list[OperationalAccountDescriptor] = []

    if ledger.events:
        paper_identity = derive_paper_identity(
            paper_account_id=ledger.paper_account_id,
            execution_provider=ledger.execution_provider,
            data_mode=ledger.data_mode,
        )
        accounts.append(
            OperationalAccountDescriptor(
                identity=paper_identity,
                display_label=f"Paper · {_paper_broker_display(ledger)}",
                available=True,
                capability_state="AVAILABLE",
            )
        )
        demo_identity = derive_demo_identity(
            paper_account_id=ledger.paper_account_id,
            data_mode=ledger.data_mode,
        )
        accounts.append(
            OperationalAccountDescriptor(
                identity=demo_identity,
                display_label="Demo · read-only simulation view",
                available=True,
                capability_state="READ_ONLY",
            )
        )

    from . import canary_projections

    for account_ref, ctx in canary_projections.list_operator_contexts().items():
        live_identity = derive_live_canary_identity(
            account_ref=account_ref,
            broker=ctx.canary_policy.broker,
        )
        accounts.append(
            OperationalAccountDescriptor(
                identity=live_identity,
                display_label=f"Live canary · {ctx.canary_policy.broker}",
                available=ctx.broker_health in ("HEALTHY", "UNKNOWN"),
                capability_state="OBSERVATIONAL",
                reason_code=None if ctx.broker_health in ("HEALTHY", "UNKNOWN") else ctx.broker_health,
            )
        )
    return accounts


def build_accounts_payload(store: ReplayStore) -> dict[str, Any]:
    accounts = list_operational_accounts(store)
    return {
        "authority_boundary": AUTHORITY_BOUNDARY,
        "accounts": [account.to_dict() for account in accounts],
    }


def resolve_operational_account(
    store: ReplayStore,
    *,
    mode: str | None = None,
    broker: str | None = None,
    account_id: str | None = None,
) -> OperationalIdentity:
    accounts = list_operational_accounts(store)
    if not account_id:
        if mode:
            mode_upper = str(mode).upper()
            matches = [account for account in accounts if account.identity.mode == mode_upper]
            if len(matches) == 1:
                return matches[0].identity
            if len(matches) > 1:
                raise OperationalIdentityError("OPERATIONAL_ACCOUNT_AMBIGUOUS")
        raise OperationalIdentityError("OPERATIONAL_ACCOUNT_ID_REQUIRED")

    for account in accounts:
        identity = account.identity
        if identity.account_id != account_id:
            continue
        if broker and identity.broker != broker:
            continue
        if mode and identity.mode != str(mode).upper():
            continue
        return identity
    raise UnknownOperationalAccountError(f"OPERATIONAL_ACCOUNT_UNKNOWN: {account_id}")


def resolve_paper_portfolio_identity(
    store: ReplayStore,
    *,
    view_mode: str | None = None,
) -> OperationalIdentity:
    ledger = store.paper_ledger
    if not ledger.events:
        raise OperationalIdentityError("PAPER_SESSION_NOT_OPEN")
    view = str(view_mode or "PAPER").upper()
    if view == "DEMO":
        return derive_demo_identity(paper_account_id=ledger.paper_account_id, data_mode=ledger.data_mode)
    if view in {"PAPER", "INTERNAL_SIMULATION", "BROKER_PAPER"}:
        return derive_paper_identity(
            paper_account_id=ledger.paper_account_id,
            execution_provider=ledger.execution_provider,
            data_mode=ledger.data_mode,
        )
    raise OperationalIdentityError(f"OPERATIONAL_VIEW_MODE_INVALID: {view_mode}")
