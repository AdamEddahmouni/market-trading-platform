"""Congressional PTR primary-source verification (bounded; no anti-bot bypass)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

from ..canonical import canonical_bytes, sha256_bytes

PARSER_VERSION = "congressional_ptr.primary_verification/1.0.0"
EVIDENCE_CLASS_FIXTURE = "SOFTWARE/FIXTURE/REPLAY"
EVIDENCE_CLASS_MANUAL = "SOFTWARE/FIXTURE/REPLAY"
AUTOMATED_DOCUMENT_FETCH_CLAIM = "NOT_SUPPORTED"

_SENATE_HOSTS = frozenset({"efdsearch.senate.gov", "www.senate.gov"})
_HOUSE_HOSTS = frozenset({"disclosures-clerk.house.gov", "clerk.house.gov"})


@dataclass(frozen=True, slots=True)
class PtrDocumentProvenance:
    primary_url: str
    document_identifier: str
    source_hash_sha256: str
    retrieval_time: str
    parser_version: str
    chamber: str
    automation_claim: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "automation_claim": self.automation_claim,
            "chamber": self.chamber,
            "document_identifier": self.document_identifier,
            "parser_version": self.parser_version,
            "primary_url": self.primary_url,
            "retrieval_time": self.retrieval_time,
            "source_hash_sha256": self.source_hash_sha256,
        }


@dataclass(frozen=True, slots=True)
class PtrPrimaryVerificationResult:
    status: str
    evidence_class: str
    ptr_primary: dict[str, str] | None
    provenance: PtrDocumentProvenance
    reconcile_hints: tuple[str, ...]
    aggregator_mapping: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregator_mapping": self.aggregator_mapping,
            "evidence_class": self.evidence_class,
            "ptr_primary": self.ptr_primary,
            "provenance": self.provenance.to_dict(),
            "reconcile_hints": list(self.reconcile_hints),
            "status": self.status,
        }


def _validate_primary_url(chamber: str, url: str) -> tuple[bool, str]:
    text = (url or "").strip()
    if not text:
        return False, "PRIMARY_URL_MISSING"
    parsed = urlparse(text)
    if parsed.scheme not in {"https", "http"}:
        return False, "PRIMARY_URL_SCHEME_INVALID"
    host = (parsed.hostname or "").lower()
    chamber_key = str(chamber or "").strip().lower()
    if chamber_key == "senate":
        if host not in _SENATE_HOSTS:
            return False, "PRIMARY_URL_HOST_NOT_SENATE_EFD"
        return True, "SENATE_EFD_URL_PATTERN"
    if chamber_key == "house":
        if host not in _HOUSE_HOSTS:
            return False, "PRIMARY_URL_HOST_NOT_HOUSE_CLERK"
        return True, "HOUSE_CLERK_URL_PATTERN"
    return False, "CHAMBER_UNKNOWN"


def verify_congressional_row_primary(
    row: Mapping[str, Any],
    *,
    ptr_primary_metadata: Mapping[str, Any] | None = None,
    observed_time: str,
) -> PtrPrimaryVerificationResult:
    """Verify aggregator PTR row against chamber URL + optional primary metadata fixture.

    Automated document download is intentionally not implemented (terms / bot protections).
    Operators may supply ``ptr_primary_metadata`` from a lawful manual or fixture capture.
    """
    chamber = str(row.get("chamber") or "").strip().lower()
    doc_id = str(row.get("docId") or "").strip()
    if not doc_id:
        raise ValueError("PTR_DOC_ID_REQUIRED")

    provenance_row = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    primary_url = str(provenance_row.get("sourceUrl") or "")
    ok, url_hint = _validate_primary_url(chamber, primary_url)

    hints: list[str] = ["MARKET_TRACKERS_REPLACEABLE"]
    if ok:
        hints.append(url_hint)
        hints.append("PRIMARY_URL_CHAMBER_HOST_OK")
    else:
        hints.append(url_hint)

    ptr_primary: dict[str, str] | None = None
    if ptr_primary_metadata is not None:
        filing_date = str(
            ptr_primary_metadata.get("filing_date")
            or ptr_primary_metadata.get("filingDate")
            or ptr_primary_metadata.get("filedAt")
            or ""
        )
        if not filing_date:
            raise ValueError("PTR_FILING_DATE_REQUIRED")
        ptr_primary = {
            "filing_date": filing_date,
            "published_at": str(ptr_primary_metadata.get("published_at") or ptr_primary_metadata.get("publishedAt") or ""),
            "document_retrieved_time": str(
                ptr_primary_metadata.get("document_retrieved_time")
                or ptr_primary_metadata.get("documentRetrievedTime")
                or ""
            ),
        }
        hints.append("PRIMARY_SOURCE_PTR_METADATA_SUPPLIED")
        hints.append("PRIMARY_SOURCE_PTR_WINS")
    else:
        hints.append("PTR_PRIMARY_METADATA_NOT_SUPPLIED")
        hints.append("AGGREGATOR_FILING_PUBLICATION_ONLY")

    payload_hash = sha256_bytes(canonical_bytes(dict(row)))
    if ptr_primary_metadata is not None:
        payload_hash = sha256_bytes(
            canonical_bytes({"row": dict(row), "ptr_primary": dict(ptr_primary_metadata)})
        )
        hints.append("PRIMARY_METADATA_FIXTURE_BOUND")

    status = "VERIFIED_URL_AND_METADATA" if ptr_primary else ("VERIFIED_URL_ONLY" if ok else "AGGREGATOR_URL_UNVERIFIED")
    evidence_class = EVIDENCE_CLASS_FIXTURE if ptr_primary_metadata else EVIDENCE_CLASS_MANUAL

    return PtrPrimaryVerificationResult(
        status=status,
        evidence_class=evidence_class,
        ptr_primary=ptr_primary,
        provenance=PtrDocumentProvenance(
            primary_url=primary_url,
            document_identifier=doc_id,
            source_hash_sha256=payload_hash,
            retrieval_time=str(provenance_row.get("retrievedAt") or observed_time),
            parser_version=PARSER_VERSION,
            chamber=chamber,
            automation_claim=AUTOMATED_DOCUMENT_FETCH_CLAIM,
        ),
        reconcile_hints=tuple(dict.fromkeys(hints)),
        aggregator_mapping={
            "upstream_row_id": str(row.get("id") or ""),
            "upstream_dataset": "market_trackers.congress_trades",
            "aggregator_source_url": primary_url,
            "aggregator_parser": str(provenance_row.get("parser") or ""),
            "aggregator_retrieved_at": str(provenance_row.get("retrievedAt") or ""),
        },
    )


__all__ = [
    "AUTOMATED_DOCUMENT_FETCH_CLAIM",
    "PARSER_VERSION",
    "PtrDocumentProvenance",
    "PtrPrimaryVerificationResult",
    "verify_congressional_row_primary",
]
