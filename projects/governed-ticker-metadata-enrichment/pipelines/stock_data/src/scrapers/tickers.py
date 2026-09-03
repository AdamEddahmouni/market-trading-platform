"""
Multi-Exchange Ticker Discovery - Multi-source ticker discovery using stealth scraping.
Fetches comprehensive ticker lists from NASDAQ Trader, SEC EDGAR, and Wikipedia.
Deduplicates and validates symbols. Tracks which exchange each ticker belongs to.
"""

import json
import re
import time
from datetime import datetime
from typing import Set, List, Dict, Optional, Tuple
from collections import Counter

import requests
from bs4 import BeautifulSoup

from src.config import (
    TICKER_URLS, TICKER_LIST_PATH, REQUEST_TIMEOUT,
    INCLUDE_ETF, EXCHANGE_NAMES, EXCHANGE_CODES, MAX_RETRIES
)
from src.database import upsert_ticker, get_ticker_count, get_connection, init_database


def _parse_exchange_code(code: str) -> str:
    """Map NASDAQ Trader exchange codes to canonical exchange names."""
    code = code.strip().upper()
    if code in EXCHANGE_CODES:
        return EXCHANGE_CODES[code]
    return code if code else "UNKNOWN"


def fetch_nasdaq_trader_list() -> List[Dict[str, str]]:
    """Fetch NASDAQ-listed tickers from NASDAQ Trader (most authoritative source)."""
    url = TICKER_URLS["nasdaq_trader"]
    print(f"  [TICKERS] Fetching NASDAQ Trader list from {url}...")
    tickers = []

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

        lines = resp.text.strip().split("\n")
        for line in lines[1:]:
            if not line.strip() or "|" not in line:
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                symbol = parts[0].strip()
                name = parts[1].strip()
                is_etf = len(parts) > 3 and parts[3].strip().upper() == "Y"

                if not INCLUDE_ETF and is_etf:
                    continue

                tickers.append({
                    "ticker": symbol,
                    "company_name": name,
                    "exchange": EXCHANGE_NAMES["NASDAQ"],
                    "is_etf": is_etf,
                    "source": "nasdaq_trader"
                })

        print(f"    Found {len(tickers)} NASDAQ-listed securities")
    except Exception as e:
        print(f"    [ERROR] Fetching NASDAQ Trader list: {e}")

    return tickers


def fetch_other_listed() -> List[Dict[str, str]]:
    """Fetch other exchange listings from NASDAQ Trader (NYSE, NYSE Arca, BATS, etc.)."""
    url = TICKER_URLS["other_listed"]
    print(f"  [TICKERS] Fetching Other Listed from {url}...")
    tickers = []

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

        lines = resp.text.strip().split("\n")
        for line in lines[1:]:
            if not line.strip() or "|" not in line:
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                symbol = parts[0].strip()
                name = parts[1].strip()
                ex_code = parts[2].strip() if len(parts) > 2 else ""

                if symbol.startswith(("TEST", "MTEST")) or "File Creation Time" in line:
                    continue

                exchange = _parse_exchange_code(ex_code)
                is_etf = "ETF" in name.upper() or "INDEX" in name.upper()

                tickers.append({
                    "ticker": symbol,
                    "company_name": name,
                    "exchange": exchange,
                    "is_etf": is_etf,
                    "source": f"other_{ex_code}" if ex_code else "other_unknown"
                })

        print(f"    Found {len(tickers)} other-listed securities")
    except Exception as e:
        print(f"    [ERROR] Fetching Other Listed: {e}")

    return tickers


def fetch_wikipedia_nasdaq_100() -> List[Dict[str, str]]:
    """Fetch NASDAQ-100 component tickers from Wikipedia (secondary source)."""
    print("  [TICKERS] Fetching NASDAQ-100 from Wikipedia...")
    tickers = []

    try:
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        tables = soup.find_all("table", class_="wikitable")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cols = row.find_all("td")
                if len(cols) >= 2:
                    ticker_cell = cols[0].get_text(strip=True)
                    name_cell = cols[1].get_text(strip=True)
                    if ticker_cell and re.match(r'^[A-Z\.\-]+$', ticker_cell):
                        tickers.append({
                            "ticker": ticker_cell,
                            "company_name": name_cell,
                            "exchange": EXCHANGE_NAMES["NASDAQ"],
                            "is_etf": False,
                            "source": "wikipedia_nasdaq100"
                        })
    except Exception as e:
        print(f"    [ERROR] Fetching NASDAQ-100 Wikipedia: {e}")

    print(f"    Found {len(tickers)} from Wikipedia NASDAQ-100")
    return tickers


def fetch_wikipedia_nyse_components() -> List[Dict[str, str]]:
    """Fetch NYSE companies from Wikipedia."""
    print("  [TICKERS] Fetching NYSE companies from Wikipedia...")
    tickers = []

    try:
        urls = [
            "https://en.wikipedia.org/wiki/List_of_companies_listed_on_the_New_York_Stock_Exchange",
            "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
        ]

        seen = set()
        for url in urls:
            try:
                resp = requests.get(url, timeout=REQUEST_TIMEOUT,
                                    headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

                tables = soup.find_all("table", class_="wikitable")
                for table in tables:
                    rows = table.find_all("tr")
                    for row in rows[1:]:
                        cols = row.find_all(["td", "th"])
                        for col in cols:
                            text = col.get_text(strip=True)
                            if re.match(r'^[A-Z]{1,5}$', text) and text not in ("Ticker", "Symbol", "NYSE", "NASDAQ"):
                                if text not in seen:
                                    seen.add(text)
                                    tickers.append({
                                        "ticker": text,
                                        "company_name": "",
                                        "exchange": EXCHANGE_NAMES["NYSE"],
                                        "is_etf": False,
                                        "source": "wikipedia_nyse"
                                    })
                                break
            except Exception as e:
                print(f"    [WARN] Error fetching {url}: {e}")
                continue

    except Exception as e:
        print(f"  [ERROR] Fetching NYSE Wikipedia: {e}")

    print(f"    Found {len(tickers)} from Wikipedia NYSE sources")
    return tickers


def fetch_all_tickers() -> List[Dict[str, str]]:
    """
    Aggregate tickers from ALL available sources across ALL exchanges,
    deduplicate with proper exchange precedence.
    """
    all_tickers: Dict[str, Dict] = {}

    # Priority 1: Official NASDAQ Trader list
    for t in fetch_nasdaq_trader_list():
        all_tickers[t["ticker"]] = t

    # Priority 2: Other exchange listings
    for t in fetch_other_listed():
        sym = t["ticker"]
        if sym not in all_tickers:
            all_tickers[sym] = t
        elif all_tickers[sym]["source"].startswith("wikipedia"):
            all_tickers[sym] = t

    # Priority 3: Wikipedia sources (supplemental)
    for t in fetch_wikipedia_nasdaq_100():
        sym = t["ticker"]
        if sym not in all_tickers:
            all_tickers[sym] = t

    for t in fetch_wikipedia_nyse_components():
        sym = t["ticker"]
        if sym not in all_tickers:
            all_tickers[sym] = t

    # Build master list
    master_list = list(all_tickers.values())
    master_list = [
        t for t in master_list
        if not t["ticker"].startswith(("TEST", "ZZ", "MTEST"))
        and len(t["ticker"]) <= 10
        and t.get("company_name", "") not in ("File Creation Time",)
    ]

    print(f"\n  [TICKERS] Master list: {len(master_list)} unique tickers")

    exchange_counts = Counter(t.get("exchange", "UNKNOWN") for t in master_list)
    print(f"  [TICKERS] Exchange breakdown:")
    for ex, count in sorted(exchange_counts.items(), key=lambda x: -x[1]):
        print(f"    {ex:<20} {count:>6}")

    return master_list


def save_ticker_list(tickers: List[Dict[str, str]]) -> str:
    """Save ticker list to JSON."""
    data = {
        "source": "Multi-Exchange Data Pipeline",
        "timestamp": datetime.utcnow().isoformat(),
        "total_count": len(tickers),
        "tickers": tickers,
    }
    with open(TICKER_LIST_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  [TICKERS] Saved to {TICKER_LIST_PATH}")
    return str(TICKER_LIST_PATH)


def load_ticker_list() -> List[Dict[str, str]]:
    """Load previously saved ticker list."""
    if TICKER_LIST_PATH.exists():
        with open(TICKER_LIST_PATH) as f:
            data = json.load(f)
        return data.get("tickers", [])
    return []


def load_tickers_into_db(tickers: List[Dict[str, str]]):
    """Load all tickers into the database."""
    print(f"  [DB] Loading {len(tickers)} tickers into database...")
    for i, t in enumerate(tickers):
        upsert_ticker(
            ticker=t["ticker"],
            company_name=t.get("company_name"),
            exchange=t.get("exchange"),
            sector=t.get("sector"),
            industry=t.get("industry"),
            country=t.get("country"),
            market_cap=t.get("market_cap"),
            is_etf=t.get("is_etf", False),
            source=t.get("source", "unknown"),
        )
        if (i + 1) % 500 == 0:
            print(f"    Loaded {i+1}/{len(tickers)} tickers...")

    count = get_ticker_count()
    print(f"  [DB] Total tickers in database: {count}")


def run_ticker_discovery() -> int:
    """Full ticker discovery pipeline. Returns number of tickers found."""
    print("\n" + "=" * 60)
    print("  MULTI-EXCHANGE TICKER DISCOVERY PIPELINE")
    print("=" * 60)

    tickers = fetch_all_tickers()

    if not tickers:
        print("  [ERROR] No tickers found from any source!")
        return 0

    save_ticker_list(tickers)
    print(f"\n  [TICKERS] {len(tickers)} total tickers discovered")

    load_tickers_into_db(tickers)

    # Print exchange breakdown from DB
    from sqlalchemy.sql import text
    with get_connection() as conn:
        result = conn.execute(text(
            "SELECT exchange, COUNT(*) as cnt FROM tickers WHERE is_active=1 "
            "GROUP BY exchange ORDER BY cnt DESC"
        )).fetchall()
        print(f"\n  [DB] Exchange breakdown in database:")
        for ex, cnt in result:
            print(f"    {ex:<20} {cnt:>6}")

    return len(tickers)


if __name__ == "__main__":
    init_database()
    count = run_ticker_discovery()
    print(f"\nDone! {count} tickers loaded into database.")
