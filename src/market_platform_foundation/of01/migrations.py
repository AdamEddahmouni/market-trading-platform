"""Ordered OF-01 SQLite migrations."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .canonical import (
    CAS_LOCATOR_PROFILE,
    COMMAND_PROFILE,
    COMMIT_PROFILE,
    HASH_PROFILE,
    RECORD_PROFILE,
)
from .errors import OF01Error, OF01ErrorCode
from .ids import validate_uuid
from .sqlite_schema import (
    ALL_TABLES,
    AUTHORITATIVE_TABLES,
    DEPLOYMENT_TOPOLOGY,
    MIGRATION_V1_STATEMENTS,
    SCHEMA_VERSION,
    append_only_trigger_sql,
)


def _normalize_sql(sql: str) -> str:
    return " ".join(sql.split())


def current_database_schema_version(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ledger_metadata'"
    ).fetchone()
    if row is None:
        return None
    version_row = conn.execute(
        "SELECT database_schema_version FROM ledger_metadata WHERE singleton = 1"
    ).fetchone()
    if version_row is None:
        return None
    return int(version_row[0])


def verify_schema_objects(conn: sqlite3.Connection) -> None:
    for table in ALL_TABLES:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if row is None or row[0] is None:
            raise OF01Error(
                OF01ErrorCode.SCHEMA_UNSUPPORTED,
                f"missing table {table}",
                {"table": table},
            )
        if "STRICT" not in str(row[0]).upper():
            raise OF01Error(
                OF01ErrorCode.SCHEMA_UNSUPPORTED,
                f"table {table} is not STRICT",
                {"table": table},
            )
    for table in AUTHORITATIVE_TABLES:
        for suffix in ("append_only_update", "append_only_delete"):
            trigger_name = f"trg_{table}_{suffix}"
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
                (trigger_name,),
            ).fetchone()
            if row is None:
                raise OF01Error(
                    OF01ErrorCode.SCHEMA_UNSUPPORTED,
                    f"missing trigger {trigger_name}",
                    {"trigger": trigger_name},
                )


def apply_migrations(conn: sqlite3.Connection) -> int:
    existing = current_database_schema_version(conn)
    if existing is not None and existing > SCHEMA_VERSION:
        raise OF01Error(
            OF01ErrorCode.SCHEMA_UNSUPPORTED,
            "unknown newer schema version",
            {"version": existing},
        )
    if existing == SCHEMA_VERSION:
        verify_schema_objects(conn)
        return SCHEMA_VERSION
    if existing is not None and existing != SCHEMA_VERSION:
        raise OF01Error(
            OF01ErrorCode.MIGRATION_PATH_UNSUPPORTED,
            "unsupported migration path",
            {"from_version": existing, "to_version": SCHEMA_VERSION},
        )
    for statement in MIGRATION_V1_STATEMENTS:
        conn.execute(statement)
    verify_schema_objects(conn)
    return SCHEMA_VERSION


def bootstrap_authority_metadata(
    conn: sqlite3.Connection,
    *,
    ledger_authority_id: str,
    created_at_ns: int | None = None,
) -> None:
    validate_uuid(ledger_authority_id, field="ledger_authority_id")
    if created_at_ns is None:
        created_at_ns = time.time_ns()
    existing = conn.execute(
        "SELECT ledger_authority_id FROM ledger_metadata WHERE singleton = 1"
    ).fetchone()
    if existing is not None:
        if str(existing[0]) != ledger_authority_id:
            raise OF01Error(
                OF01ErrorCode.AUTHORITY_IDENTITY_MISMATCH,
                "ledger authority identity mismatch",
                {"expected": ledger_authority_id, "actual": existing[0]},
            )
        return
    conn.execute(
        """
        INSERT INTO ledger_metadata (
          singleton, ledger_authority_id, database_schema_version,
          commit_schema_version, command_profile, record_profile,
          commit_profile, hash_profile, cas_locator_profile,
          created_at_ns, deployment_topology
        ) VALUES (1, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ledger_authority_id,
            SCHEMA_VERSION,
            COMMAND_PROFILE,
            RECORD_PROFILE,
            COMMIT_PROFILE,
            HASH_PROFILE,
            CAS_LOCATOR_PROFILE,
            created_at_ns,
            DEPLOYMENT_TOPOLOGY,
        ),
    )
    conn.execute(
        """
        INSERT INTO runtime_control (singleton, mode, revision, changed_at_ns, reason_code)
        VALUES (1, 'STOPPED', 0, ?, 'BOOTSTRAP')
        """,
        (created_at_ns,),
    )


def bootstrap_authority(
    db_path: Path,
    *,
    ledger_authority_id: str,
    busy_timeout_ms: int = 5000,
) -> sqlite3.Connection:
    from .sqlite_store import configure_connection, open_connection

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = open_connection(db_path, busy_timeout_ms=busy_timeout_ms)
    try:
        conn.execute("BEGIN IMMEDIATE")
        apply_migrations(conn)
        bootstrap_authority_metadata(conn, ledger_authority_id=ledger_authority_id)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        conn.close()
        raise
    configure_connection(conn, busy_timeout_ms=busy_timeout_ms)
    return conn


def open_authority(
    db_path: Path,
    *,
    ledger_authority_id: str,
    busy_timeout_ms: int = 5000,
) -> sqlite3.Connection:
    from .sqlite_store import configure_connection, open_connection

    if not db_path.exists():
        return bootstrap_authority(
            db_path,
            ledger_authority_id=ledger_authority_id,
            busy_timeout_ms=busy_timeout_ms,
        )
    conn = open_connection(db_path, busy_timeout_ms=busy_timeout_ms)
    configure_connection(conn, busy_timeout_ms=busy_timeout_ms)
    version = current_database_schema_version(conn)
    if version is None:
        raise OF01Error(
            OF01ErrorCode.SCHEMA_UNSUPPORTED,
            "database exists but schema is missing",
            {"path": str(db_path)},
        )
    if version > SCHEMA_VERSION:
        raise OF01Error(
            OF01ErrorCode.SCHEMA_UNSUPPORTED,
            "unknown newer schema version",
            {"version": version},
        )
    apply_migrations(conn)
    row = conn.execute(
        "SELECT ledger_authority_id FROM ledger_metadata WHERE singleton = 1"
    ).fetchone()
    if row is None:
        raise OF01Error(
            OF01ErrorCode.SCHEMA_UNSUPPORTED,
            "ledger metadata missing",
            {},
        )
    if str(row[0]) != ledger_authority_id:
        conn.close()
        raise OF01Error(
            OF01ErrorCode.AUTHORITY_IDENTITY_MISMATCH,
            "ledger authority identity mismatch",
            {"expected": ledger_authority_id, "actual": row[0]},
        )
    return conn
