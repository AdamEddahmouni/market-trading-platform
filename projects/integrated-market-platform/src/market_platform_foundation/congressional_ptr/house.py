"""House Clerk financial-disclosure primary source: filing index and PTR transactions.

Official source: the House Clerk publishes a yearly filing index
(``public_disc/financial-pdfs/{YEAR}FD.zip`` → ``{YEAR}FD.xml``) with the member,
state/district, filing type, filing date, and document id of every disclosure,
and each Periodic Transaction Report (``FilingType == "P"``) as a PDF
(``public_disc/ptr-pdfs/{YEAR}/{DocID}.pdf``).

Electronically filed PTRs are generated PDFs with a text layer (Standard security
handler with an empty user password, CID fonts with ToUnicode maps). This module
reads that text layer with the standard library only — RC4/MD5 object keys, Flate,
ToUnicode CMaps — and parses the transaction table. Paper filings are scanned
images: they have no text layer and are reported ``SCANNED_UNPARSED`` (legacy state
``TRANSACTIONS_NOT_MACHINE_READABLE``), never guessed. S14 separates the document
class (TEXT_PDF / SCANNED_PDF / MIXED / MALFORMED / UNSUPPORTED) from the parse state
(PARSED / PARTIALLY_PARSED / NO_TRANSACTIONS / SCANNED_UNPARSED / PARSE_FAILED), so
"not read" is never "no transactions", and puts scanned extraction behind
``ScannedPtrExtractor`` (no engine by default).

Semantics kept exact:

* the transaction date is when the member (or spouse/dependent) traded; the
  filing date is when the report was filed; availability is never the
  transaction date (see ``market_trackers.congressional_disclosure.reconcile``);
* the amount is the disclosed *range* — minimum, maximum, and the verbatim
  label — never a point value;
* a ticker is used only when the filer disclosed it in the asset description.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo
from collections.abc import Iterable

PARSER_VERSION = "congressional_ptr.house/1.1.0"
INDEX_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
PTR_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
CHAMBER = "HOUSE"
PTR_FILING_TYPE = "P"
MAX_PDF_BYTES = 8 * 1024 * 1024
_ET = ZoneInfo("America/New_York")

#: STOCK Act transaction codes as printed on House PTRs.
TRANSACTION_TYPES = {"P": "PURCHASE", "S": "SALE", "S (partial)": "SALE_PARTIAL", "E": "EXCHANGE"}
#: Owner codes; an empty owner column is the filer.
OWNER_CODES = {"SP": "SPOUSE", "JT": "JOINT", "DC": "DEPENDENT_CHILD"}
#: Asset-type codes (https://fd.house.gov/reference/asset-type-codes.aspx) that identify a listed security by ticker.
TICKER_ASSET_TYPES = {"ST": "STOCK", "EF": "EXCHANGE_TRADED_FUND", "OP": "OPTION"}

_PAD = bytes.fromhex("28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A")
_OBJ = re.compile(rb"(\d+) 0 obj")
_TICKER = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,9})\)\s*$")
_ASSET_CODE = re.compile(r"\[([A-Z]{2})\]\s*$")
_DATE = r"(\d{2}/\d{2}/\d{4})"
_ANCHOR = re.compile(r"(?:^|\|)\s*(P|S \(partial\)|S|E)\s*\|\s*" + _DATE + r"\s*\|\s*" + _DATE + r"\s*\|\s*(.+)$")
_AMOUNT = re.compile(r"\$([\d,]+)\s*-\s*\$([\d,]+)")
_OVER = re.compile(r"(?:Spouse/DC\s+)?Over\s+\$([\d,]+)", re.I)
# Bold labels keep only their capitals (lower-case glyphs have no Unicode mapping):
# "F   S :" (Filing Status), "D :" (Description), "S   O :" (Subholding Of), titles "P   T   R".
_LABEL = re.compile(r"^[A-Z](?:\s+[A-Z])*\s*:|^[A-Z](?:\s+[A-Z])+\s*$")
_CONTROL = re.compile(r"[\x00-\x1f]")


# ------------------------------------------------------------------ amounts
@dataclass(frozen=True, slots=True)
class AmountRange:
    """A disclosed amount band. Never a point value; ``max_amount`` is None for open-ended bands."""

    min_amount: int | None
    max_amount: int | None
    display: str

    def to_dict(self) -> dict[str, Any]:
        return {"min_amount": self.min_amount, "max_amount": self.max_amount, "display": self.display,
                "class": "OBSERVED", "exact_value_disclosed": False}


def parse_amount_range(text: str) -> AmountRange | None:
    raw = " ".join((text or "").split())
    match = _AMOUNT.search(raw)
    if match:
        low, high = (int(value.replace(",", "")) for value in match.groups())
        if high < low:
            return None
        return AmountRange(low, high, f"${low:,} – ${high:,}")
    over = _OVER.search(raw)
    if over:
        low = int(over.group(1).replace(",", ""))
        spouse = raw.lower().startswith("spouse")
        return AmountRange(low + 1, None, f"{'Spouse/DC ' if spouse else ''}Over ${low:,}")
    return None


# ------------------------------------------------------------------ filing index
@dataclass(frozen=True, slots=True)
class HouseFiling:
    doc_id: str
    year: int
    filing_type: str
    prefix: str
    first: str
    last: str
    suffix: str
    state_district: str
    filing_date: date

    @property
    def member_name(self) -> str:
        return " ".join(part for part in (self.first, self.last, self.suffix) if part)

    @property
    def member_id(self) -> str:
        """Stable within the official index (name + state/district); the index carries no bioguide id."""

        return f"HOUSE:{self.last.upper()}:{self.first.upper()}:{self.state_district.upper()}"

    @property
    def document_url(self) -> str:
        return PTR_URL.format(year=self.year, doc_id=self.doc_id)


def parse_filing_index(payload: bytes, *, year: int) -> list[HouseFiling]:
    """Parse ``{YEAR}FD.zip`` (or the bare XML) into filings; malformed members are skipped."""

    raw = payload
    if payload[:2] == b"PK":
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            name = next((item for item in archive.namelist() if item.lower().endswith(".xml")), None)
            if name is None:
                raise ValueError("HOUSE_INDEX_XML_MISSING")
            raw = archive.read(name)
    root = ET.fromstring(raw)
    filings: list[HouseFiling] = []
    for member in root.iter("Member"):
        text = {child.tag: (child.text or "").strip() for child in member}
        doc_id = text.get("DocID", "")
        try:
            filed = datetime.strptime(text.get("FilingDate", ""), "%m/%d/%Y").date()
        except ValueError:
            continue
        if not doc_id.isdigit():
            continue
        filings.append(HouseFiling(doc_id=doc_id, year=int(text.get("Year") or year), filing_type=text.get("FilingType", ""),
                                   prefix=text.get("Prefix", ""), first=text.get("First", ""), last=text.get("Last", ""),
                                   suffix=text.get("Suffix", ""), state_district=text.get("StateDst", ""), filing_date=filed))
    return filings


def periodic_transaction_reports(filings: list[HouseFiling]) -> list[HouseFiling]:
    return sorted((item for item in filings if item.filing_type == PTR_FILING_TYPE),
                  key=lambda item: (item.filing_date, item.doc_id), reverse=True)


# ------------------------------------------------------------------ PDF text layer
def _rc4(key: bytes, data: bytes) -> bytes:
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) % 256
        state[i], state[j] = state[j], state[i]
    i = j = 0
    out = bytearray()
    for byte in data:
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        out.append(byte ^ state[(state[i] + state[j]) % 256])
    return bytes(out)


class _Pdf:
    """Minimal reader for the House PTR generator's PDFs (not a general PDF parser)."""

    def __init__(self, data: bytes) -> None:
        if not data.startswith(b"%PDF-"):
            raise ValueError("NOT_A_PDF")
        self.data = data
        starts = [(int(match.group(1)), match.end()) for match in _OBJ.finditer(data)]
        self.objects: dict[int, bytes] = {}
        for index, (number, start) in enumerate(starts):
            end = starts[index + 1][1] if index + 1 < len(starts) else len(data)
            self.objects[number] = data[start:end]
        self.key = self._file_key()

    def _file_key(self) -> bytes | None:
        ref = re.search(rb"/Encrypt\s+(\d+) 0 R", self.data)
        if not ref:
            return None
        encrypt = self.objects.get(int(ref.group(1)), b"")
        filt = re.search(rb"/Filter\s*/(\w+)", encrypt)
        version = re.search(rb"/V\s+(\d+)", encrypt)
        if not filt or filt.group(1) != b"Standard" or not version or int(version.group(1)) > 2:
            raise ValueError("UNSUPPORTED_PDF_ENCRYPTION")
        owner = re.search(rb"/O\s*<([0-9A-Fa-f]+)>", encrypt)
        perms = re.search(rb"/P\s+(-?\d+)", encrypt)
        revision = re.search(rb"/R\s+(\d+)", encrypt)
        length = re.search(rb"/Length\s+(\d+)", encrypt)
        ident = re.search(rb"/ID\s*\[\s*<([0-9A-Fa-f]+)>", self.data)
        if not (owner and perms and revision and ident):
            raise ValueError("UNSUPPORTED_PDF_ENCRYPTION")
        size = int(length.group(1)) // 8 if length else 5
        digest = hashlib.md5(_PAD + bytes.fromhex(owner.group(1).decode())
                             + (int(perms.group(1)) & 0xFFFFFFFF).to_bytes(4, "little")
                             + bytes.fromhex(ident.group(1).decode())).digest()
        if int(revision.group(1)) >= 3:
            for _ in range(50):
                digest = hashlib.md5(digest[:size]).digest()
        return digest[:size]

    def dictionary(self, number: int) -> bytes:
        body = self.objects.get(number, b"")
        cut = re.search(rb"\bstream\r?\n", body)
        return body[:cut.start()] if cut else body

    def stream(self, number: int) -> bytes:
        body = self.objects[number]
        cut = re.search(rb"\bstream\r?\n", body)
        if cut is None:
            raise ValueError("PDF_STREAM_MISSING")
        head = body[:cut.start()]
        length = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", head)
        raw = body[cut.end():cut.end() + int(length.group(1))] if length else body[cut.end():body.rfind(b"endstream")]
        if self.key:
            object_key = hashlib.md5(self.key + number.to_bytes(3, "little") + b"\0\0").digest()[:min(len(self.key) + 5, 16)]
            raw = _rc4(object_key, raw)
        if b"/FlateDecode" in head:
            # Tolerant: some generator streams omit the final zlib checksum bytes.
            return zlib.decompressobj().decompress(raw)
        return raw


def _cmap(text: bytes) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for block in re.findall(rb"beginbfchar(.*?)endbfchar", text, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            mapping[int(src, 16)] = bytes.fromhex(dst.decode()).decode("utf-16-be", "replace")
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", text, re.S):
        for low, high, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            base = int(dst, 16)
            for offset, cid in enumerate(range(int(low, 16), int(high, 16) + 1)):
                mapping[cid] = chr(base + offset)
    return mapping


_FONT_REF = re.compile(rb"/([A-Za-z]+\d*(?:_\d+)?)\s+(\d+) 0 R")
_TEXT_OPS = re.compile(
    rb"/([A-Za-z]+\d*(?:_\d+)?)\s+[-\d.]+\s+Tf"          # 1: font select
    rb"|([-\d.]+)\s+([-\d.]+)\s+T[dD]"                   # 2,3: relative move
    rb"|[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+[-\d.]+\s+([-\d.]+)\s+([-\d.]+)\s+Tm"  # 4,5: absolute
    rb"|<([0-9A-Fa-f]*)>\s*Tj"                            # 6: hex show
    rb"|\[((?:[^\]\\]|\\.)*)\]\s*TJ",                     # 7: array show
    re.S,
)


def pdf_pages(data: bytes) -> tuple[list[list[str]], int]:
    """Text-layer lines per page (cells joined by ' | ') and the number of image XObjects.

    A scanned (image-only) document has no text lines on any page; its page objects may
    sit in compressed object streams this reader does not expand, so the page list can be
    empty — the image count is what distinguishes a scan from an empty document.
    """

    pdf = _Pdf(data)
    fonts: dict[int, dict[int, str]] = {}
    images = 0
    for number in pdf.objects:
        head = pdf.dictionary(number)
        if re.search(rb"/Subtype\s*/Image\b", head):
            images += 1
        if b"/Type /Font" in head and b"/ToUnicode" in head:
            ref = re.search(rb"/ToUnicode\s+(\d+) 0 R", head)
            if ref:
                fonts[number] = _cmap(pdf.stream(int(ref.group(1))))
    pages = [number for number in pdf.objects if re.search(rb"/Type\s*/Page\b(?!s)", pdf.dictionary(number))]
    out: list[list[str]] = []
    for page in sorted(pages, key=lambda number: _page_order(pdf, number)):
        head = pdf.dictionary(page)
        page_fonts = {name.decode(): fonts[int(ref)] for name, ref in _FONT_REF.findall(head) if int(ref) in fonts}
        contents = [int(ref) for ref in re.findall(rb"/Contents\s+(\d+) 0 R", head)]
        contents += [int(ref) for ref in re.findall(rb"/XObject\s*<<\s*(?:/\w+\s+\d+ 0 R\s*)*?/\w+\s+(\d+) 0 R", head)]
        lines: list[str] = []
        for ref in contents:
            if ref not in pdf.objects or re.search(rb"/Subtype\s*/Image\b", pdf.dictionary(ref)):
                continue
            own = {name.decode(): fonts[int(num)] for name, num in _FONT_REF.findall(pdf.dictionary(ref)) if int(num) in fonts}
            lines.extend(_content_lines(pdf.stream(ref), {**page_fonts, **own}))
        cleaned = (_CONTROL.sub("", line).strip() for line in lines)
        out.append([line for line in cleaned if line.strip(" |")])
    return out, images


def pdf_text_lines(data: bytes) -> list[str]:
    """Text-layer lines (cells joined by ' | '); empty for a scanned (image-only) document."""

    pages, _images = pdf_pages(data)
    return [line for page in pages for line in page]


def _page_order(pdf: _Pdf, page: int) -> int:
    kids = re.search(rb"/Kids\s*\[([^\]]*)\]", b"".join(pdf.dictionary(n) for n in pdf.objects if b"/Type /Pages" in pdf.dictionary(n)))
    order = [int(ref) for ref in re.findall(rb"(\d+) 0 R", kids.group(1))] if kids else []
    return order.index(page) if page in order else len(order) + page


def _decode(font: dict[int, str] | None, hex_text: bytes) -> str:
    if font is None:
        return ""
    return "".join(font.get(int(hex_text[i:i + 4], 16), "") for i in range(0, len(hex_text) - 3, 4))


def _content_lines(content: bytes, fonts: dict[str, dict[int, str]]) -> list[str]:
    lines: list[str] = []
    current: list[str] = []
    font: dict[int, str] | None = None
    y: float | None = None
    for token in _TEXT_OPS.finditer(content):
        if token.group(1) is not None:
            font = fonts.get(token.group(1).decode())
        elif token.group(4) is not None:
            new_y = float(token.group(5))
            if y is not None and abs(new_y - y) > 2 and current:
                lines.append("".join(current))
                current = []
            elif current:
                current.append(" | ")
            y = new_y
        elif token.group(2) is not None:
            if abs(float(token.group(3))) > 2 and current:
                lines.append("".join(current))
                current = []
            elif current:
                current.append(" ")
        else:
            hex_text = token.group(6) if token.group(6) is not None else b"".join(re.findall(rb"<([0-9A-Fa-f]*)>", token.group(7)))
            current.append(_decode(font, hex_text))
    if current:
        lines.append("".join(current))
    return lines


# ------------------------------------------------------------------ transactions
@dataclass(frozen=True, slots=True)
class PtrTransaction:
    owner: str                   # SELF / SPOUSE / JOINT / DEPENDENT_CHILD
    asset_description: str
    asset_type_code: str | None  # e.g. ST, EF, OP, GS
    disclosed_ticker: str | None
    transaction_type: str        # PURCHASE / SALE / SALE_PARTIAL / EXCHANGE
    transaction_type_code: str
    transaction_date: date | None
    notification_date: date | None
    amount: AmountRange | None
    row_index: int
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    filing_status: str | None = None    # per-row "Filing Status" as printed (e.g. New, Amended)
    description: str | None = None      # "Description" (e.g. option strike / expiry) as printed
    subholding_of: str | None = None    # "Subholding Of" account as printed
    source_page: int | None = None      # 1-based page of the row's anchor line
    evidence_class: str = "OBSERVED"    # OBSERVED (text layer) / EXTRACTED (scanned-document extractor)
    extraction: dict[str, Any] | None = None  # extractor provenance (page, raw text, confidence) when EXTRACTED

    @property
    def matchable_ticker(self) -> str | None:
        return self.disclosed_ticker if self.asset_type_code in TICKER_ASSET_TYPES else None


def _clean(text: str) -> str:
    return " ".join(text.replace(" | ", " ").split())


def _is_label(line: str) -> bool:
    return bool(_LABEL.match(line.strip(" |").strip()))


def _parse_date(text: str) -> date | None:
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
        return None


_HEADER_PREFIXES = ("$ 2 0 0", "* For the complete list", "Filing ID", "Name:", "Status:", "State/District:",
                    "Digitally Signed", "I D | O w n e r")
_HEADER_LINES = frozenset({"T y p e", "D at e", "Cap .", "G ai n s >"})


def _is_boundary(body: str) -> bool:
    return (_is_label(body) or body.startswith(_HEADER_PREFIXES) or body in _HEADER_LINES
            or "Clerk of the House" in body)


@dataclass(slots=True)
class _Row:
    code: str
    traded: str
    notified: str
    asset_text: str
    amount_text: str
    amount_open: bool  # the amount's upper bound has not been read yet ("$15,001 -")
    page: int | None = None
    labels: dict[str, str] = field(default_factory=dict)

    @property
    def asset_complete(self) -> bool:
        return bool(_ASSET_CODE.search(self.asset_text))


def _freeze(row: _Row, row_index: int) -> PtrTransaction:
    flags: list[str] = []
    amount = parse_amount_range(row.amount_text)
    if amount is None:
        flags.append("AMOUNT_RANGE_UNPARSED")
    asset_text = _clean(row.asset_text)
    owner = "SELF"
    head = asset_text.split(" ", 1)
    if head and head[0] in OWNER_CODES:
        owner = OWNER_CODES[head[0]]
        asset_text = head[1] if len(head) > 1 else ""
    code_match = _ASSET_CODE.search(asset_text)
    asset_code = code_match.group(1) if code_match else None
    description = _ASSET_CODE.sub("", asset_text).strip()
    ticker_match = _TICKER.search(description)
    if not description:
        flags.append("ASSET_DESCRIPTION_MISSING")
    if asset_code is None:
        flags.append("ASSET_TYPE_CODE_MISSING")
    traded, notified = _parse_date(row.traded), _parse_date(row.notified)
    if traded is None:
        flags.append("TRANSACTION_DATE_UNPARSED")
    if notified is None:
        flags.append("NOTIFICATION_DATE_UNPARSED")
    if traded is not None and notified is not None and notified < traded:
        flags.append("NOTIFICATION_BEFORE_TRANSACTION")
    return PtrTransaction(
        owner=owner, asset_description=description, asset_type_code=asset_code,
        disclosed_ticker=ticker_match.group(1) if ticker_match else None,
        transaction_type=TRANSACTION_TYPES[row.code], transaction_type_code=row.code,
        transaction_date=traded, notification_date=notified, amount=amount,
        row_index=row_index, quality_flags=tuple(flags), filing_status=row.labels.get("F"),
        description=row.labels.get("D"), subholding_of=row.labels.get("S O"), source_page=row.page)


#: Row flags that mean a field the Screener relies on was not read; such a row is kept, the document is PARTIALLY_PARSED.
CRITICAL_FLAGS = frozenset({"AMOUNT_RANGE_UNPARSED", "TRANSACTION_DATE_UNPARSED", "ASSET_DESCRIPTION_MISSING"})
_LABEL_VALUE = re.compile(r"^([A-Z](?:\s+[A-Z])*)\s*:\s*\|?\s*(.*)$")
_ROWISH = re.compile(r"\d{2}/\d{2}/\d{4}\s*\|\s*\d{2}/\d{2}/\d{4}")


def _spaced_text(text: str) -> str:
    """Undo the generator's per-glyph spacing: words are separated by 2+ spaces ("N ew" → "New")."""

    words = [part.replace(" ", "") for part in re.split(r"\s{2,}", text.strip()) if part.strip()]
    return " ".join(words)


def _row_label(body: str) -> tuple[str, str] | None:
    """A per-row label line ("F   S :  | N ew") → (label capitals, value); None for anything else."""

    match = _LABEL_VALUE.match(body)
    if not match:
        return None
    capitals = " ".join(match.group(1).split())
    key = {"F S": "F", "D": "D", "S O": "S O"}.get(capitals)
    if key is None:
        return None
    return key, _spaced_text(match.group(2))


def parse_transactions(lines: list[str], *, line_pages: list[int] | None = None) -> list[PtrTransaction]:
    """Parse the transaction table from PTR text-layer lines.

    A row is anchored on ``type | transaction date | notification date | amount``;
    the asset text precedes it and ends with the ``[XX]`` asset-type code. A row
    cut by a page break continues after the next page's table header: the
    remaining asset text (up to ``[XX]``) and/or the amount's upper bound. The
    per-row label lines that follow a row (Filing Status, Description, Subholding
    Of) are attached to it verbatim. ``line_pages`` (1-based) records each row's page.
    """

    rows: list[_Row] = []
    buffer: list[str] = []
    for position, raw in enumerate(lines):
        body = raw.strip(" |").strip()
        anchor = _ANCHOR.search(body)
        pending = rows[-1] if rows and (rows[-1].amount_open or not rows[-1].asset_complete) else None
        label = _row_label(body) if rows else None
        if anchor and not _is_label(body):
            code, traded, notified, amount_text = anchor.groups()
            prefix = body[:anchor.start()].strip(" |")
            if prefix:
                buffer.append(prefix)
            rows.append(_Row(code, traded, notified, " ".join(buffer), amount_text,
                             amount_text.rstrip().endswith("-"),
                             line_pages[position] if line_pages and position < len(line_pages) else None))
            buffer = []
        elif pending is not None and pending.amount_open and body.startswith("$") and not _is_boundary(body):
            pending.amount_text = f"{pending.amount_text} {body}"
            pending.amount_open = False
        elif label is not None:
            rows[-1].labels.setdefault(label[0], label[1])
            buffer = []
        elif _is_boundary(body) or _ROWISH.search(body):
            # A row-shaped line that is not a valid anchor (e.g. an unknown transaction code) is counted
            # as unrecognized by the caller; its asset text must not bleed into the next row.
            buffer = []
        elif pending is not None and not pending.asset_complete and not buffer and _ASSET_CODE.search(body.split(" | $")[0]):
            # Page-break continuation: "Common Stock (LAMR) |  [ST] | $50,000".
            asset_part, _, amount_tail = body.partition(" | $")
            pending.asset_text = f"{pending.asset_text} {asset_part}"
            if amount_tail and pending.amount_open:
                pending.amount_text = f"{pending.amount_text} ${amount_tail}"
                pending.amount_open = False
        else:
            buffer.append(body)
            if len(buffer) > 6:  # an asset description never spans this many lines: drop stale text
                buffer = buffer[-6:]
    return [_freeze(row, index) for index, row in enumerate(rows)]


#: Document classes (what the file is) and parse states (what IMP read from it) are separate.
DOCUMENT_CLASSES = ("TEXT_PDF", "SCANNED_PDF", "MIXED", "MALFORMED", "UNSUPPORTED")
PARSE_STATES = ("PARSED", "PARTIALLY_PARSED", "NO_TRANSACTIONS", "SCANNED_UNPARSED", "PARSE_FAILED")
#: S12's coarse document state, kept for existing consumers.
LEGACY_STATE = {"PARSED": "PARSED", "PARTIALLY_PARSED": "PARSED", "NO_TRANSACTIONS": "PARSED",
                "SCANNED_UNPARSED": "TRANSACTIONS_NOT_MACHINE_READABLE", "PARSE_FAILED": "PARSE_ERROR"}
_UNSUPPORTED = frozenset({"UNSUPPORTED_PDF_ENCRYPTION", "PDF_TOO_LARGE"})
_TABLE_HEADER = "I D | O w n e r"


@dataclass(frozen=True, slots=True)
class PtrDocument:
    doc_id: str
    state: str                     # legacy: PARSED / TRANSACTIONS_NOT_MACHINE_READABLE / PARSE_ERROR
    reason: str | None
    transactions: tuple[PtrTransaction, ...]
    source_sha256: str
    parser_version: str = PARSER_VERSION
    document_class: str = "TEXT_PDF"
    parse_state: str = "PARSED"
    page_count: int | None = None
    text_pages: int | None = None
    image_objects: int | None = None
    unrecognized_rows: int = 0
    withheld_rows: int = 0
    amended_rows: int = 0
    extraction: dict[str, Any] | None = None

    def coverage(self) -> dict[str, Any]:
        return {"document_class": self.document_class, "parse_state": self.parse_state, "reason": self.reason,
                "page_count": self.page_count, "text_pages": self.text_pages, "transactions": len(self.transactions),
                "unrecognized_rows": self.unrecognized_rows, "withheld_rows": self.withheld_rows,
                "amended_rows": self.amended_rows, "extraction": self.extraction}


def _document(doc_id: str, digest: str, document_class: str, parse_state: str, reason: str | None,
              transactions: tuple[PtrTransaction, ...] = (), **extra: Any) -> PtrDocument:
    amended = sum(1 for item in transactions if (item.filing_status or "").lower().startswith("amend"))
    return PtrDocument(doc_id, LEGACY_STATE[parse_state], reason, transactions, digest, document_class=document_class,
                       parse_state=parse_state, amended_rows=amended, **extra)


# ------------------------------------------------------------------ scanned documents
@dataclass(frozen=True, slots=True)
class ExtractedRow:
    """One row an extractor read from a scanned page, with the evidence to audit it."""

    transaction: PtrTransaction
    page: int
    raw_text: str
    confidence: float
    bbox: tuple[float, float, float, float] | None = None
    field_text: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScannedExtraction:
    status: str                      # EXTRACTED / ENGINE_NOT_CONFIGURED / FAILED
    rows: tuple[ExtractedRow, ...] = ()
    confidence: float | None = None
    engine: str | None = None
    warnings: tuple[str, ...] = ()


class ScannedPtrExtractor:
    """Boundary for reading scanned PTRs. The default has no engine: scans stay SCANNED_UNPARSED.

    An engine plugged in here must be deterministic, report per-row confidence and the
    source page, and fail closed; its rows are EXTRACTED evidence, never OBSERVED, and a
    row below ``MIN_EXTRACTION_CONFIDENCE`` is withheld rather than shown as a filed fact.
    """

    engine = None

    def extract(self, doc_id: str, data: bytes) -> ScannedExtraction:
        return ScannedExtraction("ENGINE_NOT_CONFIGURED", engine=None)


MIN_EXTRACTION_CONFIDENCE = 0.98


def _admit_extraction(doc_id: str, digest: str, extraction: ScannedExtraction, **extra: Any) -> PtrDocument:
    summary = {"status": extraction.status, "engine": extraction.engine, "confidence": extraction.confidence,
               "warnings": list(extraction.warnings), "min_confidence": MIN_EXTRACTION_CONFIDENCE}
    if extraction.status != "EXTRACTED":
        reason = "NO_TEXT_LAYER_SCANNED_FILING" if extraction.status == "ENGINE_NOT_CONFIGURED" else "SCANNED_EXTRACTION_FAILED"
        return _document(doc_id, digest, "SCANNED_PDF", "SCANNED_UNPARSED", reason, extraction=summary, **extra)
    admitted, withheld = [], 0
    for index, row in enumerate(extraction.rows):
        if row.confidence < MIN_EXTRACTION_CONFIDENCE or row.page < 1:
            withheld += 1
            continue
        txn = row.transaction
        admitted.append(PtrTransaction(
            owner=txn.owner, asset_description=txn.asset_description, asset_type_code=txn.asset_type_code,
            disclosed_ticker=txn.disclosed_ticker, transaction_type=txn.transaction_type,
            transaction_type_code=txn.transaction_type_code, transaction_date=txn.transaction_date,
            notification_date=txn.notification_date, amount=txn.amount, row_index=index,
            quality_flags=(*txn.quality_flags, "EXTRACTED_FROM_SCAN"), filing_status=txn.filing_status,
            description=txn.description, subholding_of=txn.subholding_of, source_page=row.page,
            evidence_class="EXTRACTED",
            extraction={"engine": extraction.engine, "page": row.page, "raw_text": row.raw_text,
                        "confidence": row.confidence, "bbox": list(row.bbox) if row.bbox else None,
                        "fields": dict(row.field_text)}))
    if not admitted:
        return _document(doc_id, digest, "SCANNED_PDF", "SCANNED_UNPARSED",
                         "EXTRACTION_BELOW_CONFIDENCE" if withheld else "EXTRACTION_FOUND_NO_ROWS",
                         withheld_rows=withheld, extraction=summary, **extra)
    state = "PARTIALLY_PARSED" if withheld else "PARSED"
    return _document(doc_id, digest, "SCANNED_PDF", state, "LOW_CONFIDENCE_ROWS_WITHHELD" if withheld else None,
                     tuple(admitted), withheld_rows=withheld, extraction=summary, **extra)


def parse_ptr_pdf(doc_id: str, data: bytes, *, scanned: ScannedPtrExtractor | None = None) -> PtrDocument:
    """Classify the document, then read what it lawfully and reliably contains.

    ``parse_state`` never lets "not read" look like "no transactions": NO_TRANSACTIONS
    requires a readable transaction table with no row in it.
    """

    digest = hashlib.sha256(data).hexdigest()
    if len(data) > MAX_PDF_BYTES:
        return _document(doc_id, digest, "UNSUPPORTED", "PARSE_FAILED", "PDF_TOO_LARGE")
    try:
        pages, images = pdf_pages(data)
    except (ValueError, KeyError, zlib.error) as exc:
        code = str(exc) if str(exc).isupper() else "PDF_TEXT_LAYER_UNREADABLE"
        return _document(doc_id, digest, "UNSUPPORTED" if code in _UNSUPPORTED else "MALFORMED", "PARSE_FAILED", code)
    text_pages = sum(1 for page in pages if page)
    counts = {"page_count": len(pages) or None, "text_pages": text_pages, "image_objects": images}
    if text_pages == 0:
        if images == 0:
            return _document(doc_id, digest, "MALFORMED", "PARSE_FAILED", "NO_TEXT_LAYER_AND_NO_IMAGES", **counts)
        return _admit_extraction(doc_id, digest, (scanned or ScannedPtrExtractor()).extract(doc_id, data), **counts)
    document_class = "MIXED" if text_pages < len(pages) else "TEXT_PDF"
    lines = [line for page in pages for line in page]
    line_pages = [number for number, page in enumerate(pages, start=1) for _ in page]
    transactions = tuple(parse_transactions(lines, line_pages=line_pages))
    rowish = sum(1 for line in lines if _ROWISH.search(line))
    unrecognized = max(0, rowish - len(transactions))
    counts["unrecognized_rows"] = unrecognized
    if not transactions:
        if unrecognized:
            return _document(doc_id, digest, document_class, "PARSE_FAILED", "TRANSACTION_ROWS_UNRECOGNIZED", **counts)
        if any(line.startswith(_TABLE_HEADER) for line in lines):
            if document_class == "MIXED":
                return _document(doc_id, digest, document_class, "PARTIALLY_PARSED", "IMAGE_ONLY_PAGES_UNPARSED", **counts)
            return _document(doc_id, digest, document_class, "NO_TRANSACTIONS", "TRANSACTION_TABLE_EMPTY", **counts)
        return _document(doc_id, digest, document_class, "PARSE_FAILED", "TRANSACTION_TABLE_NOT_FOUND", **counts)
    reasons = []
    if document_class == "MIXED":
        reasons.append("IMAGE_ONLY_PAGES_UNPARSED")
    if unrecognized:
        reasons.append("SOME_ROWS_UNRECOGNIZED")
    if any(CRITICAL_FLAGS & set(item.quality_flags) for item in transactions):
        reasons.append("SOME_ROW_FIELDS_UNPARSED")
    return _document(doc_id, digest, document_class, "PARTIALLY_PARSED" if reasons else "PARSED",
                     ";".join(reasons) or None, transactions, **counts)


def coverage_metrics(documents: Iterable[PtrDocument], *, loading: int = 0, document_errors: int = 0) -> dict[str, int]:
    """Coverage counts for a set of documents — how much was read, not a quality score."""

    items = list(documents)
    by_class = {name: 0 for name in DOCUMENT_CLASSES}
    by_state = {name: 0 for name in PARSE_STATES}
    for item in items:
        by_class[item.document_class] = by_class.get(item.document_class, 0) + 1
        by_state[item.parse_state] = by_state.get(item.parse_state, 0) + 1
    return {"documents_total": len(items) + loading + document_errors, "documents_read": len(items),
            "machine_readable": by_class["TEXT_PDF"] + by_class["MIXED"], "scanned": by_class["SCANNED_PDF"],
            "mixed": by_class["MIXED"], "malformed": by_class["MALFORMED"], "unsupported": by_class["UNSUPPORTED"],
            "parsed": by_state["PARSED"], "partially_parsed": by_state["PARTIALLY_PARSED"],
            "no_transactions": by_state["NO_TRANSACTIONS"], "scanned_unparsed": by_state["SCANNED_UNPARSED"],
            "failed": by_state["PARSE_FAILED"], "loading": loading, "document_errors": document_errors,
            "transaction_count": sum(len(item.transactions) for item in items),
            "extracted_transactions": sum(1 for item in items for txn in item.transactions if txn.evidence_class == "EXTRACTED"),
            "withheld_rows": sum(item.withheld_rows for item in items),
            "unrecognized_rows": sum(item.unrecognized_rows for item in items)}


# ------------------------------------------------------------------ availability
def filing_available_at(filing_date: date, *, retrieved_at: datetime | None = None) -> tuple[datetime, str]:
    """Public-availability bound for a House filing (never the transaction date).

    The Clerk's index carries a filing *date* only, and that date is Eastern. A filing
    is therefore public no earlier than the end of that ET day. (S12 used the end of the
    UTC day, which precedes the end of the ET day by four to five hours — a filing made
    in the evening, ET, would have looked public before it was filed.)

    IMP's own first retrieval is a separate clock (``imp_known_at``); it never moves
    public availability (S14). ``retrieved_at`` is accepted for S12 callers and ignored.
    """

    del retrieved_at
    end_of_et_day = datetime.combine(filing_date, time(23, 59, 59), tzinfo=_ET).astimezone(UTC)
    return end_of_et_day, "house_index.filing_date_end_of_et_day"


def imp_known_at(available_at: datetime, retrieved_at: datetime | None) -> datetime:
    """When IMP itself could first have known the record: the later of public availability and first retrieval."""

    return max(available_at, retrieved_at) if retrieved_at is not None else available_at


def disclosure_lag_days(transaction_date: date | None, filing_date: date) -> int | None:
    """DERIVED: calendar days from the transaction date to the filing date."""

    if transaction_date is None:
        return None
    return (filing_date - transaction_date).days


__all__ = [
    "AmountRange", "CHAMBER", "CRITICAL_FLAGS", "DOCUMENT_CLASSES", "ExtractedRow", "HouseFiling", "INDEX_URL",
    "LEGACY_STATE", "MIN_EXTRACTION_CONFIDENCE", "OWNER_CODES", "PARSER_VERSION", "PARSE_STATES", "PTR_URL",
    "PtrDocument", "PtrTransaction", "ScannedExtraction", "ScannedPtrExtractor", "TICKER_ASSET_TYPES",
    "TRANSACTION_TYPES", "coverage_metrics", "disclosure_lag_days", "filing_available_at", "imp_known_at",
    "parse_amount_range", "parse_filing_index", "parse_ptr_pdf", "parse_transactions", "pdf_pages", "pdf_text_lines",
    "periodic_transaction_reports",
]
