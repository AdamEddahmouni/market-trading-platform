"""Point-in-time semantics for SEC Form 3/4/5 rows via Market Trackers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .pin import UPSTREAM_PIN


@dataclass(frozen=True, slots=True)
class PitClocksPrep:
    """Clock bundle for normalization (evidence-separated)."""

    economic_event_date: str | None
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
    """Derive PIT prep without treating transaction date as public knowledge.

    Market Trackers exposes ``filedAt`` (filing date) and optional ``transactedAt``.
    EDGAR ``acceptanceDateTime`` is authoritative for sub-day public availability
    but is not present on the published row — only ``provenance.sourceUrl`` links
    to the primary filing.
    """

    filed_at = str(row.get("filedAt") or "").strip()
    if not filed_at:
        raise ValueError("MARKET_TRACKERS_FILED_AT_REQUIRED")

    transacted = row.get("transactedAt")
    economic = str(transacted).strip() if transacted else None
    provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    retrieved_at = str(provenance.get("retrievedAt") or "")

    flags: list[str] = [
        "PUBLIC_KNOWLEDGE_NOT_TRANSACTION_DATE",
        "MARKET_TRACKERS_REPLACEABLE",
        "SEC_PRIMARY_NOT_SUPPLIED_AGGREGATOR_FILING_ONLY",
        "AGGREGATOR_FILING_PUBLICATION_ONLY",
    ]
    if economic:
        flags.append("ECONOMIC_DATE_PRESENT")
    else:
        flags.append("FORM3_OR_HOLDING_ROW_NO_TRANSACTION_DATE")

    # Filing date is a day-bounded lower bound on public knowledge from SEC filing,
    # not the economic transaction moment and not a prospective catalyst timestamp.
    return PitClocksPrep(
        economic_event_date=economic,
        filing_date=filed_at,
        public_knowledge_date_basis=f"market_trackers.filedAt:{filed_at}",
        available_time_basis=f"market_trackers.filedAt:{filed_at}",
        aggregator_retrieved_at=retrieved_at,
        event_time_role="economic_attribution_only_when_transactedAt_present",
        available_time_role="filing_publication_day_bounded_pending_edgar_acceptance_reconcile",
        pit_flags=tuple(dict.fromkeys(flags)),
    )


def pit_doctrine_notes() -> tuple[str, ...]:
    return (
        "Do not use transactedAt as prospective public-knowledge or catalyst ingress time.",
        "Do not treat Form 4 rows as automatically bullish or bearish from code or A/D alone.",
        f"Upstream schemaVersion={UPSTREAM_PIN.schema_version} pinned in market_trackers.sec_insider.pin.",
    )
