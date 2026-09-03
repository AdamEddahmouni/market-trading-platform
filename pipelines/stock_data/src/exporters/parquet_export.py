"""
Parquet Export - Exports all collected data to Parquet format.
Parquet provides 10-100x compression vs CSV and is ideal for analytics.
"""

import pandas as pd

from src.config import (
    PARQUET_PRICES, PARQUET_FINANCIALS, PARQUET_DIVIDENDS,
    PARQUET_SPLITS, PARQUET_COMPANY_INFO, PARQUET_OPTIONS,
    PARQUET_INSIDER_TRADES, PARQUET_EARNINGS
)
from src.database import get_engine


def query_to_dataframe(query: str) -> pd.DataFrame:
    """Execute a SQL query and return results as a DataFrame."""
    engine = get_engine()
    try:
        return pd.read_sql_query(query, engine)
    except Exception as e:
        print(f"    [WARN] Query failed: {e}")
        return pd.DataFrame()


def export_prices_to_parquet():
    """Export price data to Parquet files, partitioned by ticker."""
    print("\n  [PARQUET] Exporting price data...")

    # Daily prices
    print("  [PARQUET] Daily prices...")
    df = query_to_dataframe("""
        SELECT t.ticker, dp.date, dp.open, dp.high, dp.low,
               dp.close, dp.volume, dp.adj_close
        FROM daily_prices dp
        JOIN tickers t ON t.id = dp.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, dp.date
    """)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        path = PARQUET_PRICES / "daily"
        path.mkdir(exist_ok=True, parents=True)
        df.to_parquet(path / "nasdaq_daily_prices.parquet",
                      index=False, compression='snappy')
        print(f"    Saved {len(df):,} daily price records")

        # Per-ticker partitioning
        for ticker, group in df.groupby('ticker'):
            t_path = path / ticker.lower()
            t_path.mkdir(exist_ok=True, parents=True)
            group.to_parquet(t_path / f"{ticker.lower()}_daily.parquet",
                             index=False, compression='snappy')
        print(f"    Partitioned by {df['ticker'].nunique()} tickers")

    # Weekly prices
    print("  [PARQUET] Weekly prices...")
    df_weekly = query_to_dataframe("""
        SELECT t.ticker, wp.week_start, wp.open, wp.high, wp.low,
               wp.close, wp.volume, wp.adj_close
        FROM weekly_prices wp
        JOIN tickers t ON t.id = wp.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, wp.week_start
    """)
    if not df_weekly.empty:
        df_weekly['week_start'] = pd.to_datetime(df_weekly['week_start'])
        path = PARQUET_PRICES / "weekly"
        path.mkdir(exist_ok=True, parents=True)
        df_weekly.to_parquet(path / "nasdaq_weekly_prices.parquet",
                             index=False, compression='snappy')
        print(f"    Saved {len(df_weekly):,} weekly price records")
        for ticker, group in df_weekly.groupby('ticker'):
            t_path = path / ticker.lower()
            t_path.mkdir(exist_ok=True, parents=True)
            group.to_parquet(t_path / f"{ticker.lower()}_weekly.parquet",
                             index=False, compression='snappy')

    # Monthly prices
    print("  [PARQUET] Monthly prices...")
    df_monthly = query_to_dataframe("""
        SELECT t.ticker, mp.month_start, mp.open, mp.high, mp.low,
               mp.close, mp.volume, mp.adj_close
        FROM monthly_prices mp
        JOIN tickers t ON t.id = mp.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, mp.month_start
    """)
    if not df_monthly.empty:
        df_monthly['month_start'] = pd.to_datetime(df_monthly['month_start'])
        path = PARQUET_PRICES / "monthly"
        path.mkdir(exist_ok=True, parents=True)
        df_monthly.to_parquet(path / "nasdaq_monthly_prices.parquet",
                              index=False, compression='snappy')
        print(f"    Saved {len(df_monthly):,} monthly price records")
        for ticker, group in df_monthly.groupby('ticker'):
            t_path = path / ticker.lower()
            t_path.mkdir(exist_ok=True, parents=True)
            group.to_parquet(t_path / f"{ticker.lower()}_monthly.parquet",
                             index=False, compression='snappy')

    # Dividends
    print("  [PARQUET] Dividends...")
    df_div = query_to_dataframe("""
        SELECT t.ticker, d.date, d.amount
        FROM dividends d
        JOIN tickers t ON t.id = d.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, d.date
    """)
    if not df_div.empty:
        df_div['date'] = pd.to_datetime(df_div['date'])
        path = PARQUET_DIVIDENDS
        path.mkdir(exist_ok=True, parents=True)
        df_div.to_parquet(path / "nasdaq_dividends.parquet",
                          index=False, compression='snappy')
        print(f"    Saved {len(df_div):,} dividend records")
        for ticker, group in df_div.groupby('ticker'):
            group.to_parquet(path / f"{ticker.lower()}_dividends.parquet",
                             index=False, compression='snappy')

    # Splits
    print("  [PARQUET] Stock splits...")
    df_splits = query_to_dataframe("""
        SELECT t.ticker, s.date, s.ratio, s.split_factor
        FROM splits s
        JOIN tickers t ON t.id = s.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, s.date
    """)
    if not df_splits.empty:
        df_splits['date'] = pd.to_datetime(df_splits['date'])
        path = PARQUET_SPLITS
        path.mkdir(exist_ok=True, parents=True)
        df_splits.to_parquet(path / "nasdaq_splits.parquet",
                             index=False, compression='snappy')
        print(f"    Saved {len(df_splits):,} split records")


def export_financials_to_parquet():
    """Export financial statements to Parquet."""
    print("\n  [PARQUET] Exporting financial statements...")

    tables = [
        ("income_statements_annual", "income_statements_annual"),
        ("income_statements_quarterly", "income_statements_quarterly"),
        ("balance_sheets_annual", "balance_sheets_annual"),
        ("balance_sheets_quarterly", "balance_sheets_quarterly"),
        ("cash_flow_annual", "cash_flow_annual"),
        ("cash_flow_quarterly", "cash_flow_quarterly"),
    ]

    for table_name, file_prefix in tables:
        print(f"  [PARQUET] {table_name}...")
        df = query_to_dataframe(f"""
            SELECT t.ticker, fs.*
            FROM {table_name} fs
            JOIN tickers t ON t.id = fs.ticker_id
            WHERE t.is_active = 1
            ORDER BY t.ticker, fs.fiscal_date DESC
        """)
        if not df.empty:
            df = df.drop(columns=['id', 'ticker_id'], errors='ignore')
            df['fiscal_date'] = pd.to_datetime(df['fiscal_date'])
            path = PARQUET_FINANCIALS / table_name
            path.mkdir(exist_ok=True, parents=True)
            df.to_parquet(path / f"nasdaq_{file_prefix}.parquet",
                          index=False, compression='snappy')
            print(f"    Saved {len(df):,} records")


def export_fundamentals_to_parquet():
    """Export fundamentals data to Parquet."""
    print("\n  [PARQUET] Exporting fundamentals...")

    # Fundamentals snapshot
    df = query_to_dataframe("""
        SELECT t.ticker, f.*
        FROM fundamentals f
        JOIN tickers t ON t.id = f.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker
    """)
    if not df.empty:
        df = df.drop(columns=['id', 'ticker_id'], errors='ignore')
        df['snapshot_date'] = pd.to_datetime(df['snapshot_date'])
        path = PARQUET_FINANCIALS / "fundamentals"
        path.mkdir(exist_ok=True, parents=True)
        df.to_parquet(path / "nasdaq_fundamentals.parquet",
                      index=False, compression='snappy')
        print(f"    Saved {len(df):,} fundamentals records")

    # Company info
    print("  [PARQUET] Company info...")
    df_info = query_to_dataframe("""
        SELECT ticker, company_name, exchange, sector, industry,
               country, market_cap, is_etf, is_active
        FROM tickers
        WHERE is_active = 1
        ORDER BY ticker
    """)
    if not df_info.empty:
        PARQUET_COMPANY_INFO.mkdir(exist_ok=True, parents=True)
        df_info.to_parquet(PARQUET_COMPANY_INFO / "nasdaq_company_info.parquet",
                           index=False, compression='snappy')
        print(f"    Saved {len(df_info):,} company records")

    # Supplemental data
    print("  [PARQUET] Supplemental data...")
    df_supp = query_to_dataframe("""
        SELECT t.ticker, s.data_type, s.source, s.data_date,
               s.data_content, s.url, s.scraped_at
        FROM supplemental_data s
        JOIN tickers t ON t.id = s.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, s.data_type
    """)
    if not df_supp.empty:
        path = PARQUET_FINANCIALS / "supplemental"
        path.mkdir(exist_ok=True, parents=True)
        df_supp.to_parquet(path / "nasdaq_supplemental.parquet",
                           index=False, compression='snappy')
        print(f"    Saved {len(df_supp):,} supplemental records")


def export_options_to_parquet():
    """Export options chain data to Parquet."""
    print("\n  [PARQUET] Options chain...")
    df = query_to_dataframe("""
        SELECT t.ticker, oc.expiration_date, oc.strike, oc.option_type,
               oc.last_price, oc.bid, oc.ask, oc.volume, oc.open_interest,
               oc.implied_volatility, oc.delta, oc.gamma, oc.theta, oc.vega
        FROM options_chain oc
        JOIN tickers t ON t.id = oc.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, oc.expiration_date, oc.strike
    """)
    if not df.empty:
        df['expiration_date'] = pd.to_datetime(df['expiration_date'])
        PARQUET_OPTIONS.mkdir(exist_ok=True, parents=True)
        df.to_parquet(PARQUET_OPTIONS / "nasdaq_options_chain.parquet",
                      index=False, compression='snappy')
        print(f"    Saved {len(df):,} option records")


def export_insider_trades_to_parquet():
    """Export insider trading data to Parquet."""
    print("\n  [PARQUET] Insider trades...")
    df = query_to_dataframe("""
        SELECT t.ticker, it.filing_date, it.transaction_date,
               it.insider_name, it.relationship, it.transaction_type,
               it.shares_traded, it.price_per_share, it.shares_owned
        FROM insider_trades it
        JOIN tickers t ON t.id = it.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, it.filing_date DESC
    """)
    if not df.empty:
        for col in ['filing_date', 'transaction_date']:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        PARQUET_INSIDER_TRADES.mkdir(exist_ok=True, parents=True)
        df.to_parquet(PARQUET_INSIDER_TRADES / "nasdaq_insider_trades.parquet",
                      index=False, compression='snappy')
        print(f"    Saved {len(df):,} insider trade records")


def export_earnings_to_parquet():
    """Export earnings calendar data to Parquet."""
    print("\n  [PARQUET] Earnings calendar...")
    df = query_to_dataframe("""
        SELECT t.ticker, ec.earnings_date, ec.eps_estimate, ec.eps_actual,
               ec.eps_surprise, ec.revenue_estimate, ec.revenue_actual,
               ec.revenue_surprise, ec.fiscal_quarter
        FROM earnings_calendar ec
        JOIN tickers t ON t.id = ec.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, ec.earnings_date DESC
    """)
    if not df.empty:
        df['earnings_date'] = pd.to_datetime(df['earnings_date'])
        PARQUET_EARNINGS.mkdir(exist_ok=True, parents=True)
        df.to_parquet(PARQUET_EARNINGS / "nasdaq_earnings_calendar.parquet",
                      index=False, compression='snappy')
        print(f"    Saved {len(df):,} earnings records")


def export_new_data_to_parquet():
    """Export all new data types to Parquet."""
    export_options_to_parquet()
    export_insider_trades_to_parquet()
    export_earnings_to_parquet()


if __name__ == "__main__":
    export_prices_to_parquet()
    export_financials_to_parquet()
    export_fundamentals_to_parquet()
    export_new_data_to_parquet()
