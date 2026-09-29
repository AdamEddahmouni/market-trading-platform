"""Fund-held U.S. bond reference catalog from SEC Form N-PORT data sets (Screener S16).

The SEC publishes the public part of every registered fund's Form N-PORT as
quarterly structured data sets (``<yyyy>q<n>_nport.zip``: SUBMISSION,
FUND_REPORTED_INFO, FUND_REPORTED_HOLDING, IDENTIFIERS, DEBT_SECURITY, …).
Each debt holding carries the issuer, a CUSIP, maturity, coupon type and
annualized rate, default/PIK/convertible flags, and the fund's own valuation.
It is the only permitted, universe-scale public source of corporate, agency,
municipal, and securitized bond *reference* terms: TRACE security prints are a
licensed product, MSRB EMMA bulk data is a paid subscription, and NRSRO rating
histories need a terms acceptance.

What a row is — and is not:

- a CUSIP that at least one SEC-registered fund reported holding at its
  report date (so the catalog is *fund-held* coverage, not every outstanding
  bond, and a bond called since the report date can still appear);
- reconciled terms across every reporting fund (see ``reconcile``);
- the funds' own fair values (percent of par) at the report date — a stale,
  fund-reported valuation, never a current price or a trade.

N-PORT has no coupon frequency, day count, call schedule, or rating, so no
price/yield/duration math is ever run on these rows.

Reconciliation per CUSIP (after amended filings supersede the original for
the same series and report date):

1. the CUSIP must pass its check digit (placeholders like ``999999999`` fail);
   UMBS/GNMA TBA forwards (``01F``/``01N``/``21H`` prefixes, or "TBA" in the
   title) are excluded — they are forward contracts, not securities; an
   identifier starting with a letter (CINS-shaped) is admitted only when a
   reporting fund's ISIN embeds it — fund administrators' internal IDs
   (``ACI…``, ``BL…``, ``BA000…``) carry a CUSIP-style check digit too, and
   would otherwise pose as CUSIPs and duplicate real bonds
   (``UNCORROBORATED_IDENTIFIER``); an ISIN is derived (``US`` + CUSIP) only
   for a numeric CUSIP of a U.S. issuer with no reported ISIN;
2. only USD holdings of asset category DBT or ABS-* count; UST lines are
   skipped because the Treasury catalog is authoritative; non-U.S. sovereign,
   loan, and other categories are excluded and counted;
3. category and maturity each need ≥ 75 % of lines to agree, else the CUSIP is
   rejected (``CATEGORY_CONFLICT`` / ``MATURITY_CONFLICT``);
4. a fixed coupon is the modal exact value of the 2-dp cluster that ≥ 75 % of
   fixed-coupon lines fall into; a fraction-encoded rate (0.0457 for 4.57 %)
   is folded ×100 only when corroborated — by another filing's rate or by a
   percentage stated in a reporting fund's own security title ("FNMA 4.50% …");
   a split or uncorroborated sub-0.1 % value withholds the coupon (the row stays);
5. floating/variable ``ANNUALIZED_RATE`` is the rate on the report date and is
   never stored as a coupon.

The build runs offline from a verified ZIP into one SQLite generation under an
external data root managed by the S14 lifecycle (``NportStore`` /
``NportLifecycle`` subclass it); the Screener only reads the active generation.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
import statistics
import threading
import time
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from contextlib import closing
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..sec_edgar.thirteen_f_index import SourceIntegrityError
from ..sec_edgar.thirteen_f_lifecycle import (
    SEC_ORIGIN, DatasetRef, RefreshError, ThirteenFLifecycle, ThirteenFStore, status as lifecycle_status,
)
from ..xa01.enums import InstrumentKind, XaAssetClass
from ..xa01.identity import bond_identity_key, derive_canonical_id
from .identifiers import cusip_valid, isin_from_cusip, isin_valid

SOURCE = "SEC_FORM_NPORT"
SCHEMA = "imp-nport-bond-catalog/1"
MANIFEST_SCHEMA = "imp-nport-generation-manifest/1"
TOOL_VERSION = "fixed_income.nport_catalog/1.0.0"
ROOT_ENV = "IMP_NPORT_DATA_ROOT"
LISTING_URL = "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets"
IMPORT_URL_BASE = f"{SEC_ORIGIN}/files/dera/data/form-n-port-data-sets/"
DEFAULT_DATASETS = 1          # the newest quarter: N-PORT is a holdings snapshot, not a history
CONSENSUS = 0.75
TBA_PREFIXES = ("01F", "01N", "21H")
_TBA_TITLE = re.compile(r"\bTBA\b", re.I)
_TITLE_PERCENT = re.compile(r"(?<![\d.])(\d{1,2}(?:\.\d{1,4})?)\s?%")
_QUARTER = re.compile(r"^(\d{4})q([1-4])_nport\.zip$")
_HREF = re.compile(r"""href\s*=\s*["']([^"']+_nport\.zip)["']""", re.I)
_MONTHS = {name: index for index, name in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), start=1)}

CORPORATE, AGENCY, MUNICIPAL, SECURITIZED, TREASURY = "Corporate", "Agency", "Municipal", "Securitized", "Treasury"
CATEGORIES = (CORPORATE, AGENCY, MUNICIPAL, SECURITIZED)
REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "SUBMISSION.tsv": ("ACCESSION_NUMBER", "FILING_DATE", "SUB_TYPE", "REPORT_DATE"),
    "FUND_REPORTED_INFO.tsv": ("ACCESSION_NUMBER", "SERIES_ID"),
    "FUND_REPORTED_HOLDING.tsv": ("ACCESSION_NUMBER", "HOLDING_ID", "ISSUER_NAME", "ISSUER_LEI", "ISSUER_TITLE",
                                  "ISSUER_CUSIP", "BALANCE", "UNIT", "CURRENCY_CODE", "CURRENCY_VALUE", "ASSET_CAT",
                                  "ISSUER_TYPE", "INVESTMENT_COUNTRY"),
    "IDENTIFIERS.tsv": ("HOLDING_ID", "IDENTIFIER_ISIN"),
    "DEBT_SECURITY.tsv": ("HOLDING_ID", "MATURITY_DATE", "COUPON_TYPE", "ANNUALIZED_RATE", "IS_DEFAULT",
                          "IS_ANY_PORTION_INTEREST_PAID", "IS_CONVTIBLE_MANDATORY", "IS_CONVTIBLE_CONTINGENT"),
}
_SUBTYPES = {("ABS-MBS", True): "Agency MBS", ("ABS-MBS", False): "Non-agency MBS", "ABS-CBDO": "CDO / CLO",
             "ABS-APCP": "Asset-backed CP", "ABS-O": "Other ABS"}


def _day(raw: str | None) -> str | None:
    """``31-MAR-2026`` (N-PORT) or ISO → ISO date text; anything else → None."""

    text = (raw or "").strip().upper()
    try:
        if len(text) == 11 and text[2] == "-" and text[6] == "-":
            return date(int(text[7:]), _MONTHS[text[3:6]], int(text[:2])).isoformat()
        return date.fromisoformat(text[:10]).isoformat()
    except (KeyError, ValueError):
        return None


def _float(raw: str | None) -> float | None:
    try:
        value = float(raw) if raw not in (None, "", "N/A") else None
    except ValueError:
        return None
    return value if value is not None and value == value and abs(value) != float("inf") else None


def line_category(asset_cat: str, issuer_type: str) -> tuple[str | None, str | None, str | None]:
    """(category, subtype, exclusion reason) for one holding line."""

    if issuer_type == "UST":
        return None, None, "TREASURY_FROM_TREASURY_CATALOG"
    if asset_cat == "DBT":
        if issuer_type == "CORP":
            return CORPORATE, "Corporate debt", None
        if issuer_type in ("USGA", "USGSE"):
            return AGENCY, "Agency debt (GSE)" if issuer_type == "USGSE" else "Agency debt (U.S. government agency)", None
        if issuer_type == "MUN":
            return MUNICIPAL, "Municipal", None
        return None, None, "EXCLUDED_ISSUER_TYPE"
    if asset_cat.startswith("ABS-"):
        subtype = _SUBTYPES.get((asset_cat, issuer_type in ("USGA", "USGSE"))) or _SUBTYPES.get(asset_cat) or "Other ABS"
        return SECURITIZED, subtype, None
    return None, None, "EXCLUDED_ASSET_CATEGORY"


def is_tba(cusip: str, title: str) -> bool:
    return cusip.startswith(TBA_PREFIXES) or bool(_TBA_TITLE.search(title or ""))


def _consensus(counter: Counter[Any]) -> tuple[Any, float]:
    value, count = counter.most_common(1)[0]
    return value, count / sum(counter.values())


def title_percents(titles: Iterable[str]) -> set[float]:
    """Percentages a security title states ("GNMA 8.00% 6/30" → {8.0}), rounded to 2 dp."""

    return {round(float(match), 2) for title in titles for match in _TITLE_PERCENT.findall(title or "")}


def reconcile_coupon(rates: list[float], titles: Iterable[str] = ()) -> tuple[float | None, str]:
    """Fixed-coupon consensus over every fixed-coupon line (see module docstring)."""

    if not rates:
        return None, "NO_FIXED_RATE_REPORTED"
    direct = Counter(round(value, 2) for value in rates if value >= 0.1)
    stated = title_percents(titles)
    folded: list[float] = []
    for value in rates:
        if 0 < value < 0.1:
            candidate = value * 100
            if round(candidate, 2) in direct or round(candidate, 2) in stated:
                folded.append(candidate)
                continue
            return None, "AMBIGUOUS_RATE_ENCODING"
        folded.append(value)
    clusters = Counter(round(value, 2) for value in folded)
    top, share = _consensus(clusters)
    if share < CONSENSUS:
        return None, "COUPON_CONFLICT"
    exact = Counter(round(value, 6) for value in folded if round(value, 2) == top)
    return exact.most_common(1)[0][0], "CONSENSUS"


@dataclass(slots=True)
class Line:
    category: str
    subtype: str
    maturity: str | None
    coupon_type: str
    rate: float | None
    in_default: bool
    pik: bool
    convertible: bool
    currency: str
    unit: str
    balance: float | None
    value: float | None
    report_date: str
    filing_date: str
    series: str
    issuer: str
    title: str
    lei: str
    isin: str
    country: str


def reconcile(cusip: str, lines: list[Line]) -> tuple[dict[str, Any] | None, str | None]:
    """One catalog record from every surviving line of one CUSIP, or (None, rejection code)."""

    usd = [line for line in lines if line.currency == "USD"]
    if not usd:
        return None, "NON_USD"
    reported = Counter(line.isin for line in usd if isin_valid(line.isin) and line.isin[2:11] == cusip).most_common(1)
    if not cusip[0].isdigit() and not reported:
        return None, "UNCORROBORATED_IDENTIFIER"
    category, share = _consensus(Counter(line.category for line in usd))
    if share < CONSENSUS:
        return None, "CATEGORY_CONFLICT"
    usd = [line for line in usd if line.category == category]
    maturities = Counter(line.maturity for line in usd if line.maturity)
    if not maturities:
        return None, "MISSING_MATURITY"
    maturity, share = _consensus(maturities)
    if share < CONSENSUS:
        return None, "MATURITY_CONFLICT"
    coupon_type, share = _consensus(Counter(line.coupon_type or "Unknown" for line in usd))
    if share < CONSENSUS:
        coupon, coupon_state, coupon_type = None, "COUPON_TYPE_CONFLICT", "Conflicting"
    elif coupon_type == "Fixed":
        coupon, coupon_state = reconcile_coupon([line.rate for line in usd if line.coupon_type == "Fixed" and line.rate is not None],
                                                [line.title for line in usd])
    elif coupon_type == "None":
        coupon, coupon_state = 0.0, "ZERO_COUPON"
    else:
        coupon, coupon_state = None, "NOT_FIXED"
    latest = max(line.report_date for line in usd)
    current = [line for line in usd if line.report_date == latest]
    valued = [line.value / line.balance * 100 for line in current
              if line.unit == "PA" and line.balance and line.balance > 0 and line.value is not None]
    value_pct = statistics.median(valued) if valued else None
    if value_pct is not None and not 0 < value_pct < 300:
        value_pct = None  # an implausible ratio is a reporting-unit error, never shown
    rate_lines = [line.rate for line in current if line.rate is not None and line.coupon_type in ("Floating", "Variable")]
    subtype = Counter(line.subtype for line in usd).most_common(1)[0][0]
    issuer = Counter(line.issuer for line in usd if line.issuer).most_common(1)
    title = Counter(line.title for line in usd if line.title).most_common(1)
    lei = Counter(line.lei for line in usd if len(line.lei) == 20 and line.lei.isalnum()).most_common(1)
    country = Counter(line.country for line in usd if line.country).most_common(1)
    country_code = country[0][0] if country else None
    if reported:
        isin, isin_source = reported[0][0], "REPORTED"
    elif country_code == "US":
        isin, isin_source = isin_from_cusip(cusip, "US"), "DERIVED"
    else:
        isin, isin_source = None, None
    funds = {line.series for line in usd}
    par = sum(line.balance for line in usd if line.unit == "PA" and line.balance and line.balance > 0)
    return {
        "cusip": cusip, "category": category, "subtype": subtype,
        "instrument_id": derive_canonical_id(instrument_kind=InstrumentKind.BOND, asset_class=XaAssetClass.BOND,
                                             identity_key=bond_identity_key(security_id=cusip)),
        "issuer": issuer[0][0] if issuer else None, "title": title[0][0] if title else None,
        "issuer_lei": lei[0][0] if lei else None, "country": country_code, "isin": isin, "isin_source": isin_source,
        "maturity": maturity, "coupon": coupon, "coupon_type": coupon_type, "coupon_state": coupon_state,
        "reported_rate": round(statistics.median(rate_lines), 6) if rate_lines else None,
        "in_default": int(sum(line.in_default for line in current) * 2 > len(current)),
        "pik": int(sum(line.pik for line in current) * 2 > len(current)),
        "convertible": int(sum(line.convertible for line in current) * 2 > len(current)),
        "fund_count": len(funds), "line_count": len(usd), "par_held": round(par, 2) if par else None,
        "value_pct_par": round(value_pct, 4) if value_pct is not None else None, "value_count": len(valued),
        "report_date_min": min(line.report_date for line in usd), "report_date_max": latest,
        "filing_date_max": max(line.filing_date for line in usd),
    }, None


# ------------------------------------------------------------------ archive reading
def verify_nport_archive(path: Path) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            for table, columns in REQUIRED_COLUMNS.items():
                if table not in names:
                    raise SourceIntegrityError(f"NPORT_SOURCE_TABLE_MISSING:{table}")
                with archive.open(table) as handle:
                    header = handle.readline().decode("utf-8", "replace").rstrip("\r\n").split("\t")
                if any(column not in header for column in columns):
                    raise SourceIntegrityError(f"NPORT_SOURCE_COLUMNS_MISSING:{table}")
            return {"tables": sorted(REQUIRED_COLUMNS), "members": len(names)}
    except (zipfile.BadZipFile, EOFError, OSError) as exc:
        raise SourceIntegrityError("NPORT_SOURCE_CORRUPT") from exc


def _rows(archive: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    with archive.open(name) as handle:
        text = io.TextIOWrapper(handle, encoding="utf-8", errors="replace", newline="")
        yield from csv.DictReader(text, delimiter="\t", quoting=csv.QUOTE_NONE)


_STAGING = """
CREATE TABLE sub(accession TEXT PRIMARY KEY, filing_date TEXT, report_date TEXT, amendment INTEGER);
CREATE TABLE info(accession TEXT PRIMARY KEY, series TEXT);
CREATE TABLE debt(holding_id TEXT PRIMARY KEY, maturity TEXT, coupon_type TEXT, rate REAL,
                  in_default INTEGER, pik INTEGER, convertible INTEGER);
CREATE TABLE ident(holding_id TEXT PRIMARY KEY, isin TEXT);
CREATE TABLE hold(holding_id TEXT, accession TEXT, cusip TEXT, category TEXT, subtype TEXT, currency TEXT, unit TEXT,
                  balance REAL, value REAL, issuer TEXT, title TEXT, lei TEXT, country TEXT);
"""

_CATALOG = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE securities(
  cusip TEXT PRIMARY KEY, instrument_id TEXT NOT NULL UNIQUE, category TEXT NOT NULL, subtype TEXT NOT NULL,
  issuer TEXT, title TEXT, issuer_lei TEXT, country TEXT, isin TEXT, isin_source TEXT,
  maturity TEXT NOT NULL, coupon REAL, coupon_type TEXT NOT NULL, coupon_state TEXT NOT NULL, reported_rate REAL,
  in_default INTEGER NOT NULL, pik INTEGER NOT NULL, convertible INTEGER NOT NULL,
  fund_count INTEGER NOT NULL, line_count INTEGER NOT NULL, par_held REAL, value_pct_par REAL, value_count INTEGER NOT NULL,
  report_date_min TEXT NOT NULL, report_date_max TEXT NOT NULL, filing_date_max TEXT NOT NULL);
CREATE TABLE rejections(reason TEXT PRIMARY KEY, count INTEGER NOT NULL);
"""
_COLUMNS = ("cusip", "instrument_id", "category", "subtype", "issuer", "title", "issuer_lei", "country", "isin",
            "isin_source", "maturity", "coupon", "coupon_type", "coupon_state", "reported_rate", "in_default", "pik",
            "convertible", "fund_count", "line_count", "par_held", "value_pct_par", "value_count", "report_date_min",
            "report_date_max", "filing_date_max")


def _flag(raw: str | None) -> int:
    return 1 if (raw or "").strip().upper() == "Y" else 0


def _stage(archive: zipfile.ZipFile, db: sqlite3.Connection, rejected: Counter[str]) -> dict[str, int]:
    db.executemany("INSERT OR REPLACE INTO sub VALUES (?,?,?,?)", (
        (row["ACCESSION_NUMBER"], _day(row["FILING_DATE"]) or "", _day(row["REPORT_DATE"]) or "",
         1 if row["SUB_TYPE"].strip().upper().endswith("/A") else 0) for row in _rows(archive, "SUBMISSION.tsv")))
    db.executemany("INSERT OR REPLACE INTO info VALUES (?,?)", (
        (row["ACCESSION_NUMBER"], row["SERIES_ID"].strip() or None) for row in _rows(archive, "FUND_REPORTED_INFO.tsv")))
    db.executemany("INSERT OR REPLACE INTO debt VALUES (?,?,?,?,?,?,?)", (
        (row["HOLDING_ID"], _day(row["MATURITY_DATE"]), row["COUPON_TYPE"].strip(), _float(row["ANNUALIZED_RATE"]),
         _flag(row["IS_DEFAULT"]), _flag(row["IS_ANY_PORTION_INTEREST_PAID"]),
         _flag(row["IS_CONVTIBLE_MANDATORY"]) or _flag(row["IS_CONVTIBLE_CONTINGENT"]))
        for row in _rows(archive, "DEBT_SECURITY.tsv")))
    db.executemany("INSERT OR IGNORE INTO ident VALUES (?,?)", (
        (row["HOLDING_ID"], row["IDENTIFIER_ISIN"].strip().upper()) for row in _rows(archive, "IDENTIFIERS.tsv")
        if row["IDENTIFIER_ISIN"].strip()))
    lines = 0

    def holdings() -> Iterator[tuple[Any, ...]]:
        nonlocal lines
        for row in _rows(archive, "FUND_REPORTED_HOLDING.tsv"):
            asset = row["ASSET_CAT"].strip().upper()
            if asset != "DBT" and not asset.startswith("ABS-"):
                continue
            lines += 1
            cusip = row["ISSUER_CUSIP"].strip().upper()
            if not cusip_valid(cusip):
                rejected["INVALID_CUSIP_LINES"] += 1
                continue
            category, subtype, reason = line_category(asset, row["ISSUER_TYPE"].strip().upper())
            if category is None:
                rejected[f"{reason}_LINES"] += 1
                continue
            title = row["ISSUER_TITLE"].strip()
            if is_tba(cusip, f"{title} {row['ISSUER_NAME']}"):
                rejected["TBA_FORWARD_LINES"] += 1
                continue
            yield (row["HOLDING_ID"], row["ACCESSION_NUMBER"], cusip, category, subtype,
                   row["CURRENCY_CODE"].strip().upper(), row["UNIT"].strip().upper(), _float(row["BALANCE"]),
                   _float(row["CURRENCY_VALUE"]), row["ISSUER_NAME"].strip()[:160], title[:200],
                   row["ISSUER_LEI"].strip().upper(), row["INVESTMENT_COUNTRY"].strip().upper())

    db.executemany("INSERT INTO hold VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", holdings())
    db.execute("CREATE INDEX hold_cusip ON hold(cusip)")
    # An amendment supersedes every earlier filing for the same series and report date.
    db.execute("""CREATE TABLE kept AS SELECT accession FROM (
                    SELECT s.accession, ROW_NUMBER() OVER (PARTITION BY COALESCE(i.series, s.accession), s.report_date
                                                          ORDER BY s.filing_date DESC, s.amendment DESC, s.accession DESC) AS rank
                    FROM sub s LEFT JOIN info i ON i.accession = s.accession) WHERE rank = 1""")
    db.execute("CREATE UNIQUE INDEX kept_accession ON kept(accession)")
    superseded = db.execute("SELECT COUNT(*) FROM sub WHERE accession NOT IN (SELECT accession FROM kept)").fetchone()[0]
    return {"debt_lines": lines, "superseded_filings": superseded,
            "submissions": db.execute("SELECT COUNT(*) FROM sub").fetchone()[0]}


def _joined(db: sqlite3.Connection) -> Iterator[tuple[str, list[Line]]]:
    cursor = db.execute("""
        SELECT h.cusip, h.category, h.subtype, d.maturity, d.coupon_type, d.rate, d.in_default, d.pik, d.convertible,
               h.currency, h.unit, h.balance, h.value, s.report_date, s.filing_date,
               COALESCE(i.series, h.accession), h.issuer, h.title, h.lei, COALESCE(x.isin, ''), h.country
        FROM hold h JOIN kept k ON k.accession = h.accession
             JOIN debt d ON d.holding_id = h.holding_id
             JOIN sub s ON s.accession = h.accession
             LEFT JOIN info i ON i.accession = h.accession
             LEFT JOIN ident x ON x.holding_id = h.holding_id
        ORDER BY h.cusip""")
    current: str | None = None
    group: list[Line] = []
    for row in cursor:
        if row[0] != current:
            if group:
                yield current, group  # type: ignore[misc]
            current, group = row[0], []
        group.append(Line(row[1], row[2], row[3], row[4] or "", row[5], bool(row[6]), bool(row[7]), bool(row[8]),
                          row[9], row[10], row[11], row[12], row[13], row[14], row[15], row[16] or "", row[17] or "",
                          row[18] or "", row[19] or "", row[20] or ""))
    if group:
        yield current, group  # type: ignore[misc]


def build_catalog_db(sources: list[Path], out: Path, *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build one catalog SQLite from the newest N-PORT data set in ``sources`` (deterministic)."""

    if not sources:
        raise RefreshError("NPORT_NO_SOURCE", "build")
    source = sorted(sources, key=lambda path: path.name)[-1]
    started = time.monotonic()
    staging_path = out.with_name(out.name + ".staging")
    staging_path.unlink(missing_ok=True)
    rejected: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    try:
        with zipfile.ZipFile(source) as archive, closing(sqlite3.connect(staging_path)) as staging:
            staging.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA temp_store=FILE;" + _STAGING)
            stats = _stage(archive, staging, rejected)
            staging.commit()
            with closing(sqlite3.connect(out)) as db:
                db.executescript(_CATALOG)
                batch: list[tuple[Any, ...]] = []
                report_min, report_max, filing_max = "9999", "", ""
                for cusip, lines in _joined(staging):
                    record, reason = reconcile(cusip, lines)
                    if record is None:
                        rejected[reason or "REJECTED"] += 1
                        continue
                    counts[record["category"]] += 1
                    counts[f"coupon:{record['coupon_state']}"] += 1
                    report_min = min(report_min, record["report_date_min"])
                    report_max = max(report_max, record["report_date_max"])
                    filing_max = max(filing_max, record["filing_date_max"])
                    batch.append(tuple(record[column] for column in _COLUMNS))
                    if len(batch) >= 20_000:
                        db.executemany(f"INSERT INTO securities VALUES ({','.join('?' * len(_COLUMNS))})", batch)
                        batch.clear()
                if batch:
                    db.executemany(f"INSERT INTO securities VALUES ({','.join('?' * len(_COLUMNS))})", batch)
                db.executemany("INSERT INTO rejections VALUES (?,?)", sorted(rejected.items()))
                securities = sum(counts[category] for category in CATEGORIES)
                info = {**(meta or {}), "schema": SCHEMA, "source_dataset": source.name,
                        "report_date_min": report_min if securities else None,
                        "report_date_max": report_max or None, "filing_date_max": filing_max or None,
                        "securities": securities, "by_category": {category: counts[category] for category in CATEGORIES},
                        "coupon_states": {key[7:]: value for key, value in sorted(counts.items()) if key.startswith("coupon:")},
                        "rejections": dict(sorted(rejected.items())), **stats}
                db.executemany("INSERT INTO meta VALUES (?,?)", [(key, json.dumps(value)) for key, value in sorted(info.items())])
                db.commit()
                db.execute("VACUUM")
    finally:
        staging_path.unlink(missing_ok=True)
    info["build_s"] = round(time.monotonic() - started, 1)
    return info


# ------------------------------------------------------------------ managed lifecycle (S14 mechanics)
def dataset_from_name(name: str, url: str) -> DatasetRef | None:
    """Quarter data sets cover filings made in that calendar quarter."""

    match = _QUARTER.match(name.lower())
    if not match:
        return None
    year, number = int(match.group(1)), int(match.group(2))
    start = date(year, 3 * number - 2, 1)
    end = (date(year + 1, 1, 1) if number == 4 else date(year, 3 * number + 1, 1)) - timedelta(days=1)
    return DatasetRef(name.lower(), url, start.isoformat(), end.isoformat())


def parse_listing(html: str) -> list[DatasetRef]:
    from urllib.parse import urljoin

    found: dict[str, DatasetRef] = {}
    for href in _HREF.findall(html or ""):
        url = urljoin(SEC_ORIGIN + "/", href.strip())
        ref = dataset_from_name(url.rsplit("/", 1)[-1], url)
        if ref is not None and url.startswith(SEC_ORIGIN + "/"):
            found.setdefault(ref.name, ref)
    return sorted(found.values(), key=lambda ref: (ref.coverage_end, ref.name))


class NportStore(ThirteenFStore):
    SOURCE_SUFFIX = "_nport.zip"
    MANIFEST_SCHEMA = MANIFEST_SCHEMA
    TOOL_VERSION = TOOL_VERSION
    ERROR_PREFIX = "NPORT"
    IMPORT_URL_BASE = IMPORT_URL_BASE

    def verify_source(self, path: Path) -> dict[str, Any]:
        return verify_nport_archive(path)

    def dataset_ref(self, name: str, url: str) -> DatasetRef | None:
        return dataset_from_name(name, url)


def smoke_catalog(index_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Open the candidate like the Screener does; every category must be present and loadable."""

    with closing(sqlite3.connect(index_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RefreshError("INDEX_QUICK_CHECK_FAILED", "validate")
        counts = dict(db.execute("SELECT category, COUNT(*) FROM securities GROUP BY category").fetchall())
    missing = [category for category in CATEGORIES if not counts.get(category)]
    if missing:
        raise RefreshError("NPORT_CATEGORY_MISSING", "validate")
    catalog = NportCatalog.load(index_path)
    if catalog.meta.get("generation") != manifest["generation"] or len(catalog.records) != sum(counts.values()):
        raise RefreshError("INDEX_GENERATION_MISMATCH", "validate")
    return {"by_category": counts, "securities": len(catalog.records)}


class NportLifecycle(ThirteenFLifecycle):
    def __init__(self, store: NportStore, *, fetch_listing: Callable[[], str] | None = None,
                 download: Callable[[str, Path], None] | None = None, datasets: int = DEFAULT_DATASETS,
                 builder: Callable[..., dict[str, Any]] = build_catalog_db,
                 smoke: Callable[[Path, dict[str, Any]], dict[str, Any]] = smoke_catalog, hook: Any = None) -> None:
        if fetch_listing is None:
            def fetch_listing() -> str:
                from ..sec_edgar.thirteen_f_lifecycle import _user_agent
                from ..sec_edgar.transport import SecTransport
                import os

                return SecTransport(user_agent=_user_agent(os.environ.get)).get(LISTING_URL).decode("utf-8", "replace")
        super().__init__(store, fetch_listing=fetch_listing, download=download, datasets=datasets, builder=builder,
                         smoke=smoke, hook=hook)

    def parse_listing(self, listing: str) -> list[DatasetRef]:
        return parse_listing(listing)

    def manifest_counts(self, stats: dict[str, Any]) -> dict[str, Any]:
        if not stats.get("securities"):
            raise RefreshError("INDEX_EMPTY", "build")
        return {"index_schema": SCHEMA, **{key: stats.get(key) for key in (
            "source_dataset", "securities", "by_category", "coupon_states", "rejections", "report_date_min",
            "report_date_max", "filing_date_max", "submissions", "superseded_filings", "debt_lines")}}


def status(root: str | Path | None, *, clock: Callable[[], float] = time.time) -> dict[str, Any]:
    return lifecycle_status(root, clock=clock, store_cls=NportStore, root_env=ROOT_ENV, not_built="NPORT_CATALOG_NOT_BUILT")


# ------------------------------------------------------------------ Screener-side catalog
@dataclass(frozen=True, slots=True)
class NportRecord:
    cusip: str
    instrument_id: str
    category: str
    subtype: str
    issuer: str | None
    title: str | None
    issuer_lei: str | None
    country: str | None
    isin: str | None
    isin_source: str | None
    maturity: date
    coupon: float | None
    coupon_type: str
    coupon_state: str
    reported_rate: float | None
    in_default: bool
    pik: bool
    convertible: bool
    fund_count: int
    line_count: int
    par_held: float | None
    value_pct_par: float | None
    value_count: int
    report_date_min: str
    report_date_max: str
    filing_date_max: str


class NportCatalog:
    """The active generation's records, loaded once into memory (read-only)."""

    def __init__(self, records: tuple[NportRecord, ...], meta: dict[str, Any]) -> None:
        self.records = records
        self.meta = meta
        self._by_id = {record.instrument_id: record for record in records}

    @classmethod
    def load(cls, path: Path) -> "NportCatalog":
        with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
            meta = {key: json.loads(value) for key, value in db.execute("SELECT key, value FROM meta")}
            if meta.get("schema") != SCHEMA:
                raise ValueError("NPORT_SCHEMA_MISMATCH")
            intern: dict[Any, Any] = {}

            def shared(value: Any) -> Any:
                return intern.setdefault(value, value)

            records = []
            for row in db.execute(f"SELECT {', '.join(_COLUMNS)} FROM securities ORDER BY maturity, cusip"):
                values = dict(zip(_COLUMNS, row))
                for key in ("category", "subtype", "country", "coupon_type", "coupon_state", "isin_source", "issuer",
                            "report_date_min", "report_date_max", "filing_date_max"):
                    values[key] = shared(values[key])
                values["maturity"] = shared(date.fromisoformat(values["maturity"]))
                for key in ("in_default", "pik", "convertible"):
                    values[key] = bool(values[key])
                records.append(NportRecord(**values))
        return cls(tuple(records), meta)

    def by_instrument(self, instrument_id: str) -> NportRecord | None:
        return self._by_id.get(instrument_id)


class ManagedCatalog:
    """Screener view of an N-PORT data root: files only, swaps to a newly published generation."""

    def __init__(self, root: str | Path, *, clock: Callable[[], float] = time.time, recheck_s: float = 60.0) -> None:
        self.root = Path(root)
        self._clock = clock
        self._recheck_s = recheck_s
        self._lock = threading.Lock()
        self._catalog: NportCatalog | None = None
        self._generation: str | None = None
        self._status: dict[str, Any] = {}
        self._problem: str | None = None
        self._checked = float("-inf")
        self.loads = 0

    def current(self) -> tuple[NportCatalog | None, dict[str, Any]]:
        with self._lock:
            now = self._clock()
            if now - self._checked < self._recheck_s:
                return self._catalog, self._status
            self._checked = now
            self._status = status(self.root, clock=time.time)
            store = NportStore(self.root)
            generation = store.current_generation()
            if generation != self._generation or self._catalog is None:
                problem = store.verify_generation(generation) if generation else "NPORT_CATALOG_NOT_BUILT"
                catalog = None
                if problem is None and generation is not None:
                    try:
                        catalog = NportCatalog.load(store.generation_dir(generation) / "index.sqlite")
                        self.loads += 1
                    except (sqlite3.Error, ValueError, OSError, TypeError):
                        problem = "INDEX_UNREADABLE"
                if catalog is not None or self._catalog is None:
                    self._catalog, self._generation, self._problem = catalog, generation if catalog else None, problem
                else:
                    self._problem = problem  # keep serving the last good generation
            if self._problem and self._catalog is None:
                self._status = {**self._status, "load_problem": self._problem}
            return self._catalog, self._status


def iter_records(catalog: NportCatalog | None, today: date) -> Iterable[NportRecord]:
    """Records whose maturity is after ``today`` (a matured bond is not listed)."""

    if catalog is None:
        return ()
    return (record for record in catalog.records if record.maturity > today)

