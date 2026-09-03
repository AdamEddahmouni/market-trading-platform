"""
Earnings Calendar Scraper - Collects earnings report data for all active tickers.
Uses yfinance for free earnings calendar data (Ticker.earnings_dates, Ticker.quarterly_earnings).
Falls back to Yahoo Finance web scraping for tickers yfinance can't handle.

Resume-from-crash with graceful shutdown support via BaseScraper.
"""

import re
import time
from datetime import datetime, date
from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np

import yfinance as yf

from src.config import MAX_RETRIES, REQUEST_TIMEOUT
from src.database import fast_bulk_insert
from src.scrapers.base import BaseScraper
from src.scrapers.http_client import StealthSession


# ── Helper Functions ───────────────────────────────────────────

def fetch_earnings_yfinance(ticker: str) -> Optional[List[Dict]]:
    """Fetch earnings calendar data via yfinance."""
    records = []
    for attempt in range(MAX_RETRIES):
        try:
            obj = yf.Ticker(ticker)
            info = obj.info

            # Get quarterly earnings history
            earnings = obj.quarterly_earnings
            if earnings is not None and not earnings.empty:
                for idx, row in earnings.iterrows():
                    try:
                        # idx can be a date or string like "Q1 2024"
                        earnings_date = None
                        fiscal_quarter = None

                        if hasattr(idx, 'strftime'):
                            earnings_date = idx.date() if hasattr(idx, 'date') else idx
                            fiscal_quarter = earnings_date.strftime("%Y-Q%m") if earnings_date else None

                        # Handle string indices like "2024-03-31"
                        if isinstance(idx, str):
                            try:
                                dt = datetime.strptime(idx[:10], "%Y-%m-%d")
                                earnings_date = dt.date()
                                fiscal_quarter = f"Q{(dt.month - 1) // 3 + 1} {dt.year}"
                            except ValueError:
                                earnings_date = None

                        record = {
                            "earnings_date": earnings_date,
                            "fiscal_quarter": fiscal_quarter,
                        }

                        # EPS estimate and actual
                        eps_est = row.get("Estimate") if hasattr(row, 'get') else None
                        eps_act = row.get("Earnings") if hasattr(row, 'get') else None

                        if eps_est is not None and not (isinstance(eps_est, float) and np.isnan(eps_est)):
                            record["eps_estimate"] = float(eps_est)
                        if eps_act is not None and not (isinstance(eps_act, float) and np.isnan(eps_act)):
                            record["eps_actual"] = float(eps_act)

                        if record.get("eps_estimate") and record.get("eps_actual"):
                            record["eps_surprise"] = record["eps_actual"] - record["eps_estimate"]

                        records.append(record)
                    except Exception:
                        continue

            # Also try earnings_dates for upcoming/estimated earnings
            try:
                earnings_dates = obj.earnings_dates
                if earnings_dates is not None and not earnings_dates.empty:
                    for idx, row in earnings_dates.iterrows():
                        try:
                            earnings_date = idx.date() if hasattr(idx, 'date') else idx
                            record = {"earnings_date": earnings_date}

                            # EPS estimate and actual
                            for col, key in [
                                ("EPS Estimate", "eps_estimate"),
                                ("Reported EPS", "eps_actual"),
                                ("Revenue Estimate", "revenue_estimate"),
                                ("Reported Revenue", "revenue_actual"),
                            ]:
                                val = row.get(col) if hasattr(row, 'get') else None
                                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                                    record[key] = float(val)

                            if record.get("eps_estimate") and record.get("eps_actual"):
                                record["eps_surprise"] = record["eps_actual"] - record["eps_estimate"]
                            if record.get("revenue_estimate") and record.get("revenue_actual"):
                                record["revenue_surprise"] = record["revenue_actual"] - record["revenue_estimate"]

                            # Avoid duplicates with quarterly_earnings
                            existing_dates = {r["earnings_date"] for r in records if r.get("earnings_date")}
                            if record["earnings_date"] not in existing_dates:
                                records.append(record)
                        except Exception:
                            continue
            except Exception:
                pass

            if records:
                return records
            return None

        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.5)
            else:
                return None


def scrape_earnings_alternative(ticker: str, session: StealthSession) -> Optional[List[Dict]]:
    """Fallback: scrape earnings data from Yahoo Finance web."""
    records = []
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}/history/"
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        if resp is None:
            return None

        # Try to extract earnings data from embedded JSON
        patterns = [
            r'root\.App\.main\s*=\s*({.*?});\s*\n',
            r'"QuoteSummaryStore"\s*:\s*({.*?}),\s*"QuoteTimeMostRecentStore"',
        ]
        for pattern in patterns:
            match = re.search(pattern, resp.text, re.DOTALL)
            if match:
                try:
                    import json
                    data = json.loads(match.group(1))

                    # Navigate to earnings data
                    earnings = (data.get("QuoteSummaryStore", {})
                                .get("earningsData", {}))
                    if earnings:
                        fin_data = earnings.get("financialsChart", {}).get("quarterly", [])
                        for q_data in fin_data:
                            record = {"fiscal_quarter": q_data.get("date", "")}
                            if q_data.get("estimate"):
                                record["eps_estimate"] = q_data["estimate"].get("raw")
                            if q_data.get("actual"):
                                record["eps_actual"] = q_data["actual"].get("raw")
                            if record.get("eps_estimate") and record.get("eps_actual"):
                                record["eps_surprise"] = record["eps_actual"] - record["eps_estimate"]
                            records.append(record)
                        if records:
                            return records
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

        return None
    except Exception:
        return None


def process_ticker_earnings(ticker: str, ticker_id: int) -> bool:
    """Fetch and store earnings data for one ticker."""
    records = fetch_earnings_yfinance(ticker)

    # Fallback to web scraping
    if not records:
        session = StealthSession()
        try:
            records = scrape_earnings_alternative(ticker, session)
        finally:
            session.close()

    if not records:
        return False

    # Store records
    df = pd.DataFrame(records)
    if not df.empty:
        df["ticker_id"] = ticker_id
        # Convert date columns
        if "earnings_date" in df.columns:
            df["earnings_date"] = pd.to_datetime(df["earnings_date"], errors='coerce')
        fast_bulk_insert("earnings_calendar", df)

    return True


# ── BaseScraper Subclass ───────────────────────────────────────

class EarningsCalendarScraper(BaseScraper):
    """Earnings calendar scraper using BaseScraper infrastructure."""

    def __init__(self):
        super().__init__(stage="earnings", name="EARNINGS")

    def _process_single(self, item: dict) -> bool:
        """Process a single ticker's earnings data."""
        return process_ticker_earnings(item["ticker"], item["id"])


# ── Convenience Entry Point ────────────────────────────────────

def run_earnings_scraper(retry_errored: bool = False, max_tickers: int = None,
                        ticker_filter=None):
    """Run earnings calendar scraper (convenience wrapper)."""
    scraper = EarningsCalendarScraper()
    try:
        scraper.run(retry_errored=retry_errored, max_items=max_tickers)
    finally:
        scraper.cleanup()


if __name__ == "__main__":
    from src.database import init_database
    init_database()
    run_earnings_scraper(max_tickers=5)
