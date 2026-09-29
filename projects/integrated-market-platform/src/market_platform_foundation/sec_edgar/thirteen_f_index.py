"""Local 13F holdings index built from the SEC's Form 13F data sets (Screener S12).

Source: https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets — one
ZIP per filing-date window (~100 MB) holding ``SUBMISSION.tsv``, ``COVERPAGE.tsv``
and ``INFOTABLE.tsv``. The index is operator-built (``tools/sec_edgar/thirteen_f_index.py``),
lives outside the repository, and is opened read-only by the Screener
(``IMP_13F_INDEX_PATH``). Nothing is downloaded at request time.

Semantics kept exact:

* a 13F line is a manager's holding **as of the quarter end** (``period``), filed up
  to 45 days later; it is never a live position and never a trade;
* the data sets carry a filing *date* only, so a filing is available from the end
  of its filing day (UTC) — never earlier;
* per (manager, period) the newest holdings report or RESTATEMENT amendment filed by
  the query's point in time is the base; NEW HOLDINGS amendments filed after it add
  lines. Every report is stored, so an earlier point in time sees what was filed
  then. Notice-only reports (``13F NOTICE REPORT``) carry no holdings;
* position = sum of the manager's SH lines in the CUSIP (put/call lines are option
  positions and are excluded; PRN lines are principal, not shares);
* changes are DERIVED per manager between consecutive periods
  (``classify_reported_change``); ``EXITED`` is only inferred when the manager filed
  the later period at all. Holdings of different managers are never summed —
  "other included managers" make cross-manager totals double-count.
"""

from __future__ import annotations

import csv
import io
import sqlite3
import threading
import zipfile
from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from .ownership import classify_reported_change

SOURCE_URL = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
SCHEMA = "imp-13f-index/2"
HOLDINGS_TYPES = frozenset({"13F HOLDINGS REPORT", "13F COMBINATION REPORT"})
TOP_HOLDERS = 10
_MONTHS = {name: index for index, name in enumerate(
    ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), start=1)}


def parse_sec_date(value: str) -> date | None:
    """``31-JUL-2026`` → date (the data sets' format)."""

    try:
        day, month, year = value.strip().split("-")
        return date(int(year), _MONTHS[month.upper()], int(day))
    except (ValueError, KeyError):
        return None


def _rows(archive: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    with archive.open(name) as handle:
        text = io.TextIOWrapper(handle, encoding="utf-8", errors="replace", newline="")
        yield from csv.DictReader(text, delimiter="\t", quoting=csv.QUOTE_NONE)


def _number(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def select_reports(submissions: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Pick the accessions whose lines form each (manager, period) position set.

    ``submissions`` maps accession → {cik, period, filing_date, type, report_type,
    amendment_type}. Returns accession → the same record for every selected one.
    """

    groups: dict[tuple[str, date], list[tuple[str, dict[str, Any]]]] = {}
    for accession, item in submissions.items():
        if item["report_type"] not in HOLDINGS_TYPES or item["period"] is None or item["filing_date"] is None:
            continue
        groups.setdefault((item["cik"], item["period"]), []).append((accession, item))
    selected: dict[str, dict[str, Any]] = {}
    for reports in groups.values():
        reports.sort(key=lambda pair: (pair[1]["filing_date"], pair[0]))
        bases = [pair for pair in reports if pair[1]["amendment_type"] != "NEW HOLDINGS"]
        if not bases:
            continue  # only add-on amendments present: the base report is outside the loaded windows
        base_accession, base = bases[-1]
        selected[base_accession] = base
        for accession, item in reports:
            if item["amendment_type"] == "NEW HOLDINGS" and item["filing_date"] >= base["filing_date"]:
                selected[accession] = item
    return selected


def build_index(zip_paths: Iterable[Path], out_path: Path) -> dict[str, int]:
    """Build (or replace) the SQLite index from one or more data-set ZIPs."""

    submissions: dict[str, dict[str, Any]] = {}
    archives = [zipfile.ZipFile(path) for path in zip_paths]
    try:
        for archive in archives:
            covers = {row["ACCESSION_NUMBER"]: row for row in _rows(archive, "COVERPAGE.tsv")}
            for row in _rows(archive, "SUBMISSION.tsv"):
                accession = row["ACCESSION_NUMBER"]
                cover = covers.get(accession, {})
                submissions[accession] = {
                    "cik": row["CIK"].zfill(10), "period": parse_sec_date(row["PERIODOFREPORT"]),
                    "filing_date": parse_sec_date(row["FILING_DATE"]), "type": row["SUBMISSIONTYPE"],
                    "report_type": (cover.get("REPORTTYPE") or "").strip().upper(),
                    "amendment_type": (cover.get("AMENDMENTTYPE") or "").strip().upper(),
                    "manager": (cover.get("FILINGMANAGER_NAME") or "").strip()}
        holdings = {accession: item for accession, item in submissions.items()
                    if item["report_type"] in HOLDINGS_TYPES and item["period"] and item["filing_date"]}
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = out_path.with_suffix(".tmp")
        tmp.unlink(missing_ok=True)
        db = sqlite3.connect(tmp)
        # Every holdings report is kept (originals, restatements, add-ons): which ones form a
        # manager's position depends on what had been filed at the query's point in time.
        db.executescript("""
            CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE filings(accession TEXT PRIMARY KEY, manager_cik TEXT, period TEXT, filing_date TEXT,
                                 manager TEXT, amendment_type TEXT);
            CREATE TABLE positions(cusip TEXT, accession TEXT, shares REAL, value_usd REAL, lines INTEGER,
                                   option_lines INTEGER);
        """)
        db.executemany("INSERT INTO filings VALUES (?,?,?,?,?,?)", [
            (accession, item["cik"], item["period"].isoformat(), item["filing_date"].isoformat(), item["manager"],
             item["amendment_type"] or None) for accession, item in holdings.items()])
        # Lines are staged in SQLite and aggregated there: an INFOTABLE holds millions of rows.
        db.execute("CREATE TEMP TABLE staged(cusip TEXT, accession TEXT, shares REAL, value_usd REAL, is_share INTEGER, "
                   "is_option INTEGER)")
        lines_read = 0
        batch: list[tuple[Any, ...]] = []
        for archive in archives:
            for row in _rows(archive, "INFOTABLE.tsv"):
                accession = row["ACCESSION_NUMBER"]
                cusip = (row.get("CUSIP") or "").strip().upper()
                if accession not in holdings or len(cusip) != 9:
                    continue
                lines_read += 1
                option = bool((row.get("PUTCALL") or "").strip())
                share = not option and (row.get("SSHPRNAMTTYPE") or "").strip().upper() == "SH"
                batch.append((cusip, accession, (_number(row.get("SSHPRNAMT")) or 0.0) if share else 0.0,
                              (_number(row.get("VALUE")) or 0.0) if share else 0.0, int(share), int(option)))
                if len(batch) >= 50_000:
                    db.executemany("INSERT INTO staged VALUES (?,?,?,?,?,?)", batch)
                    batch.clear()
        db.executemany("INSERT INTO staged VALUES (?,?,?,?,?,?)", batch)
        db.execute("INSERT INTO positions SELECT cusip, accession, SUM(shares), SUM(value_usd), SUM(is_share), "
                   "SUM(is_option) FROM staged GROUP BY cusip, accession")
        positions = db.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
        db.execute("DROP TABLE staged")
        db.execute("CREATE INDEX positions_cusip ON positions(cusip)")
        db.execute("CREATE INDEX filings_manager ON filings(manager_cik, period)")
        db.executemany("INSERT INTO meta VALUES (?,?)", [
            ("schema", SCHEMA), ("built_at", datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")),
            ("sources", ";".join(Path(path.filename or "").name for path in archives))])
        db.commit()
        db.execute("VACUUM")
        db.close()
        tmp.replace(out_path)
        return {"submissions": len(submissions), "holdings_reports": len(holdings), "lines": lines_read,
                "positions": positions}
    finally:
        for archive in archives:
            archive.close()


def _available(filing_date: str) -> datetime:
    return datetime.combine(date.fromisoformat(filing_date) + timedelta(days=1), time(0), tzinfo=UTC)


class ThirteenFIndex:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._db = connection
        self._lock = threading.Lock()  # one read-only connection shared by request threads
        meta = dict(connection.execute("SELECT key, value FROM meta").fetchall())
        if meta.get("schema") != SCHEMA:
            raise ValueError("THIRTEEN_F_INDEX_SCHEMA_MISMATCH")
        self.built_at = meta.get("built_at")

    @classmethod
    def load(cls, path: str | Path) -> ThirteenFIndex:
        uri = Path(path).resolve().as_uri() + "?mode=ro"
        return cls(sqlite3.connect(uri, uri=True, check_same_thread=False))

    def section(self, cusips: list[str], *, now: datetime, top: int = TOP_HOLDERS) -> dict[str, Any]:
        """Holders of ``cusips`` in the newest quarter whose filings were public at ``now``."""

        with self._lock:
            return self._section(cusips, now=now, top=top)

    def _section(self, cusips: list[str], *, now: datetime, top: int) -> dict[str, Any]:
        cusips = sorted({item.upper() for item in cusips if len(item) == 9})
        cutoff = (now.astimezone(UTC) - timedelta(days=1)).date().isoformat()  # filed by the end of a past UTC day
        marks = ",".join("?" for _ in cusips)
        rows = self._db.execute(
            f"SELECT p.accession, f.manager_cik, f.period, p.shares, p.value_usd, p.option_lines FROM positions p "
            f"JOIN filings f ON f.accession = p.accession WHERE p.cusip IN ({marks}) AND f.filing_date <= ?",
            (*cusips, cutoff)).fetchall()
        base = {"source_url": SOURCE_URL, "index_built_at": self.built_at, "cusips": cusips,
                "evidence_basis": "THIRTEEN_F_QUARTER_END_HOLDINGS"}
        periods = sorted({row[2] for row in rows}, reverse=True)
        if not periods:
            return {"state": "NO_DISCLOSURES", "reason": "NO_13F_LINES_FOR_CUSIP", **base}
        current, prior = periods[0], (periods[1] if len(periods) > 1 else None)
        wanted = [period for period in (current, prior) if period]
        reports = self._reports(sorted({row[1] for row in rows}), wanted, cutoff)
        selected = select_reports(reports)                       # as filed by the cutoff
        filed_periods = {(item["cik"], item["period"].isoformat()) for item in selected.values()}
        by_manager: dict[str, dict[str, Any]] = {}
        for accession, manager, period, shares, value, options in rows:
            if accession not in selected or period not in wanted:
                continue
            filed = selected[accession]["filing_date"].isoformat()
            slot = by_manager.setdefault(manager, {}).setdefault(period, {"shares": 0.0, "value_usd": 0.0,
                                                                          "option_lines": 0, "filing_date": filed})
            slot["shares"] += shares
            slot["value_usd"] += value
            slot["option_lines"] += options
            slot["filing_date"] = max(slot["filing_date"], filed)
        names = {item["cik"]: item["manager"] for item in sorted(reports.values(), key=lambda item: item["filing_date"])}
        holders, counts = [], {"NEW": 0, "INCREASED": 0, "DECREASED": 0, "UNCHANGED": 0, "EXITED": 0,
                               "INSUFFICIENT_EVIDENCE": 0}
        for manager in sorted({item["cik"] for item in selected.values()}):
            per = by_manager.get(manager, {})
            now_pos, old_pos = per.get(current), per.get(prior) if prior else None
            if (manager, current) not in filed_periods:
                continue  # the manager has not filed the newest quarter yet: nothing to say
            if now_pos is None and old_pos is None:
                continue
            change = classify_reported_change(old_pos["shares"] if old_pos else None,
                                              now_pos["shares"] if now_pos else None,
                                              prior_available=(manager, prior) in filed_periods)
            counts[change["change"] or change["class"]] += 1
            if now_pos is None or now_pos["shares"] <= 0:
                continue
            holders.append({"manager_cik": manager, "manager": names.get(manager) or manager,
                            "shares": now_pos["shares"], "value_usd": now_pos["value_usd"],
                            "option_lines": now_pos["option_lines"], "filing_date": now_pos["filing_date"],
                            "available_at": _available(now_pos["filing_date"]).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "prior_shares": old_pos["shares"] if old_pos else None, "change": change})
        holders.sort(key=lambda item: (-item["shares"], item["manager"]))
        deadline = date.fromisoformat(current) + timedelta(days=45)
        window_open = now.astimezone(UTC).date() <= deadline
        return {"state": "PARTIAL" if window_open else "CURRENT_AS_FILED",
                "reason": "FILING_WINDOW_OPEN" if window_open else None, **base, "period": current, "prior_period": prior,
                "filing_deadline": deadline.isoformat(), "filing_window_open": window_open,
                "holder_count": len(holders), "change_counts": counts, "holders": holders[:top],
                "note": ("Quarter-end holdings reported by 13F managers, filed up to 45 days later. Managers who have "
                         "not yet filed this quarter are not counted. Holdings are per manager and never summed "
                         "across managers (other-included managers double-count).")}

    def _reports(self, managers: list[str], periods: list[str], cutoff: str) -> dict[str, dict[str, Any]]:
        """Every holdings report these managers had filed for ``periods`` by the cutoff."""

        out: dict[str, dict[str, Any]] = {}
        period_marks = ",".join("?" for _ in periods)
        for start in range(0, len(managers), 500):
            chunk = managers[start:start + 500]
            marks = ",".join("?" for _ in chunk)
            for accession, cik, period, filed, manager, amendment in self._db.execute(
                    f"SELECT accession, manager_cik, period, filing_date, manager, amendment_type FROM filings "
                    f"WHERE manager_cik IN ({marks}) AND period IN ({period_marks}) AND filing_date <= ?",
                    (*chunk, *periods, cutoff)).fetchall():
                out[accession] = {"cik": cik, "period": date.fromisoformat(period), "filing_date": date.fromisoformat(filed),
                                  "report_type": "13F HOLDINGS REPORT", "amendment_type": amendment or "",
                                  "manager": manager}
        return out


__all__ = ["HOLDINGS_TYPES", "SOURCE_URL", "ThirteenFIndex", "build_index", "parse_sec_date", "select_reports"]
