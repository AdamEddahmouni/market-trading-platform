"""Point-in-time semantics for congressional PTR rows via Market Trackers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .pin import UPSTREAM_PIN


@dataclass(frozen=True, slots=True)
class PitClocksPrep:
    """Clock bundle for normalization (evidence-separated)."""

    economic_event_date: str
    filing_date: str
    public_knowledge_date_basis: str
    available_time_basis: str
    aggregator_retrieved_at: str
    event_time_role: str
    available_time_role: str
    pit_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregator_retrieved_at": self.aggregator_retrieved_at,
            "available_time_basis": self.available_time_basis,
            "available_time_role": self.available_time_role,
            "economic_event_date": self.economic_event_date,
            "event_time_role": self.event_time_role,
            "filing_date": self.filing_date,
            "pit_flags": list(self.pit_flags),
            "public_knowledge_date_basis": self.public_knowledge_date_basis,
        }


def derive_pit_clocks(row: Mapping[str, Any]) -> PitClocksPrep:
    """Derive PIT prep without treating transaction date as public knowledge."""

    filed_at = str(row.get("filedAt") or "").strip()
    if not filed_at:
        raise ValueError("MARKET_TRACKERS_FILED_AT_REQUIRED")

    transacted = str(row.get("transactedAt") or "").strip()
    if not transacted:
        raise ValueError("MARKET_TRACKERS_TRANSACTED_AT_REQUIRED")

    provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    retrieved_at = str(provenance.get("retrievedAt") or "")

    flags: list[str] = [
        "PUBLIC_KNOWLEDGE_NOT_TRANSACTION_DATE",
        "MARKET_TRACKERS_REPLACEABLE",
        "PTR_PRIMARY_NOT_SUPPLIED_AGGREGATOR_FILING_ONLY",
        "AGGREGATOR_FILING_PUBLICATION_ONLY",
        "STOCK_ACT_REPORTING_LAG_EXPECTED",
        "ECONOMIC_DATE_PRESENT",
        "DISCLOSED_AMOUNT_IS_RANGE",
    ]

    return PitClocksPrep(
        economic_event_date=transacted,
        filing_date=filed_at,
        public_knowledge_date_basis=f"market_trackers.filedAt:{filed_at}",
        available_time_basis=f"market_trackers.filedAt:{filed_at}",
        aggregator_retrieved_at=retrieved_at,
        event_time_role="economic_attribution_transactedAt",
        available_time_role="filing_publication_day_bounded_pending_ptr_primary_reconcile",
        pit_flags=tuple(dict.fromkeys(flags)),
    )


def pit_doctrine_notes() -> tuple[str, ...]:
    return (
        "Do not use transactedAt as prospective public-knowledge or catalyst ingress time.",
        "Do not map disclosed buy/sell/exchange to LONG/SHORT execution sides.",
        "Amount ranges are disclosure bounds; never infer exact trade size.",
        f"Upstream schemaVersion={UPSTREAM_PIN.schema_version} pinned in market_trackers.congressional_disclosure.pin.",
    )
