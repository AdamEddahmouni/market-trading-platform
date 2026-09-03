import ast
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from src.ticker_metadata.contract import REQUEST_CONTRACT_SHA256
from src.ticker_metadata.models import CollectorProvenance
from src.ticker_metadata.provider import YFinanceMetadataAdapter
from src.ticker_metadata.runner import MetadataRunner
from src.ticker_metadata.storage import MetadataStore
from src.ui.filter import FilterSpec


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "ticker_metadata"
NOW = datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)


REGISTRY_SQL = """
CREATE TABLE tickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    company_name VARCHAR(255), exchange VARCHAR(50), sector VARCHAR(100),
    industry VARCHAR(100), country VARCHAR(100), market_cap FLOAT,
    is_etf BOOLEAN, is_active BOOLEAN
)
"""


def test_provider_source_contains_only_approved_yfinance_method_boundary():
    tree = ast.parse((PACKAGE / "provider.py").read_text(encoding="utf-8"))
    provider_methods = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    forbidden = {
        "history",
        "get_actions",
        "get_dividends",
        "get_splits",
        "get_financials",
        "get_income_stmt",
        "get_balance_sheet",
        "get_cash_flow",
        "get_recommendations",
        "get_news",
        "option_chain",
        "get_calendar",
    }
    source = (PACKAGE / "provider.py").read_text(encoding="utf-8")
    assert provider_methods.isdisjoint(forbidden)
    assert ".info" not in source
    assert source.count(".get_info()") == 1


def test_metadata_package_has_no_legacy_mutator_or_fundamentals_dependency():
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(PACKAGE.glob("*.py"))
    ).lower()
    for forbidden in (
        "src.scrapers.fundamentals",
        "process_ticker_fundamentals",
        "src.database",
        "upsert_ticker",
        "update tickers",
        "insert into fundamentals",
        "income_statements",
        "balance_sheets",
        "cash_flow_annual",
        "supplemental_data",
    ):
        assert forbidden not in combined


def test_representative_run_changes_only_metadata_tables_and_stores_no_raw_payload(tmp_path):
    path = tmp_path / "market.db"
    with sqlite3.connect(path) as connection:
        connection.execute(REGISTRY_SQL)
        connection.execute(
            "INSERT INTO tickers (id, ticker, company_name, is_active) VALUES (1, 'AAPL', 'Original', 0)"
        )
        for table in (
            "daily_prices",
            "dividends",
            "splits",
            "fundamentals",
            "income_statements_annual",
            "supplemental_data",
            "scraping_progress",
            "acquisition_attempts",
        ):
            connection.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, value TEXT)")
            connection.execute(f"INSERT INTO {table} VALUES (1, 'protected-{table}')")

    protected = (
        "tickers",
        "daily_prices",
        "dividends",
        "splits",
        "fundamentals",
        "income_statements_annual",
        "supplemental_data",
        "scraping_progress",
        "acquisition_attempts",
    )

    def snapshot():
        with sqlite3.connect(path) as connection:
            return {
                table: tuple(connection.execute(f"SELECT * FROM {table} ORDER BY 1"))
                for table in protected
            }

    before = snapshot()
    store = MetadataStore(path)
    store.initialize_schema()
    selected = store.select_tickers(
        FilterSpec(), None, False, REQUEST_CONTRACT_SHA256
    )

    raw_payload = {
        "symbol": "AAPL",
        "shortName": "Apple",
        "exchange": "NMS",
        "quoteType": "EQUITY",
        "longBusinessSummary": "RAW-PAYLOAD-MARKER",
        "website": "https://secret.example/?token=SECRET-QUERY",
        "companyOfficers": [{"name": "SECRET-OFFICER"}],
    }
    adapter = YFinanceMetadataAdapter(
        ticker_factory=lambda symbol: type(
            "Ticker", (), {"get_info": lambda self: raw_payload}
        )(),
        utcnow=lambda: NOW,
    )
    MetadataRunner(
        store,
        adapter,
        CollectorProvenance("abc", False, "3.11.15", "yfinance", "1.6.0"),
        limiter=type("Noop", (), {"wait": lambda self: None})(),
        workers=1,
    ).run(selected)

    assert snapshot() == before
    with sqlite3.connect(path) as connection:
        evidence = "\n".join(
            str(value)
            for table in ("ticker_metadata_attempts", "ticker_metadata_observations")
            for row in connection.execute(f"SELECT * FROM {table}")
            for value in row
            if value is not None
        )
    for forbidden in (
        "RAW-PAYLOAD-MARKER",
        "SECRET-QUERY",
        "SECRET-OFFICER",
        "secret.example",
        "companyOfficers",
    ):
        assert forbidden not in evidence


def test_operator_docs_state_safety_and_live_gates():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    schema = (ROOT / "docs" / "SCHEMA.md").read_text(encoding="utf-8")
    for required in (
        "refresh-ticker-metadata",
        "--database",
        "noncanonical",
        "get_info()",
        "live canary",
    ):
        assert required in readme
    for required in (
        "ticker_metadata_attempts",
        "ticker_metadata_observations",
        "append-only",
        "noncanonical",
    ):
        assert required in schema
