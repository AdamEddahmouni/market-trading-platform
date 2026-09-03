"""Independent ledger reconciliation."""

from __future__ import annotations

from typing import Any

from .ledger import apply_fill, build_ledger_state


def reconcile_ledgers(
    *,
    authoritative: dict[str, Any],
    fills: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    recomputed = build_ledger_state(initial_cash_minor=int(policy["initial_cash_minor"]))
    for fill in fills:
        recomputed = apply_fill(recomputed, fill=fill, policy=policy)

    fields = (
        "cash_minor",
        "position_shares",
        "realized_pnl_minor",
        "total_commission_minor",
        "total_fees_minor",
    )
    mismatches: list[str] = []
    for field in fields:
        if int(authoritative[field]) != int(recomputed[field]):
            mismatches.append(field)

    return {
        "authoritative": {field: authoritative[field] for field in fields},
        "match": not mismatches,
        "mismatch_fields": mismatches,
        "recomputed": {field: recomputed[field] for field in fields},
        "status": "PASS" if not mismatches else "FAIL",
    }
