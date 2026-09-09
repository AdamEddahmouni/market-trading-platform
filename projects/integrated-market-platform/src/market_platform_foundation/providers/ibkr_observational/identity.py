"""Canonical identity boundary for IBKR subscriptions (G6).

Every IBKR subscription resolves to a canonical XA-01 instrument id. The
provider contract (conId + qualified fields) is provenance, never canonical
identity. Symbol-only keys are not authoritative market-data state.

Admission rules (fail closed):

- unknown instrument → rejected (``UNKNOWN_INSTRUMENT``)
- future family / root → rejected (not a tradable depth contract)
- continuous futures series → rejected (no execution/depth authority)
- specific future contract → allowed only when canonical metadata exists
  (``FUTURE_CONTRACT`` with a contract id)
- option contract → requires the specific strike/expiry/right identity
  (``OPTION_CONTRACT`` with an option id)
- equity / ETF → requires the canonical security identity
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ...xa01.contracts import InstrumentRecord
from ...xa01.enums import InstrumentKind
from ...xa01.registry import InstrumentRegistry, get_registry
from .contracts import ContractQualification


class IdentityAdmissionError(ValueError):
    """Fail-closed identity admission failure with a reason code."""

    def __init__(self, reason: str, *, instrument_id: str = "") -> None:
        self.reason = reason
        self.instrument_id = instrument_id
        super().__init__(f"{reason}:{instrument_id}")


class InstrumentLookup(Protocol):
    def get(self, canonical_id: str) -> InstrumentRecord: ...


@dataclass(frozen=True, slots=True)
class AdmittedInstrument:
    instrument_id: str
    qualification: ContractQualification | None


class Xa01Admission:
    """Default admission using the canonical XA-01 instrument registry."""

    def __init__(self, registry: InstrumentRegistry | None = None) -> None:
        self._registry = registry or get_registry()

    def admit(
        self,
        *,
        instrument_id: str,
        con_id: int | None = None,
        qualification: ContractQualification | None = None,
    ) -> AdmittedInstrument:
        canonical = str(instrument_id or "").strip()
        if not canonical:
            raise IdentityAdmissionError("EMPTY_INSTRUMENT_ID")
        try:
            record = self._registry.get(canonical)
        except Exception as exc:
            raise IdentityAdmissionError(
                "UNKNOWN_INSTRUMENT",
                instrument_id=canonical,
            ) from exc
        kind = record.descriptor.identity.instrument_kind
        _assert_observable_kind(kind, canonical)
        effective = qualification
        if con_id is not None and effective is None:
            effective = ContractQualification(con_id=con_id)
        return AdmittedInstrument(
            instrument_id=record.descriptor.identity.canonical_id,
            qualification=effective,
        )

    def admit_with_lookup(
        self,
        *,
        instrument_id: str,
        con_id: int | None = None,
        qualification: ContractQualification | None = None,
        lookup: InstrumentLookup | None = None,
    ) -> AdmittedInstrument:
        """Admission with an injected lookup (tests use a minimal fake)."""
        canonical = str(instrument_id or "").strip()
        if not canonical:
            raise IdentityAdmissionError("EMPTY_INSTRUMENT_ID")
        if lookup is None:
            return self.admit(
                instrument_id=canonical,
                con_id=con_id,
                qualification=qualification,
            )
        try:
            record = lookup.get(canonical)
        except Exception as exc:
            raise IdentityAdmissionError(
                "UNKNOWN_INSTRUMENT",
                instrument_id=canonical,
            ) from exc
        kind = record.descriptor.identity.instrument_kind
        _assert_observable_kind(kind, canonical)
        effective = qualification
        if con_id is not None and effective is None:
            effective = ContractQualification(con_id=con_id)
        return AdmittedInstrument(
            instrument_id=record.descriptor.identity.canonical_id,
            qualification=effective,
        )


_OBSERVABLE_KINDS = frozenset(
    {
        InstrumentKind.TRADABLE_SECURITY,
        InstrumentKind.FUTURE_CONTRACT,
        InstrumentKind.OPTION_CONTRACT,
        InstrumentKind.CRYPTO_PAIR,
        InstrumentKind.COMMODITY_SPOT,
    }
)


def _assert_observable_kind(kind: InstrumentKind, canonical: str) -> None:
    if kind is InstrumentKind.FUTURE_FAMILY:
        raise IdentityAdmissionError(
            "FUTURE_FAMILY_NOT_SUBSCRIBABLE",
            instrument_id=canonical,
        )
    if kind is InstrumentKind.CONTINUOUS_SERIES:
        raise IdentityAdmissionError(
            "CONTINUOUS_FUTURES_NOT_SUBSCRIBABLE",
            instrument_id=canonical,
        )
    if kind not in _OBSERVABLE_KINDS:
        raise IdentityAdmissionError(
            f"NON_OBSERVABLE_KIND:{kind.value}",
            instrument_id=canonical,
        )


def require_observable_kind(kind: InstrumentKind, *, instrument_id: str) -> None:
    """Fail closed unless the kind is a legitimate observational instrument."""
    _assert_observable_kind(kind, instrument_id)


__all__ = [
    "AdmittedInstrument",
    "IdentityAdmissionError",
    "InstrumentLookup",
    "Xa01Admission",
    "require_observable_kind",
]