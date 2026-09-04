"""Canonical operational identity for account-scoped broker and portfolio state.

Operational identity distinguishes execution mode, broker, account, and environment
without conflating display labels or implicit defaults. Cache keys and API envelopes
derive from this model so unrelated contexts cannot share snapshots or risk state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .canonical import canonical_bytes, sha256_bytes

OPERATIONAL_MODES: frozenset[str] = frozenset({"DEMO", "PAPER", "LIVE"})
_ACCOUNT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")

# Synthetic demo view identity — never used for mutations or broker wire.
DEMO_VIEW_PREFIX = "demo:"


class OperationalIdentityError(ValueError):
    """Raised when operational identity is invalid or ambiguous."""


@dataclass(frozen=True)
class OperationalIdentity:
    """Stable identity for operational state that must not leak across contexts."""

    mode: str
    broker: str
    account_id: str
    portfolio_id: str | None = None
    environment: str = "local"

    def __post_init__(self) -> None:
        mode = str(self.mode).upper()
        if mode not in OPERATIONAL_MODES:
            raise OperationalIdentityError(f"OPERATIONAL_MODE_INVALID: {self.mode}")
        object.__setattr__(self, "mode", mode)
        if not self.broker or not str(self.broker).strip():
            raise OperationalIdentityError("OPERATIONAL_BROKER_REQUIRED")
        if not _ACCOUNT_ID_PATTERN.match(self.account_id):
            raise OperationalIdentityError(f"OPERATIONAL_ACCOUNT_ID_INVALID: {self.account_id}")
        if self.portfolio_id is not None and not _ACCOUNT_ID_PATTERN.match(self.portfolio_id):
            raise OperationalIdentityError(f"OPERATIONAL_PORTFOLIO_ID_INVALID: {self.portfolio_id}")

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "mode": self.mode,
            "broker": self.broker,
            "account_id": self.account_id,
            "environment": self.environment,
        }
        if self.portfolio_id is not None:
            body["portfolio_id"] = self.portfolio_id
        return body

    def cache_key_parts(self) -> dict[str, str]:
        """Dimensions included in account-scoped cache keys."""
        parts: dict[str, str] = {
            "mode": self.mode,
            "broker": self.broker,
            "account_id": self.account_id,
            "environment": self.environment,
        }
        if self.portfolio_id is not None:
            parts["portfolio_id"] = self.portfolio_id
        return parts

    def cache_key(self, logical_id: str) -> str:
        body = {"logical_id": logical_id, **self.cache_key_parts()}
        return sha256_bytes(canonical_bytes(body))

    def is_demo_view(self) -> bool:
        return self.mode == "DEMO" or self.account_id.startswith(DEMO_VIEW_PREFIX)


def parse_operational_identity(
    *,
    mode: str | None = None,
    broker: str | None = None,
    account_id: str | None = None,
    portfolio_id: str | None = None,
    environment: str | None = None,
) -> OperationalIdentity:
    if not account_id:
        raise OperationalIdentityError("OPERATIONAL_ACCOUNT_ID_REQUIRED")
    if not broker:
        raise OperationalIdentityError("OPERATIONAL_BROKER_REQUIRED")
    if not mode:
        raise OperationalIdentityError("OPERATIONAL_MODE_REQUIRED")
    return OperationalIdentity(
        mode=mode,
        broker=broker,
        account_id=account_id,
        portfolio_id=portfolio_id,
        environment=environment or "local",
    )


def derive_paper_identity(
    *,
    paper_account_id: str,
    execution_provider: str,
    data_mode: str,
) -> OperationalIdentity:
    broker = _paper_broker_label(execution_provider, data_mode)
    return OperationalIdentity(
        mode="PAPER",
        broker=broker,
        account_id=paper_account_id,
        portfolio_id=paper_account_id,
        environment=_environment_from_data_mode(data_mode),
    )


def derive_demo_identity(*, paper_account_id: str, data_mode: str) -> OperationalIdentity:
    """Synthetic read-only demo view over the internal simulation ledger."""
    return OperationalIdentity(
        mode="DEMO",
        broker="internal.simulation",
        account_id=f"{DEMO_VIEW_PREFIX}{paper_account_id}",
        portfolio_id=paper_account_id,
        environment=_environment_from_data_mode(data_mode),
    )


def derive_live_canary_identity(*, account_ref: str, broker: str, environment: str = "canary") -> OperationalIdentity:
    return OperationalIdentity(
        mode="LIVE",
        broker=broker,
        account_id=account_ref,
        portfolio_id=account_ref,
        environment=environment,
    )


def attach_operational_identity(payload: dict[str, Any], identity: OperationalIdentity) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["operational_identity"] = identity.to_dict()
    return enriched


def _paper_broker_label(execution_provider: str, data_mode: str) -> str:
    provider = str(execution_provider or "INTERNAL").upper()
    if provider == "INTERNAL":
        return "internal.simulation"
    if data_mode == "LIVE_OBSERVATIONAL":
        return "moomoo.observational"
    return provider.lower().replace("_", ".")


def _environment_from_data_mode(data_mode: str) -> str:
    if data_mode == "LIVE_OBSERVATIONAL":
        return "observational"
    if data_mode == "FIXTURE_REPLAY":
        return "fixture"
    return "local"
