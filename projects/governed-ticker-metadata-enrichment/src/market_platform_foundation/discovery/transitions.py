"""Candidate transition tracking across discovery runs."""

from __future__ import annotations

from typing import Any

from .models import CandidateTransition


def compute_transitions(
    *,
    previous_symbols: set[str],
    current_symbols: set[str],
    reentered_symbols: set[str] | None = None,
) -> list[dict[str, Any]]:
    reentered = reentered_symbols or set()
    transitions: list[dict[str, Any]] = []
    for symbol in sorted(current_symbols):
        if symbol in previous_symbols:
            kind = CandidateTransition.STILL_MATCHES
        elif symbol in reentered:
            kind = CandidateTransition.REENTERED
        else:
            kind = CandidateTransition.NEW_ENTRY
        transitions.append({"instrument_id": symbol, "transition": kind.value})
    for symbol in sorted(previous_symbols - current_symbols):
        transitions.append({"instrument_id": symbol, "transition": CandidateTransition.DROPPED.value})
    return transitions


def load_previous_symbols(catalog_row: dict[str, Any] | None) -> set[str]:
    if not catalog_row:
        return set()
    symbols = catalog_row.get("candidate_symbols") or []
    return {str(s).upper() for s in symbols if s}
