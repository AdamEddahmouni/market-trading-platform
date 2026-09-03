"""Ordered, fail-closed SQLite migrations for local IMP state."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .schema import CREATE_STATEMENTS, SCHEMA_VERSION


class SchemaVersionError(ValueError):
    """Unknown or incompatible schema_version."""


MIGRATIONS: dict[int, tuple[str, ...]] = {
    1: CREATE_STATEMENTS,
}


def current_schema_version(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
    ).fetchone()
    if row is None:
        return None
    version_row = conn.execute(
        "SELECT schema_version FROM schema_meta ORDER BY schema_version DESC LIMIT 1"
    ).fetchone()
    if version_row is None:
        return None
    return int(version_row[0])


def apply_migrations(conn: sqlite3.Connection) -> int:
    existing = current_schema_version(conn)
    if existing is not None and existing > SCHEMA_VERSION:
        raise SchemaVersionError(
            f"UNKNOWN_NEWER_SCHEMA:{existing}>supported:{SCHEMA_VERSION}"
        )
    start = 1 if existing is None else existing + 1
    applied_at = datetime.now(timezone.utc).isoformat()
    for version in range(start, SCHEMA_VERSION + 1):
        statements = MIGRATIONS.get(version)
        if statements is None:
            raise SchemaVersionError(f"MISSING_MIGRATION:{version}")
        for statement in statements:
            conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_meta(schema_version, applied_at) VALUES (?, ?)",
            (version, applied_at),
        )
    conn.commit()
    final = current_schema_version(conn)
    if final != SCHEMA_VERSION:
        raise SchemaVersionError(f"SCHEMA_VERIFY_FAILED:{final}")
    return final
