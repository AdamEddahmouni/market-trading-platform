"""Resolve the ticker universe from a Finviz Elite screener export.

Purpose
-------
Dynamic watchlist for the **standalone** engine scheduler (not the news agent's
Path A discovery pipeline).

Features / API role
-------------------
``resolve_universe`` → capped ticker list from Finviz screener CSV, saved
snapshots (``source: snapshots``), or ``fallback_tickers``.

How ``news_momentum_agent`` consumes it
---------------------------------------
Not imported by the live agent loop. Agent passes explicit tickers to
``options_client.score_ticker`` one at a time.

Options-specific vs reusable
----------------------------
Finviz screener integration is options-engine-local. ``list_rich_snapshot_tickers``
reuse is shared with replay provider for offline universe.

The engine can score a dynamic universe (e.g. most-active optionable stocks)
instead of a hand-maintained watchlist. This module fetches a configured Finviz
screener export, extracts the ``Ticker`` column, and returns a de-duplicated,
capped list. On any failure it falls back to a configured static list so the
scheduler keeps running.

Configure via ``settings.universe``::

    "universe": {
        "source": "finviz_screener",
        "screener_export_url": "https://elite.finviz.com/export.ashx?v=111&s=ta_mostactive&f=sh_opt_option",
        "max_tickers": 15,
        "fallback_tickers": ["AAPL", "TSLA", "NVDA"]
    }

You can paste any screener URL from your browser; a ``screener.ashx`` URL is
automatically rewritten to the ``export.ashx`` CSV endpoint.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

from options_engine.finviz_provider import DEFAULT_HEADERS, _resolve_token
from options_engine.replay_provider import list_rich_snapshot_tickers


DEFAULT_SCREENER_URL = "https://elite.finviz.com/export.ashx?v=111&s=ta_mostactive&f=sh_opt_option"


def _to_export_url(url: str, token: str) -> str:
    """Normalize a Finviz screener URL to the authenticated CSV export URL."""
    parsed = urlparse(url)
    path = parsed.path.replace("screener.ashx", "export.ashx")
    netloc = parsed.netloc or "elite.finviz.com"
    query = parse_qs(parsed.query)
    query["auth"] = [token]
    new_query = urlencode({k: v[-1] for k, v in query.items()})
    return urlunparse((parsed.scheme or "https", netloc, path, parsed.params, new_query, parsed.fragment))


def parse_screener_tickers(csv_text: str) -> List[str]:
    """Extract the ordered, de-duplicated ticker list from a screener CSV."""
    if not csv_text or not csv_text.strip():
        return []
    reader = csv.DictReader(io.StringIO(csv_text))
    ticker_field = None
    for name in reader.fieldnames or []:
        if name and name.strip().lower() == "ticker":
            ticker_field = name
            break
    if not ticker_field:
        return []
    seen: set[str] = set()
    tickers: List[str] = []
    for row in reader:
        raw = (row.get(ticker_field) or "").strip().upper()
        if raw and raw not in seen and raw.replace(".", "").replace("-", "").isalnum():
            seen.add(raw)
            tickers.append(raw)
    return tickers


def resolve_universe(settings: Dict[str, Any]) -> List[str]:
    """Resolve the list of tickers to score, per ``settings.universe``."""
    universe_cfg = settings.get("universe", {})
    fallback = [str(t).upper().strip() for t in universe_cfg.get("fallback_tickers", []) if str(t).strip()]
    max_tickers = int(universe_cfg.get("max_tickers", 15))
    source = str(universe_cfg.get("source", "static")).lower()

    if source == "snapshots":
        tickers = list_rich_snapshot_tickers(settings)
        if tickers:
            return tickers[:max_tickers]
        return fallback[:max_tickers]

    if source != "finviz_screener":
        return fallback[:max_tickers] if fallback else fallback

    token = _resolve_token(settings)
    if not token:
        return fallback[:max_tickers]

    url = str(universe_cfg.get("screener_export_url", DEFAULT_SCREENER_URL))
    timeout = float(settings.get("chain", {}).get("request_timeout_seconds", 10))
    try:
        response = requests.get(_to_export_url(url, token), headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        tickers = parse_screener_tickers(response.text)
    except Exception:
        tickers = []

    if not tickers:
        return fallback[:max_tickers]
    return tickers[:max_tickers]
