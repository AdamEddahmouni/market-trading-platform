"""Path A.2 — scan wire RSS feeds for fresh headlines on optionable tickers.

Purpose
-------
Broadcast wire scan (no per-ticker EDGAR) that maps headlines → tickers in a
merged universe (seeds, watchlists, configured extras). Optional Finviz mover
lane adds price-action names without headlines.

Pipeline role
-------------
``refresh_catalyst_watchlist`` persists ``state/news_catalyst_watchlist.json``.
``main.run_news_catalyst_cycle`` enriches rows and runs the standard news pipeline
with ``require_social_signal`` relaxed for ``source=news_catalyst``.

Key outputs
-----------
Watchlist rows: ``{ticker, headline, news_source, url, published_at, source,
social_signal_level=IGNORE, ...}``.

Handoff notes
-------------
**Reusable (equity/futures):** Headline→ticker extraction, seen-URL dedupe, wire
feed iteration — works for any symbol universe.

**Options-only coupling:** Universe built from optionable seeds/watchlists;
``enrich_with_finviz_movers`` uses ``sh_opt_option`` filter — drop for pure
equity/futures momentum.

**Safe to run live:** Writes state and seen articles; does not execute trades
(decisions happen in ``main`` with ``path_a2_auto_execute`` gate).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import feedparser

from news.rss_monitor import (
    get_rss_sources,
    headline_matches_ticker,
    is_recent,
    load_seen_articles,
    parse_entry_datetime,
    save_seen_articles,
)
from news.solicitation_filter import is_law_firm_solicitation


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
CATALYST_STATE_PATH = STATE_DIR / "news_catalyst_watchlist.json"

_TICKER_IN_HEADLINE = re.compile(r"\$([A-Z]{1,5})\b")


def _load_ticker_set(settings: Optional[Dict[str, Any]] = None) -> Set[str]:
    """Merge seeds, configured extras, and recent watchlists into match universe."""
    cfg = (settings or {}).get("news_catalyst") or {}
    tickers: Set[str] = set()

    for section in ("expiry_screener",):
        seeds = ((settings or {}).get(section) or {}).get("seed_tickers") or []
        tickers.update(str(t).upper().strip() for t in seeds if t)

    for t in cfg.get("extra_tickers") or []:
        tickers.add(str(t).upper().strip())

    for rel in ("watchlist.json", "odte_watchlist.json", "expiry_watchlist.json"):
        path = STATE_DIR / rel
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = payload.get("ranked") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            rows = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("ticker"):
                tickers.add(str(row["ticker"]).upper().strip())

    return {t for t in tickers if t and len(t) <= 5}


def _headline_tickers(headline: str, universe: Set[str]) -> List[str]:
    """Return tickers mentioned in a headline (universe-filtered)."""
    text = str(headline or "").upper()
    found: Set[str] = set()
    for match in _TICKER_IN_HEADLINE.finditer(text):
        sym = match.group(1).upper()
        if sym in universe:
            found.add(sym)
    for sym in universe:
        if re.search(rf"\b{re.escape(sym)}\b", text):
            found.add(sym)
    return sorted(found)


def scan_catalyst_headlines(
    settings: Optional[Dict[str, Any]] = None,
    *,
    universe: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Scan PR/Globe/BusinessWire feeds for fresh headlines mentioning optionable tickers.

    Returns deduped rows: ticker, headline, source, url, published_at.
    """
    cfg = (settings or {}).get("news_catalyst") or {}
    max_age = max(1, int(cfg.get("max_article_age_hours", 4)))
    max_per_cycle = max(1, int(cfg.get("max_candidates_per_cycle", 12)))
    uni = universe or _load_ticker_set(settings)
    if not uni:
        return []

    seen = load_seen_articles()
    hits: List[Dict[str, Any]] = []
    seen_pairs: Set[tuple[str, str]] = set()

    # Broadcast wire feeds only — skip per-ticker EDGAR (too slow for broad scan).
    feeds = get_rss_sources("SPY", settings=settings, include_edgar=False)

    for feed in feeds:
        try:
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries:
                title = str(entry.get("title", "")).strip()
                link = str(entry.get("link", "")).strip()
                if not title or not link or link in seen:
                    continue
                news_cfg = (settings or {}).get("news") or {}
                if bool(news_cfg.get("exclude_law_firm_solicitations", True)) and is_law_firm_solicitation(
                    title, url=link
                ):
                    print(f"[catalyst_scanner] skipped solicitation: {title[:90]}")
                    seen.add(link)
                    continue
                published = parse_entry_datetime(entry)
                if not is_recent(published, max_age_hours=max_age):
                    continue
                tickers = _headline_tickers(title, uni)
                # Also catch company-name style hits already in universe via $TICKER / word boundary.
                if not tickers:
                    tickers = [
                        sym
                        for sym in uni
                        if headline_matches_ticker(title, sym, company_name="")
                    ]
                if not tickers:
                    continue
                seen.add(link)
                for ticker in tickers:
                    key = (ticker, link)
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    hits.append(
                        {
                            "ticker": ticker,
                            "company_name": ticker,
                            "headline": title,
                            "news_source": feed["name"],
                            "url": link,
                            "published_at": published.isoformat() if published else None,
                            "source": "news_catalyst",
                            "social_signal_level": "IGNORE",
                            "social_triggered_posts": [],
                            "added_at": datetime.now(timezone.utc).isoformat(),
                            "current_price": None,
                            "percent_change": None,
                            "relative_volume": None,
                        }
                    )
                    if len(hits) >= max_per_cycle:
                        break
                if len(hits) >= max_per_cycle:
                    break
        except Exception as error:
            print(f"[catalyst_scanner] feed {feed.get('name')}: {error}")
        if len(hits) >= max_per_cycle:
            break

    save_seen_articles(seen)
    return hits


def enrich_with_finviz_movers(
    candidates: List[Dict[str, Any]],
    settings: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Optionally add Finviz mover rows that have no headline yet (price-action lane)."""
    cfg = (settings or {}).get("news_catalyst") or {}
    if not bool(cfg.get("include_finviz_movers", True)):
        return candidates

    try:
        from screener.finviz_screener import (
            fetch_finviz_rows,
            parse_number_with_suffix,
            parse_percent,
        )

        pct_min = float(cfg.get("finviz_price_change_min", -15.0))
        pct_max = float(cfg.get("finviz_price_change_max", 15.0))
        vol_mult = float(cfg.get("finviz_volume_multiplier", 1.2))
        max_rows = int(cfg.get("finviz_max_rows", 80))
        screener_cfg = (settings or {}).get("screener") or {}
        filter_codes = str(
            cfg.get(
                "finviz_filter_codes",
                "ind_stocksonly,sh_opt_option,sh_price_o5,sh_avgvol_o200",
            )
        )
        rows = fetch_finviz_rows(
            max_rows=max_rows,
            screener_cfg=screener_cfg,
            filter_codes=filter_codes,
        )
    except Exception as error:
        print(f"[catalyst_scanner] Finviz mover scan failed: {error}")
        return candidates

    existing = {str(c.get("ticker", "")).upper() for c in candidates}
    max_add = max(0, int(cfg.get("max_finviz_movers", 8)))
    added = 0
    for row in rows:
        ticker = str(row.get("Ticker", row.get("ticker", ""))).upper().strip()
        if not ticker or ticker in existing:
            continue
        pct = parse_percent(row.get("Change", row.get("percent_change")))
        if pct < pct_min or pct > pct_max:
            continue
        cur_vol = parse_number_with_suffix(row.get("Volume", row.get("volume")))
        avg_vol = parse_number_with_suffix(row.get("Average Volume", row.get("average_volume")))
        if avg_vol > 0 and cur_vol < avg_vol * vol_mult:
            continue
        price = parse_number_with_suffix(row.get("Price", row.get("current_price")))
        candidates.append(
            {
                "ticker": ticker,
                "company_name": str(row.get("Company", row.get("company_name")) or ticker),
                "headline": f"Finviz mover scan ({pct:+.2f}% today)",
                "news_source": "finviz_mover",
                "url": "",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "source": "news_catalyst",
                "social_signal_level": "IGNORE",
                "social_triggered_posts": [],
                "added_at": datetime.now(timezone.utc).isoformat(),
                "current_price": round(price, 4) if price else None,
                "percent_change": round(pct, 4),
                "relative_volume": round(cur_vol / avg_vol, 2) if avg_vol > 0 else None,
            }
        )
        existing.add(ticker)
        added += 1
        if added >= max_add:
            break
    return candidates


def refresh_catalyst_watchlist(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Scan feeds + optional movers; persist watchlist for the pipeline."""
    cfg = (settings or {}).get("news_catalyst") or {}
    if not bool(cfg.get("enabled", True)):
        return {"enabled": False, "items": []}

    hits = scan_catalyst_headlines(settings)
    hits = enrich_with_finviz_movers(hits, settings)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": hits,
        "count": len(hits),
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = CATALYST_STATE_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(CATALYST_STATE_PATH)
    print(f"[catalyst_scanner] Path A.2 watchlist: {len(hits)} candidate(s)")
    return payload
