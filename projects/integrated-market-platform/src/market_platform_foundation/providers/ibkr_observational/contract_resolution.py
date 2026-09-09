"""Provider contract resolution for IBKR observational runtime (G8).

Maps provider contract facts → ``ContractQualification`` provenance. Canonical
identity remains XA-01; provider symbols never become canonical identity.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Protocol

from .contracts import ContractQualification
from .identity import IdentityAdmissionError, Xa01Admission


class QualifyBroker(Protocol):
    def qualifyContracts(self, *contracts: Any) -> list[Any]: ...


def qualification_from_contract(contract: Any) -> ContractQualification:
    """Build provider provenance from a qualified ib_insync contract."""
    con_id = int(getattr(contract, "conId", 0) or 0)
    if con_id <= 0:
        raise ValueError("qualified contract missing conId")
    return ContractQualification(
        con_id=con_id,
        symbol=str(getattr(contract, "symbol", "") or ""),
        sec_type=str(getattr(contract, "secType", "") or ""),
        exchange=str(getattr(contract, "exchange", "") or ""),
        currency=str(getattr(contract, "currency", "") or ""),
        multiplier=str(getattr(contract, "multiplier", "") or "") or None,
        local_symbol=str(getattr(contract, "localSymbol", "") or "") or None,
        last_trade_date=str(getattr(contract, "lastTradeDateOrContractMonth", "") or "") or None,
        strike=str(getattr(contract, "strike", "") or "") or None,
        right=str(getattr(contract, "right", "") or "") or None,
        trading_class=str(getattr(contract, "tradingClass", "") or "") or None,
    )


def resolve_equity_contract(
    broker: QualifyBroker,
    *,
    instrument_id: str,
    admission: Xa01Admission | None = None,
    lookup: Any | None = None,
) -> tuple[str, ContractQualification]:
    """Resolve a canonical equity id to provider qualification facts."""
    gate = admission or Xa01Admission()
    if lookup is not None:
        admitted = gate.admit_with_lookup(instrument_id=instrument_id, lookup=lookup)
    else:
        admitted = gate.admit(instrument_id=instrument_id)
    canonical = admitted.instrument_id
    contract = SimpleNamespace(symbol=canonical, secType="STK", exchange="SMART", currency="USD")
    qualified = broker.qualifyContracts(contract)
    if not qualified:
        raise IdentityAdmissionError("CONTRACT_RESOLUTION_FAILED", instrument_id=canonical)
    qualification = qualification_from_contract(qualified[0])
    return canonical, qualification


def resolve_specific_contract(
    broker: QualifyBroker,
    *,
    instrument_id: str,
    contract_builder: Any,
    admission: Xa01Admission | None = None,
    lookup: Any | None = None,
) -> tuple[str, ContractQualification]:
    """Resolve option/future contracts that require specific descriptors."""
    gate = admission or Xa01Admission()
    if lookup is not None:
        admitted = gate.admit_with_lookup(instrument_id=instrument_id, lookup=lookup)
    else:
        admitted = gate.admit(instrument_id=instrument_id)
    canonical = admitted.instrument_id
    sec_type = str(getattr(contract_builder, "secType", "") or "")
    if sec_type == "OPT":
        if not all(
            getattr(contract_builder, attr, None)
            for attr in ("strike", "right", "lastTradeDateOrContractMonth")
        ):
            raise IdentityAdmissionError("OPTION_UNDERLYING_ONLY", instrument_id=canonical)
    if sec_type == "FUT":
        if not getattr(contract_builder, "lastTradeDateOrContractMonth", None):
            raise IdentityAdmissionError("FUTURE_FAMILY_NOT_SUBSCRIBABLE", instrument_id=canonical)
    qualified = broker.qualifyContracts(contract_builder)
    if not qualified:
        raise IdentityAdmissionError("CONTRACT_RESOLUTION_FAILED", instrument_id=canonical)
    qualification = qualification_from_contract(qualified[0])
    return canonical, qualification


__all__ = [
    "QualifyBroker",
    "qualification_from_contract",
    "resolve_equity_contract",
    "resolve_specific_contract",
]
