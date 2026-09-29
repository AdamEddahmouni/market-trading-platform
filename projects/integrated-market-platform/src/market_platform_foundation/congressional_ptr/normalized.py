"""One normalized congressional disclosure for both chambers, with point-in-time rules (S14).

House (Clerk PTR PDFs) and Senate (eFD reports) normalize into ``CongressionalDisclosure``.
Only genuinely common semantics are normalized; chamber-specific fields travel in
``source_specific`` unchanged. Clocks stay separate:

* ``transaction_date`` — when the member (or spouse/dependent) traded;
* ``notification_date`` — House only (when the filer was notified);
* ``filing_date`` / ``filed_at`` — as the source states them (House: date; Senate: minute);
* ``available_at`` — public availability used for point-in-time queries, with
  ``available_basis`` and ``date_quality`` (a date-only source is bounded at the end of
  its Eastern day; no time is invented);
* ``retrieved_at`` — IMP's first retrieval (or the operator's, for a Senate import);
* ``imp_known_at`` — the later of the two: when IMP itself could have known.

``visible_as_of`` never uses the transaction date; ``versions_as_of`` picks the report
version known at a cutoff without erasing earlier ones.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from . import house as house_module
from . import senate as senate_module
from .identity import MemberResolution, MemberResolver, SourceIdentity, house_identity, split_full_name

CONTRACT_VERSION = "congressional_disclosure/1.0.0"


def _iso(moment: datetime | None) -> str | None:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


@dataclass(frozen=True, slots=True)
class CongressionalDisclosure:
    id: str
    chamber: str
    source_provider: str                 # house_ptr / senate_efd
    source_document: str                 # House DocID / Senate report id
    source_url: str | None
    row_index: int
    identity: SourceIdentity
    owner: str
    asset_description: str
    disclosed_ticker: str | None
    asset_type_code: str | None
    asset_type: str | None
    transaction_type: str
    transaction_type_code: str
    transaction_date: date | None
    notification_date: date | None
    filing_date: date
    filed_at: datetime | None
    available_at: datetime
    available_basis: str
    date_quality: str
    retrieved_at: datetime | None
    amount: house_module.AmountRange | None
    parse_state: str
    evidence_class: str
    quality_flags: tuple[str, ...] = ()
    amendment: dict[str, Any] | None = None
    version_key: str | None = None
    source_specific: dict[str, Any] = field(default_factory=dict)
    legacy_member_id: str | None = None   # S12's member id, kept so existing filter links keep working

    @property
    def matchable_ticker(self) -> str | None:
        return self.disclosed_ticker if self.asset_type_code in house_module.TICKER_ASSET_TYPES else None

    @property
    def imp_known_at(self) -> datetime:
        return house_module.imp_known_at(self.available_at, self.retrieved_at)

    def to_row(self, resolution: MemberResolution | None) -> dict[str, Any]:
        """The Screener row (S12 keys preserved; S14 keys added)."""

        identity = self.identity
        seat = identity.seat or identity.state or ""
        member = {"name": identity.source_name, "source_name": identity.source_name, "state_district": seat,
                  "chamber": self.chamber, "member_id": self.legacy_member_id or f"{self.chamber}:{identity.source_name.upper()}",
                  "identity_basis": "HOUSE_INDEX_NAME_AND_DISTRICT" if self.chamber == "HOUSE" else "SENATE_EFD_FILER_NAME"}
        if resolution is not None:
            member.update(resolution.to_dict())
            if resolution.confident:
                member["name"] = resolution.canonical_name
        return {
            "id": self.id, "chamber": self.chamber, "member": member, "owner": self.owner,
            "asset_description": self.asset_description, "asset_type_code": self.asset_type_code,
            "asset_type": self.asset_type, "disclosed_ticker": self.disclosed_ticker,
            "matchable_ticker": self.matchable_ticker, "transaction_type": self.transaction_type,
            "transaction_type_code": self.transaction_type_code,
            "transaction_date": self.transaction_date.isoformat() if self.transaction_date else None,
            "notification_date": self.notification_date.isoformat() if self.notification_date else None,
            "filing_date": self.filing_date.isoformat(), "filed_at": _iso(self.filed_at),
            "available_at": _iso(self.available_at), "available_basis": self.available_basis,
            "date_quality": self.date_quality, "retrieved_at": _iso(self.retrieved_at),
            "imp_known_at": _iso(self.imp_known_at),
            "amount": self.amount.to_dict() if self.amount else None,
            "disclosure_lag_days": house_module.disclosure_lag_days(self.transaction_date, self.filing_date),
            "doc_id": self.source_document, "source_url": self.source_url, "source_provider": self.source_provider,
            "parse_state": self.parse_state, "evidence_class": self.evidence_class,
            "quality_flags": list(self.quality_flags), "amendment": self.amendment,
            "source_specific": self.source_specific, "contract_version": CONTRACT_VERSION,
        }


# ------------------------------------------------------------------ House
def from_house(filing: house_module.HouseFiling, document: house_module.PtrDocument,
               retrieved_at: datetime | None) -> list[CongressionalDisclosure]:
    available, basis = house_module.filing_available_at(filing.filing_date)
    identity = house_identity(filing.first, filing.last, filing.suffix, filing.prefix, filing.state_district,
                              filing.filing_date, source_name=filing.member_name)
    out = []
    for txn in document.transactions:
        amended = (txn.filing_status or "").lower().startswith("amend")
        out.append(CongressionalDisclosure(
            id=f"house:{filing.doc_id}:{txn.row_index}", chamber="HOUSE", source_provider="house_ptr",
            source_document=filing.doc_id, source_url=filing.document_url, row_index=txn.row_index, identity=identity,
            owner=txn.owner, asset_description=txn.asset_description, disclosed_ticker=txn.disclosed_ticker,
            asset_type_code=txn.asset_type_code, asset_type=house_module.TICKER_ASSET_TYPES.get(txn.asset_type_code or ""),
            transaction_type=txn.transaction_type, transaction_type_code=txn.transaction_type_code,
            transaction_date=txn.transaction_date, notification_date=txn.notification_date,
            filing_date=filing.filing_date, filed_at=None, available_at=available, available_basis=basis,
            date_quality="DATE_ONLY", retrieved_at=retrieved_at, amount=txn.amount, parse_state=document.parse_state,
            evidence_class=txn.evidence_class, quality_flags=txn.quality_flags,
            # The House form marks an amended row but does not name the report it amends: no linkage is invented.
            amendment={"row_filing_status": txn.filing_status, "linked_to": None} if amended else None,
            source_specific={"filing_status": txn.filing_status, "description": txn.description,
                             "subholding_of": txn.subholding_of, "source_page": txn.source_page,
                             "document_class": document.document_class, "extraction": txn.extraction},
            legacy_member_id=filing.member_id))
    return out


# ------------------------------------------------------------------ Senate
def senate_identity(report: senate_module.SenateReport) -> SourceIdentity:
    name = report.filer_name or ""
    return SourceIdentity("SENATE", "senate_efd", name, split_full_name(name), report.filed_date)


def from_senate(report: senate_module.SenateReport) -> list[CongressionalDisclosure]:
    available, basis, quality = report.available_at
    if available is None or report.filed_date is None:
        return []
    identity = senate_identity(report)
    version_key = f"senate:{identity.key}:{report.report_for.isoformat() if report.report_for else report.report_id}"
    out = []
    for txn in report.transactions:
        out.append(CongressionalDisclosure(
            id=f"senate:{report.report_id}:{txn.row_index}", chamber="SENATE", source_provider="senate_efd",
            source_document=report.report_id, source_url=report.source_url, row_index=txn.row_index, identity=identity,
            owner=txn.owner, asset_description=txn.asset_description, disclosed_ticker=txn.disclosed_ticker,
            asset_type_code=txn.asset_type_code, asset_type=txn.asset_type, transaction_type=txn.transaction_type,
            transaction_type_code=txn.transaction_type_code, transaction_date=txn.transaction_date,
            notification_date=None, filing_date=report.filed_date, filed_at=report.filed_at, available_at=available,
            available_basis=basis, date_quality=quality, retrieved_at=report.retrieved_at, amount=txn.amount,
            parse_state=report.parse_state, evidence_class=txn.evidence_class, quality_flags=txn.quality_flags,
            amendment={"amendment_number": report.amendment_number} if report.is_amendment else None,
            version_key=version_key,
            source_specific={"row_number": txn.row_number, "owner_text": txn.owner_text,
                             "transaction_type_text": txn.transaction_type_text, "comment": txn.comment,
                             "report_for": report.report_for.isoformat() if report.report_for else None,
                             "filer_alternate": report.filer_alternate, "retrieved_basis": report.retrieved_basis,
                             "file_name": report.file_name}))
    return out


# ------------------------------------------------------------------ point in time
def visible_as_of(items: Iterable[CongressionalDisclosure], cutoff: datetime, *,
                  clock: str = "public") -> list[CongressionalDisclosure]:
    """Disclosures known at ``cutoff``: ``clock="public"`` (availability) or ``"imp"`` (IMP's own knowledge)."""

    if clock not in ("public", "imp"):
        raise ValueError("INVALID_PIT_CLOCK")
    return [item for item in items if (item.available_at if clock == "public" else item.imp_known_at) <= cutoff]


def versions_as_of(items: Iterable[CongressionalDisclosure], cutoff: datetime) -> dict[str, dict[str, Any]]:
    """Per linked report (``version_key``): which version was the newest public one at ``cutoff``.

    Earlier versions are never dropped from the record; they are reported as superseded.
    Rows without a version key (House rows, whose amendments do not name the original) are omitted.
    """

    reports: dict[str, dict[str, tuple[int, datetime]]] = {}
    for item in visible_as_of(items, cutoff):
        if item.version_key is None:
            continue
        number = (item.amendment or {}).get("amendment_number") or 0
        reports.setdefault(item.version_key, {})[item.source_document] = (number, item.available_at)
    out = {}
    for key, versions in reports.items():
        ordered = sorted(versions.items(), key=lambda pair: (pair[1][0], pair[1][1], pair[0]))
        out[key] = {"current": ordered[-1][0], "superseded": [doc for doc, _ in ordered[:-1]], "versions": len(ordered)}
    return out


def to_rows(items: list[CongressionalDisclosure], *, resolver: MemberResolver | None = None,
            now: datetime | None = None) -> list[dict[str, Any]]:
    """Rows with member identity resolved over the whole batch and version state as of ``now``."""

    resolutions = (resolver or MemberResolver()).resolve(item.identity for item in items)
    versions = versions_as_of(items, now) if now is not None else {}
    rows = []
    for item in items:
        row = item.to_row(resolutions.get(item.identity.key))
        if item.version_key and item.version_key in versions:
            state = versions[item.version_key]
            row["version"] = {"key": item.version_key, "versions_known": state["versions"],
                              "superseded": item.source_document in state["superseded"],
                              "current_document": state["current"]}
        rows.append(row)
    return rows


__all__ = ["CONTRACT_VERSION", "CongressionalDisclosure", "from_house", "from_senate", "senate_identity", "to_rows",
           "versions_as_of", "visible_as_of"]
