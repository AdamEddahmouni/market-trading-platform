"""Deterministic, outcome-blind contract resolution (ibapi-free, unit-testable).

Filters candidates using only structural fields -- never prices, outcomes, company
names, or web lookups.
"""

from __future__ import annotations

from collections.abc import Sequence

from .models import ContractCandidate, ContractResolution
from .statuses import ContractStatus


def _passes_filter(symbol: str, candidate: ContractCandidate) -> bool:
    if candidate.sec_type != "STK":
        return False
    if candidate.currency != "USD":
        return False
    if candidate.con_id <= 0:
        return False
    wanted = symbol.strip().upper()
    return wanted in {candidate.symbol.strip().upper(), candidate.local_symbol.strip().upper()}


def resolve_contract(
    symbol: str, candidates: Sequence[ContractCandidate]
) -> ContractResolution:
    """Resolve a single frozen symbol to at most one unique contract."""
    kept = [c for c in candidates if _passes_filter(symbol, c)]
    by_con_id: dict[int, ContractCandidate] = {}
    for candidate in kept:
        by_con_id.setdefault(candidate.con_id, candidate)

    all_candidates = tuple(candidates)
    if len(by_con_id) == 1:
        resolved = next(iter(by_con_id.values()))
        return ContractResolution(
            requested_symbol=symbol,
            status=ContractStatus.CONTRACT_RESOLVED,
            candidates=all_candidates,
            resolved=resolved,
            reason=f"unique conId {resolved.con_id}",
        )
    if len(by_con_id) == 0:
        return ContractResolution(
            requested_symbol=symbol,
            status=ContractStatus.CONTRACT_NOT_RESOLVED,
            candidates=all_candidates,
            resolved=None,
            reason="no STK/USD candidate matched the requested symbol",
        )
    return ContractResolution(
        requested_symbol=symbol,
        status=ContractStatus.CONTRACT_AMBIGUOUS,
        candidates=all_candidates,
        resolved=None,
        reason=f"{len(by_con_id)} distinct conIds matched; not guessed",
    )


__all__ = ["resolve_contract"]
