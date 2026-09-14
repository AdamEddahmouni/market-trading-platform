"""Canonical EventV1 mapping preparation (no runtime normalization yet)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ...research.security_identity import resolve_us_equity_ticker
from ...sec_edgar.identity import normalize_accession
from .pin import ADAPTER_PREP_VERSION

PROVIDER_ID = "market_trackers.sec_insider"
CHANNEL_PREFIX = "sec.form"


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
    entity_cik: str
    insider_cik: str
    identity_flags: tuple[str, ...]
    payload_core: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "channel_id": self.channel_id,
            "entity_cik": self.entity_cik,
            "event_family": self.event_family,
            "event_type": self.event_type,
            "identity_flags": list(self.identity_flags),
            "insider_cik": self.insider_cik,
            "instrument_qualified_id": self.instrument_qualified_id,
            "payload_core": self.payload_core,
            "provider_id": self.provider_id,
            "publisher_id": self.publisher_id,
            "source_record_id": self.source_record_id,
        }


def _form_channel(form_type: str) -> str:
    base = form_type.replace("/A", "_AMEND").replace("/", "_")
    return f"{CHANNEL_PREFIX}.{base}"


def map_event_v1_prep(row: Mapping[str, Any]) -> EventMapPrep:
    accession = normalize_accession(str(row.get("accessionNumber") or ""))
    if not accession:
        raise ValueError("MARKET_TRACKERS_ACCESSION_REQUIRED")

    form_type = str(row.get("formType") or "")
    insider = row.get("insider") if isinstance(row.get("insider"), Mapping) else {}
    issuer_cik = str(row.get("issuerCik") or "").strip()
    insider_cik = str(insider.get("cik") or "").strip()

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

    if not issuer_cik:
        identity_flags.append("ISSUER_CIK_MISSING")

    payload_core = {
        "accession_number": accession,
        "form_type": form_type,
        "issuer_cik": issuer_cik,
        "issuer_name": row.get("issuerName"),
        "insider_name": insider.get("name"),
        "transaction_code": row.get("code"),
        "acquired_disposed": row.get("acquiredDisposed"),
        "security_title": row.get("securityTitle"),
        "shares": row.get("shares"),
        "price_per_share": row.get("pricePerShare"),
        "shares_owned_after": row.get("sharesOwnedAfter"),
        "ownership": row.get("ownership"),
        "is_derivative": row.get("isDerivative"),
        "transacted_at": row.get("transactedAt"),
        "filed_at": row.get("filedAt"),
        "interpretation": "regulatory_fact_not_trade_signal",
    }

    return EventMapPrep(
        provider_id=PROVIDER_ID,
        adapter_id="market_trackers.sec_insider.row",
        adapter_version=ADAPTER_PREP_VERSION,
        event_family="REGULATORY_OWNERSHIP",
        event_type="INSIDER_OWNERSHIP_ROW",
        channel_id=_form_channel(form_type),
        source_record_id=str(row.get("id") or accession),
        publisher_id="sec.edgar",
        instrument_qualified_id=instrument_qid,
        entity_cik=issuer_cik,
        insider_cik=insider_cik,
        identity_flags=tuple(dict.fromkeys(identity_flags)),
        payload_core=payload_core,
    )
