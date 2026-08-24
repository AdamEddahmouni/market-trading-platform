from __future__ import annotations

import sqlite3
import json
import re
from contextlib import closing
from pathlib import Path

from src.acquisition import AcquisitionOutcome
from src.ticker_metadata.models import (
    AttemptRecord,
    ObservationRecord,
    PreflightSummary,
    Selection,
    TickerRef,
    WriteReceipt,
)


SQLITE_HEADER = b"SQLite format 3\x00"
REQUIRED_REGISTRY_COLUMNS = (
    "id",
    "ticker",
    "company_name",
    "exchange",
    "sector",
    "industry",
    "country",
    "market_cap",
    "is_etf",
    "is_active",
)

ATTEMPTS_TABLE_SQL = """
CREATE TABLE ticker_metadata_attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    raw_ticker_id INTEGER NOT NULL REFERENCES tickers(id),
    requested_symbol TEXT NOT NULL,
    provider TEXT NOT NULL,
    method TEXT NOT NULL,
    request_contract_json TEXT NOT NULL,
    request_contract_version TEXT NOT NULL,
    request_contract_sha256 TEXT NOT NULL,
    retry_ordinal INTEGER NOT NULL CHECK (retry_ordinal >= 1),
    started_at_utc TEXT NOT NULL,
    completed_at_utc TEXT NOT NULL,
    requested_fields_json TEXT NOT NULL,
    observed_fields_json TEXT NOT NULL,
    outcome TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    detail TEXT,
    collector_git_revision TEXT NOT NULL,
    collector_dirty INTEGER NOT NULL CHECK (collector_dirty IN (0, 1)),
    python_version TEXT NOT NULL,
    provider_library_name TEXT NOT NULL,
    provider_library_version TEXT NOT NULL
)
"""

OBSERVATIONS_TABLE_SQL = """
CREATE TABLE ticker_metadata_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL UNIQUE REFERENCES ticker_metadata_attempts(attempt_id),
    run_id TEXT NOT NULL,
    raw_ticker_id INTEGER NOT NULL REFERENCES tickers(id),
    requested_symbol TEXT NOT NULL,
    provider TEXT NOT NULL,
    method TEXT NOT NULL,
    request_contract_json TEXT NOT NULL,
    request_contract_version TEXT NOT NULL,
    request_contract_sha256 TEXT NOT NULL,
    provider_observed_at_utc TEXT NOT NULL,
    provider_symbol TEXT,
    short_name TEXT,
    long_name TEXT,
    exchange_code TEXT,
    exchange_name TEXT,
    quote_type TEXT,
    currency TEXT,
    sector TEXT,
    industry TEXT,
    country TEXT,
    market_cap INTEGER,
    present_fields_json TEXT NOT NULL,
    collector_git_revision TEXT NOT NULL,
    collector_dirty INTEGER NOT NULL CHECK (collector_dirty IN (0, 1)),
    python_version TEXT NOT NULL,
    provider_library_name TEXT NOT NULL,
    provider_library_version TEXT NOT NULL
)
"""

INDEX_SQL = {
    "idx_tma_ticker_contract_attempt": "CREATE INDEX idx_tma_ticker_contract_attempt ON ticker_metadata_attempts(raw_ticker_id, request_contract_sha256, attempt_id)",
    "idx_tma_outcome": "CREATE INDEX idx_tma_outcome ON ticker_metadata_attempts(outcome)",
    "idx_tmo_attempt_id": "CREATE INDEX idx_tmo_attempt_id ON ticker_metadata_observations(attempt_id)",
}

TRIGGER_SQL = {
    "trg_tma_no_update": """
        CREATE TRIGGER trg_tma_no_update BEFORE UPDATE ON ticker_metadata_attempts
        BEGIN SELECT RAISE(ABORT, 'ticker_metadata_attempts is append-only'); END
    """,
    "trg_tma_no_delete": """
        CREATE TRIGGER trg_tma_no_delete BEFORE DELETE ON ticker_metadata_attempts
        BEGIN SELECT RAISE(ABORT, 'ticker_metadata_attempts is append-only'); END
    """,
    "trg_tmo_no_update": """
        CREATE TRIGGER trg_tmo_no_update BEFORE UPDATE ON ticker_metadata_observations
        BEGIN SELECT RAISE(ABORT, 'ticker_metadata_observations is append-only'); END
    """,
    "trg_tmo_no_delete": """
        CREATE TRIGGER trg_tmo_no_delete BEFORE DELETE ON ticker_metadata_observations
        BEGIN SELECT RAISE(ABORT, 'ticker_metadata_observations is append-only'); END
    """,
}

_METADATA_TABLES = {"ticker_metadata_attempts", "ticker_metadata_observations"}
_TERMINAL = {
    AcquisitionOutcome.COMPLETE.value,
    AcquisitionOutcome.PARTIAL_RESPONSE.value,
    AcquisitionOutcome.NO_DATA.value,
    AcquisitionOutcome.INVALID_SYMBOL.value,
    AcquisitionOutcome.SCHEMA_DRIFT.value,
}
_RETRY_ERRORED = {
    AcquisitionOutcome.PARTIAL_RESPONSE.value,
    AcquisitionOutcome.NO_DATA.value,
    AcquisitionOutcome.INVALID_SYMBOL.value,
    AcquisitionOutcome.SCHEMA_DRIFT.value,
}

_TEXT_REGISTRY_COLUMNS = {
    "ticker",
    "company_name",
    "exchange",
    "sector",
    "industry",
    "country",
}
_NUMERIC_REGISTRY_COLUMNS = {"market_cap", "is_etf", "is_active"}


class MetadataBoundaryError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message[:500])
        self.code = code


def resolve_existing_database(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve(strict=False)
    if not path.exists():
        raise MetadataBoundaryError("database_missing", "Selected database does not exist")
    if not path.is_file():
        raise MetadataBoundaryError(
            "database_not_regular_file", "Selected database is not a regular file"
        )
    size = path.stat().st_size
    if size == 0:
        raise MetadataBoundaryError("database_empty", "Selected database is empty")
    with path.open("rb") as handle:
        if handle.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
            raise MetadataBoundaryError(
                "database_header_invalid", "Selected file has no SQLite header"
            )
    return path


def _rw_uri(path: Path) -> str:
    return f"{path.as_uri()}?mode=rw"


def _connect_rw(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(
            _rw_uri(path),
            uri=True,
            timeout=30.0,
            isolation_level=None,
        )
    except sqlite3.Error as exc:
        raise MetadataBoundaryError(
            "database_open_failed", "Selected database could not be opened read-write"
        ) from exc
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _sqlite_affinity(declared_type: object) -> str:
    value = str(declared_type or "").upper()
    if "INT" in value:
        return "INTEGER"
    if any(token in value for token in ("CHAR", "CLOB", "TEXT")):
        return "TEXT"
    if not value or "BLOB" in value:
        return "BLOB"
    if any(token in value for token in ("REAL", "FLOA", "DOUB")):
        return "REAL"
    return "NUMERIC"


class MetadataStore:
    def __init__(self, path: str | Path):
        self.path = resolve_existing_database(path)

    @classmethod
    def preflight(cls, path: str | Path) -> PreflightSummary:
        resolved = resolve_existing_database(path)
        try:
            with closing(_connect_rw(resolved)) as connection:
                try:
                    checks = tuple(
                        str(row[0]) for row in connection.execute("PRAGMA quick_check")
                    )
                except sqlite3.DatabaseError as exc:
                    raise MetadataBoundaryError(
                        "database_corrupt", "SQLite quick_check could not inspect the database"
                    ) from exc
                if checks != ("ok",):
                    raise MetadataBoundaryError(
                        "database_quick_check_failed", "SQLite quick_check did not return ok"
                    )

                try:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute("ROLLBACK")
                except sqlite3.Error as exc:
                    raise MetadataBoundaryError(
                        "database_not_writable", "Selected database is not writable"
                    ) from exc

                table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tickers'"
                ).fetchone()
                if table is None:
                    raise MetadataBoundaryError(
                        "registry_missing", "Required tickers table is missing"
                    )
                rows = tuple(connection.execute("PRAGMA table_info('tickers')"))
                columns = {str(row[1]): row for row in rows}
                identifier = columns.get("id")
                if (
                    identifier is None
                    or "INT" not in str(identifier[2]).upper()
                    or int(identifier[5]) != 1
                ):
                    raise MetadataBoundaryError(
                        "registry_primary_key_invalid",
                        "tickers.id must be the integer primary key",
                    )
                symbol = columns.get("ticker")
                if symbol is None:
                    raise MetadataBoundaryError(
                        "registry_symbol_missing", "tickers.ticker is missing"
                    )
                if int(symbol[3]) != 1:
                    raise MetadataBoundaryError(
                        "registry_symbol_nullable", "tickers.ticker must be non-null"
                    )
                if _sqlite_affinity(symbol[2]) != "TEXT":
                    raise MetadataBoundaryError(
                        "registry_symbol_type_invalid",
                        "tickers.ticker must have SQLite TEXT affinity",
                    )
                missing = [
                    name for name in REQUIRED_REGISTRY_COLUMNS if name not in columns
                ]
                if missing:
                    raise MetadataBoundaryError(
                        "registry_filter_columns_missing",
                        "Required ticker registry filter columns are missing",
                    )
                incompatible = [
                    name
                    for name in sorted(_TEXT_REGISTRY_COLUMNS - {"ticker"})
                    if _sqlite_affinity(columns[name][2]) != "TEXT"
                ]
                incompatible.extend(
                    name
                    for name in sorted(_NUMERIC_REGISTRY_COLUMNS)
                    if _sqlite_affinity(columns[name][2])
                    not in {"INTEGER", "REAL", "NUMERIC"}
                )
                if incompatible:
                    raise MetadataBoundaryError(
                        "registry_filter_column_type_invalid",
                        "Ticker registry filter columns have incompatible SQLite affinity",
                    )
                ticker_count = int(
                    connection.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]
                )
        except MetadataBoundaryError:
            raise
        except sqlite3.DatabaseError as exc:
            raise MetadataBoundaryError(
                "database_corrupt", "Selected database could not be inspected"
            ) from exc
        return PreflightSummary(
            database_path=resolved,
            quick_check="ok",
            ticker_count=ticker_count,
            registry_columns=REQUIRED_REGISTRY_COLUMNS,
        )

    def initialize_schema(self) -> None:
        self.preflight(self.path)
        with closing(_connect_rw(self.path)) as connection:
            rows = tuple(
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?, ?)",
                    tuple(sorted(_METADATA_TABLES)),
                )
            )
            existing_tables = {str(row[0]) for row in rows}
            if existing_tables:
                if existing_tables != _METADATA_TABLES:
                    raise MetadataBoundaryError(
                        "metadata_schema_incompatible",
                        "Metadata tables are only partially present",
                    )
                self._validate_schema(connection)
                return
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(ATTEMPTS_TABLE_SQL)
                connection.execute(OBSERVATIONS_TABLE_SQL)
                for statement in INDEX_SQL.values():
                    connection.execute(statement)
                for statement in TRIGGER_SQL.values():
                    connection.execute(statement)
                connection.execute("COMMIT")
            except sqlite3.Error as exc:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise MetadataBoundaryError(
                    "metadata_schema_incompatible",
                    "Metadata schema objects conflict with the required contract",
                ) from exc
            self._validate_schema(connection)

    @staticmethod
    def _normalized_sql(value: str | None) -> str:
        return " ".join((value or "").strip().rstrip(";").split()).lower()

    def _validate_schema(self, connection: sqlite3.Connection) -> None:
        expected = {
            "ticker_metadata_attempts": ATTEMPTS_TABLE_SQL,
            "ticker_metadata_observations": OBSERVATIONS_TABLE_SQL,
            **INDEX_SQL,
            **TRIGGER_SQL,
        }
        placeholders = ",".join("?" for _ in expected)
        actual = {
            str(row[0]): str(row[1])
            for row in connection.execute(
                f"SELECT name, sql FROM sqlite_master WHERE name IN ({placeholders})",
                tuple(expected),
            )
        }
        if set(actual) != set(expected) or any(
            self._normalized_sql(actual[name]) != self._normalized_sql(statement)
            for name, statement in expected.items()
        ):
            raise MetadataBoundaryError(
                "metadata_schema_incompatible",
                "Existing metadata schema differs from the required contract",
            )
        extras = tuple(
            connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE tbl_name IN ('ticker_metadata_attempts', 'ticker_metadata_observations')
                  AND type IN ('index', 'trigger')
                  AND name NOT LIKE 'sqlite_autoindex%'
                """
            )
        )
        if {str(row[0]) for row in extras} != set(INDEX_SQL) | set(TRIGGER_SQL):
            raise MetadataBoundaryError(
                "metadata_schema_incompatible",
                "Existing metadata indexes or triggers differ from the required contract",
            )
        foreign_key_issues = tuple(connection.execute("PRAGMA foreign_key_check"))
        if foreign_key_issues:
            raise MetadataBoundaryError(
                "metadata_schema_incompatible", "Metadata foreign keys are invalid"
            )

    def record_attempt(
        self,
        attempt: AttemptRecord,
        observation: ObservationRecord | None,
    ) -> WriteReceipt:
        has_observation = attempt.outcome in {
            AcquisitionOutcome.COMPLETE,
            AcquisitionOutcome.PARTIAL_RESPONSE,
        }
        if has_observation and observation is None:
            raise ValueError("complete or partial attempt requires exactly one observation")
        if not has_observation and observation is not None:
            raise ValueError("non-observation outcome must not have an observation")
        if observation is not None and (
            observation.run_id != attempt.run_id
            or observation.raw_ticker_id != attempt.raw_ticker_id
            or observation.requested_symbol != attempt.requested_symbol
            or observation.provider != attempt.provider
            or observation.method != attempt.method
            or observation.request_contract_json != attempt.request_contract_json
            or observation.request_contract_version != attempt.request_contract_version
            or observation.request_contract_sha256 != attempt.request_contract_sha256
        ):
            raise ValueError("observation does not match linked attempt identity")
        if observation is not None and (
            observation.provider_observed_at_utc != attempt.completed_at_utc
            or observation.collector_git_revision != attempt.collector_git_revision
            or observation.collector_dirty != attempt.collector_dirty
            or observation.python_version != attempt.python_version
            or observation.provider_library_name != attempt.provider_library_name
            or observation.provider_library_version != attempt.provider_library_version
            or tuple(sorted(observation.projected))
            != tuple(sorted(observation.present_fields))
        ):
            raise ValueError("observation does not match linked attempt evidence")

        attempt_values = {
            "run_id": attempt.run_id,
            "raw_ticker_id": attempt.raw_ticker_id,
            "requested_symbol": attempt.requested_symbol,
            "provider": attempt.provider,
            "method": attempt.method,
            "request_contract_json": attempt.request_contract_json,
            "request_contract_version": attempt.request_contract_version,
            "request_contract_sha256": attempt.request_contract_sha256,
            "retry_ordinal": attempt.retry_ordinal,
            "started_at_utc": _utc_text(attempt.started_at_utc),
            "completed_at_utc": _utc_text(attempt.completed_at_utc),
            "requested_fields_json": _canonical_list(attempt.requested_fields),
            "observed_fields_json": _canonical_list(attempt.observed_fields),
            "outcome": attempt.outcome.value,
            "reason_code": attempt.reason_code,
            "detail": attempt.detail,
            "collector_git_revision": attempt.collector_git_revision,
            "collector_dirty": int(attempt.collector_dirty),
            "python_version": attempt.python_version,
            "provider_library_name": attempt.provider_library_name,
            "provider_library_version": attempt.provider_library_version,
        }
        with closing(_connect_rw(self.path)) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                columns = tuple(attempt_values)
                cursor = connection.execute(
                    f"INSERT INTO ticker_metadata_attempts ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                    tuple(attempt_values[column] for column in columns),
                )
                attempt_id = int(cursor.lastrowid)
                observation_id = None
                if observation is not None:
                    projected = observation.projected
                    observation_values = {
                        "attempt_id": attempt_id,
                        "run_id": observation.run_id,
                        "raw_ticker_id": observation.raw_ticker_id,
                        "requested_symbol": observation.requested_symbol,
                        "provider": observation.provider,
                        "method": observation.method,
                        "request_contract_json": observation.request_contract_json,
                        "request_contract_version": observation.request_contract_version,
                        "request_contract_sha256": observation.request_contract_sha256,
                        "provider_observed_at_utc": _utc_text(observation.provider_observed_at_utc),
                        "provider_symbol": projected.get("provider_symbol"),
                        "short_name": projected.get("short_name"),
                        "long_name": projected.get("long_name"),
                        "exchange_code": projected.get("exchange_code"),
                        "exchange_name": projected.get("exchange_name"),
                        "quote_type": projected.get("quote_type"),
                        "currency": projected.get("currency"),
                        "sector": projected.get("sector"),
                        "industry": projected.get("industry"),
                        "country": projected.get("country"),
                        "market_cap": projected.get("market_cap"),
                        "present_fields_json": _canonical_list(observation.present_fields),
                        "collector_git_revision": observation.collector_git_revision,
                        "collector_dirty": int(observation.collector_dirty),
                        "python_version": observation.python_version,
                        "provider_library_name": observation.provider_library_name,
                        "provider_library_version": observation.provider_library_version,
                    }
                    observation_columns = tuple(observation_values)
                    observation_cursor = connection.execute(
                        f"INSERT INTO ticker_metadata_observations ({','.join(observation_columns)}) VALUES ({','.join('?' for _ in observation_columns)})",
                        tuple(observation_values[column] for column in observation_columns),
                    )
                    observation_id = int(observation_cursor.lastrowid)
                connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
        return WriteReceipt(attempt_id, observation_id)

    def latest_outcomes(self, contract_hash: str) -> dict[int, str]:
        with closing(_connect_rw(self.path)) as connection:
            rows = connection.execute(
                """
                SELECT a.raw_ticker_id, a.outcome
                FROM ticker_metadata_attempts AS a
                JOIN (
                    SELECT raw_ticker_id, MAX(attempt_id) AS latest_id
                    FROM ticker_metadata_attempts
                    WHERE request_contract_sha256 = ?
                    GROUP BY raw_ticker_id
                ) AS latest ON latest.latest_id = a.attempt_id
                ORDER BY a.raw_ticker_id
                """,
                (contract_hash,),
            )
            return {int(row[0]): str(row[1]) for row in rows}

    def select_tickers(
        self,
        filter_spec,
        limit: int | None,
        retry_errored: bool,
        contract_hash: str,
    ) -> Selection:
        with closing(_connect_rw(self.path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = tuple(
                connection.execute(
                    """
                    SELECT id, ticker, company_name, exchange, sector, industry,
                           country, market_cap, is_etf, is_active
                    FROM tickers ORDER BY id
                    """
                )
            )
        latest = self.latest_outcomes(contract_hash)
        selected: list[TickerRef] = []
        skipped = 0
        effective_limit = limit if limit is not None else filter_spec.limit
        for row in rows:
            if not _matches_filter(row, filter_spec):
                continue
            outcome = latest.get(int(row["id"]))
            terminal_skip = outcome in _TERMINAL and not (
                retry_errored and outcome in _RETRY_ERRORED
            )
            if terminal_skip:
                skipped += 1
                continue
            if effective_limit is None or len(selected) < effective_limit:
                selected.append(TickerRef(int(row["id"]), str(row["ticker"])))
        return Selection(
            tickers=tuple(selected),
            skipped_terminal=skipped,
            filter_description=(
                filter_spec.describe()
                if filter_spec
                else "(no filter — all registry tickers)"
            ),
        )


def _canonical_list(values: tuple[str, ...]) -> str:
    return json.dumps(sorted(set(values)), separators=(",", ":"))


def _utc_text(value) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("metadata timestamps must be timezone-aware")
    return value.astimezone(__import__("datetime").timezone.utc).isoformat()


def _matches_filter(row: sqlite3.Row, spec) -> bool:
    if spec.exchanges and row["exchange"] not in spec.exchanges:
        return False
    if spec.sectors and row["sector"] not in spec.sectors:
        return False
    if spec.industries and row["industry"] not in spec.industries:
        return False
    if spec.countries and row["country"] not in spec.countries:
        return False
    if spec.is_etf is not None and bool(row["is_etf"]) is not spec.is_etf:
        return False
    if spec.min_market_cap is not None and (
        row["market_cap"] is None or row["market_cap"] < spec.min_market_cap
    ):
        return False
    if spec.max_market_cap is not None and (
        row["market_cap"] is None or row["market_cap"] > spec.max_market_cap
    ):
        return False
    try:
        if spec.ticker_regex and re.search(spec.ticker_regex, str(row["ticker"])) is None:
            return False
        if spec.company_name_regex:
            company = str(row["company_name"] or "")
            if (
                re.search(spec.company_name_regex, company) is None
                and spec.company_name_regex not in company
            ):
                return False
    except re.error:
        return False
    return True
