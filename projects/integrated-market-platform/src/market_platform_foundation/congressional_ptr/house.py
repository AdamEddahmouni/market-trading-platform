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
images: they have no text layer and are reported ``TRANSACTIONS_NOT_MACHINE_READABLE``,
never guessed.

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

PARSER_VERSION = "congressional_ptr.house/1.0.0"
INDEX_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
PTR_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"
CHAMBER = "HOUSE"
PTR_FILING_TYPE = "P"
MAX_PDF_BYTES = 8 * 1024 * 1024

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


def pdf_text_lines(data: bytes) -> list[str]:
    """Text-layer lines (cells joined by ' | '); empty for a scanned (image-only) document."""

    pdf = _Pdf(data)
    fonts: dict[int, dict[int, str]] = {}
    for number in pdf.objects:
        head = pdf.dictionary(number)
        if b"/Type /Font" in head and b"/ToUnicode" in head:
            ref = re.search(rb"/ToUnicode\s+(\d+) 0 R", head)
            if ref:
                fonts[number] = _cmap(pdf.stream(int(ref.group(1))))
    pages = [number for number in pdf.objects if re.search(rb"/Type\s*/Page\b(?!s)", pdf.dictionary(number))]
    lines: list[str] = []
    for page in sorted(pages, key=lambda number: _page_order(pdf, number)):
        head = pdf.dictionary(page)
        page_fonts = {name.decode(): fonts[int(ref)] for name, ref in _FONT_REF.findall(head) if int(ref) in fonts}
        contents = [int(ref) for ref in re.findall(rb"/Contents\s+(\d+) 0 R", head)]
        contents += [int(ref) for ref in re.findall(rb"/XObject\s*<<\s*(?:/\w+\s+\d+ 0 R\s*)*?/\w+\s+(\d+) 0 R", head)]
        for ref in contents:
            if ref not in pdf.objects:
                continue
            own = {name.decode(): fonts[int(num)] for name, num in _FONT_REF.findall(pdf.dictionary(ref)) if int(num) in fonts}
            lines.extend(_content_lines(pdf.stream(ref), {**page_fonts, **own}))
    cleaned = (_CONTROL.sub("", line).strip() for line in lines)
    return [line for line in cleaned if line.strip(" |")]


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
    return PtrTransaction(
        owner=owner, asset_description=description, asset_type_code=asset_code,
        disclosed_ticker=ticker_match.group(1) if ticker_match else None,
        transaction_type=TRANSACTION_TYPES[row.code], transaction_type_code=row.code,
        transaction_date=_parse_date(row.traded), notification_date=_parse_date(row.notified), amount=amount,
        row_index=row_index, quality_flags=tuple(flags))


def parse_transactions(lines: list[str]) -> list[PtrTransaction]:
    """Parse the transaction table from PTR text-layer lines.

    A row is anchored on ``type | transaction date | notification date | amount``;
    the asset text precedes it and ends with the ``[XX]`` asset-type code. A row
    cut by a page break continues after the next page's table header: the
    remaining asset text (up to ``[XX]``) and/or the amount's upper bound.
    """

    rows: list[_Row] = []
    buffer: list[str] = []
    for raw in lines:
        body = raw.strip(" |").strip()
        anchor = _ANCHOR.search(body)
        pending = rows[-1] if rows and (rows[-1].amount_open or not rows[-1].asset_complete) else None
        if anchor and not _is_label(body):
            code, traded, notified, amount_text = anchor.groups()
            prefix = body[:anchor.start()].strip(" |")
            if prefix:
                buffer.append(prefix)
            rows.append(_Row(code, traded, notified, " ".join(buffer), amount_text,
                             amount_text.rstrip().endswith("-")))
            buffer = []
        elif pending is not None and pending.amount_open and body.startswith("$") and not _is_boundary(body):
            pending.amount_text = f"{pending.amount_text} {body}"
            pending.amount_open = False
        elif _is_boundary(body):
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


@dataclass(frozen=True, slots=True)
class PtrDocument:
    doc_id: str
    state: str                     # PARSED / TRANSACTIONS_NOT_MACHINE_READABLE / PARSE_ERROR
    reason: str | None
    transactions: tuple[PtrTransaction, ...]
    source_sha256: str
    parser_version: str = PARSER_VERSION


def parse_ptr_pdf(doc_id: str, data: bytes) -> PtrDocument:
    digest = hashlib.sha256(data).hexdigest()
    if len(data) > MAX_PDF_BYTES:
        return PtrDocument(doc_id, "PARSE_ERROR", "PDF_TOO_LARGE", (), digest)
    try:
        lines = pdf_text_lines(data)
    except (ValueError, KeyError, zlib.error) as exc:
        code = str(exc) if str(exc).isupper() else "PDF_TEXT_LAYER_UNREADABLE"
        return PtrDocument(doc_id, "PARSE_ERROR", code, (), digest)
    if not lines:
        return PtrDocument(doc_id, "TRANSACTIONS_NOT_MACHINE_READABLE", "NO_TEXT_LAYER_SCANNED_FILING", (), digest)
    transactions = tuple(parse_transactions(lines))
    if not transactions:
        return PtrDocument(doc_id, "TRANSACTIONS_NOT_MACHINE_READABLE", "NO_TRANSACTION_ROWS_RECOGNIZED", (), digest)
    return PtrDocument(doc_id, "PARSED", None, transactions, digest)


# ------------------------------------------------------------------ availability
def filing_available_at(filing_date: date, *, retrieved_at: datetime | None) -> tuple[datetime, str]:
    """Lawful public-availability bound for a House filing (never the transaction date).

    The index carries a filing *date* only. As in the canonical congressional clock
    reconciliation, availability is the later of the end of the filing's UTC day
    and IMP's own first retrieval of the document.
    """

    end_of_day = datetime.combine(filing_date, time(23, 59, 59), tzinfo=UTC)
    if retrieved_at is not None and retrieved_at > end_of_day:
        return retrieved_at, "imp.first_retrieved_at"
    return end_of_day, "house_index.filing_date_end_of_utc_day"


def disclosure_lag_days(transaction_date: date | None, filing_date: date) -> int | None:
    """DERIVED: calendar days from the transaction date to the filing date."""

    if transaction_date is None:
        return None
    return (filing_date - transaction_date).days


__all__ = [
    "AmountRange", "CHAMBER", "HouseFiling", "INDEX_URL", "OWNER_CODES", "PARSER_VERSION", "PTR_URL", "PtrDocument",
    "PtrTransaction", "TICKER_ASSET_TYPES", "TRANSACTION_TYPES", "disclosure_lag_days",
    "filing_available_at", "parse_amount_range", "parse_filing_index", "parse_ptr_pdf", "parse_transactions",
    "pdf_text_lines", "periodic_transaction_reports",
]
