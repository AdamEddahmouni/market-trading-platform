"""
Insider Trading Tracker - Scrapes SEC EDGAR Form 4 filings for insider transactions.
Sources:
  - Primary: SEC EDGAR XML bulk data feed (free)
  - Fallback: Direct SEC EDGAR Form 4 page scraping

Resume-from-crash with graceful shutdown support via BaseScraper.
"""

import json
import re
import time
from datetime import datetime, date
from typing import Optional, Dict, Any, List
import pandas as pd

from src.config import MAX_RETRIES, REQUEST_TIMEOUT, SEC_USER_AGENT, SEC_RATE_LIMIT
from src.database import get_connection, fast_bulk_insert, get_ticker_id, get_all_ticker_ids
from src.scrapers.base import BaseScraper
from src.scrapers.http_client import StealthSession
from sqlalchemy.sql import text


# ── Helper Functions ───────────────────────────────────────────

def fetch_sec_cik(ticker: str, session: StealthSession) -> Optional[str]:
    """Look up a ticker's SEC CIK number via EDGAR."""
    try:
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={ticker}&action=getcompany"
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        if resp is None:
            return None

        # Extract CIK from the page
        match = re.search(r'CIK=(\d{10})', resp.text)
        if match:
            return match.group(1)
        return None
    except Exception:
        return None


def fetch_form4_filings(cik: str, ticker: str, session: StealthSession, throttler=None) -> Optional[List[Dict]]:
    """Fetch recent Form 4 filings for a CIK number via SEC EDGAR."""
    records = []
    try:
        # Apply thread-safe throttling before SEC request
        if throttler:
            throttler.wait("sec.gov", min_delay=SEC_RATE_LIMIT, max_delay=SEC_RATE_LIMIT + 2)

        url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar?"
            f"action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=40"
            f"&output=atom"
        )
        resp = session.get(url, timeout=REQUEST_TIMEOUT, content_type="xml")
        if resp is None:
            return None

        # Parse the Atom feed
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)

        ns = '{http://www.w3.org/2005/Atom}'
        entries = root.findall(f'.//{ns}entry')

        for entry in entries:
            try:
                title_el = entry.find(f'{ns}title')
                link_el = entry.find(f'{ns}link')
                date_el = entry.find(f'{ns}updated')

                title = title_el.text if title_el is not None else ""
                filing_url = link_el.get('href') if link_el is not None else ""
                filing_date_str = date_el.text[:10] if date_el is not None else ""

                # Parse filing date
                filing_date = None
                try:
                    filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    continue

                # Extract insider name from title (format: "FORM 4 - Insider Name")
                insider_name = title.replace("FORM 4 - ", "").replace("Form 4 - ", "").strip()
                if not insider_name or insider_name == title:
                    insider_name = title.strip()

                records.append({
                    "filing_date": filing_date,
                    "insider_name": insider_name[:200] if insider_name else "",
                    "sec_form_type": "Form 4",
                    "filing_url": filing_url,
                })
            except Exception:
                continue

        if records:
            return records
        return None

    except Exception:
        return None


def parse_form4_details(filing_url: str, session: StealthSession) -> Optional[Dict]:
    """Parse a specific Form 4 filing page for transaction details."""
    try:
        resp = session.get(filing_url, timeout=REQUEST_TIMEOUT)
        if resp is None:
            return None

        text_content = resp.text
        result = {}

        # Extract relationship (CEO, CFO, Director, etc.)
        rel_patterns = [
            r'<strong>Reporting Owner[^<]*</strong>\s*</td>\s*<td[^>]*>(.*?)</td>',
            r'issuerTradingSymbol[^>]*>([^<]+)',
            r'<span[^>]*class="[^"]*"[^>]*>Relationship</span>[^<]*<[^>]*>(.*?)</',
        ]
        for pattern in rel_patterns:
            match = re.search(pattern, text_content, re.DOTALL | re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                if val:
                    result["relationship"] = val[:200]
                    break

        # Extract transaction details from XML embedded data
        # SEC Form 4 filings contain XML with transaction data
        xml_match = re.search(
            r'<ownershipDocument>.*?</ownershipDocument>',
            text_content, re.DOTALL
        )
        if xml_match:
            xml_content = xml_match.group(0)

            # Transaction date
            td_match = re.search(r'<transactionDate>.*?<value>(.*?)</value>', xml_content, re.DOTALL)
            if td_match:
                try:
                    result["transaction_date"] = datetime.strptime(
                        td_match.group(1).strip(), "%Y-%m-%d"
                    ).date()
                except ValueError:
                    pass

            # Transaction type (Buy/Sell)
            tt_match = re.search(r'<transactionCode>(.*?)</transactionCode>', xml_content, re.DOTALL)
            if tt_match:
                code = tt_match.group(1).strip()
                code_map = {
                    "P": "Buy", "S": "Sell", "A": "Grant",
                    "D": "Sell (Derivative)", "F": "Tax Withholding",
                    "I": "Discretionary", "M": "Exercise",
                    "X": "Exercise (Derivative)", "C": "Conversion",
                    "W": "Warrant Exercise",
                }
                result["transaction_type"] = code_map.get(code, f"Code {code}")

            # Shares traded
            st_match = re.search(
                r'<transactionShares>.*?<value>(.*?)</value>',
                xml_content, re.DOTALL
            )
            if st_match:
                try:
                    val = st_match.group(1).strip().replace(",", "")
                    result["shares_traded"] = float(val)
                except ValueError:
                    pass

            # Price per share
            pp_match = re.search(
                r'<transactionPricePerShare>.*?<value>(.*?)</value>',
                xml_content, re.DOTALL
            )
            if pp_match:
                try:
                    result["price_per_share"] = float(pp_match.group(1).strip())
                except ValueError:
                    pass

            # Shares owned after transaction
            so_match = re.search(
                r'<sharesOwnedFollowingTransaction>.*?<value>(.*?)</value>',
                xml_content, re.DOTALL
            )
            if so_match:
                try:
                    val = so_match.group(1).strip().replace(",", "")
                    result["shares_owned"] = float(val)
                except ValueError:
                    pass

        return result if result else None

    except Exception:
        return None


def process_ticker_insider_trades(ticker: str, ticker_id: int, throttler=None) -> bool:
    """Fetch and store insider trading data for one ticker."""
    session = StealthSession()
    try:
        # Step 1: Look up CIK
        cik = fetch_sec_cik(ticker, session)
        if not cik:
            return False

        # Step 2: Fetch recent Form 4 filings (with thread-safe SEC rate limiting)
        filings = fetch_form4_filings(cik, ticker, session, throttler=throttler)
        if not filings:
            return False

        # Step 3: Parse details for each filing
        records = []
        for filing in filings:
            if filing.get("filing_url"):
                details = parse_form4_details(filing["filing_url"], session)
                if details:
                    record = {**filing, **details}
                else:
                    record = filing
                # Remove URL field (not stored in DB)
                record.pop("filing_url", None)
                record["ticker_id"] = ticker_id
                records.append(record)

        if not records:
            return False

        # Store in database
        df = pd.DataFrame(records)
        date_cols = ["filing_date", "transaction_date"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        fast_bulk_insert("insider_trades", df)

        return True
    finally:
        session.close()


# ── BaseScraper Subclass ───────────────────────────────────────

class InsiderTradingScraper(BaseScraper):
    """Insider trading tracker using BaseScraper infrastructure."""

    def __init__(self):
        super().__init__(stage="insiders", name="INSIDERS")

    def _process_single(self, item: dict) -> bool:
        """Process a single ticker's insider trading data."""
        return process_ticker_insider_trades(
            item["ticker"], item["id"], throttler=self.throttler
        )


# ── Convenience Entry Point ────────────────────────────────────

def run_insider_scraper(retry_errored: bool = False, max_tickers: int = None,
                       ticker_filter=None):
    """Run insider trading scraper (convenience wrapper)."""
    scraper = InsiderTradingScraper()
    try:
        scraper.run(retry_errored=retry_errored, max_items=max_tickers)
    finally:
        scraper.cleanup()


if __name__ == "__main__":
    from src.database import init_database
    init_database()
    run_insider_scraper(max_tickers=5)
