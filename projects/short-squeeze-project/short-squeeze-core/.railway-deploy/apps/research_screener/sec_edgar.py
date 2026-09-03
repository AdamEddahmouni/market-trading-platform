"""Live SEC EDGAR provider adapter.

Uses the official SEC EDGAR API (public, no API key required). Respects the SEC's
fair-access policy: no more than 10 requests per second, proper User-Agent header.

Reference: https://www.sec.gov/os/accessing-edgar-data
"""

from __future__ import annotations

import gzip
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.request import Request, urlopen

# SEC fair-access policy: no more than 10 requests/second.
MIN_INTERVAL_S = 0.15
TIMEOUT_S = 15.0

# Required by SEC: a descriptive User-Agent with contact information per
# https://www.sec.gov/os/accessing-edgar-data
# The SEC enforces User-Agent format and rejects requests without one.
USER_AGENT = "ResearchScreener/1.0 integration@example.invalid"

CIK_LOOKUP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{}.json"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _iso(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class SecFiling:
    form_type: str
    accession_number: str
    filed_at: str
    period_of_report: str | None
    primary_document: str | None
    issuer_cik: str
    description: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "form_type": self.form_type,
            "accession_number": self.accession_number,
            "filed_at": self.filed_at,
            "period_of_report": self.period_of_report,
            "primary_document": self.primary_document,
            "issuer_cik": self.issuer_cik,
            "description": self.description,
            "source": "SEC_EDGAR",
        }


@dataclass(slots=True)
class SecResult:
    symbol: str
    cik: str | None = None
    company_name: str | None = None
    filings: list[SecFiling] = field(default_factory=list)
    error: str | None = None
    retrieved_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "cik": self.cik,
            "company_name": self.company_name,
            "filings": [f.as_dict() for f in self.filings],
            "error": self.error,
            "retrieved_at": self.retrieved_at,
            "provider": "SEC_EDGAR",
        }


def _make_request(
    url: str,
    *,
    host: str | None = None,
    user_agent: str = USER_AGENT,
) -> bytes:
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }
    if host:
        headers["Host"] = host
    req = Request(url, headers=headers)
    with urlopen(req, timeout=TIMEOUT_S) as response:
        raw = response.read()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return raw


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _iso(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (ValueError, TypeError):
        return value


class EdgardClient:
    """Rate-limited SEC EDGAR client."""

    configured = True

    def __init__(self, user_agent: str = USER_AGENT) -> None:
        self._lock = threading.Lock()
        self._last_request: float = 0.0
        self._cik_cache: dict[str, str] = {}
        self.user_agent = user_agent

    def _pace(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_request
            if elapsed < MIN_INTERVAL_S:
                time.sleep(MIN_INTERVAL_S - elapsed)
            self._last_request = time.monotonic()

    def _load_ticker_map(self) -> dict[str, str]:
        """Load the SEC ticker-CIK mapping from company_tickers.json."""
        self._pace()
        try:
            data = json.loads(
                _make_request(
                    CIK_LOOKUP_URL,
                    host="www.sec.gov",
                    user_agent=self.user_agent,
                )
            )
            mapping: dict[str, str] = {}
            for entry in data.values():
                if isinstance(entry, dict):
                    ticker = str(entry.get("ticker", "")).upper().strip()
                    cik = str(entry.get("cik_str", ""))
                    if ticker and cik:
                        mapping[ticker] = cik
            return mapping
        except Exception:
            return {}

    def lookup_cik(self, symbol: str) -> str | None:
        symbol_upper = symbol.strip().upper()
        cached = self._cik_cache.get(symbol_upper)
        if cached:
            return cached
        ticker_map = self._load_ticker_map()
        cik = ticker_map.get(symbol_upper)
        if cik:
            self._cik_cache[symbol_upper] = cik
        return cik

    def recent_filings(self, symbol: str, *, max_results: int = 20) -> SecResult:
        result = SecResult(symbol=symbol)
        cik = self.lookup_cik(symbol)
        if cik is None:
            result.error = f"No CIK found for {symbol} via SEC EDGAR lookup."
            result.retrieved_at = _now()
            return result
        result.cik = cik

        self._pace()
        try:
            padded = cik.zfill(10)
            data = json.loads(
                _make_request(
                    SUBMISSIONS_URL.format(padded),
                    host="data.sec.gov",
                    user_agent=self.user_agent,
                )
            )
            result.company_name = data.get("name")
            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            accession_numbers = recent.get("accessionNumber", [])
            filing_dates = recent.get("filingDate", [])
            descriptions = recent.get("primaryDocument", [])
            period_reports = recent.get("reportDate", [])

            taken = 0
            # Scan through all recent filings (up to the full list)
            for i in range(min(len(forms), 200)):
                if taken >= max_results:
                    break
                form = forms[i]
                # Include all SEC filings that could be meaningful for research
                if form not in ("8-K", "10-K", "10-Q", "S-1", "S-3", "S-4", "6-K",
                                "20-F", "40-F", "F-1", "F-3", "F-4",
                                "3", "4", "5", "13F", "13D", "13G",
                                "SC 13G", "SC 13D", "SC 13G/A", "SC 13D/A",
                                "SD", "DEF 14A", "PRE 14A", "PREM14A",
                                "425", "EFFECT", "CORRESP"):
                    continue
                result.filings.append(SecFiling(
                    form_type=form,
                    accession_number=accession_numbers[i] if i < len(accession_numbers) else "",
                    filed_at=filing_dates[i] if i < len(filing_dates) else "",
                    period_of_report=period_reports[i] if i < len(period_reports) else None,
                    primary_document=descriptions[i] if i < len(descriptions) else None,
                    issuer_cik=cik,
                    description=f"{form} filed {filing_dates[i]}" if i < len(filing_dates) else form,
                ))
                taken += 1
        except Exception as exc:
            result.error = f"SEC EDGAR request failed: {type(exc).__name__}: {exc}"
        result.retrieved_at = _now()
        return result

    def has_recent_catalyst_filing(self, symbol: str) -> dict[str, Any]:
        """Check for recent 8-K, S-1, or other catalyst-type filings."""
        sec = self.recent_filings(symbol, max_results=30)
        catalyst_forms = {"8-K", "S-1", "S-3", "S-4", "SC 13D", "SC 13G",
                           "13D", "13G", "6-K", "425", "DEF 14A", "PREM14A",
                           "10-K", "10-Q", "20-F", "40-F", "F-1", "F-3", "F-4"}
        catalysts = [f for f in sec.filings if f.form_type in catalyst_forms]
        return {
            "available": len(catalysts) > 0,
            "catalyst_count": len(catalysts),
            "most_recent": catalysts[0].as_dict() if catalysts else None,
            "all_filings": [f.as_dict() for f in sec.filings],
            "cik": sec.cik,
            "company_name": sec.company_name,
            "error": sec.error,
            "retrieved_at": sec.retrieved_at,
            "provider": "SEC_EDGAR",
        }


_EDGAR_CLIENT: EdgardClient | None = None
_EDGAR_LOCK = threading.Lock()


def get_edgar_client() -> EdgardClient:
    global _EDGAR_CLIENT
    with _EDGAR_LOCK:
        if _EDGAR_CLIENT is None:
            _EDGAR_CLIENT = EdgardClient()
        return _EDGAR_CLIENT


__all__ = [
    "EdgardClient",
    "SecFiling",
    "SecResult",
    "get_edgar_client",
]
