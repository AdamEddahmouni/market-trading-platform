"""Primary-source SEC ownership documents: Form 4, Schedule 13D/13G, 13F, daily form index.

Parsers only — no network. Built against the official EDGAR XML technical
specifications (Ownership 5.5, Schedule 13D/13G 2.3, Form 13F 2.0) and real
filings. Every value keeps the meaning the filer reported:

* Form 4 — one insider's transactions in the issuer's securities. The
  transaction date is when they traded; the filing's EDGAR acceptance is when it
  became public. A single transaction is never read as "insider confidence".
* Schedule 13D / 13G — a beneficial owner's aggregate shares and percent of
  class as of the event date. Joint filers frequently report the *same* shares:
  rows are per reporting person and are never summed. 13G is the passive/
  exempt form; neither form is read as intent beyond what it states.
* 13F information table — a manager's reported long positions in 13(f)
  securities as of quarter end, public only at filing. ``value`` is in dollars
  (since the 2023 specification). Quarter-over-quarter differences are DERIVED:
  a larger position is not a purchase (splits, corporate actions, and reporting
  changes also move reported shares).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

PARSER_VERSION = "sec_edgar.ownership/1.0.0"

#: Form 4 transaction codes (General Instructions, Form 4, Item 8) — labels only, no direction implied.
FORM4_CODES = {
    "P": "Open market or private purchase", "S": "Open market or private sale",
    "A": "Grant or award", "D": "Disposition to the issuer", "F": "Tax withholding / exercise payment",
    "I": "Discretionary transaction", "M": "Exercise or conversion of derivative (exempt)",
    "C": "Conversion of derivative", "E": "Expiration of short derivative position",
    "H": "Expiration or cancellation of long derivative position", "O": "Exercise of out-of-the-money derivative",
    "X": "Exercise of in-the-money or at-the-money derivative", "G": "Bona fide gift", "L": "Small acquisition",
    "W": "Acquisition or disposition by will or laws of descent", "Z": "Deposit into or withdrawal from voting trust",
    "J": "Other acquisition or disposition", "K": "Equity swap or similar", "U": "Disposition from tender of shares",
    "V": "Transaction voluntarily reported earlier than required",
}
INSIDER_FORMS = frozenset({"4", "4/A"})
BENEFICIAL_FORMS = frozenset({"SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A",
                              "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A"})
THIRTEEN_F_FORMS = frozenset({"13F-HR", "13F-HR/A"})


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find(node: ET.Element | None, *path: str) -> ET.Element | None:
    """Namespace-agnostic child walk."""

    current = node
    for name in path:
        if current is None:
            return None
        current = next((child for child in current if _local(child.tag) == name), None)
    return current


def _findall(node: ET.Element | None, name: str) -> list[ET.Element]:
    return [child for child in node if _local(child.tag) == name] if node is not None else []


def _text(node: ET.Element | None, *path: str) -> str:
    found = _find(node, *path)
    return (found.text or "").strip() if found is not None and found.text else ""


def _value(node: ET.Element | None, *path: str) -> str:
    """Ownership XML wraps most values in ``<value>``."""

    found = _find(node, *path)
    if found is None:
        return ""
    inner = _find(found, "value")
    return ((inner if inner is not None else found).text or "").strip()


def _number(text: str) -> float | None:
    cleaned = (text or "").replace(",", "").replace("%", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _iso_date(text: str) -> str | None:
    raw = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _root(payload: bytes | str) -> ET.Element:
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("SEC_XML_MALFORMED") from exc


def raw_xml_document(primary_document: str) -> str:
    """``xslF345X06/wk-form4_1.xml`` → ``wk-form4_1.xml`` (the XSL directory is a rendered view)."""

    name = (primary_document or "").strip()
    if not name.lower().endswith(".xml"):
        raise ValueError("SEC_PRIMARY_DOCUMENT_NOT_XML")
    parts = name.split("/")
    return parts[-1] if len(parts) > 1 and parts[0].lower().startswith("xsl") else name


# ------------------------------------------------------------------ Form 4
@dataclass(frozen=True, slots=True)
class InsiderTransaction:
    security_title: str
    derivative: bool
    transaction_date: str | None
    code: str
    code_label: str
    acquired_disposed: str | None      # "A" / "D" as reported
    shares: float | None
    price_per_share: float | None      # None when not disclosed (e.g. grants, gifts)
    shares_owned_after: float | None
    direct_or_indirect: str | None     # "D" / "I"
    footnote_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InsiderFiling:
    document_type: str
    issuer_cik: str
    issuer_name: str
    issuer_symbol: str
    period_of_report: str | None
    owners: tuple[dict[str, Any], ...]
    rule_10b5_1: bool | None           # the 10b5-1 checkbox as filed; None when absent
    transactions: tuple[InsiderTransaction, ...]
    signature_date: str | None


def _relationship(node: ET.Element | None) -> dict[str, Any]:
    def flag(name: str) -> bool:
        return _text(node, name).lower() in ("1", "true")

    roles = [label for name, label in (("isDirector", "Director"), ("isOfficer", "Officer"),
                                       ("isTenPercentOwner", "10% owner"), ("isOther", "Other")) if flag(name)]
    return {"roles": roles, "officer_title": _text(node, "officerTitle") or None,
            "other_text": _text(node, "otherText") or None}


def _insider_transaction(node: ET.Element, *, derivative: bool) -> InsiderTransaction:
    code = _text(node, "transactionCoding", "transactionCode")
    footnotes = tuple(sorted({item.attrib.get("id", "") for item in node.iter() if _local(item.tag) == "footnoteId"} - {""}))
    return InsiderTransaction(
        security_title=_value(node, "securityTitle"), derivative=derivative,
        transaction_date=_iso_date(_value(node, "transactionDate")), code=code,
        code_label=FORM4_CODES.get(code, "Unlisted code"),
        acquired_disposed=_value(node, "transactionAmounts", "transactionAcquiredDisposedCode") or None,
        shares=_number(_value(node, "transactionAmounts", "transactionShares")),
        price_per_share=_number(_value(node, "transactionAmounts", "transactionPricePerShare")),
        shares_owned_after=_number(_value(node, "postTransactionAmounts", "sharesOwnedFollowingTransaction")),
        direct_or_indirect=_value(node, "ownershipNature", "directOrIndirectOwnership") or None,
        footnote_ids=footnotes)


def parse_form4(payload: bytes | str) -> InsiderFiling:
    root = _root(payload)
    if _local(root.tag) != "ownershipDocument":
        raise ValueError("SEC_FORM4_ROOT_MISSING")
    owners = []
    for owner in _findall(root, "reportingOwner"):
        owners.append({"cik": _text(owner, "reportingOwnerId", "rptOwnerCik"),
                       "name": _text(owner, "reportingOwnerId", "rptOwnerName"),
                       **_relationship(_find(owner, "reportingOwnerRelationship"))})
    rule = _text(root, "aff10b5One").lower()
    transactions = [_insider_transaction(item, derivative=False)
                    for item in _findall(_find(root, "nonDerivativeTable"), "nonDerivativeTransaction")]
    transactions += [_insider_transaction(item, derivative=True)
                     for item in _findall(_find(root, "derivativeTable"), "derivativeTransaction")]
    return InsiderFiling(
        document_type=_text(root, "documentType"), issuer_cik=_text(root, "issuer", "issuerCik"),
        issuer_name=_text(root, "issuer", "issuerName"), issuer_symbol=_text(root, "issuer", "issuerTradingSymbol").upper(),
        period_of_report=_iso_date(_text(root, "periodOfReport")), owners=tuple(owners),
        rule_10b5_1=None if rule == "" else rule in ("1", "true"), transactions=tuple(transactions),
        signature_date=_iso_date(_text(root, "ownerSignature", "signatureDate")))


# ------------------------------------------------------------------ Schedule 13D / 13G
@dataclass(frozen=True, slots=True)
class BeneficialOwner:
    name: str
    cik: str | None
    aggregate_shares: float | None
    percent_of_class: float | None
    sole_voting: float | None
    shared_voting: float | None
    person_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BeneficialOwnershipFiling:
    submission_type: str               # SCHEDULE 13D / 13D/A / 13G / 13G/A
    schedule: str                      # 13D / 13G
    is_amendment: bool
    amendment_number: str | None
    issuer_cik: str
    issuer_name: str
    issuer_cusips: tuple[str, ...]
    class_title: str
    event_date: str | None             # date of the event requiring the filing, as reported
    reporting_persons: tuple[BeneficialOwner, ...]
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


def parse_schedule_13dg(payload: bytes | str) -> BeneficialOwnershipFiling:
    root = _root(payload)
    submission = _text(root, "headerData", "submissionType").upper()
    if "13D" not in submission and "13G" not in submission:
        raise ValueError("SEC_13DG_SUBMISSION_TYPE_UNKNOWN")
    schedule = "13D" if "13D" in submission else "13G"
    form = _find(root, "formData")
    cover = _find(form, "coverPageHeader")
    issuer = _find(cover, "issuerInfo")
    cusips = tuple(item.text.strip().upper() for item in _findall(_find(issuer, "issuerCusips"), "issuerCusipNumber")
                   if item.text and item.text.strip())
    persons: list[BeneficialOwner] = []
    if schedule == "13G":
        for node in _findall(form, "coverPageHeaderReportingPersonDetails"):
            shares = _find(node, "reportingPersonBeneficiallyOwnedNumberOfShares")
            persons.append(BeneficialOwner(
                name=_text(node, "reportingPersonName"), cik=_text(node, "reportingCik") or None,
                aggregate_shares=_number(_text(node, "reportingPersonBeneficiallyOwnedAggregateNumberOfShares")),
                percent_of_class=_number(_text(node, "classPercent")),
                sole_voting=_number(_text(shares, "soleVotingPower")), shared_voting=_number(_text(shares, "sharedVotingPower")),
                person_types=tuple(item.text.strip() for item in _findall(node, "typeOfReportingPerson") if item.text)))
        event = _text(cover, "eventDateRequiresFilingThisStatement")
    else:
        for node in _findall(_find(form, "reportingPersons"), "reportingPersonInfo"):
            persons.append(BeneficialOwner(
                name=_text(node, "reportingPersonName"), cik=_text(node, "reportingPersonCIK") or None,
                aggregate_shares=_number(_text(node, "aggregateAmountOwned")),
                percent_of_class=_number(_text(node, "percentOfClass")),
                sole_voting=_number(_text(node, "soleVotingPower")), shared_voting=_number(_text(node, "sharedVotingPower")),
                person_types=tuple(item.text.strip() for item in _findall(node, "typeOfReportingPerson") if item.text)))
        event = _text(cover, "dateOfEvent")
    flags = []
    if len({(person.aggregate_shares, person.percent_of_class) for person in persons}) < len(persons):
        flags.append("JOINT_FILERS_REPORT_SAME_POSITION_NOT_ADDITIVE")
    amendment = _text(cover, "amendmentNo") or _text(form, "amendmentNo") or None
    return BeneficialOwnershipFiling(
        submission_type=submission, schedule=schedule, is_amendment=submission.endswith("/A"), amendment_number=amendment,
        issuer_cik=_text(issuer, "issuerCik") or _text(issuer, "issuerCIK"), issuer_name=_text(issuer, "issuerName"),
        issuer_cusips=cusips, class_title=_text(cover, "securitiesClassTitle"), event_date=_iso_date(event),
        reporting_persons=tuple(persons), quality_flags=tuple(flags))


# ------------------------------------------------------------------ 13F information table
@dataclass(frozen=True, slots=True)
class ThirteenFHolding:
    issuer_name: str
    title_of_class: str
    cusip: str
    figi: str | None
    value_usd: float | None
    shares_or_principal: float | None
    amount_type: str                   # SH (shares) / PRN (principal)
    put_call: str | None               # a listed option position, never the underlying shares
    investment_discretion: str


def parse_13f_information_table(payload: bytes | str) -> list[ThirteenFHolding]:
    root = _root(payload)
    holdings = []
    for node in root.iter():
        if _local(node.tag) != "infoTable":
            continue
        cusip = _text(node, "cusip").upper()
        if not cusip:
            continue
        holdings.append(ThirteenFHolding(
            issuer_name=_text(node, "nameOfIssuer"), title_of_class=_text(node, "titleOfClass"), cusip=cusip,
            figi=_text(node, "figi") or None, value_usd=_number(_text(node, "value")),
            shares_or_principal=_number(_text(node, "shrsOrPrnAmt", "sshPrnamt")),
            amount_type=_text(node, "shrsOrPrnAmt", "sshPrnamtType") or "SH", put_call=_text(node, "putCall") or None,
            investment_discretion=_text(node, "investmentDiscretion")))
    return holdings


def aggregate_13f_position(holdings: list[ThirteenFHolding], cusip: str) -> dict[str, float] | None:
    """One manager's reported *share* position in a CUSIP: SH lines only, option lines excluded."""

    lines = [item for item in holdings if item.cusip == cusip.upper() and item.amount_type == "SH" and not item.put_call]
    if not lines:
        return None
    return {"shares": sum(item.shares_or_principal or 0.0 for item in lines),
            "value_usd": sum(item.value_usd or 0.0 for item in lines), "lines": float(len(lines))}


#: DERIVED change classes. No trade direction is implied.
CHANGE_NEW, CHANGE_INCREASED, CHANGE_DECREASED, CHANGE_EXITED, CHANGE_UNCHANGED = (
    "NEW", "INCREASED", "DECREASED", "EXITED", "UNCHANGED")
CHANGE_METHOD = ("DERIVED: reported shares at this quarter end minus the manager's prior reported quarter. A change can "
                 "come from trades, splits, corporate actions, or reporting changes; it is not a purchase or sale.")


def classify_reported_change(prior_shares: float | None, current_shares: float | None, *,
                             prior_available: bool = True) -> dict[str, Any]:
    """Classify a manager's reported-share change between consecutive 13F filings."""

    flags: list[str] = []
    if not prior_available:
        return {"change": None, "delta_shares": None, "class": "INSUFFICIENT_EVIDENCE",
                "flags": ["PRIOR_FILING_NOT_AVAILABLE"], "method": CHANGE_METHOD}
    prior = prior_shares or 0.0
    current = current_shares or 0.0
    if prior <= 0 and current > 0:
        change = CHANGE_NEW
    elif prior > 0 and current <= 0:
        change = CHANGE_EXITED
    elif current > prior:
        change = CHANGE_INCREASED
    elif current < prior:
        change = CHANGE_DECREASED
    else:
        change = CHANGE_UNCHANGED
    if prior > 0 and current > 0:
        ratio = current / prior
        # Whole-number ratios (2:1, 3:1, 1:2 …) are what a split produces; flag, never reinterpret.
        for factor in (2, 3, 4, 5, 10, 20):
            if abs(ratio - factor) < 1e-6 or abs(ratio - 1 / factor) < 1e-9:
                flags.append("SPLIT_LIKE_RATIO")
                break
    return {"change": change, "delta_shares": current - prior, "class": "DERIVED", "flags": flags, "method": CHANGE_METHOD}


# ------------------------------------------------------------------ daily form index
@dataclass(frozen=True, slots=True)
class IndexEntry:
    form_type: str
    company_name: str
    cik: str
    date_filed: date
    accession: str
    path: str


_INDEX_LINE = re.compile(r"^(?P<form>\S.{0,16}?)\s{2,}(?P<name>.+?)\s{2,}(?P<cik>\d{1,10})\s+(?P<date>\d{8})\s+(?P<path>edgar/\S+)\s*$")


def parse_daily_form_index(text: str, *, forms: frozenset[str] | None = None) -> list[IndexEntry]:
    """Parse EDGAR ``form.YYYYMMDD.idx``. A filing appears once per associated CIK (issuer and each filer)."""

    entries = []
    started = False
    for line in text.splitlines():
        if not started:
            started = line.startswith("-----")
            continue
        match = _INDEX_LINE.match(line)
        if not match:
            continue
        form = match.group("form").strip()
        if forms is not None and form not in forms:
            continue
        path = match.group("path")
        accession = path.rsplit("/", 1)[-1].removesuffix(".txt")
        entries.append(IndexEntry(form_type=form, company_name=match.group("name").strip(),
                                  cik=match.group("cik").zfill(10),
                                  date_filed=datetime.strptime(match.group("date"), "%Y%m%d").date(),
                                  accession=accession, path=path))
    return entries


def group_index_filings(entries: list[IndexEntry], issuer_ciks: dict[str, Any], *,
                        listed_ciks: frozenset[str] | set[str] = frozenset()) -> list[dict[str, Any]]:
    """Group index rows by accession; the subject issuer is an associated CIK present in ``issuer_ciks``.

    The index lists a filing once per associated CIK without saying which is the
    subject company and which the filer, so the role is resolved conservatively:

    * a Schedule 13D/13G is never about its own filer, so for those forms the CIK that
      submitted the filing (the accession-number prefix) is a filer, not the subject
      (e.g. a listed company reporting its stake in another company);
    * ``role_basis`` is ``SINGLE_CANDIDATE`` when exactly one associated CIK can be the
      subject — counting every listed company in ``listed_ciks``, not only this
      universe (a listed company can be a Form 4 reporting owner of another) — and
      ``ROLE_UNVERIFIED`` when several can (every candidate row is kept and marked;
      the filing document names the real issuer).

    A filing with no candidate is dropped.
    """

    by_accession: dict[str, list[IndexEntry]] = {}
    for entry in entries:
        by_accession.setdefault(entry.accession, []).append(entry)
    grouped = []
    for accession, rows in by_accession.items():
        submitter = accession.split("-", 1)[0].zfill(10)
        issuers = [row for row in rows if row.cik in issuer_ciks
                   and not (row.form_type in BENEFICIAL_FORMS and row.cik == submitter)]
        candidates = {row.cik for row in issuers} | {
            row.cik for row in rows if row.cik in listed_ciks
            and not (row.form_type in BENEFICIAL_FORMS and row.cik == submitter)}
        for issuer in issuers:
            filers = sorted({row.company_name for row in rows if row.cik != issuer.cik})
            grouped.append({"accession": accession, "form_type": issuer.form_type, "issuer_cik": issuer.cik,
                            "issuer_name": issuer.company_name, "filers": filers, "date_filed": issuer.date_filed,
                            "path": issuer.path,
                            "role_basis": "SINGLE_CANDIDATE" if len(candidates) == 1 else "ROLE_UNVERIFIED"})
    return grouped


def filing_index_url(cik: str, accession: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{accession}-index.html"


__all__ = [
    "BENEFICIAL_FORMS", "BeneficialOwner", "BeneficialOwnershipFiling", "CHANGE_METHOD", "FORM4_CODES", "INSIDER_FORMS",
    "IndexEntry", "InsiderFiling", "InsiderTransaction", "PARSER_VERSION", "THIRTEEN_F_FORMS", "ThirteenFHolding",
    "aggregate_13f_position", "classify_reported_change", "filing_index_url", "group_index_filings",
    "parse_13f_information_table", "parse_daily_form_index", "parse_form4", "parse_schedule_13dg", "raw_xml_document",
]
