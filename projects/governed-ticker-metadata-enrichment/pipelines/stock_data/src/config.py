"""
Configuration module for NASDAQ + NYSE Multi-Exchange Data Pipeline.
Centralizes all settings, paths, and constants.
"""

import os
from pathlib import Path

# Project root (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# ── Data Directory (separate from source code) ─────────────────
DATA_DIR = PROJECT_ROOT / "data"

# Database
DATABASE_DIR = DATA_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "market_data.db"

# Exports
PARQUET_DIR = DATA_DIR / "parquet"
CSV_EXPORT_DIR = DATA_DIR / "csv_exports"

# Metadata
METADATA_DIR = DATA_DIR / "metadata"

# Docs
DOCS_DIR = PROJECT_ROOT / "docs"

# Ensure directories exist
for d in [DATABASE_DIR, PARQUET_DIR, CSV_EXPORT_DIR, METADATA_DIR, DOCS_DIR]:
    d.mkdir(exist_ok=True, parents=True)

# Parquet subdirectories
PARQUET_PRICES = PARQUET_DIR / "prices"
PARQUET_FINANCIALS = PARQUET_DIR / "financials"
PARQUET_DIVIDENDS = PARQUET_DIR / "dividends"
PARQUET_SPLITS = PARQUET_DIR / "splits"
PARQUET_COMPANY_INFO = PARQUET_DIR / "financials" / "company_info"
PARQUET_OPTIONS = PARQUET_DIR / "options"
PARQUET_INSIDER_TRADES = PARQUET_DIR / "insider_trades"
PARQUET_EARNINGS = PARQUET_DIR / "earnings"
for d in [PARQUET_PRICES, PARQUET_FINANCIALS, PARQUET_DIVIDENDS,
          PARQUET_SPLITS, PARQUET_COMPANY_INFO, PARQUET_OPTIONS,
          PARQUET_INSIDER_TRADES, PARQUET_EARNINGS]:
    d.mkdir(exist_ok=True, parents=True)

# Metadata files
TICKER_LIST_PATH = METADATA_DIR / "all_tickers.json"
PROGRESS_PATH = METADATA_DIR / "progress.json"
ERRORS_PATH = METADATA_DIR / "errors.json"

# ── Scraping Configuration ─────────────────────────────────────
REQUEST_DELAY = 0.0           # No artificial delay - yfinance handles rate limiting
MAX_RETRIES = 3               # Max retries per ticker
REQUEST_TIMEOUT = 60          # HTTP request timeout in seconds
CONCURRENT_WORKERS = 30       # Number of parallel workers for scraping (I/O-bound)
PRICE_BATCH_SIZE = 50         # Tickers per yf.download() batch
PROGRESS_BATCH_SIZE = 500     # Save progress every N tickers

# Yahoo Finance periods
MAX_HISTORY_PERIOD = "max"   # Get all available historical data

# ── Stealth Scraping Configuration ─────────────────────────────
STEALTH_CONFIG = {
    "min_delay": 0.5,            # Minimum delay between requests to same domain (seconds)
    "max_delay": 3.0,            # Maximum jitter delay
    "max_retries": 3,            # Max retries per request
    "retry_backoff": 2.0,        # Exponential backoff multiplier
    "rotate_user_agents": True,  # Rotate User-Agent on each request
    "rotate_proxies": False,     # Rotate proxies (requires proxy list)
    "browser_impersonate": True, # Use curl_cffi browser impersonation
    "impersonate_browser": "chrome124",
    "verify_ssl": True,          # Verify SSL certificates
    "respect_robots_txt": False, # Respect robots.txt (disabled for data collection)
}

# ── Exchange Names & Codes ─────────────────────────────────────
EXCHANGE_NAMES = {
    "NASDAQ": "NASDAQ",
    "NYSE": "NYSE",
    "NYSE_AMERICAN": "NYSE American",
    "NYSE_ARCA": "NYSE Arca",
    "BATS": "BATS",
    "IEX": "IEX",
}

# NASDAQ Trader exchange code mapping
EXCHANGE_CODES = {
    "N": "NYSE",
    "A": "NYSE American",
    "P": "NYSE Arca",
    "Z": "BATS",
    "V": "IEX",
    "Q": "NASDAQ",
    "M": "OTHER",
}

# URL sources for ticker data
TICKER_URLS = {
    "nasdaq_trader": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "other_listed": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
}

# SEC EDGAR configuration
SEC_EDGAR_BASE = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
SEC_RATE_LIMIT = 10  # seconds between SEC requests (they enforce this)

# Data collection scope
INCLUDE_ETF = False
INCLUDE_PINK_SHEETS = False
MIN_MARKET_CAP = 0

# Fields to collect per category
PRICE_FIELDS = ["Open", "High", "Low", "Close", "Volume", "Adj Close"]

FUNDAMENTAL_FIELDS = [
    "marketCap", "enterpriseValue", "trailingPE", "forwardPE",
    "priceToBook", "priceToSalesTrailing12Months", "pegRatio",
    "earningsPerShare", "bookValue", "revenuePerShare",
    "profitMargins", "grossMargins", "ebitdaMargins",
    "operatingMargins", "returnOnAssets", "returnOnEquity",
    "revenueGrowth", "earningsGrowth", "debtToEquity",
    "currentRatio", "quickRatio", "totalDebt", "totalRevenue",
    "revenueQuarterlyGrowth", "netIncomeToCommon",
    "freeCashflow", "operatingCashflow", "grossProfit",
    "ebitda", "totalCash", "totalCashPerShare",
    "shortRatio", "shortPercentOfFloat", "heldPercentInstitutions",
    "heldPercentInsiders", "sharesOutstanding", "sharesFloat",
    "sharesShort", "sharesShortPriorMonth",
    "beta", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
    "fiftyDayAverage", "twoHundredDayAverage",
    "dividendRate", "dividendYield", "payoutRatio",
    "exDividendDate", "lastDividendDate", "lastDividendValue",
    "averageVolume", "averageVolume10days",
    "bid", "ask", "bidSize", "askSize",
    "dayLow", "dayHigh", "regularMarketPreviousClose",
    "regularMarketOpen", "regularMarketDayLow", "regularMarketDayHigh",
    "regularMarketVolume", "regularMarketPrice",
    "targetMeanPrice", "targetHighPrice", "targetLowPrice",
    "recommendationMean", "recommendationKey",
    "numberOfAnalystOpinions",
    "sector", "industry", "country",
    "longBusinessSummary", "website",
]

FINANCIAL_STMT_FIELDS = {
    "income_statement": [
        "Total Revenue", "Cost of Revenue", "Gross Profit",
        "Operating Expenses", "Operating Income", "Interest Expense",
        "Income Before Tax", "Income Tax Expense", "Net Income",
        "Diluted EPS", "Basic EPS", "Weighted Average Shares",
        "EBITDA", "Research and Development", "Selling General and Administrative",
        "Other Operating Expenses", "Total Operating Income",
        "Other Income/Expenses", "Pretax Income", "Net Income from Continuing Operations",
        "Net Income from Discontinued Operations", "Minority Interest",
        "Total Other Income/Expenses Net",
        "Extraordinary Items", "Effect of Accounting Charges",
        "Net Income Applicable to Common Shares",
    ],
    "balance_sheet": [
        "Total Assets", "Total Liabilities", "Total Equity",
        "Current Assets", "Current Liabilities", "Cash and Cash Equivalents",
        "Short Term Investments", "Accounts Receivable", "Inventory",
        "Property Plant and Equipment", "Goodwill", "Intangible Assets",
        "Long Term Debt", "Short Term Debt", "Total Debt",
        "Accounts Payable", "Deferred Revenue",
        "Other Current Assets", "Other Current Liabilities",
        "Other Non-Current Assets", "Other Non-Current Liabilities",
        "Net Tangible Assets", "Working Capital",
        "Capital Surplus", "Retained Earnings", "Treasury Stock",
        "Common Stock", "Preferred Stock",
        "Accumulated Other Comprehensive Income",
        "Total Stockholders Equity",
    ],
    "cash_flow": [
        "Operating Cash Flow", "Investing Cash Flow", "Financing Cash Flow",
        "Capital Expenditure", "Free Cash Flow", "Depreciation and Amortization",
        "Stock Based Compensation", "Change in Accounts Receivable",
        "Change in Inventory", "Change in Accounts Payable",
        "Change in Working Capital", "Dividends Paid",
        "Purchase of Investments", "Sale of Investments",
        "Purchase of Property Plant and Equipment",
        "Debt Issuance", "Debt Repayment",
        "Common Stock Issued", "Common Stock Repurchased",
        "Net Borrowings", "Other Financing Activities",
        "Other Investing Activities", "Effect of Exchange Rate Changes",
        "Change in Cash and Cash Equivalents",
        "Beginning Cash Position", "Ending Cash Position",
    ]
}
