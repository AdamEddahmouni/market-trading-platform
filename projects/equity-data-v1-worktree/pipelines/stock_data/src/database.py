"""
Database schema and operations for NASDAQ Complete Data Pipeline.
Uses SQLAlchemy for ORM and raw SQL for bulk operations.
"""

import sqlalchemy as sa
import re as _re_global_for_engine
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Float,
    DateTime, Date, Text, BigInteger, Boolean, UniqueConstraint, Index,
    inspect,
    event as _sa_event,
)
from sqlalchemy.sql import text
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator
from contextlib import contextmanager
import json
import pandas as pd

from src.config import DATABASE_PATH, PRICE_FIELDS

# Global engine (lazy init)
_engine = None
_metadata = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        db_path = str(DATABASE_PATH)
        _engine = create_engine(
            f"sqlite:///{db_path}?check_same_thread=False",
            echo=False,
            connect_args={"timeout": 30}
        )
        _register_sqlite_functions(_engine)
    return _engine


def _register_sqlite_functions(engine):
    """Register custom SQLite helpers used by SQL generated elsewhere.

     enables  queries —
    stock SQLite has no REGEXP operator, so without this the
     output would raise  at execution time. Delegates to Python's
    . Invalid regex silently evaluates to False.
    """
    @_sa_event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _connection_record):
        def regexp(expr, item):
            if expr is None or item is None:
                return False
            try:
                return bool(_re_global_for_engine.search(expr, item))
            except _re_global_for_engine.error:
                return False
        dbapi_connection.create_function("regexp", 2, regexp, deterministic=True)


def get_metadata():
    """Get or create the metadata object with all table definitions."""
    global _metadata
    if _metadata is None:
        _metadata = define_schema()
    return _metadata


@contextmanager
def get_connection():
    """Context manager for database connections."""
    engine = get_engine()
    conn = engine.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def define_schema() -> MetaData:
    """
    Define the complete database schema with all tables and constraints.
    Returns a SQLAlchemy MetaData object.
    """
    meta = MetaData()

    # -- Tickers Master Table -----------------------------------------
    Table(
        "tickers", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker", String(10), nullable=False, unique=True),
        Column("company_name", String(255)),
        Column("exchange", String(50)),
        Column("sector", String(100)),
        Column("industry", String(100)),
        Column("country", String(100)),
        Column("market_cap", Float),
        Column("ipo_year", Integer),
        Column("is_etf", Boolean, default=False),
        Column("is_active", Boolean, default=True),
        Column("source", String(50)),
        Column("first_seen", DateTime, default=datetime.utcnow),
        Column("last_updated", DateTime, default=datetime.utcnow,
               onupdate=datetime.utcnow),
    )

    # -- Daily Price Data ---------------------------------------------
    Table(
        "daily_prices", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("date", Date, nullable=False),
        Column("open", Float),
        Column("high", Float),
        Column("low", Float),
        Column("close", Float),
        Column("volume", BigInteger),
        Column("adj_close", Float),
        UniqueConstraint("ticker_id", "date", name="uq_daily_price"),
        Index("idx_daily_prices_ticker_date", "ticker_id", "date"),
    )

    # -- Weekly Price Data --------------------------------------------
    Table(
        "weekly_prices", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("week_start", Date, nullable=False),
        Column("open", Float),
        Column("high", Float),
        Column("low", Float),
        Column("close", Float),
        Column("volume", BigInteger),
        Column("adj_close", Float),
        UniqueConstraint("ticker_id", "week_start", name="uq_weekly_price"),
        Index("idx_weekly_prices_ticker_date", "ticker_id", "week_start"),
    )

    # -- Monthly Price Data -------------------------------------------
    Table(
        "monthly_prices", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("month_start", Date, nullable=False),
        Column("open", Float),
        Column("high", Float),
        Column("low", Float),
        Column("close", Float),
        Column("volume", BigInteger),
        Column("adj_close", Float),
        UniqueConstraint("ticker_id", "month_start", name="uq_monthly_price"),
        Index("idx_monthly_prices_ticker_date", "ticker_id", "month_start"),
    )

    # -- Dividends ----------------------------------------------------
    Table(
        "dividends", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("date", Date, nullable=False),
        Column("amount", Float),
        Index("idx_dividends_ticker_date", "ticker_id", "date"),
    )

    # -- Stock Splits -------------------------------------------------
    Table(
        "splits", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("date", Date, nullable=False),
        Column("ratio", Float),
        Column("split_factor", String(20)),
        Index("idx_splits_ticker_date", "ticker_id", "date"),
    )

    # -- Fundamentals Snapshot ----------------------------------------
    Table(
        "fundamentals", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("snapshot_date", Date, nullable=False),
        Column("market_cap", Float),
        Column("enterprise_value", Float),
        Column("trailing_pe", Float),
        Column("forward_pe", Float),
        Column("price_to_book", Float),
        Column("price_to_sales", Float),
        Column("peg_ratio", Float),
        Column("earnings_per_share", Float),
        Column("book_value", Float),
        Column("revenue_per_share", Float),
        Column("profit_margin", Float),
        Column("gross_margin", Float),
        Column("ebitda_margin", Float),
        Column("operating_margin", Float),
        Column("return_on_assets", Float),
        Column("return_on_equity", Float),
        Column("revenue_growth", Float),
        Column("earnings_growth", Float),
        Column("debt_to_equity", Float),
        Column("current_ratio", Float),
        Column("quick_ratio", Float),
        Column("total_debt", Float),
        Column("total_revenue", Float),
        Column("net_income", Float),
        Column("free_cashflow", Float),
        Column("operating_cashflow", Float),
        Column("gross_profit", Float),
        Column("ebitda", Float),
        Column("total_cash", Float),
        Column("total_cash_per_share", Float),
        Column("short_ratio", Float),
        Column("short_percent_float", Float),
        Column("held_percent_institutions", Float),
        Column("held_percent_insiders", Float),
        Column("shares_outstanding", Float),
        Column("shares_float", Float),
        Column("shares_short", Float),
        Column("beta", Float),
        Column("fifty_two_week_high", Float),
        Column("fifty_two_week_low", Float),
        Column("fifty_day_average", Float),
        Column("two_hundred_day_average", Float),
        Column("dividend_rate", Float),
        Column("dividend_yield", Float),
        Column("payout_ratio", Float),
        Column("ex_dividend_date", Date),
        Column("average_volume", BigInteger),
        Column("average_volume_10days", BigInteger),
        Column("bid", Float),
        Column("ask", Float),
        Column("target_mean_price", Float),
        Column("target_high_price", Float),
        Column("target_low_price", Float),
        Column("recommendation_mean", Float),
        Column("number_of_analyst_opinions", Integer),
        UniqueConstraint("ticker_id", "snapshot_date", name="uq_fundamentals"),
        Index("idx_fundamentals_ticker_date", "ticker_id", "snapshot_date"),
    )

    # -- Income Statement (Annual) ------------------------------------
    Table(
        "income_statements_annual", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("fiscal_date", Date, nullable=False),
        Column("total_revenue", Float),
        Column("cost_of_revenue", Float),
        Column("gross_profit", Float),
        Column("operating_expenses", Float),
        Column("operating_income", Float),
        Column("interest_expense", Float),
        Column("income_before_tax", Float),
        Column("income_tax_expense", Float),
        Column("net_income", Float),
        Column("diluted_eps", Float),
        Column("basic_eps", Float),
        Column("weighted_avg_shares", Float),
        Column("ebitda", Float),
        Column("research_development", Float),
        Column("selling_general_admin", Float),
        Column("total_other_income", Float),
        Column("minority_interest", Float),
        Column("net_income_continuing", Float),
        Column("net_income_common", Float),
        UniqueConstraint("ticker_id", "fiscal_date", name="uq_income_annual"),
        Index("idx_income_annual", "ticker_id", "fiscal_date"),
    )

    # -- Income Statement (Quarterly) ---------------------------------
    Table(
        "income_statements_quarterly", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("fiscal_date", Date, nullable=False),
        Column("total_revenue", Float),
        Column("cost_of_revenue", Float),
        Column("gross_profit", Float),
        Column("operating_income", Float),
        Column("net_income", Float),
        Column("diluted_eps", Float),
        Column("basic_eps", Float),
        Column("ebitda", Float),
        Column("research_development", Float),
        Column("selling_general_admin", Float),
        Column("interest_expense", Float),
        Column("income_before_tax", Float),
        Column("income_tax_expense", Float),
        UniqueConstraint("ticker_id", "fiscal_date", name="uq_income_quarterly"),
        Index("idx_income_quarterly", "ticker_id", "fiscal_date"),
    )

    # -- Balance Sheet (Annual) ---------------------------------------
    Table(
        "balance_sheets_annual", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("fiscal_date", Date, nullable=False),
        Column("total_assets", Float),
        Column("total_liabilities", Float),
        Column("total_equity", Float),
        Column("current_assets", Float),
        Column("current_liabilities", Float),
        Column("cash_and_equivalents", Float),
        Column("short_term_investments", Float),
        Column("accounts_receivable", Float),
        Column("inventory", Float),
        Column("property_plant_equipment", Float),
        Column("goodwill", Float),
        Column("intangible_assets", Float),
        Column("long_term_debt", Float),
        Column("short_term_debt", Float),
        Column("total_debt", Float),
        Column("accounts_payable", Float),
        Column("deferred_revenue", Float),
        Column("working_capital", Float),
        Column("retained_earnings", Float),
        Column("treasury_stock", Float),
        Column("common_stock", Float),
        Column("preferred_stock", Float),
        Column("net_tangible_assets", Float),
        UniqueConstraint("ticker_id", "fiscal_date", name="uq_bs_annual"),
        Index("idx_bs_annual", "ticker_id", "fiscal_date"),
    )

    # -- Balance Sheet (Quarterly) ------------------------------------
    Table(
        "balance_sheets_quarterly", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("fiscal_date", Date, nullable=False),
        Column("total_assets", Float),
        Column("total_liabilities", Float),
        Column("total_equity", Float),
        Column("current_assets", Float),
        Column("current_liabilities", Float),
        Column("cash_and_equivalents", Float),
        Column("accounts_receivable", Float),
        Column("inventory", Float),
        Column("property_plant_equipment", Float),
        Column("goodwill", Float),
        Column("long_term_debt", Float),
        Column("short_term_debt", Float),
        Column("total_debt", Float),
        Column("accounts_payable", Float),
        Column("retained_earnings", Float),
        UniqueConstraint("ticker_id", "fiscal_date", name="uq_bs_quarterly"),
        Index("idx_bs_quarterly", "ticker_id", "fiscal_date"),
    )

    # -- Cash Flow Statement (Annual) ---------------------------------
    Table(
        "cash_flow_annual", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("fiscal_date", Date, nullable=False),
        Column("operating_cashflow", Float),
        Column("investing_cashflow", Float),
        Column("financing_cashflow", Float),
        Column("capital_expenditure", Float),
        Column("free_cashflow", Float),
        Column("depreciation_amortization", Float),
        Column("stock_based_compensation", Float),
        Column("dividends_paid", Float),
        Column("debt_issuance", Float),
        Column("debt_repayment", Float),
        Column("common_stock_issued", Float),
        Column("common_stock_repurchased", Float),
        Column("change_in_working_capital", Float),
        Column("change_in_cash", Float),
        Column("beginning_cash", Float),
        Column("ending_cash", Float),
        UniqueConstraint("ticker_id", "fiscal_date", name="uq_cf_annual"),
        Index("idx_cf_annual", "ticker_id", "fiscal_date"),
    )

    # -- Cash Flow Statement (Quarterly) ------------------------------
    Table(
        "cash_flow_quarterly", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("fiscal_date", Date, nullable=False),
        Column("operating_cashflow", Float),
        Column("investing_cashflow", Float),
        Column("financing_cashflow", Float),
        Column("capital_expenditure", Float),
        Column("free_cashflow", Float),
        Column("depreciation_amortization", Float),
        Column("stock_based_compensation", Float),
        Column("dividends_paid", Float),
        Column("change_in_working_capital", Float),
        Column("change_in_cash", Float),
        UniqueConstraint("ticker_id", "fiscal_date", name="uq_cf_quarterly"),
        Index("idx_cf_quarterly", "ticker_id", "fiscal_date"),
    )

    # -- Web Scraped Supplemental Data --------------------------------
    Table(
        "supplemental_data", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("data_type", String(50)),
        Column("source", String(100)),
        Column("data_date", Date),
        Column("data_content", Text),
        Column("url", Text),
        Column("scraped_at", DateTime, default=datetime.utcnow),
        Index("idx_supplemental_ticker_type", "ticker_id", "data_type"),
    )

    # -- Index Membership (S&P 500, Dow Jones, etc.) ------------------
    Table(
        "index_membership", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("index_name", String(50), nullable=False),
        Column("sector", String(100)),
        Column("sub_industry", String(100)),
        Column("date_added", Date),
        Column("cik", String(20)),
        Column("founded", Integer),
        Column("headquarters", String(200)),
        Column("index_weight", Float),
        Column("notes", Text),
        UniqueConstraint("ticker_id", "index_name", name="uq_index_member"),
        Index("idx_index_member_ticker", "ticker_id"),
        Index("idx_index_member_name", "index_name"),
    )

    # -- Options Chain Data --------------------------------------------
    Table(
        "options_chain", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("expiration_date", Date, nullable=False),
        Column("strike", Float, nullable=False),
        Column("option_type", String(4), nullable=False),  # 'call' or 'put'
        Column("last_price", Float),
        Column("bid", Float),
        Column("ask", Float),
        Column("volume", Integer),
        Column("open_interest", Integer),
        Column("implied_volatility", Float),
        Column("delta", Float),
        Column("gamma", Float),
        Column("theta", Float),
        Column("vega", Float),
        Column("scraped_at", DateTime, default=datetime.utcnow),
        UniqueConstraint("ticker_id", "expiration_date", "strike", "option_type",
                         name="uq_options_chain"),
        Index("idx_options_ticker_expiry", "ticker_id", "expiration_date"),
    )

    # -- Insider Trading Data (SEC Form 4) ----------------------------
    Table(
        "insider_trades", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("filing_date", Date, nullable=False),
        Column("transaction_date", Date),
        Column("insider_name", String(200)),
        Column("relationship", String(200)),  # e.g. CEO, CFO, Director, 10% Owner
        Column("transaction_type", String(20)),  # Buy, Sell, Exercise, etc.
        Column("shares_traded", Float),
        Column("price_per_share", Float),
        Column("shares_owned", Float),
        Column("sec_form_type", String(10)),  # Form 4, Form 4/A
        Column("scraped_at", DateTime, default=datetime.utcnow),
        UniqueConstraint("ticker_id", "filing_date", "insider_name", "transaction_date",
                         name="uq_insider_trade"),
        Index("idx_insider_ticker", "ticker_id"),
        Index("idx_insider_filing_date", "filing_date"),
    )

    # -- Earnings Calendar Data ---------------------------------------
    Table(
        "earnings_calendar", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker_id", Integer, nullable=False),
        Column("earnings_date", Date, nullable=False),
        Column("eps_estimate", Float),
        Column("eps_actual", Float),
        Column("eps_surprise", Float),
        Column("revenue_estimate", Float),
        Column("revenue_actual", Float),
        Column("revenue_surprise", Float),
        Column("fiscal_quarter", String(10)),  # e.g., Q1 2024
        Column("scraped_at", DateTime, default=datetime.utcnow),
        UniqueConstraint("ticker_id", "earnings_date", name="uq_earnings_date"),
        Index("idx_earnings_ticker_date", "ticker_id", "earnings_date"),
    )

    # -- Append-only acquisition evidence ----------------------------
    Table(
        "acquisition_attempts", meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("stage", String(50), nullable=False),
        Column("ticker", String(32), nullable=False),
        Column("outcome", String(32), nullable=False),
        Column("started_at", DateTime, nullable=False),
        Column("finished_at", DateTime, nullable=False),
        Column("requested_start", Date),
        Column("requested_end", Date),
        Column("observed_start", Date),
        Column("observed_end", Date),
        Column("detail", Text, nullable=False, default=""),
    )

    return meta


def init_database():
    """Create all tables if they don't exist."""
    meta = get_metadata()
    engine = get_engine()
    meta.create_all(engine)
    print(f"[DB] Database initialized at {DATABASE_PATH}")

    # Enable WAL mode for better concurrent performance
    with get_connection() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))
        conn.execute(text("PRAGMA temp_store=MEMORY"))
        conn.execute(text("PRAGMA mmap_size=268435456"))  # 256MB
        conn.execute(text("PRAGMA cache_size=-32000"))     # 32MB cache
    print("[DB] Performance pragmas set (WAL mode, etc.)")


def get_table(name: str):
    """Get a table object by name."""
    meta = get_metadata()
    if name in meta.tables:
        return meta.tables[name]
    raise KeyError(f"Table '{name}' not found in schema")


def ticker_exists(ticker: str) -> bool:
    """Check if a ticker already exists in the database."""
    with get_connection() as conn:
        result = conn.execute(
            text("SELECT id FROM tickers WHERE ticker = :t"),
            {"t": ticker.upper()}
        ).fetchone()
        return result is not None


def get_ticker_id(ticker: str) -> Optional[int]:
    """Get the database ID for a ticker symbol."""
    with get_connection() as conn:
        result = conn.execute(
            text("SELECT id FROM tickers WHERE ticker = :t"),
            {"t": ticker.upper()}
        ).fetchone()
        return result[0] if result else None


def get_all_ticker_ids() -> List[Dict[str, Any]]:
    """Get all ticker IDs and symbols."""
    with get_connection() as conn:
        rows = conn.execute(
            text("SELECT id, ticker FROM tickers WHERE is_active = 1 ORDER BY ticker")
        ).fetchall()
        return [{"id": r[0], "ticker": r[1]} for r in rows]


def upsert_ticker(ticker: str, **fields) -> int:
    """
    Insert or update a ticker record.
    Returns the ticker ID.
    """
    ticker = ticker.upper()
    with get_connection() as conn:
        existing = conn.execute(
            text("SELECT id FROM tickers WHERE ticker = :t"),
            {"t": ticker}
        ).fetchone()

        if existing:
            ticker_id = existing[0]
            if fields:
                set_parts = []
                params = {"tid": ticker_id}
                for key, val in fields.items():
                    if val is not None:
                        set_parts.append(f"{key} = :{key}")
                        params[key] = val
                if set_parts:
                    set_parts.append("last_updated = datetime('now')")
                    conn.execute(
                        text(f"UPDATE tickers SET {', '.join(set_parts)} WHERE id = :tid"),
                        params
                    )
            return ticker_id
        else:
            fields["ticker"] = ticker
            fields["is_active"] = fields.get("is_active", True)
            fields["first_seen"] = datetime.utcnow()
            fields["last_updated"] = datetime.utcnow()

            cols = ", ".join(fields.keys())
            vals = ", ".join([f":{k}" for k in fields.keys()])
            result = conn.execute(
                text(f"INSERT INTO tickers ({cols}) VALUES ({vals})"),
                fields
            )
            return result.lastrowid


def bulk_insert(table_name: str, records: List[Dict[str, Any]],
                chunk_size: int = 500):
    """
    Bulk insert records into a table. Handles conflicts gracefully.
    Returns (inserted, errors) counts.
    """
    if not records:
        return 0, 0

    inserted = 0
    errors = 0
    table = get_table(table_name)
    engine = get_engine()

    with get_connection() as conn:
        for i in range(0, len(records), chunk_size):
            chunk = records[i:i + chunk_size]
            try:
                conn.execute(table.insert(), chunk)
                inserted += len(chunk)
            except Exception:
                # Try one by one on conflict
                for rec in chunk:
                    try:
                        conn.execute(table.insert(), rec)
                        inserted += 1
                    except Exception:
                        errors += 1

    return inserted, errors


def fast_bulk_insert(table_name: str, df: pd.DataFrame, if_exists: str = "append"):
    """
    Ultra-fast bulk insert using pandas DataFrame.to_sql with multi-row insert.
    10-100x faster than row-by-row inserts.
    """
    if df.empty:
        return 0

    engine = get_engine()
    before = len(df)

    try:
        df.to_sql(
            table_name,
            engine,
            if_exists=if_exists,
            index=False,
            method="multi",
            chunksize=1000,
        )
        return before
    except Exception as e:
        print(f"    [WARN] Batch insert failed: {e}")
        print(f"    Falling back to chunked inserts...")
        # Fallback: smaller chunks
        for i in range(0, len(df), 100):
            chunk = df.iloc[i:i+100]
            try:
                chunk.to_sql(table_name, engine, if_exists=if_exists, index=False, method="multi")
            except Exception:
                # Ultimate fallback: one by one
                for _, row in chunk.iterrows():
                    try:
                        row.to_frame().T.to_sql(table_name, engine, if_exists=if_exists, index=False)
                    except Exception:
                        pass
        return before


def get_ticker_count() -> int:
    """Get total number of tickers in database."""
    with get_connection() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM tickers WHERE is_active = 1")
        ).fetchone()
        return result[0]


def get_data_stats() -> Dict[str, Any]:
    """Get comprehensive statistics about collected data."""
    stats = {}
    tables = [
        "tickers", "daily_prices", "weekly_prices", "monthly_prices",
        "dividends", "splits", "fundamentals",
        "income_statements_annual", "income_statements_quarterly",
        "balance_sheets_annual", "balance_sheets_quarterly",
        "cash_flow_annual", "cash_flow_quarterly",
        "supplemental_data",
        "index_membership",
        "options_chain",
        "insider_trades",
        "earnings_calendar",
    ]
    with get_connection() as conn:
        for table in tables:
            try:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table}")
                ).fetchone()
                stats[table] = result[0]
            except Exception:
                stats[table] = 0

        # Date range of price data
        try:
            result = conn.execute(
                text("SELECT MIN(date), MAX(date) FROM daily_prices")
            ).fetchone()
            stats["price_date_range"] = {
                "min": str(result[0]) if result[0] else None,
                "max": str(result[1]) if result[1] else None,
            }
        except Exception:
            stats["price_date_range"] = {"min": None, "max": None}

    return stats


def get_tickers_for_scraping() -> List[Dict[str, Any]]:
    """Get tickers that haven't been fully scraped yet."""
    with get_connection() as conn:
        rows = conn.execute(text("""
            SELECT t.id, t.ticker
            FROM tickers t
            WHERE t.is_active = 1
            ORDER BY t.ticker
        """)).fetchall()
        return [{"id": r[0], "ticker": r[1]} for r in rows]


def latest_daily_price_dates() -> dict[int, date]:
    """Return the latest stored daily-price date for each instrument."""
    with get_connection() as conn:
        rows = conn.execute(
            text(
                "SELECT ticker_id, MAX(date) AS latest_date "
                "FROM daily_prices GROUP BY ticker_id"
            )
        ).fetchall()
    return {
        int(ticker_id): (
            latest if isinstance(latest, date) else date.fromisoformat(str(latest))
        )
        for ticker_id, latest in rows
        if latest is not None
    }


def save_progress(stage: str, ticker: str, status: str, details: str = ""):
    """Log scraping progress to the progress tracking table."""
    with get_connection() as conn:
        conn.execute(text("""
            INSERT OR REPLACE INTO scraping_progress
            (ticker, stage, status, details, updated_at)
            VALUES (:ticker, :stage, :status, :details, datetime('now'))
        """), {
            "ticker": ticker,
            "stage": stage,
            "status": status,
            "details": details,
        })


def record_attempt(
    stage: str,
    ticker: str,
    outcome: str,
    started_at: datetime,
    finished_at: datetime,
    requested_start: date | None = None,
    requested_end: date | None = None,
    observed_start: date | None = None,
    observed_end: date | None = None,
    detail: str = "",
) -> int:
    """Insert one immutable acquisition-attempt record."""
    with get_connection() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO acquisition_attempts (
                    stage, ticker, outcome, started_at, finished_at,
                    requested_start, requested_end, observed_start, observed_end, detail
                ) VALUES (
                    :stage, :ticker, :outcome, :started_at, :finished_at,
                    :requested_start, :requested_end, :observed_start, :observed_end, :detail
                )
                """
            ),
            {
                "stage": stage,
                "ticker": ticker,
                "outcome": outcome,
                "started_at": started_at,
                "finished_at": finished_at,
                "requested_start": requested_start,
                "requested_end": requested_end,
                "observed_start": observed_start,
                "observed_end": observed_end,
                "detail": detail,
            },
        )
        return int(result.lastrowid)


def latest_attempt(stage: str, ticker: str) -> dict[str, object] | None:
    """Return the most recently inserted attempt for a stage and ticker."""
    with get_connection() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, stage, ticker, outcome, started_at, finished_at,
                       requested_start, requested_end, observed_start, observed_end, detail
                FROM acquisition_attempts
                WHERE stage = :stage AND ticker = :ticker
                ORDER BY id DESC LIMIT 1
                """
            ),
            {"stage": stage, "ticker": ticker},
        ).mappings().first()
        return dict(row) if row is not None else None


def latest_attempts_for_stage(stage: str) -> dict[str, dict[str, object]]:
    """Load the latest attempt for every ticker in a stage with one query."""
    with get_connection() as conn:
        rows = conn.execute(
            text(
                """
                SELECT a.id, a.stage, a.ticker, a.outcome, a.started_at, a.finished_at,
                       a.requested_start, a.requested_end,
                       a.observed_start, a.observed_end, a.detail
                FROM acquisition_attempts AS a
                JOIN (
                    SELECT ticker, MAX(id) AS latest_id
                    FROM acquisition_attempts
                    WHERE stage = :stage
                    GROUP BY ticker
                ) AS latest ON latest.latest_id = a.id
                ORDER BY a.ticker
                """
            ),
            {"stage": stage},
        ).mappings().all()
    return {str(row["ticker"]): dict(row) for row in rows}


def mark_in_progress(stage: str, ticker: str):
    """
    Mark a ticker as 'in_progress' for a stage.
    If the process crashes, this status will be stale.
    On next run, reset_stale_progress() converts these back to pending.
    """
    save_progress(stage, ticker, "in_progress")


def reset_stale_progress(stage: str) -> int:
    """
    Reset any 'in_progress' records (left over from a crash) back to 'pending'
    so they get re-scraped on the next run. Returns count of reset entries.
    """
    with get_connection() as conn:
        result = conn.execute(text("""
            UPDATE scraping_progress
            SET status = 'pending', details = 'reset from crash', updated_at = datetime('now')
            WHERE stage = :stage AND status = 'in_progress'
        """), {"stage": stage})
        return result.rowcount


def ensure_progress_table():
    """Create progress tracking table if not exists."""
    meta = get_metadata()
    if "scraping_progress" not in meta.tables:
        Table(
            "scraping_progress", meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("ticker", String(10), nullable=False),
            Column("stage", String(50), nullable=False),
            Column("status", String(20), default="pending"),
            Column("details", Text),
            Column("updated_at", DateTime, default=datetime.utcnow),
            UniqueConstraint("ticker", "stage", name="uq_progress"),
        )
    engine = get_engine()
    meta.create_all(engine)
