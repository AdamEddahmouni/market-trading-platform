"""
Supplemental Web Scraper - Multi-source data collection using stealth scraping.
Uses browser impersonation to scrape data from:
  - Yahoo Finance (profile, key statistics)
  - NASDAQ.com (company profile)
  - SEC EDGAR (company filings)
  - MarketBeat (analyst ratings)

Resume-from-crash with graceful shutdown support.
"""

import json
import time
import re
from datetime import date
from typing import Optional, Dict, Any, List

from src.config import (
    REQUEST_TIMEOUT, SEC_EDGAR_BASE, SEC_USER_AGENT, SEC_RATE_LIMIT,
)
from src.database import (
    bulk_insert,
)
from src.scrapers.base import BaseScraper
from src.scrapers.http_client import StealthSession


# ── Pure Helper Functions (stateless) ──────────────────────────

def scrape_yahoo_finance_profile(ticker: str, session: StealthSession = None) -> Optional[Dict[str, Any]]:
    """Scrape Yahoo Finance profile page for company info."""
    if session is None:
        session = StealthSession()
    url = f"https://finance.yahoo.com/quote/{ticker}/profile/"

    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        if resp is None:
            return None
        text_content = resp.text
        data = {}

        patterns = [
            r'root\.App\.main\s*=\s*({.*?});\s*\n',
            r'<script[^>]*>\s*window\.__INITIAL_STATE__\s*=\s*({.*?});\s*</script>',
            r'"QuoteSummaryStore"\s*:\s*({.*?}),\s*"QuoteTimeMostRecentStore"',
        ]
        for pattern in patterns:
            match = re.search(pattern, text_content, re.DOTALL)
            if match:
                try:
                    json_data = json.loads(match.group(1))
                    data["raw_json"] = json_data
                    break
                except json.JSONDecodeError:
                    continue

        desc_match = re.search(
            r'<p[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</p>',
            text_content, re.DOTALL | re.IGNORECASE
        )
        if desc_match:
            data["description"] = desc_match.group(1).strip()

        profile_data = {}
        rows = re.findall(
            r'<tr[^>]*>.*?<td[^>]*class="[^"]*label[^"]*"[^>]*>(.*?)</td>'
            r'.*?<td[^>]*class="[^"]*value[^"]*"[^>]*>(.*?)</td>.*?</tr>',
            text_content, re.DOTALL
        )
        for label, value in rows:
            clean_label = re.sub(r'<[^>]+>', '', label).strip()
            clean_value = re.sub(r'<[^>]+>', '', value).strip()
            profile_data[clean_label] = clean_value
        data["profile"] = profile_data

        return data
    except Exception:
        return None


def scrape_yahoo_finance_key_stats(ticker: str, session: StealthSession = None) -> Optional[Dict[str, Any]]:
    """Scrape Yahoo Finance key statistics page."""
    if session is None:
        session = StealthSession()
    url = f"https://finance.yahoo.com/quote/{ticker}/key-statistics/"

    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        if resp is None:
            return None
        text_content = resp.text
        data = {}

        stats = {}
        rows = re.findall(
            r'<tr[^>]*>.*?<td[^>]*class="[^"]*label[^"]*"[^>]*>(.*?)</td>'
            r'.*?<td[^>]*class="[^"]*value[^"]*"[^>]*>(.*?)</td>.*?</tr>',
            text_content, re.DOTALL
        )
        for label, value in rows:
            clean_label = re.sub(r'<[^>]+>', '', label).strip()
            clean_value = re.sub(r'<[^>]+>', '', value).strip()
            stats[clean_label] = clean_value
        data["key_stats"] = stats

        return data
    except Exception:
        return None


def scrape_nasdaq_official_profile(ticker: str, session: StealthSession = None) -> Optional[Dict[str, Any]]:
    """Scrape official NASDAQ.com company profile."""
    if session is None:
        session = StealthSession()
    url = f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}/company-profile"

    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        if resp is None:
            return None
        soup_text = resp.text
        data = {}

        desc_match = re.search(
            r'<p[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</p>',
            soup_text, re.DOTALL | re.IGNORECASE
        )
        if desc_match:
            data["description"] = desc_match.group(1).strip()

        metrics = {}
        metric_patterns = [
            (r'Previous Close</span>.*?<span[^>]*data-testid="[^"]*"[^>]*>([^<]+)</span>', "previous_close"),
            (r'Day High</span>.*?<span[^>]*data-testid="[^"]*"[^>]*>([^<]+)</span>', "day_high"),
            (r'Day Low</span>.*?<span[^>]*data-testid="[^"]*"[^>]*>([^<]+)</span>', "day_low"),
            (r'Volume</span>.*?<span[^>]*data-testid="[^"]*"[^>]*>([^<]+)</span>', "volume"),
        ]
        for pattern, key in metric_patterns:
            match = re.search(pattern, soup_text, re.DOTALL)
            if match:
                metrics[key] = match.group(1).strip()
        data["metrics"] = metrics

        return data
    except Exception:
        return None


def scrape_sec_filings(ticker: str, company_name: str = "") -> Optional[Dict[str, Any]]:
    """Scrape SEC EDGAR for company filings information."""
    import requests
    headers = {
        "User-Agent": SEC_USER_AGENT,
        "Accept": "application/xml, text/xml, */*",
        "Host": "www.sec.gov",
    }
    data = {"filings": [], "cik": None, "company_name": company_name}
    url = f"{SEC_EDGAR_BASE}?CIK={ticker}&owner=exclude&action=getcompany&output=atom"

    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)
        for ns in ['', '{http://www.w3.org/2005/Atom}']:
            cik_elem = root.find(f".//{ns}company-info//{ns}cik")
            if cik_elem is not None:
                data["cik"] = cik_elem.text
            for entry in root.findall(f".//{ns}entry"):
                filing = {}
                title = entry.find(f"{ns}title")
                if title is not None:
                    filing["title"] = title.text
                link = entry.find(f"{ns}link")
                if link is not None:
                    filing["url"] = link.get("href")
                date_elem = entry.find(f"{ns}updated")
                if date_elem is not None:
                    filing["date"] = date_elem.text[:10]
                data["filings"].append(filing)
        time.sleep(SEC_RATE_LIMIT)
    except Exception as e:
        print(f"      SEC EDGAR scrape error: {e}")

    return data


def scrape_marketbeat(ticker: str, session: StealthSession = None) -> Optional[Dict[str, Any]]:
    """Scrape MarketBeat for analyst ratings and price targets."""
    if session is None:
        session = StealthSession()
    url = f"https://www.marketbeat.com/stocks/NASDAQ/{ticker}/"

    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        if resp is None:
            return None
        data = {}

        pt_match = re.search(
            r'price-target[^>]*>.*?(\d+[\.,]?\d*)',
            resp.text, re.DOTALL | re.IGNORECASE
        )
        if pt_match:
            data["price_target"] = pt_match.group(1)

        rating_match = re.search(
            r'rating[^>]*>.*?(Strong Buy|Buy|Hold|Sell|Strong Sell)',
            resp.text, re.DOTALL | re.IGNORECASE
        )
        if rating_match:
            data["analyst_rating"] = rating_match.group(1)

        return data
    except Exception:
        return None


def store_supplemental_data(ticker_id: int, data_type: str, source: str,
                            data: Dict[str, Any], url: str = ""):
    """Store supplemental scraped data in the database."""
    if not data:
        return
    record = {
        "ticker_id": ticker_id,
        "data_type": data_type,
        "source": source,
        "data_date": date.today(),
        "data_content": json.dumps(data, default=str),
        "url": url,
    }
    bulk_insert("supplemental_data", [record])


def scrape_ticker_supplemental(ticker: str, ticker_id: int) -> bool:
    """Scrape all supplemental sources for a single ticker. Returns True on success."""
    try:
        session = StealthSession()

        yf_profile = scrape_yahoo_finance_profile(ticker, session)
        if yf_profile:
            store_supplemental_data(
                ticker_id, "company_profile", "yahoo_finance",
                yf_profile,
                f"https://finance.yahoo.com/quote/{ticker}/profile/"
            )

        ndq_profile = scrape_nasdaq_official_profile(ticker, session)
        if ndq_profile:
            store_supplemental_data(
                ticker_id, "company_profile", "nasdaq_com",
                ndq_profile,
                f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}"
            )

        sec_data = scrape_sec_filings(ticker)
        if sec_data and sec_data.get("filings"):
            store_supplemental_data(
                ticker_id, "sec_filings", "sec_edgar",
                sec_data,
                f"{SEC_EDGAR_BASE}?CIK={ticker}&owner=exclude&action=getcompany"
            )

        mb_data = scrape_marketbeat(ticker, session)
        if mb_data:
            store_supplemental_data(
                ticker_id, "analyst_ratings", "marketbeat",
                mb_data,
                f"https://www.marketbeat.com/stocks/NASDAQ/{ticker}/"
            )

        session.close()
        return True
    except Exception:
        return False


# ── BaseScraper Subclass ───────────────────────────────────────

class SupplementalScraper(BaseScraper):
    """Supplemental multi-source scraper using BaseScraper infrastructure."""

    def __init__(self):
        super().__init__(stage="supplemental", name="SUPP")

    def _process_single(self, item: dict) -> bool:
        """Process a single ticker's supplemental data."""
        return scrape_ticker_supplemental(item["ticker"], item["id"])


# ── Convenience Entry Point ────────────────────────────────────

def run_supplemental_scraper(max_tickers: int = None, retry_errored: bool = False,
                           ticker_filter=None):
    """Run supplemental scraper (convenience wrapper)."""
    scraper = SupplementalScraper()
    if ticker_filter is not None:
        scraper._ticker_filter = ticker_filter
    try:
        scraper.run(retry_errored=retry_errored, max_items=max_tickers)
    finally:
        scraper.cleanup()

if __name__ == "__main__":
    from src.database import init_database
    init_database()
    run_supplemental_scraper(max_tickers=10)
