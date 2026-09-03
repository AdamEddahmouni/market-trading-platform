"""Web scraping helpers for unstructured financial news pages.

Purpose
-------
Fetch and extract readable text from finance news URLs using cloudscraper +
BeautifulSoup fallback selectors. Supplements RSS when wires lack full body text.

Pipeline role
-------------
``scrape_article_text`` enriches matched RSS URLs in ``news_aggregator``.
Ticker-page scrapers (Yahoo/Benzinga/MarketWatch) add context when RSS is empty.

Key outputs
-----------
Truncated plain-text strings (default 3000 chars) suitable for LLM prompts.

Handoff notes
-------------
**Reusable (equity/futures):** ``fetch_html`` + ``clean_html_to_text`` generalize
to any news site; add futures-specific URL builders alongside equity helpers.

**Options-only coupling:** None.

**Operational:** Respects bot protection via cloudscraper; failures return
empty string (non-fatal upstream).
"""

from __future__ import annotations

from typing import List

import cloudscraper
from bs4 import BeautifulSoup


def fetch_html(url: str) -> str:
    """
    Download raw HTML content from a URL using cloudscraper.

    Inputs:
    - url: webpage URL string.

    Output:
    - Raw HTML text. Returns an empty string if request fails.

    Why this exists:
    - Many finance sites use bot protections; cloudscraper increases
      the chance we receive page content instead of a block page.
    """
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, timeout=25)
        if response.status_code != 200:
            print(f"[web_scraper] Request failed {response.status_code} for {url}")
            return ""
        return response.text
    except Exception as error:
        print(f"[web_scraper] Could not fetch URL {url}: {error}")
        return ""


def clean_html_to_text(html: str, max_chars: int = 3000) -> str:
    """
    Extract article-like readable text from raw HTML with fallback selectors.

    Inputs:
    - html: full raw HTML string.
    - max_chars: maximum characters allowed in output.

    Output:
    - Cleaned text suitable for LLM analysis.

    Why this exists:
    - Page structures differ. A fallback selector chain helps us grab
      meaningful text even when a site uses different HTML layouts.
    """
    if not html.strip():
        return ""

    soup = BeautifulSoup(html, "lxml")

    # Remove noisy layout and ad containers before text extraction.
    for noisy_tag in soup.select("script, style, nav, header, footer, aside, form, noscript"):
        noisy_tag.decompose()

    selectors = ["article", ".article-body", ".story-body", "main", ".content", "p"]
    chunks: List[str] = []

    for selector in selectors:
        selected_elements = soup.select(selector)
        if not selected_elements:
            continue

        for element in selected_elements:
            if selector == "p":
                text = element.get_text(" ", strip=True)
                if text:
                    chunks.append(text)
                continue

            # Prefer paragraph text from structural containers.
            paragraph_nodes = element.select("p")
            if paragraph_nodes:
                for paragraph in paragraph_nodes:
                    text = paragraph.get_text(" ", strip=True)
                    if text:
                        chunks.append(text)
            else:
                text = element.get_text(" ", strip=True)
                if text:
                    chunks.append(text)

        if chunks:
            break

    joined_text = "\n".join(dict.fromkeys(chunks))  # Preserve order while removing duplicates.
    return joined_text[:max_chars]


def scrape_article_text(url: str, max_chars: int = 3000) -> str:
    """
    Fetch a webpage and return cleaned article-like text.

    Inputs:
    - url: webpage URL.
    - max_chars: character cap for output.

    Output:
    - Cleaned article text, or empty string if scraping fails.

    Why this exists:
    - This wrapper composes the fetch+clean flow into one safe call
      used by higher-level modules.
    """
    html = fetch_html(url)
    if not html:
        return ""
    return clean_html_to_text(html=html, max_chars=max_chars)


def scrape_yahoo_finance_news(ticker: str, max_chars: int = 3000) -> str:
    """
    Scrape Yahoo Finance news-page text for a ticker.

    Inputs:
    - ticker: stock symbol like 'AAPL'.
    - max_chars: output text cap.

    Output:
    - Cleaned text from Yahoo ticker news page.

    Why this exists:
    - Yahoo often contains quick context and related headlines useful
      as supplemental evidence for LLM scoring.
    """
    url = f"https://finance.yahoo.com/quote/{ticker.upper()}/news"
    return scrape_article_text(url=url, max_chars=max_chars)


def scrape_benzinga_news(ticker: str, max_chars: int = 3000) -> str:
    """
    Scrape Benzinga news-page text for a ticker.

    Inputs:
    - ticker: stock symbol like 'AAPL'.
    - max_chars: output text cap.

    Output:
    - Cleaned text from Benzinga ticker page.

    Why this exists:
    - Benzinga can provide immediate reaction context that may help
      downstream sentiment interpretation.
    """
    url = f"https://www.benzinga.com/quote/{ticker.upper()}/news"
    return scrape_article_text(url=url, max_chars=max_chars)


def scrape_marketwatch_news(ticker: str, max_chars: int = 3000) -> str:
    """
    Scrape MarketWatch stock news page text for a ticker.

    Inputs:
    - ticker: stock symbol like 'AAPL'.
    - max_chars: output text cap.

    Output:
    - Cleaned text from MarketWatch ticker page.

    Why this exists:
    - MarketWatch offers another unstructured context source that can
      add useful details around a catalyst event.
    """
    url = f"https://www.marketwatch.com/investing/stock/{ticker.upper()}/news"
    return scrape_article_text(url=url, max_chars=max_chars)


def main() -> None:
    """
    Run a simple Yahoo scrape demo for ticker AAPL.

    Inputs:
    - None.

    Output:
    - None. Prints preview text in terminal.

    Why this exists:
    - Quick direct-run testing validates scraper behavior before this
      module is combined with RSS and AI scoring layers.
    """
    text = scrape_yahoo_finance_news("AAPL")
    print(f"Extracted characters: {len(text)}")
    print("-" * 80)
    print(text[:1000] if text else "No text extracted.")


if __name__ == "__main__":
    main()
