"""Automated Senate eFD download into the operator import directory (owner decision 2026-09-30).

eFD serves search and report pages only after a visitor accepts a statement of the
statutory restrictions on using the reports (5 U.S.C. § 13107(c)). The owner accepts
those terms once, records it in the import directory's ``ACCESS_ATTESTATION.json``,
and authorizes IMP to accept them on their behalf (``automated_access: true``). With
that, this module:

* accepts the terms the way a browser does (GET the home page, POST its CSRF token with
  ``prohibition_agreement``), keeping the session cookie in memory only;
* lists Periodic Transaction Reports through the search page's own data endpoint,
  newest first, 100 per page;
* downloads each report not already in the directory, saving the page as
  ``<kind>-<report id>.html`` beside a sidecar (``source_url``, ``retrieved_at``) that
  ``senate.scan_import`` already reads.

Requests are throttled (one per ``MIN_INTERVAL_S``) and carry the owner's declared
contact. A CAPTCHA, a changed form, or an unexpected response stops the run with a
stable code; nothing is retried in a loop and nothing is guessed. The parser and the
Screener are unchanged: they read the directory exactly as they read hand-saved pages.
"""

from __future__ import annotations

import http.cookiejar
import json
import re
import time as time_module
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..local_state.external_cache import read_manifest, write_json_atomic
from .senate import ATTESTATION_FILE

LIVE_ENV = "IMP_SENATE_EFD_LIVE"
BASE_URL = "https://efdsearch.senate.gov"
HOME_PATH = "/search/home/"
SEARCH_PATH = "/search/"
DATA_PATH = "/search/report/data/"
PTR_REPORT_TYPE = "[11]"
STATE_FILE = "SYNC_STATE.json"
PAGE_SIZE = 100
MAX_NEW_REPORTS = 250            # per run; the next run continues where this one stopped
MAX_LIST_PAGES = 40
FIRST_RUN_LOOKBACK_DAYS = 730    # two years of reports on the first run
OVERLAP_DAYS = 14                # re-list the last two weeks so late-indexed reports are not missed
MIN_INTERVAL_S = 1.0
MAX_PAGE_BYTES = 4 * 1024 * 1024
TIMEOUT_S = 30.0
_TOKEN = re.compile(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"')
_LINK = re.compile(r'href="(/search/view/(ptr|paper)/([0-9a-fA-F-]{36})/)"')

#: (method, url, form or None, headers) -> (status, final url, body)
Requester = Callable[[str, str, dict[str, str] | None, dict[str, str]], tuple[int, str, bytes]]


class SenateSyncError(Exception):
    """A stable code only (never a URL, cookie or body)."""


@dataclass(frozen=True, slots=True)
class ListedReport:
    report_id: str
    kind: str                # ptr | paper
    path: str
    filer: str
    filed: date | None

    @property
    def file_name(self) -> str:
        return f"{self.kind}-{self.report_id}.html"


def automation_authorized(root: Path) -> tuple[bool, str | None]:
    """The owner's attestation must exist and authorize automated terms acceptance."""

    attestation = read_manifest(root / ATTESTATION_FILE)
    if attestation is None or not attestation.get("accepted_by") or not attestation.get("accepted_at"):
        return False, "OPERATOR_ATTESTATION_MISSING"
    if attestation.get("automated_access") is not True:
        return False, "AUTOMATED_ACCESS_NOT_AUTHORIZED"
    return True, None


def _urllib_requester() -> Requester:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(method: str, url: str, form: dict[str, str] | None, headers: dict[str, str]) -> tuple[int, str, bytes]:
        body = urllib.parse.urlencode(form).encode("ascii") if form is not None else None
        try:
            with opener.open(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=TIMEOUT_S) as resp:
                return int(getattr(resp, "status", 200)), resp.geturl(), resp.read(MAX_PAGE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            return exc.code, url, b""

    return request


class EfdSession:
    """One terms-accepted eFD session. The cookie lives only in the requester's memory."""

    def __init__(self, *, user_agent: str, requester: Requester | None = None,
                 sleep: Callable[[float], None] = time_module.sleep, monotonic: Callable[[], float] = time_module.monotonic,
                 min_interval_s: float = MIN_INTERVAL_S) -> None:
        self._agent = user_agent
        self._request = requester or _urllib_requester()
        self._sleep = sleep
        self._monotonic = monotonic
        self._interval = min_interval_s
        self._last: float | None = None
        self._csrf: str | None = None
        self.requests = 0

    def _call(self, method: str, path: str, form: dict[str, str] | None = None, referer: str | None = None) -> tuple[str, str]:
        if self._last is not None:
            wait = self._interval - (self._monotonic() - self._last)
            if wait > 0:
                self._sleep(wait)
        headers = {"User-Agent": self._agent, "Referer": BASE_URL + (referer or HOME_PATH)}
        if self._csrf:
            headers["X-CSRFToken"] = self._csrf
        try:
            status, final_url, body = self._request(method, BASE_URL + path, form, headers)
        except (urllib.error.URLError, OSError) as exc:
            raise SenateSyncError("SENATE_EFD_NETWORK_ERROR") from exc
        finally:
            self._last = self._monotonic()
            self.requests += 1
        if status == 429:
            raise SenateSyncError("SENATE_EFD_RATE_LIMITED")
        if status != 200:
            raise SenateSyncError(f"SENATE_EFD_HTTP_{status}")
        if len(body) > MAX_PAGE_BYTES:
            raise SenateSyncError("SENATE_EFD_RESPONSE_TOO_LARGE")
        text = body.decode("utf-8", "replace")
        if "captcha" in text.lower():
            raise SenateSyncError("SENATE_EFD_CAPTCHA")
        return urllib.parse.urlparse(final_url).path, text

    def accept_terms(self) -> None:
        _, home = self._call("GET", HOME_PATH)
        token = _TOKEN.search(home)
        if token is None or 'name="prohibition_agreement"' not in home:
            raise SenateSyncError("SENATE_EFD_FORM_CHANGED")
        self._csrf = token.group(1)
        landed, _ = self._call("POST", HOME_PATH, {"csrfmiddlewaretoken": token.group(1), "prohibition_agreement": "1"})
        if landed.rstrip("/") != SEARCH_PATH.rstrip("/"):
            raise SenateSyncError("SENATE_EFD_TERMS_NOT_ACCEPTED")

    def list_reports(self, since: date) -> list[ListedReport]:
        reports: list[ListedReport] = []
        for page in range(MAX_LIST_PAGES):
            form = {"start": str(page * PAGE_SIZE), "length": str(PAGE_SIZE), "report_types": PTR_REPORT_TYPE,
                    "filer_types": "[]", "submitted_start_date": since.strftime("%m/%d/%Y 00:00:00"),
                    "submitted_end_date": "", "candidate_state": "", "senator_state": "", "office_id": "",
                    "first_name": "", "last_name": "", "csrfmiddlewaretoken": self._csrf or ""}
            _, text = self._call("POST", DATA_PATH, form, referer=SEARCH_PATH)
            try:
                payload = json.loads(text)
                rows = payload["data"]
                total = int(payload.get("recordsFiltered", payload.get("recordsTotal", 0)))
            except (ValueError, KeyError, TypeError) as exc:
                raise SenateSyncError("SENATE_EFD_LIST_MALFORMED") from exc
            for row in rows:
                reports.append(_listed(row))
            if not rows or (page + 1) * PAGE_SIZE >= total:
                return [report for report in reports if report is not None]
        return [report for report in reports if report is not None]

    def fetch_report(self, report: ListedReport) -> str:
        landed, text = self._call("GET", report.path, referer=SEARCH_PATH)
        if landed.rstrip("/") == HOME_PATH.rstrip("/"):
            raise SenateSyncError("SENATE_EFD_SESSION_EXPIRED")   # sent back to the terms page
        return text


def _listed(row: Any) -> ListedReport | None:
    if not isinstance(row, list) or len(row) < 5:
        return None
    link = _LINK.search(str(row[3]))
    if link is None:
        return None
    try:
        filed = datetime.strptime(str(row[4]).strip(), "%m/%d/%Y").date()
    except ValueError:
        filed = None
    return ListedReport(link.group(3).lower(), link.group(2), link.group(1), str(row[2]).strip(), filed)


def sync(root: Path, *, user_agent: str, session: EfdSession | None = None,
         now: Callable[[], datetime] = lambda: datetime.now(UTC), max_new: int = MAX_NEW_REPORTS) -> dict[str, Any]:
    """Download reports not yet in ``root``. Returns the run summary (also written to SYNC_STATE.json).

    Raises SenateSyncError before any network call when the directory or authorization is missing."""

    if not root.is_dir():
        raise SenateSyncError("SENATE_EFD_IMPORT_DIR_MISSING")
    authorized, reason = automation_authorized(root)
    if not authorized:
        raise SenateSyncError(str(reason))
    agent = (user_agent or "").strip()
    if "@" not in agent or " " not in agent:
        raise SenateSyncError("SEC_USER_AGENT_NOT_SET")   # the same declared contact the SEC clients use
    previous = read_manifest(root / STATE_FILE) or {}
    started = now()
    try:
        through = date.fromisoformat(str(previous.get("complete_through")))
        since = through - timedelta(days=OVERLAP_DAYS)
    except ValueError:
        since = started.date() - timedelta(days=FIRST_RUN_LOOKBACK_DAYS)
    efd = session or EfdSession(user_agent=agent)
    summary: dict[str, Any] = {"schema_version": "imp-senate-efd-sync/1.0.0", "started_at": _stamp(started),
                               "since": since.isoformat(), "listed": 0, "saved": 0, "already_present": 0,
                               "complete_through": previous.get("complete_through"), "error": None}
    try:
        efd.accept_terms()
        listed = efd.list_reports(since)
        summary["listed"] = len(listed)
        pending = [report for report in listed if not (root / report.file_name).is_file()]
        summary["already_present"] = len(listed) - len(pending)
        for report in pending[:max_new]:
            text = efd.fetch_report(report)
            retrieved = _stamp(now())
            target = root / report.file_name
            temporary = target.with_name(f".{target.name}.tmp")
            temporary.write_text(text, encoding="utf-8", newline="")
            write_json_atomic(target.with_name(target.name + ".json"),
                              {"source_url": BASE_URL + report.path, "retrieved_at": retrieved,
                               "retrieved_by": "IMP_AUTOMATED_EFD_SYNC", "listed_filer": report.filer,
                               "listed_filed_date": report.filed.isoformat() if report.filed else None})
            temporary.replace(target)          # the page appears only after its sidecar is written
            summary["saved"] += 1
        if len(pending) <= max_new:
            summary["complete_through"] = started.date().isoformat()
    except SenateSyncError as exc:
        summary["error"] = str(exc)
    summary["finished_at"] = _stamp(now())
    summary["requests"] = efd.requests
    write_json_atomic(root / STATE_FILE, summary)
    return summary


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = ["BASE_URL", "EfdSession", "LIVE_ENV", "ListedReport", "MAX_NEW_REPORTS", "STATE_FILE", "SenateSyncError",
           "automation_authorized", "sync"]
