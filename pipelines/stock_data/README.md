# Market Data Pipeline - Stealth Web Scraper Suite

> **Free, comprehensive financial market data collection without paid APIs.**
> Version 2.0 | July 2026

## Overview

A complete suite of stealth web scrapers and crawlers that collect comprehensive financial market data from public sources - **completely free**. No paid APIs, no subscriptions, no market data fees required.

### What It Collects

| Data | Sources | Coverage |
|------|---------|----------|
| **Ticker Master List** | NASDAQ Trader, Wikipedia | 10,000+ symbols (NASDAQ, NYSE, NYSE American, NYSE Arca, BATS, IEX) |
| **Daily OHLCV Prices** | Yahoo Finance (via yfinance) | Full history (IPO date to present) |
| **Weekly/Monthly Prices** | Computed from daily | Aggregated OHLCV |
| **Dividends** | Yahoo Finance | Full history |
| **Stock Splits** | Yahoo Finance | Full history |
| **Fundamentals (58+ metrics)** | Yahoo Finance / Morningstar | P/E, EPS, market cap, beta, etc. |
| **Financial Statements** | Yahoo Finance / Morningstar | Income Statement, Balance Sheet, Cash Flow (annual & quarterly) |
| **Company Profiles** | NASDAQ.com, Yahoo Finance | Business descriptions, officers, sector/industry |
| **SEC Filings** | SEC EDGAR | Filing history, CIK numbers |
| **Analyst Ratings** | MarketBeat | Price targets, consensus ratings |
| **Index Membership** | Wikipedia | S&P 500, Dow Jones, S&P 100, NASDAQ-100 |

## Project Structure

```
stock-data/
+-- src/                          # Source code (organized by function)
|   +-- config.py                 # Centralized configuration
|   +-- database.py               # Database schema & operations
|   +-- pipeline.py               # Main orchestrator
|   +-- scrapers/                 # All scraper modules
|   |   +-- stealth.py           # Browser fingerprint rotation & anti-detection
|   |   +-- http_client.py       # Stealth HTTP client (curl_cffi impersonation)
|   |   +-- rate_limiter.py      # Intelligent per-domain rate limiting
|   |   +-- tickers.py           # Ticker discovery from multiple sources
|   |   +-- prices.py            # Historical price data
|   |   +-- fundamentals.py      # Fundamentals & financial statements
|   |   +-- supplemental.py      # Multi-source web scraping
|   |   +-- indexes.py           # Index membership scraping
|   +-- exporters/                # Data export modules
|   |   +-- parquet_export.py    # Parquet (efficient columnar format)
|   |   +-- csv_export.py        # CSV (universal format)
|   +-- utils/                    # Utility modules
|       +-- validators.py        # Ticker cleanup & market cap validation
+-- data/                         # All data (separated from code)
|   +-- database/                 # SQLite database
|   +-- parquet/                  # Parquet exports
|   +-- csv_exports/              # CSV exports
|   +-- metadata/                 # JSON metadata files
+-- docs/                         # Documentation
+-- scripts/                      # Thin CLI wrappers
|   +-- run.py                    # CLI entry point
+-- setup.py                      # Package installation
+-- requirements.txt              # Dependencies
+-- README.md                     # This file
```

## Key Features

### Stealth Scraping Technology
- **Browser fingerprint rotation**: Randomizes User-Agent, headers, TLS fingerprints per request
- **curl_cffi integration**: Impersonates Chrome 124's TLS stack when available
- **Adaptive rate limiting**: Token-bucket algorithm that slows down on 429 responses
- **Human behavior simulation**: Random delays, jitter, and realistic request patterns
- **Cookie persistence**: Maintains session cookies across requests

### Pipeline Reliability
- **Resume from crash**: Every ticker's progress is tracked; partial runs resume where they left off
- **Graceful shutdown**: Ctrl+C finishes in-flight work before stopping
- **Double Ctrl+C**: Force exit for emergencies
- **Retry logic**: 3 retries with exponential backoff per failed request

### Data Quality
- **Deduplication**: Multiple sources prioritized by authority
- **Validation**: Pattern-based ticker filtering removes unpriceable securities
- **WAL mode**: SQLite Write-Ahead Logging for concurrent read/write performance

## Quick Start

### Installation

```bash
# Clone the repository (private)
git clone https://github.com/AdamEddahmouni/market-data-pipeline.git stock-data
cd stock-data

# (Recommended) Install with pip
pip install -e .

# OR install dependencies manually
pip install -r requirements.txt

# (Optional) Install stealth scraping support
pip install curl_cffi
```

### Running the Pipeline

```bash
# Stage 1: Discover all tickers from NASDAQ, NYSE, and other exchanges
python scripts/run.py discover

# Stage 2: Scrape all historical price data (longest stage)
python scripts/run.py prices

# Stage 3: Scrape fundamentals & financial statements
python scripts/run.py fundamentals

# Stage 4: Supplemental web scraping (limited batch for testing)
python scripts/run.py supplemental 100

# Stage 5: Fetch index memberships (S&P 500, Dow Jones, etc.)
python scripts/run.py indexes

# Stage 6: Export to Parquet and CSV
python scripts/run.py export

# View database statistics
python scripts/run.py stats

# Test a single ticker
python scripts/run.py test AAPL

# Clean up unpriceable tickers (warrants, rights, preferred shares)
python scripts/run.py cleanup

# Run full pipeline
python scripts/run.py all
```

### Expected Run Times

| Stage | Scope | Est. Time |
|-------|-------|-----------|
| Discover | 10,000+ tickers | 30-60 sec |
| Prices | 4,000 active | 1.5-2 hrs |
| Fundamentals | 4,000 active | 2-3 hrs |
| Supplemental | 100 tickers | 10 min |
| Export | All data | 2-5 min |

## Data Sources

All data is collected from **completely free, public sources**:

| Source | Data Provided | Rate Limit |
|--------|--------------|------------|
| [NASDAQ Trader](https://www.nasdaqtrader.com/) | Official ticker lists | None |
| [Yahoo Finance](https://finance.yahoo.com/) | Prices, fundamentals, profile | 2,000/hr (yfinance handles this) |
| [NASDAQ.com](https://www.nasdaq.com/) | Company profiles, key stats | Standard |
| [SEC EDGAR](https://www.sec.gov/edgar/) | Company filings, CIK | 10 req/sec |
| [MarketBeat](https://www.marketbeat.com/) | Analyst ratings | Standard |
| [Wikipedia](https://en.wikipedia.org/) | Index components | Standard |

## System Requirements

- **Python 3.9+**
- **~10GB free disk space** (for full data collection with all exports)
- **Internet connection** (for scraping)
- **curl_cffi** optional (for enhanced browser impersonation)

## License

MIT License - Free for any use.
