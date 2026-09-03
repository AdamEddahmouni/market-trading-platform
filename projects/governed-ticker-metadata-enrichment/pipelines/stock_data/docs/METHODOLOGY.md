# NASDAQ Complete Data Pipeline -- Methodology

> **How the data is collected, processed, and validated**
> Version 1.0 | July 2026

---

## 1. Overview

The NASDAQ Complete Data Pipeline is a multi-stage data engineering system that:

1. **Discovers** all NASDAQ-listed securities from multiple authoritative sources
2. **Collects** comprehensive historical data via APIs and web scraping
3. **Stores** data in a structured SQLite database with optimized schemas
4. **Exports** to Parquet (efficient columnar) and CSV (universal) formats
5. **Documents** every field, source, and transformation

---

## 2. Ticker Discovery Methodology

### Primary Source: NASDAQ Trader
The official NASDAQ Trader listing (`nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt`) is the most authoritative source for currently listed NASDAQ securities. This file is updated daily by NASDAQ and includes:
- All NASDAQ-listed common stocks
- NASDAQ-listed ETFs
- NASDAQ-listed tracking stocks
- NASDAQ-listed preferred stocks

### Secondary Source: NASDAQ Other Listed
The `otherlisted.txt` file includes securities listed on other exchanges (NYSE, NYSE American, ARCA, BATS) that trade on NASDAQ's systems.

### Tertiary Source: Wikipedia
Wikipedia's NASDAQ-100 component list provides additional validation for the largest NASDAQ companies.

### Deduplication Strategy
- Ticker symbols are used as the primary key
- NASDAQ Trader data takes precedence over other sources
- Test/symbolic tickers (starting with TEST, ZZ) are removed
- Tickers longer than 10 characters are filtered

### Validation
Optional yfinance validation queries each ticker to confirm:
- Market data availability
- Valid price quote
- Active trading status

---

## 3. Price Data Collection Methodology

### Primary Source: Yahoo Finance (via yfinance)
yfinance provides the most comprehensive free historical market data, sourced from Yahoo Finance's data feeds which aggregate multiple exchange and third-party data providers.

### Data Collected Per Ticker
| Data Type | Collection Method | Coverage |
|-----------|------------------|----------|
| Daily OHLCV | `yfinance.Ticker.history(period="max")` | IPO date to present |
| Dividends | Included in history with `actions=True` | Full history |
| Stock Splits | Included in history with `actions=True` | Full history |
| Weekly Prices | Computed from daily (Friday-close aggregation) | Full history |
| Monthly Prices | Computed from daily (month-end aggregation) | Full history |

### Aggregation Rules
- **Weekly**: Open = first day's open, High = week's high, Low = week's low, Close = Friday's close, Volume = week's sum
- **Monthly**: Open = first day's open, High = month's high, Low = month's low, Close = last day's close, Volume = month's sum

### Rate Limiting
- 1.5-second delay between ticker requests
- Max 3 retries per ticker on failure
- Exponential backoff on retry

---

## 4. Fundamentals Collection Methodology

### Primary Source: Yahoo Finance (via yfinance)
The `yfinance.Ticker.info` dictionary provides 100+ fields of fundamental data sourced from:
- Morningstar (financial statements, ratios)
- Reuters (company profiles, estimates)
- FactSet (ownership data)
- Exchange data feeds (real-time prices, volume)

### Financial Statements
Financial statements come from:
- **Annual**: Fiscal year-end filings (10-K)
- **Quarterly**: Interim filings (10-Q)
- Data from Morningstar via Yahoo Finance's `income_stmt`, `balance_sheet`, and `cashflow` properties

### Data Coverage Limitations
- Financial statement history varies; typically 3-5 years quarterly, 10+ years annual
- Some OTC/de-listed tickers may have limited or no data
- Very small companies may have incomplete financial data

---

## 5. Supplemental Web Scraping Methodology

### Approach
When API data is insufficient, we use direct web scraping with browser impersonation:

| Source | Method | Data Collected |
|--------|--------|---------------|
| Yahoo Finance | `curl_cffi` with Chrome impersonation | Profile details, extended statistics |
| NASDAQ.com | `curl_cffi` with Chrome impersonation | Company profile, key statistics |
| SEC EDGAR | Requests with CIK lookup | Filing history, company facts |
| MarketBeat | `curl_cffi` with Chrome impersonation | Analyst ratings, price targets |

### Browser Impersonation
Using `curl_cffi` library to mimic Chrome 124's TLS fingerprint, headers, and HTTP/2 behavior to avoid bot detection.

### Ethical Scraping
- Rate limiting (1-10 seconds between requests depending on source)
- SEC-specific rate limiting (10 seconds between requests per SEC policy)
- Descriptive User-Agent with contact information
- Caching to avoid redundant requests

---

## 6. Data Storage Architecture

### Database: SQLite with WAL mode
- **Choice rationale**: Zero configuration, single-file portability, ACID compliance
- **WAL mode**: Enables concurrent reads during write operations
- **Performance optimizations**: mmap_size (256MB), cache_size (32MB), temp_store=MEMORY

### Data Export Formats

#### Parquet (Primary Export)
- **Rationale**: Columnar storage for efficient analytics, 10-100x compression vs CSV
- **Compression**: Snappy (fast compression/decompression)
- **Partitioning**: By ticker symbol for fast per-ticker queries
- **Tools**: Can be read by Pandas, Spark, DuckDB, R, MATLAB, and most BI tools

#### CSV (Secondary Export)
- **Rationale**: Universal compatibility, human-readable
- **Full export**: All tickers, complete history
- **Per-ticker export**: Individual CSVs for each ticker

---

## 7. Pipeline Execution

### Stages

```
Stage 1: Ticker Discovery  --->  Database: tickers table
Stage 2: Price Scraping    --->  Database: daily/weekly/monthly prices, dividends, splits
Stage 3: Fundamentals      --->  Database: fundamentals, financial statements
Stage 4: Supplemental      --->  Database: supplemental_data (web scraped)
Stage 5: Export            --->  Parquet files + CSV files
```

### Resume Capability
Each stage tracks progress in the `scraping_progress` table:
- Completed tickers are skipped on re-run
- Failed tickers are retried
- Partial completion is preserved

### Error Handling
- 3 retry attempts per ticker per stage
- Errors logged with details in `scraping_progress.details`
- Batch processing with periodic saves (every 50 tickers)

---

## 8. Data Quality & Limitations

### What's Included
- [DONE] All NASDAQ-listed common stocks
- [DONE] ETFs listed on NASDAQ (configurable)
- [DONE] Historical data back to the earliest available date
- [DONE] Corporate actions (dividends, splits, mergers where tracked)

### What's NOT Included
- [FAIL] Real-time streaming data (snapshot)
- [FAIL] Options chains data
- [FAIL] Order book / Level 2 data
- [FAIL] Non-US exchange data
- [FAIL] Intraday tick data (daily OHLCV only)

### Known Limitations
1. **yfinance reliability**: yfinance is an unofficial Yahoo Finance API wrapper and may break if Yahoo changes their API
2. **Data backfilling**: Historical financial statements may be restated; the database stores the current restated values
3. **Delisted tickers**: Some historical tickers may not be available through yfinance
4. **Fundamentals frequency**: Fundamentals are snapshots, collected once per scrape run

### Data Sources Attribution
- Price data: Yahoo Finance (data sourced from exchange feeds and third-party market data providers)
- Fundamentals: Morningstar, Reuters, FactSet (via Yahoo Finance)
- Company profiles: NASDAQ.com, SEC EDGAR
- Analyst ratings: MarketBeat

---

## 9. Quick Start Guide

### Prerequisites
```bash
pip install yfinance pandas numpy requests curl_cffi pyarrow sqlalchemy tqdm beautifulsoup4 lxml
```

### Running the Pipeline
```bash
# Stage 1: Discover all tickers
python scripts/pipeline.py discover

# Stage 2: Scrape price data (longest stage)
python scripts/pipeline.py prices

# Stage 3: Scrape fundamentals
python scripts/pipeline.py fundamentals

# Stage 4: Supplemental data (limited batch)
python scripts/pipeline.py supplemental 100

# Stage 5: Export to Parquet/CSV
python scripts/pipeline.py export

# View database statistics
python scripts/pipeline.py stats

# Test a single ticker
python scripts/pipeline.py test AAPL

# Run full pipeline
python scripts/pipeline.py all
```

### Expected Execution Times
| Stage | Tickers | Est. Time | Note |
|-------|---------|-----------|------|
| Discover | 4,000 | 30-60 sec | Fast API calls |
| Prices | 4,000 | 1.5-2 hrs | ~1.5s/ticker |
| Fundamentals | 4,000 | 2-3 hrs | ~2s/ticker |
| Supplemental | 100 | 10 min | ~6s/ticker |
| Export | All | 2-5 min | CPU-bound |
