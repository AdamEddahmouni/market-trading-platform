"""SQLite schema for durable local IMP state. Event-sourced paper truth."""

from __future__ import annotations

SCHEMA_VERSION = 1
PAPER_EVENT_SCHEMA_VERSION = 1
LAYOUT_SCHEMA_VERSION = 1
RECENT_INSTRUMENT_LIMIT = 24

CREATE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        schema_version INTEGER NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_sessions (
        session_id TEXT PRIMARY KEY,
        paper_account_id TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        closed_at INTEGER,
        data_mode TEXT NOT NULL,
        execution_mode TEXT NOT NULL,
        data_provider TEXT NOT NULL,
        execution_provider TEXT NOT NULL,
        starting_cash_minor INTEGER NOT NULL,
        configuration_hash TEXT NOT NULL,
        status TEXT NOT NULL,
        replay_session_id TEXT,
        instrument_id TEXT,
        symbol TEXT,
        policy_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_events (
        event_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        event_time INTEGER NOT NULL,
        available_time INTEGER NOT NULL,
        correlation_id TEXT,
        payload_json TEXT NOT NULL,
        schema_version INTEGER NOT NULL,
        sequence INTEGER NOT NULL,
        UNIQUE (session_id, sequence)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_idempotency (
        session_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        order_id TEXT NOT NULL,
        PRIMARY KEY (session_id, idempotency_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_snapshots (
        session_id TEXT PRIMARY KEY,
        last_event_sequence INTEGER NOT NULL,
        schema_version INTEGER NOT NULL,
        projection_hash TEXT NOT NULL,
        projection_json TEXT NOT NULL,
        captured_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watchlists (
        watchlist_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        is_default INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        sort_index INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS watchlist_items (
        watchlist_id TEXT NOT NULL,
        instrument_id TEXT NOT NULL,
        sort_index INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL,
        PRIMARY KEY (watchlist_id, instrument_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS recent_instruments (
        instrument_id TEXT PRIMARY KEY,
        last_seen_at INTEGER NOT NULL,
        sort_rank INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS saved_workspaces (
        workspace_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 0,
        layout_schema_version INTEGER NOT NULL,
        layout_json TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS operator_preferences (
        pref_key TEXT PRIMARY KEY,
        pref_value TEXT NOT NULL,
        updated_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS capture_catalog (
        capture_id TEXT PRIMARY KEY,
        manifest_path TEXT NOT NULL,
        events_path TEXT,
        provider TEXT,
        status TEXT NOT NULL,
        quality_summary_json TEXT,
        instruments_json TEXT,
        start_time_ns INTEGER,
        end_time_ns INTEGER,
        bytes_on_disk INTEGER,
        indexed_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS research_runs (
        run_id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        summary_json TEXT NOT NULL
    )
    """,
)
