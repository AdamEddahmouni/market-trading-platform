"""
Index Membership Fetcher - Scrapes component lists for all major US indexes.
Sources: Wikipedia (S&P 500, Dow Jones, S&P 100), yfinance (NASDAQ-100).
"""

import re
import time
from datetime import datetime, date
from typing import List, Dict, Optional, Any

import requests
from bs4 import BeautifulSoup

from src.config import REQUEST_TIMEOUT
from src.database import get_ticker_id, get_connection, init_database
from sqlalchemy.sql import text


# ── Helpers ─────────────────────────────────────────────────────

def _parse_date(val: str) -> Optional[date]:
    try:
        return datetime.strptime(val.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None


def _parse_int(val: str) -> Optional[int]:
    try:
        return int(re.sub(r'[^0-9]', '', val))
    except (ValueError, TypeError):
        return None


def _clean_text(val) -> str:
    if hasattr(val, 'get_text'):
        return val.get_text(strip=True)
    return str(val).strip()


def _find_best_table(tables, keywords, header_keywords=None):
    """Find the best matching wikitable by scoring caption and headers."""
    scored = []
    for table in tables:
        score = 0
        caption = table.find("caption")
        if caption:
            cap_text = caption.get_text().lower()
            for kw, pts in keywords:
                if kw in cap_text:
                    score += pts

        thead = table.find("thead")
        header_row = thead.find("tr") if thead else \
                     (table.find_all("tr")[0] if table.find_all("tr") else None)

        if header_row:
            headers = header_row.find_all("th")
            h_texts = [h.get_text(strip=True).lower() for h in headers]
            combo = " ".join(h_texts)
            if header_keywords:
                for kw, pts in header_keywords:
                    if kw in combo:
                        score += pts

        if score > 0:
            n_headers = len(header_row.find_all("th")) if header_row else 0
            scored.append((score, n_headers, table))

    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return scored[0][2]


# ── S&P 500 ─────────────────────────────────────────────────────

def fetch_sp500_components() -> List[Dict[str, Any]]:
    """Fetch S&P 500 component list from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    print(f"  Fetching S&P 500 from {url}...")
    components = []

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        tables = soup.find_all("table", class_="wikitable")
        target = _find_best_table(
            tables,
            keywords=[("s&p 500", 10), ("component", 5)],
            header_keywords=[("symbol", 3), ("security", 2), ("sector", 1)]
        ) or (tables[0] if tables else None)

        if not target:
            print("  [WARN] No S&P 500 table found")
            return components

        rows = target.find_all("tr")
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue
            ticker = _clean_text(cols[0])
            if not ticker or not re.match(r'^[A-Z\.\-]+$', ticker):
                continue
            components.append({
                "ticker": ticker,
                "company_name": _clean_text(cols[1]) if len(cols) > 1 else "",
                "index_name": "S&P 500",
                "sector": _clean_text(cols[2]) if len(cols) > 2 else "",
                "sub_industry": _clean_text(cols[3]) if len(cols) > 3 else "",
                "headquarters": _clean_text(cols[4]) if len(cols) > 4 else "",
                "date_added": _parse_date(_clean_text(cols[5])) if len(cols) > 5 else None,
                "cik": _clean_text(cols[6]) if len(cols) > 6 else "",
                "founded": _parse_int(_clean_text(cols[7])) if len(cols) > 7 else None,
            })

        print(f"  Found {len(components)} S&P 500 components")
    except Exception as e:
        print(f"  [ERROR] S&P 500: {e}")

    return components


# ── Dow Jones ───────────────────────────────────────────────────

def fetch_dow_components() -> List[Dict[str, Any]]:
    """Fetch DJIA components from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
    print(f"  Fetching DJIA from {url}...")
    components = []

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        tables = soup.find_all("table", class_="wikitable")
        target = _find_best_table(
            tables,
            keywords=[("component", 10), ("djia", 5), ("dow jones", 3)],
            header_keywords=[("company", 3), ("symbol", 2), ("exchange", 2),
                             ("added", 4), ("weight", 2)]
        )

        if not target:
            print("  [WARN] No DJIA table found")
            return components

        rows = target.find_all("tr")
        if len(rows) < 2:
            return components

        headers = rows[0].find_all("th")
        h_texts = [h.get_text(strip=True).lower() for h in headers]

        col_idx = {}
        for i, h in enumerate(h_texts):
            if "symbol" in h or "ticker" in h:
                col_idx["ticker"] = i
            if "company" in h:
                col_idx["company"] = i
            if "sector" in h:
                col_idx["sector"] = i
            if "added" in h:
                col_idx["date_added"] = i
            if "note" in h:
                col_idx["notes"] = i
            if "weight" in h:
                col_idx["weight"] = i

        if "ticker" not in col_idx:
            print("  [WARN] No ticker column found in DJIA table")
            return components

        ticker_pos = col_idx["ticker"]
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if ticker_pos >= len(cells):
                continue
            ticker = _clean_text(cells[ticker_pos])
            if not ticker or not re.match(r'^[A-Z\.\-]+$', ticker):
                continue
            comp = {"ticker": ticker, "index_name": "Dow Jones"}
            if "company" in col_idx and col_idx["company"] < len(cells):
                comp["company_name"] = _clean_text(cells[col_idx["company"]])
            if "sector" in col_idx and col_idx["sector"] < len(cells):
                comp["sector"] = _clean_text(cells[col_idx["sector"]])
            if "date_added" in col_idx and col_idx["date_added"] < len(cells):
                comp["date_added"] = _parse_date(_clean_text(cells[col_idx["date_added"]]))
            if "notes" in col_idx and col_idx["notes"] < len(cells):
                comp["notes"] = _clean_text(cells[col_idx["notes"]])
            if "weight" in col_idx and col_idx["weight"] < len(cells):
                try:
                    w = _clean_text(cells[col_idx["weight"]]).replace("%", "")
                    comp["index_weight"] = float(w)
                except (ValueError, TypeError):
                    pass
            components.append(comp)

        print(f"  Found {len(components)} DJIA components")
    except Exception as e:
        print(f"  [ERROR] DJIA: {e}")

    return components


# ── S&P 100 ─────────────────────────────────────────────────────

def fetch_sp100_components() -> List[Dict[str, Any]]:
    """Fetch S&P 100 (OEX) component list from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/S%26P_100"
    print(f"  Fetching S&P 100 from {url}...")
    components = []

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        tables = soup.find_all("table", class_="wikitable")
        target = _find_best_table(
            tables,
            keywords=[("symbol", 3), ("name", 2), ("sector", 1)],
            header_keywords=[("symbol", 5), ("name", 3)]
        ) or (tables[0] if tables else None)

        if not target:
            print("  [WARN] No S&P 100 table found")
            return components

        rows = target.find_all("tr")
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            ticker = _clean_text(cols[0])
            if not ticker or not re.match(r'^[A-Z\.\-]+$', ticker):
                continue
            components.append({
                "ticker": ticker,
                "company_name": _clean_text(cols[1]) if len(cols) > 1 else "",
                "index_name": "S&P 100",
                "sector": _clean_text(cols[2]) if len(cols) > 2 else "",
            })

        print(f"  Found {len(components)} S&P 100 components")
    except Exception as e:
        print(f"  [ERROR] S&P 100: {e}")

    return components


# ── NASDAQ-100 ──────────────────────────────────────────────────

def fetch_nasdaq100_components() -> List[Dict[str, Any]]:
    """Fetch NASDAQ-100 (NDX) components via yfinance."""
    print("  Fetching NASDAQ-100 via yfinance...")
    components = []

    try:
        import yfinance as yf
        ndx = yf.Ticker("^NDX")
        info = ndx.info

        if info and "components" in info:
            tickers = info["components"]
            print(f"  Found {len(tickers)} components via yfinance")
            for ticker in tickers:
                components.append({
                    "ticker": ticker,
                    "index_name": "NASDAQ-100",
                })
            return components

        # Fallback: top 100 NASDAQ by market cap
        print("  NASDAQ-100 not available via components API, using top 100 by market cap...")
        with get_connection() as conn:
            rows = conn.execute(text("""
                SELECT ticker, market_cap FROM tickers
                WHERE exchange = 'NASDAQ' AND is_active = 1
                  AND market_cap IS NOT NULL
                ORDER BY market_cap DESC
                LIMIT 100
            """)).fetchall()

        for row in rows:
            components.append({
                "ticker": row[0],
                "index_name": "NASDAQ-100",
                "market_cap": row[1],
            })

        if components:
            print(f"  Found {len(components)} NASDAQ-100 (by market cap)")
    except Exception as e:
        print(f"  [ERROR] NASDAQ-100: {e}")

    return components


# ── Storage ─────────────────────────────────────────────────────

def store_index_memberships(components: List[Dict[str, Any]]):
    """Store index membership records in the database."""
    not_found = []
    stored = 0
    skipped = 0

    with get_connection() as conn:
        for comp in components:
            tid = get_ticker_id(comp["ticker"])
            if not tid:
                not_found.append(comp["ticker"])
                skipped += 1
                continue
            try:
                conn.execute(text("""
                    INSERT OR IGNORE INTO index_membership
                    (ticker_id, index_name, sector, sub_industry,
                     date_added, cik, founded, headquarters,
                     index_weight, notes)
                    VALUES (:tid, :idx, :sector, :sub,
                            :date_added, :cik, :founded, :hq,
                            :weight, :notes)
                """), {
                    "tid": tid,
                    "idx": comp.get("index_name", "UNKNOWN"),
                    "sector": comp.get("sector"),
                    "sub": comp.get("sub_industry"),
                    "date_added": comp.get("date_added"),
                    "cik": comp.get("cik"),
                    "founded": comp.get("founded"),
                    "hq": comp.get("headquarters"),
                    "weight": comp.get("index_weight"),
                    "notes": comp.get("notes"),
                })
                stored += 1
            except Exception as e:
                print(f"  [ERROR] {comp['ticker']}: {e}")
                skipped += 1

    if not_found:
        print(f"  [WARN] {len(not_found)} tickers not in database (not stored)")
    print(f"  [DB] Stored {stored} index memberships")


# ── Main Runner ─────────────────────────────────────────────────

def run_index_fetcher():
    """Fetch all index memberships and store in database."""
    print("\n" + "=" * 60)
    print("  INDEX MEMBERSHIP FETCHER")
    print("=" * 60)

    all_components = []

    for fetcher, name in [
        (fetch_sp500_components, "S&P 500"),
        (fetch_dow_components, "Dow Jones"),
        (fetch_sp100_components, "S&P 100"),
        (fetch_nasdaq100_components, "NASDAQ-100"),
    ]:
        print(f"\n  [{name}]")
        components = fetcher()
        all_components.extend(components)

    print(f"\n  Total components collected: {len(all_components)}")
    store_index_memberships(all_components)

    # Print summary by index
    from collections import Counter
    index_counts = Counter(c.get("index_name", "UNKNOWN") for c in all_components)
    print(f"\n  Summary by index:")
    for idx, count in sorted(index_counts.items(), key=lambda x: -x[1]):
        print(f"    {idx:<20} {count:>5}")


if __name__ == "__main__":
    init_database()
    run_index_fetcher()
