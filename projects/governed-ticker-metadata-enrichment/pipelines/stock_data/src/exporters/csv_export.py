"""
CSV Export - Exports all collected data to CSV format.
Provides full exports as well as per-ticker partitioned CSVs.
"""

import pandas as pd

from src.config import CSV_EXPORT_DIR
from src.database import get_engine


def query_to_dataframe(query: str) -> pd.DataFrame:
    """Execute a SQL query and return results as a DataFrame."""
    engine = get_engine()
    try:
        return pd.read_sql_query(query, engine)
    except Exception as e:
        print(f"    [WARN] Query failed: {e}")
        return pd.DataFrame()


def export_all_to_csv():
    """Export all data to CSV files."""
    print("\n  [CSV] Exporting data to CSV...")

    export_path = CSV_EXPORT_DIR
    export_path.mkdir(exist_ok=True, parents=True)

    # Ticker master list
    print("  [CSV] Ticker master list...")
    df_tickers = query_to_dataframe("""
        SELECT ticker, company_name, exchange, sector, industry,
               country, market_cap, is_etf, is_active
        FROM tickers
        ORDER BY ticker
    """)
    if not df_tickers.empty:
        df_tickers.to_csv(export_path / "nasdaq_all_tickers.csv", index=False)
        print(f"    Saved {len(df_tickers):,} tickers")

    # Daily prices (limited to most recent 5 years for manageability)
    print("  [CSV] Daily prices (most recent 5 years)...")
    df = query_to_dataframe("""
        SELECT t.ticker, dp.date, dp.open, dp.high, dp.low,
               dp.close, dp.volume, dp.adj_close
        FROM daily_prices dp
        JOIN tickers t ON t.id = dp.ticker_id
        WHERE t.is_active = 1
          AND dp.date >= date('now', '-5 years')
        ORDER BY t.ticker, dp.date
    """)
    if not df.empty:
        csv_path = export_path / "nasdaq_daily_prices_5yr.csv"
        df.to_csv(csv_path, index=False)
        size_mb = csv_path.stat().st_size / (1024 * 1024)
        print(f"    Saved {len(df):,} records ({size_mb:.1f} MB)")

    # Per-ticker full daily prices
    print("  [CSV] Per-ticker price data...")
    ticker_dir = export_path / "by_ticker"
    ticker_dir.mkdir(exist_ok=True)

    df_all_prices = query_to_dataframe("""
        SELECT t.ticker, dp.date, dp.open, dp.high, dp.low,
               dp.close, dp.volume, dp.adj_close
        FROM daily_prices dp
        JOIN tickers t ON t.id = dp.ticker_id
        WHERE t.is_active = 1
        ORDER BY dp.date
    """)
    if not df_all_prices.empty:
        for ticker, group in df_all_prices.groupby('ticker'):
            group.to_csv(ticker_dir / f"{ticker.lower()}_daily.csv", index=False)
        print(f"    Exported {df_all_prices['ticker'].nunique()} ticker CSVs")

    # Fundamentals
    print("  [CSV] Fundamentals...")
    df_fund = query_to_dataframe("""
        SELECT t.ticker, f.*
        FROM fundamentals f
        JOIN tickers t ON t.id = f.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker
    """)
    if not df_fund.empty:
        df_fund = df_fund.drop(columns=['id', 'ticker_id'], errors='ignore')
        df_fund.to_csv(export_path / "nasdaq_fundamentals.csv", index=False)
        print(f"    Saved {len(df_fund):,} records")

    # Dividends
    print("  [CSV] Dividends...")
    df_div = query_to_dataframe("""
        SELECT t.ticker, d.date, d.amount
        FROM dividends d
        JOIN tickers t ON t.id = d.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, d.date
    """)
    if not df_div.empty:
        df_div.to_csv(export_path / "nasdaq_dividends.csv", index=False)
        print(f"    Saved {len(df_div):,} dividend records")

    # Splits
    print("  [CSV] Splits...")
    df_splits = query_to_dataframe("""
        SELECT t.ticker, s.date, s.ratio, s.split_factor
        FROM splits s
        JOIN tickers t ON t.id = s.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, s.date
    """)
    if not df_splits.empty:
        df_splits.to_csv(export_path / "nasdaq_splits.csv", index=False)
        print(f"    Saved {len(df_splits):,} split records")

    # Financial statements
    print("  [CSV] Financial statements...")
    for table_name in [
        "income_statements_annual", "income_statements_quarterly",
        "balance_sheets_annual", "balance_sheets_quarterly",
        "cash_flow_annual", "cash_flow_quarterly",
    ]:
        df = query_to_dataframe(f"""
            SELECT t.ticker, fs.*
            FROM {table_name} fs
            JOIN tickers t ON t.id = fs.ticker_id
            WHERE t.is_active = 1
            ORDER BY t.ticker, fs.fiscal_date DESC
        """)
        if not df.empty:
            df = df.drop(columns=['id', 'ticker_id'], errors='ignore')
            df.to_csv(export_path / f"nasdaq_{table_name}.csv", index=False)
            print(f"    {table_name}: {len(df):,} records")

    # Options chain
    print("  [CSV] Options chain...")
    df_opt = query_to_dataframe("""
        SELECT t.ticker, oc.expiration_date, oc.strike, oc.option_type,
               oc.last_price, oc.bid, oc.ask, oc.volume, oc.open_interest,
               oc.implied_volatility, oc.delta, oc.gamma, oc.theta, oc.vega
        FROM options_chain oc
        JOIN tickers t ON t.id = oc.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, oc.expiration_date, oc.strike
    """)
    if not df_opt.empty:
        df_opt.to_csv(export_path / "nasdaq_options_chain.csv", index=False)
        print(f"    Saved {len(df_opt):,} option records")

    # Insider trades
    print("  [CSV] Insider trades...")
    df_ins = query_to_dataframe("""
        SELECT t.ticker, it.filing_date, it.transaction_date,
               it.insider_name, it.relationship, it.transaction_type,
               it.shares_traded, it.price_per_share, it.shares_owned
        FROM insider_trades it
        JOIN tickers t ON t.id = it.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, it.filing_date DESC
    """)
    if not df_ins.empty:
        df_ins.to_csv(export_path / "nasdaq_insider_trades.csv", index=False)
        print(f"    Saved {len(df_ins):,} insider trade records")

    # Earnings calendar
    print("  [CSV] Earnings calendar...")
    df_ern = query_to_dataframe("""
        SELECT t.ticker, ec.earnings_date, ec.eps_estimate, ec.eps_actual,
               ec.eps_surprise, ec.revenue_estimate, ec.revenue_actual,
               ec.revenue_surprise, ec.fiscal_quarter
        FROM earnings_calendar ec
        JOIN tickers t ON t.id = ec.ticker_id
        WHERE t.is_active = 1
        ORDER BY t.ticker, ec.earnings_date DESC
    """)
    if not df_ern.empty:
        df_ern.to_csv(export_path / "nasdaq_earnings_calendar.csv", index=False)
        print(f"    Saved {len(df_ern):,} earnings records")

    print("  [CSV] Export complete!")


if __name__ == "__main__":
    export_all_to_csv()
