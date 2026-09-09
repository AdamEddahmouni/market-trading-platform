"""Explicit futures margin requirement facts (G13).

Structural contract for admitted margin facts — never invents brokerage
formulas. When no authoritative margin row exists for an instrument, futures
opening trades fail closed through ``UNSUPPORTED_RISK_MODEL`` /
``MARGIN_MISSING``.

Acceptable authority sources:

- provider-reported initial/maintenance margin (fixture or live adapter);
- explicit configured margin facts tied to instrument + timestamp + source.

``BROKER_MARGIN_MODEL_AVAILABLE`` is distinct from
``MARGIN_INFRASTRUCTURE_COMPLETE``: this module provides admission,
validation, and pre-trade consumption of *supplied* facts only.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Mapping

from ..portfolio.accounting import exact_decimal

MARGIN_MISSING = "MARGIN_MISSING"
MARGIN_STALE = "MARGIN_STALE"
MARGIN_CURRENCY_MISMATCH = "MARGIN_CURRENCY_MISMATCH"
INSUFFICIENT_MARGIN_CAPACITY = "INSUFFICIENT_MARGIN_CAPACITY"
MARGIN_INSTRUMENT_MISMATCH = "MARGIN_INSTRUMENT_MISMATCH"
MARGIN_INVALID = "MARGIN_INVALID"
MARGIN_AVAILABLE = "MARGIN_AVAILABLE"


class MarginAdmissionCode(StrEnum):
    MARGIN_MISSING = "MARGIN_MISSING"
    MARGIN_STALE = "MARGIN_STALE"
    MARGIN_CURRENCY_MISMATCH = "MARGIN_CURRENCY_MISMATCH"
    MARGIN_INSTRUMENT_MISMATCH = "MARGIN_INSTRUMENT_MISMATCH"
    MARGIN_INVALID = "MARGIN_INVALID"
    MARGIN_AVAILABLE = "MARGIN_AVAILABLE"


@dataclass(frozen=True, slots=True)
class MarginRequirementFacts:
    """One admitted margin requirement row for a specific futures contract."""

    instrument_id: str
    provider: str
    initial_margin_per_contract: Decimal
    maintenance_margin_per_contract: Decimal
    currency: str
    effective_time_ns: int
    received_time_ns: int
    policy_version: str = "g13-margin-v1"
    provenance: str = ""

    def revision_digest(self) -> str:
        from ..canonical import canonical_bytes, sha256_bytes

        return sha256_bytes(
            canonical_bytes(
                {
                    "currency": self.currency,
                    "effective_time_ns": self.effective_time_ns,
                    "initial_margin_per_contract": str(self.initial_margin_per_contract),
                    "instrument_id": self.instrument_id,
                    "maintenance_margin_per_contract": str(self.maintenance_margin_per_contract),
                    "policy_version": self.policy_version,
                    "provider": self.provider,
                    "provenance": self.provenance,
                    "received_time_ns": self.received_time_ns,
                }
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "currency": self.currency,
            "effective_time_ns": self.effective_time_ns,
            "initial_margin_per_contract": str(self.initial_margin_per_contract),
            "instrument_id": self.instrument_id,
            "maintenance_margin_per_contract": str(self.maintenance_margin_per_contract),
            "policy_version": self.policy_version,
            "provider": self.provider,
            "provenance": self.provenance,
            "received_time_ns": self.received_time_ns,
            "revision_digest": self.revision_digest(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MarginRequirementFacts":
        return cls(
            instrument_id=str(payload["instrument_id"]),
            provider=str(payload.get("provider", "UNKNOWN")),
            initial_margin_per_contract=exact_decimal(
                payload["initial_margin_per_contract"],
                field_name="initial_margin_per_contract",
            ),
            maintenance_margin_per_contract=exact_decimal(
                payload.get("maintenance_margin_per_contract", payload["initial_margin_per_contract"]),
                field_name="maintenance_margin_per_contract",
            ),
            currency=str(payload["currency"]).upper(),
            effective_time_ns=int(payload["effective_time_ns"]),
            received_time_ns=int(payload.get("received_time_ns", payload["effective_time_ns"])),
            policy_version=str(payload.get("policy_version", "g13-margin-v1")),
            provenance=str(payload.get("provenance", "")),
        )

    @classmethod
    def from_provider_row(
        cls,
        *,
        instrument_id: str,
        row: Mapping[str, Any],
        provider: str,
        observation_time_ns: int,
        currency: str = "USD",
    ) -> "MarginRequirementFacts":
        """Build facts from a provider margin history row (fixture or live)."""
        initial_raw = row.get("initial_margin")
        maintenance_raw = row.get("maintenance_margin", initial_raw)
        if initial_raw is None:
            raise ValueError(MARGIN_INVALID)
        return cls(
            instrument_id=str(instrument_id).upper(),
            provider=str(provider),
            initial_margin_per_contract=exact_decimal(initial_raw, field_name="initial_margin"),
            maintenance_margin_per_contract=exact_decimal(
                maintenance_raw,
                field_name="maintenance_margin",
            ),
            currency=str(currency).upper(),
            effective_time_ns=observation_time_ns,
            received_time_ns=observation_time_ns,
            provenance=str(row.get("provenance_ref", row.get("provenance", ""))),
        )


@dataclass(frozen=True, slots=True)
class MarginAdmissionResult:
    admitted: bool
    code: str
    facts: MarginRequirementFacts | None = None
    message: str = ""


def admit_margin_facts(
    facts: MarginRequirementFacts | None,
    *,
    instrument_id: str,
    order_currency: str,
    observation_time_ns: int,
    max_staleness_ns: int = 90 * 24 * 60 * 60 * 1_000_000_000,
) -> MarginAdmissionResult:
    """Validate margin facts at the risk boundary (G13 §9)."""
    if facts is None:
        return MarginAdmissionResult(False, MARGIN_MISSING, message="margin facts required")
    if str(facts.instrument_id).upper() != str(instrument_id).upper():
        return MarginAdmissionResult(
            False,
            MARGIN_INSTRUMENT_MISMATCH,
            facts=facts,
            message="margin facts instrument mismatch",
        )
    if facts.initial_margin_per_contract <= 0 or facts.maintenance_margin_per_contract <= 0:
        return MarginAdmissionResult(False, MARGIN_INVALID, facts=facts, message="non-positive margin")
    if str(facts.currency).upper() != str(order_currency).upper():
        return MarginAdmissionResult(
            False,
            MARGIN_CURRENCY_MISMATCH,
            facts=facts,
            message="margin currency mismatch",
        )
    if facts.effective_time_ns > observation_time_ns:
        return MarginAdmissionResult(False, MARGIN_INVALID, facts=facts, message="future-dated margin")
    if observation_time_ns - facts.received_time_ns > max_staleness_ns:
        return MarginAdmissionResult(False, MARGIN_STALE, facts=facts, message="stale margin facts")
    return MarginAdmissionResult(True, MARGIN_AVAILABLE, facts=facts)


def required_margin_minor(
    *,
    facts: MarginRequirementFacts,
    contracts: int,
    scale: int = 100,
) -> int:
    """Worst-case initial margin for ``contracts`` in minor units."""
    if contracts <= 0:
        return 0
    margin = facts.initial_margin_per_contract * Decimal(contracts)
    return int(margin * Decimal(scale))


def margin_facts_from_fixture_row(
    *,
    instrument_id: str,
    row: Mapping[str, Any],
    observation_time_ns: int,
    currency: str = "USD",
) -> MarginRequirementFacts:
    """Convenience builder for admitted fixture margin rows."""
    from ..normalization.equity_bars import iso_to_epoch_ns

    available = row.get("available_time") or row.get("observation_time")
    effective_ns = observation_time_ns
    if available:
        try:
            effective_ns = iso_to_epoch_ns(str(available))
        except (TypeError, ValueError):
            effective_ns = observation_time_ns
    return MarginRequirementFacts.from_provider_row(
        instrument_id=instrument_id,
        row=row,
        provider="margin.fixture.futures_margin",
        observation_time_ns=effective_ns,
        currency=currency,
    )


__all__ = [
    "INSUFFICIENT_MARGIN_CAPACITY",
    "MARGIN_AVAILABLE",
    "MARGIN_CURRENCY_MISMATCH",
    "MARGIN_INSTRUMENT_MISMATCH",
    "MARGIN_INVALID",
    "MARGIN_MISSING",
    "MARGIN_STALE",
    "MarginAdmissionCode",
    "MarginAdmissionResult",
    "MarginRequirementFacts",
    "admit_margin_facts",
    "margin_facts_from_fixture_row",
    "required_margin_minor",
]
