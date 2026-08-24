"""
Ultra-Fast Fundamentals & Financial Statements Scraper.
Uses parallel ThreadPoolExecutor workers for maximum throughput.
Each ticker's ~7 internal yfinance calls run in parallel across workers.
Resume-from-crash with graceful shutdown support.
"""

import time
from datetime import date
from typing import Optional, Dict, Any, List, Tuple

import yfinance as yf
import pandas as pd
import numpy as np

from src.config import MAX_RETRIES
from src.database import (
    fast_bulk_insert,
    get_connection
)
from src.scrapers.base import BaseScraper
from sqlalchemy.sql import text


# ── Pure Helper Functions (stateless) ──────────────────────────

def fetch_fundamentals(ticker: str) -> Optional[Dict[str, Any]]:
    """Fetch fundamentals for a single ticker."""
    for attempt in range(MAX_RETRIES):
        try:
            obj = yf.Ticker(ticker)
            return {
                "ticker": ticker,
                "info": obj.info,
                "income_stmt": obj.income_stmt,
                "income_stmt_q": obj.quarterly_income_stmt,
                "balance_sheet": obj.balance_sheet,
                "balance_sheet_q": obj.quarterly_balance_sheet,
                "cash_flow": obj.cash_flow,
                "cash_flow_q": obj.quarterly_cash_flow,
            }
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.3)
            else:
                return None


def _update_company_info(ticker_id: int, info: Dict):
    """Update ticker record with company info from yfinance."""
    with get_connection() as conn:
        set_parts = ["last_updated = datetime('now')"]
        params = {"tid": ticker_id}
        for db_key, yf_key in [
            ("company_name", "longName"), ("sector", "sector"),
            ("industry", "industry"), ("country", "country"),
            ("market_cap", "marketCap"),
        ]:
            val = info.get(yf_key)
            if val is not None:
                set_parts.append(f"{db_key} = :{db_key}")
                params[db_key] = val
        if len(set_parts) > 1:
            conn.execute(
                text(f"UPDATE tickers SET {', '.join(set_parts)} WHERE id = :tid"),
                params
            )


def _store_fundamentals_snapshot(ticker_id: int, info: Dict):
    """Store fundamentals snapshot as a single row."""
    snapshot = date.today()
    FUND_MAP = {
        "market_cap": "marketCap", "enterprise_value": "enterpriseValue",
        "trailing_pe": "trailingPE", "forward_pe": "forwardPE",
        "price_to_book": "priceToBook", "price_to_sales": "priceToSalesTrailing12Months",
        "peg_ratio": "pegRatio", "earnings_per_share": "trailingEps",
        "book_value": "bookValue", "profit_margin": "profitMargins",
        "gross_margin": "grossMargins", "ebitda_margin": "ebitdaMargins",
        "operating_margin": "operatingMargins", "return_on_assets": "returnOnAssets",
        "return_on_equity": "returnOnEquity", "revenue_growth": "revenueGrowth",
        "earnings_growth": "earningsGrowth", "debt_to_equity": "debtToEquity",
        "current_ratio": "currentRatio", "quick_ratio": "quickRatio",
        "total_debt": "totalDebt", "total_revenue": "totalRevenue",
        "net_income": "netIncomeToCommon", "free_cashflow": "freeCashflow",
        "operating_cashflow": "operatingCashflow", "gross_profit": "grossProfit",
        "ebitda": "ebitda", "total_cash": "totalCash",
        "beta": "beta", "fifty_two_week_high": "fiftyTwoWeekHigh",
        "fifty_two_week_low": "fiftyTwoWeekLow", "dividend_yield": "dividendYield",
        "shares_outstanding": "sharesOutstanding",
        "average_volume": "averageVolume", "target_mean_price": "targetMeanPrice",
        "recommendation_mean": "recommendationMean",
        "number_of_analyst_opinions": "numberOfAnalystOpinions",
    }
    record = {"ticker_id": ticker_id, "snapshot_date": snapshot}
    for db_key, yf_key in FUND_MAP.items():
        val = info.get(yf_key)
        if val is not None and not (isinstance(val, float) and np.isnan(val)):
            if isinstance(val, date):
                record[db_key] = val
            elif isinstance(val, (int, float)):
                record[db_key] = float(val)
    df = pd.DataFrame([record])
    fast_bulk_insert("fundamentals", df)


def _store_financial_stmt(ticker_id: int, stmt_df: pd.DataFrame, table_name: str):
    """Store a financial statement as a DataFrame batch."""
    if stmt_df is None or stmt_df.empty:
        return
    records = []
    for col in stmt_df.columns:
        fiscal_date = col
        if hasattr(fiscal_date, 'tz') and fiscal_date.tz is not None:
            fiscal_date = fiscal_date.tz_localize(None)
        fiscal_date = fiscal_date.date() if hasattr(fiscal_date, 'date') else fiscal_date
        row = {"ticker_id": ticker_id, "fiscal_date": fiscal_date}
        mapping = _get_mapping(table_name)
        for label, value in stmt_df[col].items():
            if label in mapping:
                safe = _safe_float(value)
                if safe is not None:
                    row[mapping[label]] = safe
        records.append(row)
    if records:
        df = pd.DataFrame(records)
        fast_bulk_insert(table_name, df)


def _get_mapping(table_name: str) -> Dict[str, str]:
    """Map yfinance financial statement labels to DB column names."""
    common = {
        "Total Revenue": "total_revenue", "Cost of Revenue": "cost_of_revenue",
        "Gross Profit": "gross_profit", "Operating Income": "operating_income",
        "Net Income": "net_income", "EBITDA": "ebitda",
        "Research and Development": "research_development",
        "Selling General and Administrative": "selling_general_admin",
        "Selling, General and Administrative": "selling_general_admin",
        "Interest Expense": "interest_expense",
        "Income Before Tax": "income_before_tax",
        "Income Tax Expense": "income_tax_expense",
        "Diluted EPS": "diluted_eps", "Basic EPS": "basic_eps",
    }
    if "income" in table_name:
        return {**common, "Weighted Average Shares": "weighted_avg_shares",
                "Operating Expense": "operating_expenses"}
    if "balance" in table_name:
        return {
            "Total Assets": "total_assets", "Total Liabilities Net Minority Interest": "total_liabilities",
            "Total Liabilities": "total_liabilities", "Stockholders Equity": "total_equity",
            "Total Equity Gross Minority Interest": "total_equity", "Current Assets": "current_assets",
            "Current Liabilities": "current_liabilities", "Cash and Cash Equivalents": "cash_and_equivalents",
            "Short Term Investments": "short_term_investments", "Accounts Receivable": "accounts_receivable",
            "Inventory": "inventory", "Property Plant and Equipment": "property_plant_equipment",
            "Goodwill": "goodwill", "Long Term Debt": "long_term_debt",
            "Short Term Debt": "short_term_debt", "Total Debt": "total_debt",
            "Accounts Payable": "accounts_payable", "Retained Earnings": "retained_earnings",
            "Working Capital": "working_capital",
        }
    if "cash_flow" in table_name or "cf_" in table_name:
        return {
            "Operating Cash Flow": "operating_cashflow", "Cash Flow from Operations": "operating_cashflow",
            "Investing Cash Flow": "investing_cashflow", "Financing Cash Flow": "financing_cashflow",
            "Capital Expenditure": "capital_expenditure", "Free Cash Flow": "free_cashflow",
            "Depreciation and Amortization": "depreciation_amortization",
            "Stock Based Compensation": "stock_based_compensation", "Dividends Paid": "dividends_paid",
            "Common Stock Repurchased": "common_stock_repurchased",
            "Change In Working Capital": "change_in_working_capital",
            "Change in Cash and Cash Equivalents": "change_in_cash",
            "Beginning Cash Position": "beginning_cash", "Ending Cash Position": "ending_cash",
        }
    return common


def _safe_float(val) -> Optional[float]:
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return None
        return float(val)
    except (ValueError, TypeError):
        return None


def process_ticker_fundamentals(ticker: str, ticker_id: int) -> bool:
    """Fetch and store all fundamentals for one ticker. Used by both class and pipeline."""
    data = fetch_fundamentals(ticker)
    if data is None:
        return False

    info = data["info"]
    if not info:
        return False

    _update_company_info(ticker_id, info)
    _store_fundamentals_snapshot(ticker_id, info)
    _store_financial_stmt(ticker_id, data["income_stmt"], "income_statements_annual")
    _store_financial_stmt(ticker_id, data["income_stmt_q"], "income_statements_quarterly")
    _store_financial_stmt(ticker_id, data["balance_sheet"], "balance_sheets_annual")
    _store_financial_stmt(ticker_id, data["balance_sheet_q"], "balance_sheets_quarterly")
    _store_financial_stmt(ticker_id, data["cash_flow"], "cash_flow_annual")
    _store_financial_stmt(ticker_id, data["cash_flow_q"], "cash_flow_quarterly")

    return True


# ── BaseScraper Subclass ───────────────────────────────────────

class FundamentalsScraper(BaseScraper):
    """Fundamentals & financial statements scraper using BaseScraper infrastructure."""

    def __init__(self):
        super().__init__(stage="fundamentals", name="FUNDAMENTALS")

    def _process_single(self, item: dict) -> bool:
        """Process a single ticker's fundamentals."""
        return process_ticker_fundamentals(item["ticker"], item["id"])


# ── Convenience Entry Point ────────────────────────────────────

def run_fundamentals_scraper(retry_errored: bool = False, ticker_filter=None):
    """Run fundamentals scraper (convenience wrapper)."""
    scraper = FundamentalsScraper()
    if ticker_filter is not None:
        scraper._ticker_filter = ticker_filter
    try:
        scraper.run(retry_errored=retry_errored)
    finally:
        scraper.cleanup()


if __name__ == "__main__":
    from src.database import init_database
    init_database()
    run_fundamentals_scraper()
