# NASDAQ Complete Data Pipeline -- Database Schema

> **Last Updated:** July 2026
> **Database:** SQLite3 (WAL mode) at `database/nasdaq_complete.db`

---

## Overview

The database contains **13 main data tables** plus a **progress tracking table** covering:

- **~4,000+ NASDAQ-listed tickers** (including NASDAQ Global Select, Global Market, and Capital Market tiers)
- **Full historical daily prices** (earliest available to present)
- **Weekly and monthly aggregated prices**
- **Dividend history** (all available records)
- **Stock split history** (all available records)
- **Fundamentals snapshots** (current key metrics)
- **Income statements** (annual and quarterly, up to 10+ years)
- **Balance sheets** (annual and quarterly)
- **Cash flow statements** (annual and quarterly)
- **Supplemental web-scraped data** (NASDAQ.com, Yahoo Finance, SEC EDGAR, MarketBeat)

---

## Table Definitions

### 1. `tickers` -- Master Ticker Registry

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-incrementing primary key |
| `ticker` | VARCHAR(10) UNIQUE | Stock ticker symbol (e.g., AAPL, MSFT) |
| `company_name` | VARCHAR(255) | Full legal or operating company name |
| `exchange` | VARCHAR(50) | Listing exchange (NASDAQ, NYSE, etc.) |
| `sector` | VARCHAR(100) | Industry sector classification |
| `industry` | VARCHAR(100) | Industry group |
| `country` | VARCHAR(100) | Headquarters country |
| `market_cap` | FLOAT | Current market capitalization |
| `ipo_year` | INTEGER | Year of initial public offering |
| `is_etf` | BOOLEAN | Whether the security is an ETF |
| `is_active` | BOOLEAN | Whether the ticker is currently trading |
| `source` | VARCHAR(50) | Discovery source (nasdaq_trader, nasdaq_other, wikipedia) |
| `first_seen` | DATETIME | When this ticker was first added to the database |
| `last_updated` | DATETIME | When this ticker's metadata was last updated |

### 2. `daily_prices` -- Daily OHLCV Price Data

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGINT PK | Auto-incrementing primary key |
| `ticker_id` | INTEGER FK -> tickers.id | Reference to ticker |
| `date` | DATE | Trading date |
| `open` | FLOAT | Opening price |
| `high` | FLOAT | Daily high price |
| `low` | FLOAT | Daily low price |
| `close` | FLOAT | Closing price |
| `volume` | BIGINT | Number of shares traded |
| `adj_close` | FLOAT | Adjusted closing price (splits & dividends) |

**Unique Constraint:** (ticker_id, date)

### 3. `weekly_prices` -- Weekly Aggregated Prices

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGINT PK | Auto-incrementing primary key |
| `ticker_id` | INTEGER FK -> tickers.id | Reference to ticker |
| `week_start` | DATE | Week starting date (Monday) |
| `open` | FLOAT | Week's opening price |
| `high` | FLOAT | Week's high price |
| `low` | FLOAT | Week's low price |
| `close` | FLOAT | Week's closing price |
| `volume` | BIGINT | Week's total volume |
| `adj_close` | FLOAT | Adjusted closing price |

### 4. `monthly_prices` -- Monthly Aggregated Prices

Same columns as weekly_prices, with `month_start` replacing `week_start`.

### 5. `dividends` -- Dividend History

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGINT PK | Auto-incrementing primary key |
| `ticker_id` | INTEGER FK -> tickers.id | Reference to ticker |
| `date` | DATE | Ex-dividend date |
| `amount` | FLOAT | Dividend amount per share |

### 6. `splits` -- Stock Split History

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGINT PK | Auto-incrementing primary key |
| `ticker_id` | INTEGER FK -> tickers.id | Reference to ticker |
| `date` | DATE | Split effective date |
| `ratio` | FLOAT | Split ratio (e.g., 4.0 = 4:1 split) |
| `split_factor` | VARCHAR(20) | Human-readable factor (e.g., "4:1") |

### 7. `fundamentals` -- Current Fundamentals Snapshot

Contains **58+ fundamental metrics** per ticker. Key columns:

| Column | Type | Description |
|--------|------|-------------|
| `ticker_id` | INTEGER FK | Reference to ticker |
| `snapshot_date` | DATE | Date of snapshot |
| `market_cap` | FLOAT | Market capitalization |
| `enterprise_value` | FLOAT | Enterprise value |
| `trailing_pe` | FLOAT | Trailing P/E ratio |
| `forward_pe` | FLOAT | Forward P/E ratio |
| `price_to_book` | FLOAT | Price-to-book ratio |
| `earnings_per_share` | FLOAT | Trailing EPS |
| `beta` | FLOAT | Beta (volatility measure) |
| `fifty_two_week_high` | FLOAT | 52-week high |
| `fifty_two_week_low` | FLOAT | 52-week low |
| `dividend_yield` | FLOAT | Dividend yield |
| `short_percent_float` | FLOAT | Short interest as % of float |
| *... and 45+ more metrics* | | See full data dictionary |

### 8-10. `income_statements_annual`, `income_statements_quarterly`

Full GAAP income statement data with 20+ line items including:
- Total Revenue, Cost of Revenue, Gross Profit
- Operating Expenses, Operating Income
- Net Income, Diluted EPS, Basic EPS
- EBITDA, Research & Development, SG&A

### 11-12. `balance_sheets_annual`, `balance_sheets_quarterly`

Full balance sheet data with 24+ line items including:
- Total Assets, Total Liabilities, Total Equity
- Current Assets, Current Liabilities
- Cash & Equivalents, Accounts Receivable, Inventory
- Property Plant & Equipment, Goodwill, Intangible Assets
- Long-term Debt, Short-term Debt
- Retained Earnings, Treasury Stock

### 13-14. `cash_flow_annual`, `cash_flow_quarterly`

Full cash flow statement data with 17+ line items including:
- Operating Cash Flow, Investing Cash Flow, Financing Cash Flow
- Capital Expenditure, Free Cash Flow
- Depreciation & Amortization, Stock-Based Compensation
- Dividends Paid, Debt Issuance/Repayment

### 15. `supplemental_data` -- Web-Scraped Data

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGINT PK | Auto-incrementing primary key |
| `ticker_id` | INTEGER FK -> tickers.id | Reference to ticker |
| `data_type` | VARCHAR(50) | Type of data (company_profile, sec_filings, analyst_ratings) |
| `source` | VARCHAR(100) | Data source (yahoo_finance, nasdaq_com, sec_edgar, marketbeat) |
| `data_date` | DATE | Date of the data |
| `data_content` | TEXT | Full scraped data as JSON |
| `url` | TEXT | Source URL |
| `scraped_at` | DATETIME | When data was scraped |

### 16. `scraping_progress` -- Pipeline Progress Tracking

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-incrementing primary key |
| `ticker` | VARCHAR(10) | Ticker symbol |
| `stage` | VARCHAR(50) | Pipeline stage (prices, fundamentals, supplemental) |
| `status` | VARCHAR(20) | Status (pending, complete, error) |
| `details` | TEXT | Error details if failed |
| `updated_at` | DATETIME | Last update timestamp |

---

## Indexes

All tables have indexes on `(ticker_id, date)` or `(ticker_id, fiscal_date)` for efficient range queries. The `daily_prices` table has a composite index for fast ticker+date lookups.

---

## Database Configuration

- **Journal Mode:** WAL (Write-Ahead Logging) for concurrent read/write
- **Synchronous:** NORMAL (balanced performance/durability)
- **Page Cache:** 32MB
- **Memory Map:** 256MB

---

## Exported Data Formats

### Parquet (Efficient, Columnar)

```
parquet/
+-- prices/
|   +-- daily/nasdaq_daily_prices.parquet
|   +-- daily/{ticker}/{ticker}_daily.parquet
|   +-- weekly/nasdaq_weekly_prices.parquet
|   +-- monthly/nasdaq_monthly_prices.parquet
+-- dividends/
|   +-- nasdaq_dividends.parquet
|   +-- {ticker}_{ticker}_dividends.parquet
+-- splits/
|   +-- nasdaq_splits.parquet
+-- financials/
    +-- income_statements_annual/
    +-- income_statements_quarterly/
    +-- balance_sheets_annual/
    +-- balance_sheets_quarterly/
    +-- cash_flow_annual/
    +-- cash_flow_quarterly/
    +-- fundamentals/
    +-- company_info/
    +-- supplemental/
```

### CSV (Universal)

```
csv_exports/
+-- nasdaq_all_tickers.csv
+-- nasdaq_daily_prices_5yr.csv
+-- nasdaq_fundamentals.csv
+-- nasdaq_dividends.csv
+-- nasdaq_splits.csv
+-- nasdaq_income_statements_annual.csv
+-- nasdaq_income_statements_quarterly.csv
+-- nasdaq_balance_sheets_annual.csv
+-- nasdaq_balance_sheets_quarterly.csv
+-- nasdaq_cash_flow_annual.csv
+-- nasdaq_cash_flow_quarterly.csv
+-- by_ticker/
    +-- {ticker}_daily.csv
    +-- ...
```
