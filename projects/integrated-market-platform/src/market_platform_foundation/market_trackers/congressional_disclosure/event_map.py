"""Canonical EventV1 mapping preparation (no runtime normalization in this lane)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ...research.security_identity import resolve_us_equity_ticker
from .pin import ADAPTER_PREP_VERSION

PROVIDER_ID = "market_trackers.congressional_disclosure"
CHANNEL_PREFIX = "congress.ptr"

_PUBLISHER_BY_CHAMBER = {
    "senate": "senate.efd",
    "house": "house.clerk",
}


@dataclass(frozen=True, slots=True)
class EventMapPrep:
    """Deterministic identity + event typing for downstream normalize_event."""

    provider_id: str
    adapter_id: str
    adapter_version: str
    event_family: str
    event_type: str
    channel_id: str
    source_record_id: str
    publisher_id: str
    instrument_qualified_id: str | None
    member_bioguide_id: str | None
    identity_flags: tuple[str, ...]
    payload_core: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "channel_id": self.channel_id,
            "event_family": self.event_family,
            "event_type": self.event_type,
            "identity_flags": list(self.identity_flags),
            "instrument_qualified_id": self.instrument_qualified_id,
            "member_bioguide_id": self.member_bioguide_id,
            "payload_core": self.payload_core,
            "provider_id": self.provider_id,
            "publisher_id": self.publisher_id,
            "source_record_id": self.source_record_id,
        }


def _chamber_channel(chamber: str) -> str:
    return f"{CHANNEL_PREFIX}.{chamber}"


def map_event_v1_prep(row: Mapping[str, Any]) -> EventMapPrep:
    chamber = str(row.get("chamber") or "").strip()
    if chamber not in _PUBLISHER_BY_CHAMBER:
        raise ValueError("MARKET_TRACKERS_CHAMBER_REQUIRED")

    doc_id = str(row.get("docId") or "").strip()
    if not doc_id:
        raise ValueError("MARKET_TRACKERS_DOC_ID_REQUIRED")

    member = row.get("member") if isinstance(row.get("member"), Mapping) else {}
    bioguide = member.get("bioguideId")
    bioguide_text = str(bioguide).strip() if bioguide else None

    identity_flags: list[str] = []
    instrument_qid: str | None = None
    ticker = row.get("ticker")
    if ticker:
        try:
            sec = resolve_us_equity_ticker(
                str(ticker),
                venue_id="US_EQUITY",
                namespace="xa01.provisional",
            )
            instrument_qid = sec.instrument.qualified_id()
        except ValueError:
            identity_flags.append("TICKER_XA01_RESOLUTION_FAILED")
    else:
        identity_flags.append("INSTRUMENT_UNRESOLVED_TICKER_NULL")

    if not bioguide_text:
        identity_flags.append("MEMBER_BIOGUIDE_UNRESOLVED")

    amount = row.get("amountRange") if isinstance(row.get("amountRange"), Mapping) else {}

    payload_core = {
        "chamber": chamber,
        "doc_id": doc_id,
        "row_index": row.get("rowIndex"),
        "member_name": member.get("name"),
        "member_party": member.get("party"),
        "member_state": member.get("state"),
        "member_bioguide_id": bioguide_text,
        "transacted_at": row.get("transactedAt"),
        "filed_at": row.get("filedAt"),
        "ticker": row.get("ticker"),
        "asset_description": row.get("assetDescription"),
        "asset_type": row.get("assetType"),
        "disclosed_side": row.get("side"),
        "owner": row.get("owner"),
        "amount_range_min": amount.get("min"),
        "amount_range_max": amount.get("max"),
        "amount_range_text": amount.get("text"),
        "interpretation": "regulatory_fact_not_trade_signal",
    }

    return EventMapPrep(
        provider_id=PROVIDER_ID,
        adapter_id="market_trackers.congressional_disclosure.row",
        adapter_version=ADAPTER_PREP_VERSION,
        event_family="REGULATORY_DISCLOSURE",
        event_type="CONGRESSIONAL_PTR_ROW",
        channel_id=_chamber_channel(chamber),
        source_record_id=str(row.get("id") or f"{chamber}:{doc_id}:{row.get('rowIndex')}"),
        publisher_id=_PUBLISHER_BY_CHAMBER[chamber],
        instrument_qualified_id=instrument_qid,
        member_bioguide_id=bioguide_text,
        identity_flags=tuple(dict.fromkeys(identity_flags)),
        payload_core=payload_core,
    )
