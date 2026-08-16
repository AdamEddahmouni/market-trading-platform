"""Fill-driven portfolio ledger and reconciliation."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

from .ledger import apply_fill, build_ledger_state
from .reconciliation import reconcile_ledgers

__all__ = ["apply_fill", "build_ledger_state", "reconcile_ledgers", "ledger_root_hash"]


def ledger_root_hash(state: dict[str, Any]) -> str:
    body = {
        "cash_minor": state["cash_minor"],
        "position_shares": state["position_shares"],
        "realized_pnl_minor": state["realized_pnl_minor"],
        "total_commission_minor": state["total_commission_minor"],
        "total_fees_minor": state["total_fees_minor"],
    }
    return sha256_bytes(canonical_bytes(body))
