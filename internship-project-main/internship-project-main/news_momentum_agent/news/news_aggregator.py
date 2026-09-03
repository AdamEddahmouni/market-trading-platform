"""Aggregate structured and unstructured news context for one ticker.

Purpose
-------
Single entry point for Path A news lookup: RSS/EDGAR matches, optional HTML
page scrapes (Yahoo/Benzinga/MarketWatch), dedupe, solicitation filter, and
LLM-ready ``combined_text`` blocks.

Pipeline role
-------------
Invoked by ``main.run_news_pipeline_for_tickers`` (and ``catalyst_scanner`` via
preloaded headlines). Output feeds ``sentiment.claude_scorer.score_news_with_claude``.

Key outputs
-----------
``{has_news, combined_text, matched_articles, source_counts, errors,
dropped_solicitations}``.

Handoff notes
-------------
**Reusable (equity/futures):** RSS monitor, dedupe, solicitation filter, scraper
fallbacks, ``build_source_block`` formatting — swap ticker page URLs for futures
news sources as needed.

**Options-only coupling:** None at this layer; options context arrives later.

**Merge tip:** Keep ``dedupe_articles`` + ``filter_solicitation_articles`` when
porting — they prevent duplicate-wire and law-firm false catalysts.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    from news.rss_monitor import find_recent_ticker_articles, source_enabled
    from news.web_scraper import (
        scrape_article_text,
        scrape_benzinga_news,
        scrape_marketwatch_news,
        scrape_yahoo_finance_news,
    )
except ImportError:
    from rss_monitor import find_recent_ticker_articles, source_enabled
    from web_scraper import (
        scrape_article_text,
        scrape_benzinga_news,
        scrape_marketwatch_news,
        scrape_yahoo_finance_news,
    )


def build_source_block(source: str, headline: str, text: str) -> str:
    """Format one source into a labeled block for LLM consumption."""
    safe_headline = headline.strip() or "No headline provided"
    safe_text = text.strip() or "No additional text available."
    return f"[{source.upper()}]\nHeadline: {safe_headline}\nText: {safe_text}\n"


def extract_primary_headline(aggregated: Dict[str, Any]) -> str:
    """Return the best available headline from aggregated news context."""
    for article in aggregated.get("matched_articles") or []:
        if not isinstance(article, dict):
            continue
        for key in ("headline", "title"):
            value = str(article.get(key) or "").strip()
            if value:
                return value
    combined = str(aggregated.get("combined_text") or "")
    for line in combined.splitlines():
        if line.startswith("Headline:"):
            candidate = line.split(":", 1)[1].strip()
            lowered = candidate.lower()
            if candidate and lowered not in {"no headline provided", "no headline"}:
                return candidate
    return "No headline"


def _normalize_source_key(source: str) -> str:
    text = str(source or "").strip().lower()
    if "pr newswire" in text or text in {"prn", "prnewswire"}:
        return "PR Newswire"
    if "globe" in text:
        return "Globe Newswire"
    if "business" in text and "wire" in text:
        return "BusinessWire"
    if "newsfile" in text:
        return "Newsfile"
    if "access" in text and "wire" in text:
        return "Access Newswire"
    if "edgar" in text or text == "sec":
        return "SEC EDGAR"
    if "yahoo" in text:
        return "Yahoo"
    if "benzinga" in text:
        return "Benzinga"
    if "marketwatch" in text:
        return "MarketWatch"
    return str(source or "Other").strip() or "Other"


def _bump_source(counts: Dict[str, int], source: str) -> None:
    key = _normalize_source_key(source)
    counts[key] = int(counts.get(key) or 0) + 1


def _normalize_headline(headline: str) -> str:
    text = str(headline or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def dedupe_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse same URL or near-identical headlines across wires."""
    out: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_headlines: set[str] = set()
    for article in articles:
        if not isinstance(article, dict):
            continue
        url = str(article.get("url") or "").strip()
        headline = str(article.get("headline") or "").strip()
        norm = _normalize_headline(headline)
        if url and url in seen_urls:
            if out:
                also = list(out[-1].get("also_seen_on") or [])
                also.append(_normalize_source_key(str(article.get("source") or "")))
                out[-1]["also_seen_on"] = sorted({a for a in also if a})
            continue
        if norm and norm in seen_headlines:
            # Attach as also_seen_on on the primary match with same headline.
            for primary in out:
                if _normalize_headline(str(primary.get("headline") or "")) == norm:
                    also = list(primary.get("also_seen_on") or [])
                    also.append(_normalize_source_key(str(article.get("source") or "")))
                    primary["also_seen_on"] = sorted({a for a in also if a})
                    break
            continue
        if url:
            seen_urls.add(url)
        if norm:
            seen_headlines.add(norm)
        out.append(dict(article))
    return out


def aggregate_news_for_ticker(
    ticker: str,
    company_name: str,
    article_text_max_chars: int = 3000,
    max_article_age_hours: int = 4,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, object]:
    """
    Combine recent RSS/EDGAR matches and scraped context into one payload.

    HTML scrapers still run when RSS is empty (Path A gap fix). Applies
    solicitation filter and source-count telemetry for pipeline health.
    """
    matched_articles = find_recent_ticker_articles(
        ticker=ticker,
        company_name=company_name,
        max_article_age_hours=max_article_age_hours,
        settings=settings,
        persist_seen=False,
        include_edgar=True,
    )
    matched_articles = dedupe_articles(matched_articles)

    try:
        from news.solicitation_filter import filter_solicitation_articles
    except ImportError:
        from solicitation_filter import filter_solicitation_articles  # type: ignore

    matched_articles, dropped_solicitations = filter_solicitation_articles(
        matched_articles, settings=settings
    )
    for article in dropped_solicitations:
        print(
            f"[news_aggregator] skipped law-firm solicitation for {ticker}: "
            f"{str(article.get('headline') or '')[:90]}"
        )

    source_counts: Dict[str, int] = {}
    errors: List[Dict[str, Any]] = []
    blocks: List[str] = []

    for article in matched_articles:
        source = str(article.get("source", "Unknown Source"))
        headline = str(article.get("headline", ""))
        url = str(article.get("url", ""))
        _bump_source(source_counts, source)

        article_text = ""
        if url and not url.startswith("https://www.sec.gov/"):
            try:
                article_text = scrape_article_text(url=url, max_chars=article_text_max_chars)
            except Exception as error:
                summary = f"{type(error).__name__}: {error}"
                print(f"[news_aggregator] Could not scrape source article URL: {error}")
                errors.append({"source": source, "summary": summary})
                article_text = ""
        elif url.startswith("https://www.sec.gov/"):
            article_text = f"SEC filing index: {url}"

        also = article.get("also_seen_on") or []
        if also:
            article_text = (article_text + f"\nAlso seen on: {', '.join(also)}").strip()

        blocks.append(build_source_block(source=source, headline=headline, text=article_text))

    # Supplemental HTML context — always attempted when enabled (even if RSS empty).
    if source_enabled("yahoo", settings):
        try:
            yahoo_text = scrape_yahoo_finance_news(ticker=ticker, max_chars=article_text_max_chars)
            if yahoo_text:
                _bump_source(source_counts, "Yahoo")
                blocks.append(build_source_block("Yahoo Finance", f"{ticker} ticker news page", yahoo_text))
        except Exception as error:
            summary = f"{type(error).__name__}: {error}"
            print(f"[news_aggregator] Yahoo scrape failed: {error}")
            errors.append({"source": "Yahoo", "summary": summary})

    if source_enabled("benzinga", settings):
        try:
            benzinga_text = scrape_benzinga_news(ticker=ticker, max_chars=article_text_max_chars)
            if benzinga_text:
                _bump_source(source_counts, "Benzinga")
                blocks.append(build_source_block("Benzinga", f"{ticker} ticker news page", benzinga_text))
        except Exception as error:
            summary = f"{type(error).__name__}: {error}"
            print(f"[news_aggregator] Benzinga scrape failed: {error}")
            errors.append({"source": "Benzinga", "summary": summary})

    if source_enabled("marketwatch", settings):
        try:
            marketwatch_text = scrape_marketwatch_news(ticker=ticker, max_chars=article_text_max_chars)
            if marketwatch_text:
                _bump_source(source_counts, "MarketWatch")
                blocks.append(
                    build_source_block("MarketWatch", f"{ticker} ticker news page", marketwatch_text)
                )
        except Exception as error:
            summary = f"{type(error).__name__}: {error}"
            print(f"[news_aggregator] MarketWatch scrape failed: {error}")
            errors.append({"source": "MarketWatch", "summary": summary})

    combined = "\n".join(blocks).strip()
    return {
        "has_news": bool(combined),
        "combined_text": combined,
        "matched_articles": matched_articles,
        "source_counts": source_counts,
        "errors": errors,
        "dropped_solicitations": len(dropped_solicitations),
    }


def main() -> None:
    """CLI smoke test: aggregate sample news for AAPL and print preview."""
    result = aggregate_news_for_ticker(ticker="AAPL", company_name="Apple", max_article_age_hours=4)
    print(f"Has news: {result['has_news']}")
    print(f"Matched RSS articles: {len(result['matched_articles'])}")
    print("-" * 80)
    preview = str(result["combined_text"])[:2000]
    print(preview if preview else "No combined text generated.")


if __name__ == "__main__":
    main()
