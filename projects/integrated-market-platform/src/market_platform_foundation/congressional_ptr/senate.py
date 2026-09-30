"""Senate eFD Periodic Transaction Reports behind an operator access boundary (Screener S14).

Access findings (see docs/engineering/SCREENER_S14_DISCLOSURE_COVERAGE.md):

* Senate financial disclosures are published through eFD (``efdsearch.senate.gov``).
  Search and report pages are served only after a person accepts, interactively, a
  statement of the statutory restrictions on obtaining and using the reports
  (5 U.S.C. § 13107(c): no unlawful or commercial purpose other than news media
  dissemination, no credit rating, no solicitation).
* There is no documented public API or bulk file.

This module reads a local import directory of eFD report pages together with an
``ACCESS_ATTESTATION.json`` recording that the owner accepted the terms. Pages arrive
either saved by hand or, since 2026-09-30 (owner decision), downloaded by
``senate_efd_sync`` under that acceptance. This module itself never contacts eFD, never
stores cookies or tokens, and never reads the directory without the attestation.

The parser is header-driven (columns located by their header text, not position) and
fails closed per report. Electronic PTR pages list: row number, transaction date,
owner, ticker, asset name, asset type, type, amount (a band), and comment; the page
header carries the filer ("The Honorable …") and a filed timestamp ("Filed MM/DD/YYYY
@ h:mm AM"). Paper (scanned) filings are images and stay ``SCANNED_UNPARSED``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time as time_module
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .house import AmountRange, parse_amount_range

PARSER_VERSION = "congressional_ptr.senate/1.0.0"
CHAMBER = "SENATE"
IMPORT_ENV = "IMP_SENATE_EFD_IMPORT_DIR"
ATTESTATION_FILE = "ACCESS_ATTESTATION.json"
SEARCH_URL = "https://efdsearch.senate.gov/search/"
TERMS_REASON = "SENATE_EFD_REQUIRES_INTERACTIVE_TERMS_ACCEPTANCE"
MAX_FILES = 2000
MAX_FILE_BYTES = 4 * 1024 * 1024
_ET = ZoneInfo("America/New_York")

OWNERS = {"self": "SELF", "spouse": "SPOUSE", "joint": "JOINT", "child": "DEPENDENT_CHILD",
          "dependent child": "DEPENDENT_CHILD", "dependent": "DEPENDENT_CHILD"}
TYPES = {"purchase": ("PURCHASE", "P"), "sale (full)": ("SALE", "S"), "sale": ("SALE", "S"),
         "sale (partial)": ("SALE_PARTIAL", "S (partial)"), "exchange": ("EXCHANGE", "E")}
#: eFD asset types that identify a listed security by ticker, mapped onto the House codes the matcher uses.
ASSET_CODES = {"stock": "ST", "stock option": "OP"}
_REPORT_URL = re.compile(r"https://efdsearch\.senate\.gov/search/view/(ptr|paper)/([0-9a-fA-F-]{8,64})/?")
_FILED = re.compile(r"Filed\s+(\d{1,2}/\d{1,2}/\d{4})(?:\s*@\s*(\d{1,2}:\d{2})\s*([AaPp][Mm]))?")
_TITLE = re.compile(r"Periodic Transaction Report", re.I)
_AMENDMENT = re.compile(r"Amendment\s*(?:No\.?\s*)?(\d+)?", re.I)
_REPORT_FOR = re.compile(r"for\s+(\d{1,2}/\d{1,2}/\d{4})", re.I)
# eFD prints sitting senators as "The Honorable …" and other filers with a courtesy title ("Mr. …").
_FILER = re.compile(r"^(?:(?:The\s+Honorable|Mr\.?|Mrs\.?|Ms\.?|Miss|Dr\.?)\s+)?(.+?)(?:\s*\(([^()]*)\))?\s*$", re.I)


# ------------------------------------------------------------------ HTML
class _Page(HTMLParser):
    """Collects headings, paragraphs, tables (cell text; header flags), links, and comments."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[tuple[str, str]] = []
        self.filer_headings: list[str] = []   # headings eFD marks class="filedReport"
        self._filer = False
        self.paragraphs: list[str] = []
        self.tables: list[list[tuple[bool, list[str]]]] = []
        self.links: list[str] = []
        self.comments: list[str] = []
        self.images = 0
        self._text: list[str] | None = None
        self._tag: str | None = None
        self._row: list[str] | None = None
        self._row_header = False
        self._cell: list[str] | None = None
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("h1", "h2", "h3", "p") and self._cell is None:
            self._text, self._tag = [], tag
            self._filer = "filedreport" in (dict(attrs).get("class") or "").lower().split()
        elif tag == "table":
            self.tables.append([])
            self._depth += 1
        elif tag == "tr" and self._depth:
            self._row, self._row_header = [], False
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._row_header = self._row_header or tag == "th"
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        elif tag == "img":
            self.images += 1
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag == self._tag and self._text is not None:
            text = " ".join("".join(self._text).split())
            if tag == "p":
                self.paragraphs.append(text)
            else:
                self.headings.append((tag, text))
                if self._filer:
                    self.filer_headings.append(text)
            self._text, self._tag = None, None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self.tables:
            self.tables[-1].append((self._row_header, self._row))
            self._row = None
        elif tag == "table" and self._depth:
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        if self._text is not None:
            self._text.append(data)

    def handle_comment(self, data: str) -> None:
        self.comments.append(data)


# ------------------------------------------------------------------ report model
@dataclass(frozen=True, slots=True)
class SenateTransaction:
    row_number: str
    owner: str
    owner_text: str
    disclosed_ticker: str | None
    asset_description: str
    asset_type: str                   # as printed by eFD
    asset_type_code: str | None       # ST / OP when the asset type names a listed stock or option
    transaction_type: str             # PURCHASE / SALE / SALE_PARTIAL / EXCHANGE
    transaction_type_code: str
    transaction_type_text: str
    transaction_date: date | None
    amount: AmountRange | None
    comment: str | None
    row_index: int
    quality_flags: tuple[str, ...] = ()
    evidence_class: str = "OBSERVED"

    @property
    def matchable_ticker(self) -> str | None:
        return self.disclosed_ticker if self.asset_type_code in ("ST", "OP") else None


@dataclass(frozen=True, slots=True)
class SenateReport:
    report_id: str
    report_kind: str                 # ptr / paper / unknown
    source_url: str | None
    filer_name: str | None           # as printed ("Thomas H Tuberville")
    filer_alternate: str | None      # the parenthetical ("Tuberville, Tommy")
    report_for: date | None
    filed_date: date | None
    filed_at: datetime | None        # UTC; from the printed ET timestamp
    amendment_number: int | None
    parse_state: str                 # PARSED / PARTIALLY_PARSED / NO_TRANSACTIONS / SCANNED_UNPARSED / PARSE_FAILED
    reason: str | None
    transactions: tuple[SenateTransaction, ...]
    source_sha256: str
    retrieved_at: datetime | None
    retrieved_basis: str
    file_name: str
    parser_version: str = PARSER_VERSION

    @property
    def available_at(self) -> tuple[datetime | None, str, str]:
        """(public availability, basis, date quality). eFD prints a filed time; else the ET day's end."""

        if self.filed_at is not None:
            return self.filed_at, "senate_efd.filed_timestamp_et", "SOURCE_TIMESTAMP_MINUTE"
        if self.filed_date is not None:
            return (datetime.combine(self.filed_date, time(23, 59, 59), tzinfo=_ET).astimezone(UTC),
                    "senate_efd.filed_date_end_of_et_day", "DATE_ONLY")
        return None, "UNKNOWN", "UNKNOWN"

    @property
    def is_amendment(self) -> bool:
        return self.amendment_number is not None


def _date(text: str) -> date | None:
    try:
        return datetime.strptime(text.strip(), "%m/%d/%Y").date()
    except ValueError:
        return None


def _column(header: list[str], *names: str) -> int | None:
    lowered = [cell.strip().lower() for cell in header]
    for name in names:
        if name in lowered:
            return lowered.index(name)
    return None


def _report_identity(page: _Page, text: str, sidecar: Mapping[str, Any]) -> tuple[str | None, str, str | None]:
    candidates = [str(sidecar.get("source_url") or ""), *page.comments, *page.links, text[:4000]]
    for candidate in candidates:
        match = _REPORT_URL.search(candidate)
        if match:
            return match.group(2).lower(), match.group(1), match.group(0)
    return None, "unknown", None


def parse_report(html_text: str, *, file_name: str = "report.html", sidecar: Mapping[str, Any] | None = None,
                 retrieved_at: datetime | None = None, retrieved_basis: str = "UNKNOWN") -> SenateReport:
    """Parse one saved eFD report page. Never raises for content problems: the state says what happened."""

    sidecar = sidecar or {}
    digest = hashlib.sha256(html_text.encode("utf-8", "replace")).hexdigest()
    page = _Page()
    try:
        page.feed(html_text)
        page.close()
    except Exception:  # noqa: BLE001 - HTMLParser is lenient; anything else is a malformed file
        return SenateReport(f"sha256:{digest[:16]}", "unknown", None, None, None, None, None, None, None, "PARSE_FAILED",
                            "HTML_UNREADABLE", (), digest, retrieved_at, retrieved_basis, file_name)
    report_id, kind, url = _report_identity(page, html_text, sidecar)
    title = next((text for level, text in page.headings if _TITLE.search(text)), None)
    # The page's own filer heading first; the title-based match is the fallback for pages saved without classes.
    filer_heading = next(iter(page.filer_headings), None) or next(
        (text for level, text in page.headings if text.lower().startswith("the honorable")), None)
    filer_name = filer_alt = None
    if filer_heading:
        match = _FILER.match(filer_heading)
        if match:
            filer_name, filer_alt = match.group(1).strip(), (match.group(2) or "").strip() or None
    filed_text = next((text for text in [*page.paragraphs, *(t for _, t in page.headings)] if _FILED.search(text)), "")
    filed = _FILED.search(filed_text)
    filed_date = _date(filed.group(1)) if filed else None
    filed_at = None
    if filed and filed_date and filed.group(2):
        try:
            clock = datetime.strptime(f"{filed.group(2)} {filed.group(3).upper()}", "%I:%M %p").time()
            filed_at = datetime.combine(filed_date, clock, tzinfo=_ET).astimezone(UTC)
        except ValueError:
            filed_at = None
    amendment = None
    if title and _AMENDMENT.search(title):
        number = _AMENDMENT.search(title).group(1)
        amendment = int(number) if number else 1
    report_for = _date(_REPORT_FOR.search(title).group(1)) if title and _REPORT_FOR.search(title) else None
    base = dict(report_id=report_id or f"sha256:{digest[:16]}", report_kind=kind, source_url=url, filer_name=filer_name,
                filer_alternate=filer_alt, report_for=report_for, filed_date=filed_date, filed_at=filed_at,
                amendment_number=amendment, source_sha256=digest, retrieved_at=retrieved_at,
                retrieved_basis=retrieved_basis, file_name=file_name)
    if kind == "paper":
        return SenateReport(**base, parse_state="SCANNED_UNPARSED", reason="PAPER_FILING_IMAGES", transactions=())
    problems = [code for code, bad in (("REPORT_ID_UNKNOWN", report_id is None), ("FILER_NOT_FOUND", filer_name is None),
                                       ("FILED_DATE_NOT_FOUND", filed_date is None),
                                       ("NOT_A_PERIODIC_TRANSACTION_REPORT", title is None)) if bad]
    if problems:
        return SenateReport(**base, parse_state="PARSE_FAILED", reason=problems[0], transactions=())
    table = next((rows for rows in page.tables if rows and rows[0][0]
                  and _column(rows[0][1], "transaction date") is not None and _column(rows[0][1], "amount") is not None), None)
    if table is None:
        if any("no transactions" in text.lower() for text in page.paragraphs):
            return SenateReport(**base, parse_state="NO_TRANSACTIONS", reason="REPORT_STATES_NO_TRANSACTIONS", transactions=())
        return SenateReport(**base, parse_state="PARSE_FAILED", reason="TRANSACTION_TABLE_NOT_FOUND", transactions=())
    header = table[0][1]
    cols = {key: _column(header, *names) for key, names in {
        "number": ("#",), "date": ("transaction date",), "owner": ("owner",), "ticker": ("ticker",),
        "asset": ("asset name",), "asset_type": ("asset type",), "type": ("type", "transaction type"),
        "amount": ("amount",), "comment": ("comment",)}.items()}
    if cols["asset"] is None or cols["type"] is None:
        return SenateReport(**base, parse_state="PARSE_FAILED", reason="TRANSACTION_COLUMNS_MISSING", transactions=())
    transactions: list[SenateTransaction] = []
    malformed = 0
    for index, (is_header, cells) in enumerate(table[1:]):
        if is_header:
            continue

        def cell(key: str) -> str:
            position = cols[key]
            return cells[position].strip() if position is not None and position < len(cells) else ""

        if len(cells) < len(header) - 1:
            malformed += 1
            continue
        flags: list[str] = []
        kind_text = cell("type")
        mapped = TYPES.get(kind_text.lower())
        if mapped is None:
            malformed += 1
            continue
        owner_text = cell("owner")
        owner = OWNERS.get(owner_text.lower())
        if owner is None:
            flags.append("OWNER_UNRECOGNIZED")
        traded = _date(cell("date"))
        if traded is None:
            flags.append("TRANSACTION_DATE_UNPARSED")
        amount = parse_amount_range(cell("amount"))
        if amount is None:
            flags.append("AMOUNT_RANGE_UNPARSED")
        ticker_text = cell("ticker").upper()
        ticker = ticker_text if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", ticker_text) else None
        asset_type = cell("asset_type")
        comment = cell("comment")
        transactions.append(SenateTransaction(
            row_number=cell("number") or str(index + 1), owner=owner or "UNKNOWN", owner_text=owner_text,
            disclosed_ticker=ticker, asset_description=cell("asset"), asset_type=asset_type,
            asset_type_code=ASSET_CODES.get(asset_type.lower()), transaction_type=mapped[0],
            transaction_type_code=mapped[1], transaction_type_text=kind_text, transaction_date=traded, amount=amount,
            comment=None if comment in ("", "--") else comment, row_index=len(transactions), quality_flags=tuple(flags)))
    if not transactions:
        if malformed:
            return SenateReport(**base, parse_state="PARSE_FAILED", reason="TRANSACTION_ROWS_UNRECOGNIZED", transactions=())
        return SenateReport(**base, parse_state="NO_TRANSACTIONS", reason="TRANSACTION_TABLE_EMPTY", transactions=())
    critical = any({"AMOUNT_RANGE_UNPARSED", "TRANSACTION_DATE_UNPARSED"} & set(item.quality_flags) for item in transactions)
    reasons = [reason for reason, bad in (("SOME_ROWS_UNRECOGNIZED", malformed), ("SOME_ROW_FIELDS_UNPARSED", critical)) if bad]
    return SenateReport(**base, parse_state="PARTIALLY_PARSED" if reasons else "PARSED", reason=";".join(reasons) or None,
                        transactions=tuple(transactions))


# ------------------------------------------------------------------ operator import boundary
@dataclass(slots=True)
class SenateImportState:
    state: str                         # TERMS_ACCEPTANCE_REQUIRED / NOT_CONFIGURED / READY / PARTIAL / SOURCE_ERROR
    reason: str | None
    reports: list[SenateReport] = field(default_factory=list)
    attestation: dict[str, Any] | None = None
    scanned_at: str | None = None
    duplicates: int = 0
    conflicts: list[str] = field(default_factory=list)
    files: int = 0

    def coverage(self) -> dict[str, Any]:
        states = Counter(report.parse_state for report in self.reports)
        return {"reports_total": len(self.reports), "parsed": states["PARSED"], "partially_parsed": states["PARTIALLY_PARSED"],
                "no_transactions": states["NO_TRANSACTIONS"], "scanned_unparsed": states["SCANNED_UNPARSED"],
                "failed": states["PARSE_FAILED"], "duplicates": self.duplicates, "conflicts": len(self.conflicts),
                "transaction_count": sum(len(report.transactions) for report in self.reports),
                "amendments": sum(1 for report in self.reports if report.is_amendment), "files": self.files,
                "scanned_at": self.scanned_at}


def _attestation(root: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads((root / ATTESTATION_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or not payload.get("accepted_by") or not payload.get("accepted_at"):
        return None
    # Only the attestation's own fields are kept; anything that looks like a secret is dropped.
    return {key: payload[key] for key in ("accepted_by", "accepted_at", "statement") if key in payload}


def _report_fingerprint(report: SenateReport) -> str:
    rows = [(t.row_number, t.transaction_date, t.owner, t.disclosed_ticker, t.asset_description, t.transaction_type,
             t.amount.display if t.amount else None) for t in report.transactions]
    return hashlib.sha256(repr((report.filer_name, report.filed_date, report.amendment_number, rows)).encode()).hexdigest()


def scan_import(root: str | Path | None, *, clock: Callable[[], float] | None = None) -> SenateImportState:
    """Read the operator's import directory. Nothing is read without the operator's attestation."""

    now = datetime.fromtimestamp((clock or time_module.time)(), tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not root:
        return SenateImportState("TERMS_ACCEPTANCE_REQUIRED", TERMS_REASON, scanned_at=now)
    path = Path(root)
    if not path.is_dir():
        return SenateImportState("NOT_CONFIGURED", "SENATE_EFD_IMPORT_DIR_MISSING", scanned_at=now)
    attestation = _attestation(path)
    if attestation is None:
        return SenateImportState("TERMS_ACCEPTANCE_REQUIRED", "OPERATOR_ATTESTATION_MISSING", scanned_at=now)
    files = sorted(item for item in path.iterdir() if item.suffix.lower() in (".htm", ".html") and item.is_file())
    state = SenateImportState("READY", None, attestation=attestation, scanned_at=now, files=len(files))
    if len(files) > MAX_FILES:
        files = files[-MAX_FILES:]
        state.reason = "IMPORT_TRUNCATED_TO_NEWEST_FILES"
    by_id: dict[str, SenateReport] = {}
    fingerprints: dict[str, str] = {}
    conflicted: set[str] = set()
    for item in files:
        if item.stat().st_size > MAX_FILE_BYTES:
            report = SenateReport(f"file:{item.name}", "unknown", None, None, None, None, None, None, None, "PARSE_FAILED",
                                  "FILE_TOO_LARGE", (), "", None, "UNKNOWN", item.name)
            by_id.setdefault(report.report_id, report)
            continue
        sidecar_path = item.with_name(item.name + ".json")
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8")) if sidecar_path.is_file() else {}
        except (OSError, ValueError):
            sidecar = {}
        retrieved, basis = None, "file_mtime"
        if isinstance(sidecar, dict) and sidecar.get("retrieved_at"):
            try:
                retrieved = datetime.fromisoformat(str(sidecar["retrieved_at"]).replace("Z", "+00:00")).astimezone(UTC)
                basis = "operator_sidecar.retrieved_at"
            except ValueError:
                retrieved = None
        if retrieved is None:
            retrieved = datetime.fromtimestamp(item.stat().st_mtime, tz=UTC)
        report = parse_report(item.read_text(encoding="utf-8", errors="replace"), file_name=item.name,
                              sidecar=sidecar if isinstance(sidecar, dict) else {}, retrieved_at=retrieved,
                              retrieved_basis=basis)
        fingerprint = _report_fingerprint(report)
        existing = by_id.get(report.report_id)
        if existing is None:
            by_id[report.report_id] = report
            fingerprints[report.report_id] = fingerprint
        elif fingerprints[report.report_id] == fingerprint:
            state.duplicates += 1       # the same official report saved twice: one copy counts
            if report.retrieved_at and existing.retrieved_at and report.retrieved_at < existing.retrieved_at:
                by_id[report.report_id] = report  # keep the earliest retrieval
        else:
            conflicted.add(report.report_id)
    for report_id in sorted(conflicted):
        old = by_id[report_id]
        by_id[report_id] = replace(old, parse_state="PARSE_FAILED", reason="DUPLICATE_REPORT_CONFLICT", transactions=())
    state.conflicts = sorted(conflicted)
    state.reports = sorted(by_id.values(), key=lambda report: (report.filed_at or datetime.min.replace(tzinfo=UTC),
                                                                report.report_id), reverse=True)
    failed = sum(1 for report in state.reports if report.parse_state == "PARSE_FAILED")
    if state.reports and failed == len(state.reports):
        state.state, state.reason = "SOURCE_ERROR", "NO_REPORT_PARSED"
    elif failed:
        state.state, state.reason = "PARTIAL", "SOME_REPORTS_FAILED"
    return state


def import_root_from_env(env: Callable[[str], str | None] = os.environ.get) -> str | None:
    value = (env(IMPORT_ENV) or "").strip()
    return value or None


__all__ = [
    "ATTESTATION_FILE", "CHAMBER", "IMPORT_ENV", "PARSER_VERSION", "SEARCH_URL", "SenateImportState", "SenateReport",
    "SenateTransaction", "TERMS_REASON", "import_root_from_env", "parse_report", "scan_import",
]
