"""
Options Chain Scraper - Collects options chain data for all active tickers.
Uses yfinance for free options data (Ticker.option_chain()).
Falls back to Market Data API (free, no key) for tickers yfinance can't handle.

Resume-from-crash with graceful shutdown support via BaseScraper.
"""

import time
from datetime import datetime, date
from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np

import yfinance as yf

from src.config import MAX_RETRIES, REQUEST_TIMEOUT
from src.database import get_connection, fast_bulk_insert
from src.scrapers.base import BaseScraper
from src.scrapers.http_client import StealthSession
from sqlalchemy.sql import text


# ── Helper Functions ───────────────────────────────────────────

def fetch_options_yfinance(ticker: str) -> Optional[List[Dict]]:
    """Fetch options chain data via yfinance. Returns list of option records."""
    records = []
    for attempt in range(MAX_RETRIES):
        try:
            obj = yf.Ticker(ticker)
            # Get all available expiration dates
            expirations = obj.options
            if not expirations:
                return None

            # Process up to 4 nearest expiration dates for manageability
            for exp_date in expirations[:4]:
                try:
                    opt_chain = obj.option_chain(exp_date)
                    exp_date_parsed = datetime.strptime(exp_date, "%Y-%m-%d").date()

                    # Process calls
                    for _, row in opt_chain.calls.iterrows():
                        records.append(_row_to_option_record(row, exp_date_parsed, "call"))

                    # Process puts
                    for _, row in opt_chain.puts.iterrows():
                        records.append(_row_to_option_record(row, exp_date_parsed, "put"))

                except Exception:
                    continue

            if records:
                return records
            return None

        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.5)
            else:
                return None


def _row_to_option_record(row, exp_date: date, opt_type: str) -> Dict:
    """Convert a yfinance options row to a database record."""
    def safe_float(val):
        try:
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                return float(val)
        except (ValueError, TypeError):
            pass
        return None

    return {
        "expiration_date": exp_date,
        "strike": safe_float(row.get("strike")),
        "option_type": opt_type,
        "last_price": safe_float(row.get("lastPrice")),
        "bid": safe_float(row.get("bid")),
        "ask": safe_float(row.get("ask")),
        "volume": int(row["volume"]) if "volume" in row.index and row["volume"] is not None and not (isinstance(row["volume"], float) and np.isnan(row["volume"])) else None,
        "open_interest": int(row["openInterest"]) if "openInterest" in row.index and row["openInterest"] is not None and not (isinstance(row["openInterest"], float) and np.isnan(row["openInterest"])) else None,
        "implied_volatility": safe_float(row.get("impliedVolatility")),
        "delta": safe_float(row.get("delta")),
        "gamma": safe_float(row.get("gamma")),
        "theta": safe_float(row.get("theta")),
        "vega": safe_float(row.get("vega")),
    }


def scrape_options_alternative(ticker: str, session: StealthSession) -> Optional[List[Dict]]:
    """Fallback: scrape options data from Market Data API (free, no key for AAPL-like tickers)."""
    try:
        url = f"https://api.marketdata.app/v1/options/chain/{ticker}/"
        resp = session.get(url, timeout=15, content_type="api")
        if resp is None:
            return None

        data = resp.json()
        if not data or "optionSymbol" not in data:
            return None

        records = []
        for i in range(len(data.get("optionSymbol", []))):
            try:
                exp_str = data["expiration"][i] if i < len(data.get("expiration", [])) else None
                if not exp_str:
                    continue
                exp_date = datetime.strptime(str(exp_str)[:8], "%Y%m%d").date()
                opt_type = "call" if data.get("putCall", [None])[i] == "call" else "put"

                records.append({
                    "expiration_date": exp_date,
                    "strike": float(data["strike"][i]) if i < len(data.get("strike", [])) else 0,
                    "option_type": opt_type,
                    "last_price": float(data["last"][i]) if i < len(data.get("last", [])) and data["last"][i] else None,
                    "bid": float(data["bid"][i]) if i < len(data.get("bid", [])) and data["bid"][i] else None,
                    "ask": float(data["ask"][i]) if i < len(data.get("ask", [])) and data["ask"][i] else None,
                    "volume": int(data["volume"][i]) if i < len(data.get("volume", [])) and data["volume"][i] else None,
                    "open_interest": int(data["openInterest"][i]) if i < len(data.get("openInterest", [])) and data["openInterest"][i] else None,
                    "implied_volatility": float(data["iv"][i]) if i < len(data.get("iv", [])) and data["iv"][i] else None,
                })
            except (IndexError, ValueError, TypeError):
                continue

        return records if records else None
    except Exception:
        return None


def process_ticker_options(ticker: str, ticker_id: int) -> bool:
    """Fetch and store options chain data for one ticker."""
    records = fetch_options_yfinance(ticker)

    # Fallback to alternative source if yfinance fails
    if not records:
        session = StealthSession()
        try:
            records = scrape_options_alternative(ticker, session)
        finally:
            session.close()

    if not records:
        return False

    # Store records in database
    df = pd.DataFrame(records)
    if not df.empty:
        df["ticker_id"] = ticker_id
        # Convert date columns
        if "expiration_date" in df.columns:
            df["expiration_date"] = pd.to_datetime(df["expiration_date"])
        fast_bulk_insert("options_chain", df)

    return True


# ── BaseScraper Subclass ───────────────────────────────────────

class OptionsChainScraper(BaseScraper):
    """Options chain data scraper using BaseScraper infrastructure."""

    def __init__(self):
        super().__init__(stage="options", name="OPTIONS")

    def _get_pending_items(self, retry_errored: bool = False):
        """Override to filter for exchange-listed tickers (only they have options)."""
        with get_connection() as conn:
            all_items = conn.execute(text("""
                SELECT id, ticker FROM tickers
                WHERE is_active = 1
                  AND exchange IN ('NASDAQ', 'NYSE', 'NYSE American', 'NYSE Arca', 'BATS')
                ORDER BY ticker
            """)).fetchall()
        all_items = [{"id": r[0], "ticker": r[1]} for r in all_items]

        with get_connection() as conn:
            progress = conn.execute(
                text("SELECT ticker, status FROM scraping_progress WHERE stage = :stage"),
                {"stage": self.stage}
            ).fetchall()
        progress_dict = {r[0]: r[1] for r in progress}

        if retry_errored:
            skip_set = {t for t, s in progress_dict.items() if s == 'complete'}
        else:
            skip_set = {t for t, s in progress_dict.items() if s in ('complete', 'error')}

        remaining = [t for t in all_items if t["ticker"] not in skip_set]
        completed = len({t for t, s in progress_dict.items() if s == 'complete'})
        errored = len({t for t, s in progress_dict.items() if s == 'error'})

        print(f"  [{self.name}] Total exchange-listed: {len(all_items)}, "
              f"Completed: {completed}, Errored: {errored}, "
              f"Remaining: {len(remaining)}")

        return remaining

    def _process_single(self, item: dict) -> bool:
        """Process a single ticker's options chain."""
        return process_ticker_options(item["ticker"], item["id"])


# ── Convenience Entry Point ────────────────────────────────────

def run_options_scraper(retry_errored: bool = False, max_tickers: int = None,
                      ticker_filter=None):
    """Run options chain scraper (convenience wrapper)."""
    scraper = OptionsChainScraper()
    try:
        scraper.run(retry_errored=retry_errored, max_items=max_tickers)
    finally:
        scraper.cleanup()


if __name__ == "__main__":
    from src.database import init_database
    init_database()
    run_options_scraper(max_tickers=5)
