"""SEC EDGAR CIK lookup and per-company 8-K Atom feeds for material filings.

Purpose
-------
Resolves ticker → CIK via SEC ``company_tickers.json`` (cached 24h in
``state/edgar_company_tickers.json``) and pulls recent 8-K (or configured form)
Atom entries for a single symbol.

Pipeline role
-------------
Called from ``news.rss_monitor`` when ``sec_edgar`` source kind is enabled.
Supplies structured ``{source, headline, url, published_utc, form_type}`` rows
that ``news.news_aggregator`` merges with wire RSS hits.

Key outputs
-----------
List of recent filing dicts per ticker (empty when CIK unknown or no fresh filings).

Handoff notes
-------------
**Reusable (equity/futures):** EDGAR Atom pattern works for any listed equity;
8-K/10-Q/10-K form lists are configurable. Rate-limit via ``_throttle``.

**Options-only coupling:** None — filings are asset-class agnostic.

**Futures:** EDGAR does not cover futures; omit this module or replace with
CFTC/exchange filing feeds for commodity catalysts.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import feedparser
from dateutil import parser as date_parser


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
CIK_CACHE_PATH = STATE_DIR / "edgar_company_tickers.json"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
USER_AGENT = "NewsMomentumAgent/1.0 internship@example.com"
_CIK_MEM: Dict[str, str] = {}
_CIK_LOADED_AT = 0.0
_CIK_TTL_SEC = 24 * 3600
_MIN_REQUEST_GAP = 0.2
_LAST_REQUEST_AT = 0.0


def _throttle() -> None:
    global _LAST_REQUEST_AT
    now = time.time()
    wait = _MIN_REQUEST_GAP - (now - _LAST_REQUEST_AT)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST_AT = time.time()


def _http_get(url: str, timeout: float = 20.0) -> bytes:
    _throttle()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "identity",
            "Accept": "application/json, application/atom+xml, application/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_entry_datetime(entry: Dict[str, Any]) -> datetime | None:
    for key in ("published", "updated", "created"):
        raw_value = entry.get(key)
        if not raw_value:
            continue
        try:
            parsed = date_parser.parse(str(raw_value))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _is_recent(publication_time: datetime | None, max_age_hours: int = 4) -> bool:
    if publication_time is None:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    return publication_time >= cutoff


def _load_cik_map(force: bool = False) -> Dict[str, str]:
    global _CIK_MEM, _CIK_LOADED_AT
    now = time.time()
    if not force and _CIK_MEM and (now - _CIK_LOADED_AT) < _CIK_TTL_SEC:
        return _CIK_MEM

    mapping: Dict[str, str] = {}
    if CIK_CACHE_PATH.exists() and not force:
        try:
            raw = json.loads(CIK_CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("tickers"), dict):
                mapping = {str(k).upper(): str(v) for k, v in raw["tickers"].items()}
                age = now - float(raw.get("fetched_at") or 0)
                if mapping and age < _CIK_TTL_SEC:
                    _CIK_MEM = mapping
                    _CIK_LOADED_AT = now
                    return mapping
        except Exception:
            mapping = {}

    try:
        payload = json.loads(_http_get(TICKERS_URL).decode("utf-8"))
        tickers: Dict[str, str] = {}
        if isinstance(payload, dict):
            for row in payload.values():
                if not isinstance(row, dict):
                    continue
                sym = str(row.get("ticker") or "").upper().strip()
                cik = row.get("cik_str")
                if not sym or cik is None:
                    continue
                tickers[sym] = str(int(cik)).zfill(10)
        mapping = tickers
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        CIK_CACHE_PATH.write_text(
            json.dumps({"fetched_at": now, "tickers": mapping}, indent=2),
            encoding="utf-8",
        )
    except Exception as error:
        print(f"[edgar_client] Failed to refresh company_tickers.json: {error}")
        if not mapping and CIK_CACHE_PATH.exists():
            try:
                raw = json.loads(CIK_CACHE_PATH.read_text(encoding="utf-8"))
                mapping = {str(k).upper(): str(v) for k, v in (raw.get("tickers") or {}).items()}
            except Exception:
                mapping = {}

    _CIK_MEM = mapping
    _CIK_LOADED_AT = now
    return mapping


def resolve_cik(ticker: str) -> Optional[str]:
    """Return zero-padded CIK string for a ticker, or None if not in SEC map."""
    sym = str(ticker or "").upper().strip()
    if not sym:
        return None
    return _load_cik_map().get(sym)


def company_atom_url(cik: str, form_type: str = "8-K", count: int = 10) -> str:
    """Build SEC browse-edgar Atom URL for a CIK and form type."""
    return (
        "https://www.sec.gov/cgi-bin/browse-edgar"
        f"?action=getcompany&CIK={cik}&type={form_type}"
        f"&dateb=&owner=include&count={int(count)}&output=atom"
    )


def fetch_recent_filings(
    ticker: str,
    *,
    forms: Optional[List[str]] = None,
    max_article_age_hours: int = 4,
    count: int = 10,
) -> List[Dict[str, Any]]:
    """
    Fetch recent SEC filings for ``ticker`` across ``forms``.

    Returns normalized article dicts within ``max_article_age_hours``.
    """
    cik = resolve_cik(ticker)
    if not cik:
        return []

    form_list = forms or ["8-K"]
    articles: List[Dict[str, Any]] = []
    for form_type in form_list:
        url = company_atom_url(cik, form_type=str(form_type), count=count)
        try:
            data = _http_get(url)
            parsed = feedparser.parse(data)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            print(f"[edgar_client] Atom fetch failed for {ticker}/{form_type}: {error}")
            continue
        except Exception as error:
            print(f"[edgar_client] Atom parse failed for {ticker}/{form_type}: {error}")
            continue

        for entry in parsed.entries:
            title = str(entry.get("title", "")).strip()
            link = str(entry.get("link", "")).strip()
            published_at = _parse_entry_datetime(entry)
            if not title or not link:
                continue
            if not _is_recent(published_at, max_age_hours=max_article_age_hours):
                continue
            articles.append(
                {
                    "source": "SEC EDGAR",
                    "headline": title,
                    "url": link,
                    "published_utc": published_at.isoformat()
                    if published_at
                    else datetime.now(timezone.utc).isoformat(),
                    "form_type": str(form_type),
                }
            )
    return articles
