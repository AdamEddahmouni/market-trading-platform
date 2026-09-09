"""Read-only IBKR account observation contract (G10 / BL-0301).

Account facts are explicitly ``READ_ONLY_OBSERVATIONAL``. They never mutate
canonical G2 portfolio state, paper ledger, or execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


READ_ONLY_OBSERVATIONAL = "READ_ONLY_OBSERVATIONAL"


@dataclass(frozen=True, slots=True)
class ProviderAccountObservation:
    """Provider account metadata — non-authoritative for portfolio accounting."""

    provider: str
    authority: str
    account_ids: tuple[str, ...]
    entitlement_context: dict[str, Any]
    summary_facts: dict[str, Any]
    received_time_ns: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_ids": list(self.account_ids),
            "authority": self.authority,
            "entitlement_context": dict(self.entitlement_context),
            "provider": self.provider,
            "received_time_ns": self.received_time_ns,
            "summary_facts": dict(self.summary_facts),
        }


def normalize_ibkr_account_discovery(
    payload: Mapping[str, Any],
    *,
    provider: str = "IBKR",
    received_time_ns: int | None = None,
) -> ProviderAccountObservation:
    """Normalize IBKR ``/portfolio/accounts`` style discovery payload."""
    accounts_raw = payload.get("accounts") or payload.get("data") or ()
    account_ids: list[str] = []
    if isinstance(accounts_raw, Mapping):
        account_ids = [str(key) for key in accounts_raw.keys()]
    elif isinstance(accounts_raw, (list, tuple)):
        for item in accounts_raw:
            if isinstance(item, Mapping):
                account_ids.append(str(item.get("accountId") or item.get("id") or ""))
            else:
                account_ids.append(str(item))
    account_ids = [value for value in account_ids if value]
    return ProviderAccountObservation(
        provider=provider,
        authority=READ_ONLY_OBSERVATIONAL,
        account_ids=tuple(account_ids),
        entitlement_context={
            "source": "IBKR_PORTFOLIO_ACCOUNTS",
            "execution_authority": False,
        },
        summary_facts={},
        received_time_ns=received_time_ns,
    )


__all__ = [
    "READ_ONLY_OBSERVATIONAL",
    "ProviderAccountObservation",
    "normalize_ibkr_account_discovery",
]
