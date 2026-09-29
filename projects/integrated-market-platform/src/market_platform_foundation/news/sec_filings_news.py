"""SEC EDGAR filings as official events beside news headlines (S11).

Replaces the Short Squeeze donor's ``collectors/sec_rss.py`` (it parsed the
EDGAR Atom feed as RSS and always returned zero items, with a placeholder
User-Agent) with the canonical ``sec_edgar`` stack: the Fair Access
``SecTransport`` (declared User-Agent, global throttle, cache), the submissions
JSON, and ``FilingEvent`` clocks.

A filing is an OFFICIAL_FILING, never a news headline: it keeps its form type,
accession, acceptance time, and EDGAR index URL. Only recent event-bearing forms
are surfaced; document bodies are never fetched here.

Opt-in: ``IMP_EDGAR_LIVE=1`` plus a declared ``SEC_USER_AGENT`` (name + email).
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import UTC, datetime
from typing import Any, Callable

from ..sec_edgar.filing import FilingEvent
from ..sec_edgar.identity import pad_cik

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
TICKER_MAP_TTL_S = 24 * 3600
SUBMISSIONS_TTL_S = 600
EVENT_FORMS = ("8-K", "8-K/A", "6-K", "10-Q", "10-K", "10-K/A", "20-F", "S-1", "S-3", "424B1", "424B2", "424B3",
               "424B4", "424B5", "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A", "SCHEDULE 13D", "SCHEDULE 13D/A",
               "SCHEDULE 13G", "SCHEDULE 13G/A", "DEF 14A", "4")
#: Beneficial-ownership schedules (EDGAR form names before and after the December 2024 change).
BENEFICIAL_FORMS = frozenset({"SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A", "SCHEDULE 13D", "SCHEDULE 13D/A",
                              "SCHEDULE 13G", "SCHEDULE 13G/A"})


def is_issuer_event(filing: FilingEvent, cik: str) -> bool:
    """An event about this issuer. A company's submissions also list the 13D/13G it filed *as a
    holder of another company* (submitted under its own CIK); those are not its news."""

    form = filing.form_type.upper()
    if form not in EVENT_FORMS:
        return False
    submitter = filing.normalized_accession.split("-", 1)[0].lstrip("0")
    return not (form in BENEFICIAL_FORMS and submitter == cik.lstrip("0"))


def live_state(env: Callable[[str], str | None] = os.environ.get) -> tuple[str, str | None]:
    if (env("IMP_EDGAR_LIVE") or "") != "1":
        return "LIVE_DISABLED", "IMP_EDGAR_LIVE_NOT_SET"
    agent = (env("SEC_USER_AGENT") or "").strip()
    if not agent or "@" not in agent or " " not in agent:
        return "NOT_CONFIGURED", "SEC_USER_AGENT_NOT_SET"
    return "CURRENT", None


def filing_headline(filing: FilingEvent) -> str:
    labels = [label for _key, label in sorted(filing.item_labels.items())] if filing.item_labels else []
    detail = f" — {'; '.join(labels[:3])}" if labels else ""
    return f"{filing.entity_name or 'Issuer'} filed {filing.form_type}{detail}"


def filing_item(filing: FilingEvent, *, ticker: str, retrieved_time: str) -> dict[str, Any]:
    """Raw item in the canonical normalizer's shape; ``source_type`` keeps it distinct from news."""

    return {
        "headline": filing_headline(filing), "url": filing.archive_index_url(),
        "published_time": filing.acceptance_datetime.replace(".000Z", "Z") if filing.acceptance_datetime else filing.filing_date,
        "summary": "", "publisher_source": "SEC EDGAR", "provider": "SEC_EDGAR",
        "provider_native_id": f"sec:{filing.normalized_accession}", "tickers": [ticker.upper()],
        "source_type": "OFFICIAL_FILING", "form_type": filing.form_type, "cik": filing.cik,
        "received_time": retrieved_time,
        "quality_flags": ["SEC_ACCEPTANCE_TIME"] if filing.acceptance_datetime else ["SEC_FILING_DATE_ONLY"],
    }


class SecFilingNews:
    """Recent filings for one ticker, through the canonical Fair Access transport."""

    provider_id = "sec_filings"

    def __init__(self, *, transport_factory: Callable[[], Any] | None = None,
                 env: Callable[[str], str | None] = os.environ.get, clock: Callable[[], float] = time.time) -> None:
        self._transport_factory = transport_factory
        self._env = env
        self._clock = clock
        self._lock = threading.Lock()
        self._transport: Any = None
        self._tickers: tuple[float, dict[str, str]] | None = None
        self._submissions: dict[str, tuple[float, list[FilingEvent]]] = {}

    def _get_transport(self) -> Any:
        if self._transport is None:
            if self._transport_factory is not None:
                self._transport = self._transport_factory()
            else:
                from ..sec_edgar.transport import SecTransport

                self._transport = SecTransport(user_agent=self._env("SEC_USER_AGENT") or "")
        return self._transport

    def cik_for(self, ticker: str) -> str | None:
        now = self._clock()
        with self._lock:
            cached = self._tickers
        if cached is None or cached[0] < now:
            body = self._get_transport().get(TICKERS_URL)
            payload = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
            mapping = {str(row.get("ticker", "")).upper(): pad_cik(str(row.get("cik_str", "")))
                       for row in (payload.values() if isinstance(payload, dict) else payload) if isinstance(row, dict)}
            with self._lock:
                self._tickers = (now + TICKER_MAP_TTL_S, mapping)
            cached = self._tickers
        return cached[1].get(ticker.upper())

    def fetch(self, ticker: str) -> dict[str, Any]:
        state, reason = live_state(self._env)
        received = datetime.fromtimestamp(self._clock(), tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        if state != "CURRENT":
            return {"success": False, "error": reason, "state": state, "items": [], "received_at": received}
        try:
            cik = self.cik_for(ticker)
            if cik is None:
                return {"success": True, "error": None, "state": "CURRENT", "items": [], "received_at": received,
                        "reason": "TICKER_NOT_IN_SEC_MAP"}
            now = self._clock()
            with self._lock:
                cached = self._submissions.get(cik)
            if cached is None or cached[0] < now:
                from ..sec_edgar.live import fetch_submissions

                filings = list(fetch_submissions(self._get_transport(), cik))
                with self._lock:
                    self._submissions[cik] = (now + SUBMISSIONS_TTL_S, filings)
            else:
                filings = cached[1]
        except Exception as exc:  # noqa: BLE001 — classified, never raised into a request
            code = str(exc) if str(exc).startswith("SEC_") else "NETWORK_ERROR"
            return {"success": False, "error": code, "state": "ERROR", "items": [], "received_at": received}
        items = [filing_item(filing, ticker=ticker, retrieved_time=received)
                 for filing in filings if is_issuer_event(filing, cik)][:40]
        return {"success": True, "error": None, "state": "CURRENT", "items": items, "received_at": received}


__all__ = ["BENEFICIAL_FORMS", "EVENT_FORMS", "SecFilingNews", "filing_headline", "filing_item", "is_issuer_event",
           "live_state"]
