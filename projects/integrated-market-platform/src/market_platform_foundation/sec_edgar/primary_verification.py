"""EDGAR primary-source verification for SEC Forms 3/4/5 (independent of Market Trackers)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote

from ..canonical import sha256_bytes
from .documents import hash_document
from .identity import normalize_accession, pad_cik
from .live import DATA_HOST, WWW_HOST
from .submission_lookup import (
    edgar_primary_mapping_for_accession,
    load_submissions_payload,
    submission_row_at,
)
from .submission_lookup import find_accession_index
from .transport import SecTransport

PARSER_VERSION = "sec_edgar.primary_verification/1.0.0"
EVIDENCE_CLASS_FIXTURE = "SOFTWARE/FIXTURE/REPLAY"
EVIDENCE_CLASS_LIVE = "PROSPECTIVE_OBSERVATIONAL"


@dataclass(frozen=True, slots=True)
class SecDocumentProvenance:
    primary_url: str
    document_identifier: str
    source_hash_sha256: str
    retrieval_time: str
    parser_version: str
    submissions_url: str
    submissions_hash_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_identifier": self.document_identifier,
            "parser_version": self.parser_version,
            "primary_url": self.primary_url,
            "retrieval_time": self.retrieval_time,
            "source_hash_sha256": self.source_hash_sha256,
            "submissions_hash_sha256": self.submissions_hash_sha256,
            "submissions_url": self.submissions_url,
        }


@dataclass(frozen=True, slots=True)
class SecPrimaryVerificationResult:
    """Outcome of reconciling aggregator row fields against EDGAR submissions."""

    status: str
    evidence_class: str
    edgar_primary: dict[str, str]
    provenance: SecDocumentProvenance
    reconcile_hints: tuple[str, ...]
    aggregator_accession: str
    aggregator_mapping: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregator_mapping": self.aggregator_mapping,
            "edgar_primary": self.edgar_primary,
            "evidence_class": self.evidence_class,
            "provenance": self.provenance.to_dict(),
            "reconcile_hints": list(self.reconcile_hints),
            "status": self.status,
        }


def submissions_url_for_cik(cik: str) -> str:
    return f"{DATA_HOST}/submissions/CIK{pad_cik(cik)}.json"


def primary_document_url(cik: str, accession: str, primary_document: str) -> str:
    compact = normalize_accession(accession).replace("-", "")
    doc = quote(primary_document)
    return f"{WWW_HOST}/Archives/edgar/data/{int(pad_cik(cik))}/{compact}/{doc}"


def archive_index_url(cik: str, accession: str) -> str:
    compact = normalize_accession(accession).replace("-", "")
    acc = normalize_accession(accession)
    return f"{WWW_HOST}/Archives/edgar/data/{int(pad_cik(cik))}/{compact}/{acc}-index.html"


def verify_sec_insider_row_against_submissions(
    row: Mapping[str, Any],
    *,
    submissions_payload: bytes | str | Mapping[str, Any],
    observed_time: str,
    document_body: bytes | None = None,
    document_retrieved_time: str = "",
    live_retrieval: bool = False,
) -> SecPrimaryVerificationResult:
    """Match aggregator accession to EDGAR submissions; optional document hash."""
    accession = normalize_accession(str(row.get("accessionNumber") or ""))
    cik = str(row.get("issuerCik") or row.get("cik") or "").strip()
    if not cik:
        raise ValueError("SEC_ISSUER_CIK_REQUIRED")

    submissions = load_submissions_payload(submissions_payload)
    submissions_bytes = (
        submissions_payload
        if isinstance(submissions_payload, bytes)
        else (
            submissions_payload.encode("utf-8")
            if isinstance(submissions_payload, str)
            else None
        )
    )
    if submissions_bytes is None:
        from ..canonical import canonical_bytes

        submissions_bytes = canonical_bytes(dict(submissions))

    submissions_url = submissions_url_for_cik(cik)
    edgar_primary = edgar_primary_mapping_for_accession(
        submissions,
        accession,
        observed_time=observed_time,
        document_retrieved_time=document_retrieved_time,
    )

    index = find_accession_index(submissions, accession)
    assert index is not None
    slice_row = submission_row_at(submissions, index)
    primary_doc = slice_row.get("primary_document") or ""
    primary_url = (
        primary_document_url(cik, accession, primary_doc)
        if primary_doc
        else archive_index_url(cik, accession)
    )

    provenance_row = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    aggregator_url = str(provenance_row.get("sourceUrl") or "")

    hints: list[str] = ["EDGAR_SUBMISSIONS_MATCHED"]
    if aggregator_url and aggregator_url != primary_url:
        hints.append("AGGREGATOR_SOURCE_URL_MAY_DIFFER_FROM_PRIMARY_DOCUMENT")
    if str(row.get("filedAt") or "") != edgar_primary["filing_date"]:
        hints.append("AGGREGATOR_FILING_DATE_DIFFERS_FROM_EDGAR")

    if document_body is not None:
        doc_hash = hash_document(document_body)
        hints.append("PRIMARY_DOCUMENT_HASH_PRESENT")
    else:
        doc_hash = sha256_bytes(submissions_bytes)
        hints.append("SUBMISSIONS_JSON_HASH_ONLY_NO_DOCUMENT_FETCH")

    evidence_class = EVIDENCE_CLASS_LIVE if live_retrieval else EVIDENCE_CLASS_FIXTURE
    status = "VERIFIED_PRIMARY_SUBMISSIONS" if document_body is None else "VERIFIED_PRIMARY_SUBMISSIONS_AND_DOCUMENT"

    return SecPrimaryVerificationResult(
        status=status,
        evidence_class=evidence_class,
        edgar_primary=edgar_primary,
        provenance=SecDocumentProvenance(
            primary_url=primary_url,
            document_identifier=accession,
            source_hash_sha256=doc_hash,
            retrieval_time=document_retrieved_time or observed_time,
            parser_version=PARSER_VERSION,
            submissions_url=submissions_url,
            submissions_hash_sha256=sha256_bytes(submissions_bytes),
        ),
        reconcile_hints=tuple(dict.fromkeys(hints)),
        aggregator_accession=accession,
        aggregator_mapping={
            "upstream_row_id": str(row.get("id") or ""),
            "upstream_dataset": "market_trackers.insider_transactions",
            "aggregator_source_url": aggregator_url,
            "aggregator_parser": str(provenance_row.get("parser") or ""),
            "aggregator_retrieved_at": str(provenance_row.get("retrievedAt") or ""),
        },
    )


def fetch_and_verify_sec_insider_row(
    row: Mapping[str, Any],
    transport: SecTransport,
    *,
    observed_time: str,
) -> SecPrimaryVerificationResult:
    """Live path: retrieve submissions JSON (and primary doc when listed) via SecTransport."""
    cik = str(row.get("issuerCik") or row.get("cik") or "").strip()
    if not cik:
        raise ValueError("SEC_ISSUER_CIK_REQUIRED")
    accession = normalize_accession(str(row.get("accessionNumber") or ""))
    url = submissions_url_for_cik(cik)
    body = transport.get(url)
    submissions = load_submissions_payload(body)
    index = find_accession_index(submissions, accession)
    if index is None:
        raise ValueError("SEC_ACCESSION_NOT_IN_SUBMISSIONS")
    slice_row = submission_row_at(submissions, index)
    document_body: bytes | None = None
    retrieved = observed_time
    primary_doc = slice_row.get("primary_document") or ""
    if primary_doc:
        doc_url = primary_document_url(cik, accession, primary_doc)
        document_body = transport.get(doc_url, immutable=True)
    return verify_sec_insider_row_against_submissions(
        row,
        submissions_payload=body,
        observed_time=observed_time,
        document_body=document_body,
        document_retrieved_time=retrieved,
        live_retrieval=True,
    )


__all__ = [
    "PARSER_VERSION",
    "SecDocumentProvenance",
    "SecPrimaryVerificationResult",
    "archive_index_url",
    "fetch_and_verify_sec_insider_row",
    "primary_document_url",
    "submissions_url_for_cik",
    "verify_sec_insider_row_against_submissions",
]
