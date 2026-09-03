"""Repository for operator and paper durable local state. Positions are not truth."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from ..canonical import canonical_bytes, sha256_bytes
from ..clock import monotonic_wall_ns
from .connection import LocalStateConnection
from .schema import LAYOUT_SCHEMA_VERSION, PAPER_EVENT_SCHEMA_VERSION, RECENT_INSTRUMENT_LIMIT

SECRET_KEY_TOKENS = (
    "secret",
    "password",
    "token",
    "api_key",
    "apikey",
    "unlock",
    "credential",
    "private_key",
)

SESSION_OPEN = "OPEN"
SESSION_CLOSED = "CLOSED"
CAPTURE_AVAILABLE = "AVAILABLE"
CAPTURE_MISSING = "MISSING"
CAPTURE_CORRUPT = "CORRUPT"
CAPTURE_INCOMPATIBLE = "INCOMPATIBLE"


def _ns() -> int:
    return monotonic_wall_ns()


def reject_secret_key(key: str) -> None:
    lowered = key.lower().replace("-", "_")
    for token in SECRET_KEY_TOKENS:
        if token in lowered:
            raise ValueError("OPERATOR_PREF_SECRET_FORBIDDEN")


class LocalStateRepository:
    def __init__(self, connection: LocalStateConnection) -> None:
        self.connection = connection
        self.ensure_default_watchlist()

    def persist_paper_events(
        self,
        *,
        session: dict[str, Any],
        events: list[dict[str, Any]],
        idempotency_index: dict[str, str],
    ) -> None:
        with self.connection.transaction():
            self._upsert_session(session)
            for event in events:
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO paper_events(
                        event_id, session_id, event_type, event_time, available_time,
                        correlation_id, payload_json, schema_version, sequence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event["event_id"],
                        event["session_id"],
                        event["event_type"],
                        int(event["event_time"]),
                        int(event["available_time"]),
                        event.get("correlation_id"),
                        json.dumps(event.get("payload") or {}, sort_keys=True, separators=(",", ":")),
                        int(event.get("schema_version") or PAPER_EVENT_SCHEMA_VERSION),
                        int(event["sequence"]),
                    ),
                )
            for key, order_id in idempotency_index.items():
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO paper_idempotency(session_id, idempotency_key, order_id)
                    VALUES (?, ?, ?)
                    """,
                    (session["session_id"], key, order_id),
                )

    def _upsert_session(self, session: dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT INTO paper_sessions(
                session_id, paper_account_id, created_at, closed_at, data_mode, execution_mode,
                data_provider, execution_provider, starting_cash_minor, configuration_hash,
                status, replay_session_id, instrument_id, symbol, policy_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                closed_at=excluded.closed_at,
                status=excluded.status,
                execution_mode=excluded.execution_mode
            """,
            (
                session["session_id"],
                session["paper_account_id"],
                int(session["created_at"]),
                session.get("closed_at"),
                session["data_mode"],
                session["execution_mode"],
                session["data_provider"],
                session["execution_provider"],
                int(session["starting_cash_minor"]),
                session["configuration_hash"],
                session["status"],
                session.get("replay_session_id"),
                session.get("instrument_id"),
                session.get("symbol"),
                json.dumps(session.get("policy") or {}, sort_keys=True, separators=(",", ":")),
            ),
        )

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM paper_sessions WHERE session_id=?",
            (session_id,),
        ).fetchone()
        return None if row is None else dict(row)

    def latest_open_session(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM paper_sessions WHERE status=? ORDER BY created_at DESC LIMIT 1",
            (SESSION_OPEN,),
        ).fetchone()
        return None if row is None else dict(row)

    def list_sessions(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM paper_sessions ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def load_events(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT event_id, session_id, event_type, event_time, available_time,
                   correlation_id, payload_json, schema_version, sequence
            FROM paper_events WHERE session_id=? ORDER BY sequence ASC
            """,
            (session_id,),
        ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            events.append(
                {
                    "available_time": int(row["available_time"]),
                    "correlation_id": row["correlation_id"],
                    "event_id": row["event_id"],
                    "event_time": int(row["event_time"]),
                    "event_type": row["event_type"],
                    "payload": payload,
                    "schema_version": int(row["schema_version"]),
                    "sequence": int(row["sequence"]),
                    "session_id": row["session_id"],
                }
            )
        return events

    def load_idempotency(self, session_id: str) -> dict[str, str]:
        rows = self.connection.execute(
            "SELECT idempotency_key, order_id FROM paper_idempotency WHERE session_id=?",
            (session_id,),
        ).fetchall()
        return {str(row["idempotency_key"]): str(row["order_id"]) for row in rows}

    def close_session(self, session_id: str, *, closed_at: int | None = None) -> None:
        self.connection.execute(
            "UPDATE paper_sessions SET status=?, closed_at=? WHERE session_id=?",
            (SESSION_CLOSED, closed_at or _ns(), session_id),
        )

    def save_snapshot(
        self,
        *,
        session_id: str,
        last_event_sequence: int,
        projection: dict[str, Any],
    ) -> None:
        blob = json.dumps(projection, sort_keys=True, separators=(",", ":"))
        self.connection.execute(
            """
            INSERT INTO paper_snapshots(
                session_id, last_event_sequence, schema_version, projection_hash,
                projection_json, captured_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                last_event_sequence=excluded.last_event_sequence,
                schema_version=excluded.schema_version,
                projection_hash=excluded.projection_hash,
                projection_json=excluded.projection_json,
                captured_at=excluded.captured_at
            """,
            (
                session_id,
                last_event_sequence,
                PAPER_EVENT_SCHEMA_VERSION,
                sha256_bytes(blob.encode("utf-8")),
                blob,
                _ns(),
            ),
        )

    def load_snapshot(self, session_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT projection_json FROM paper_snapshots WHERE session_id=?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["projection_json"])
        return payload if isinstance(payload, dict) else None

    def ensure_default_watchlist(self) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM watchlists WHERE is_default=1 LIMIT 1"
        ).fetchone()
        if row is not None:
            return dict(row)
        now = _ns()
        watchlist_id = sha256_bytes(canonical_bytes({"name": "Default", "created_at": now}))
        self.connection.execute(
            """
            INSERT INTO watchlists(watchlist_id, name, is_default, created_at, updated_at, sort_index)
            VALUES (?, ?, 1, ?, ?, 0)
            """,
            (watchlist_id, "Default", now, now),
        )
        return {
            "watchlist_id": watchlist_id,
            "name": "Default",
            "is_default": 1,
            "created_at": now,
            "updated_at": now,
            "sort_index": 0,
        }

    def list_watchlists(self) -> list[dict[str, Any]]:
        lists = [dict(row) for row in self.connection.execute(
            "SELECT * FROM watchlists ORDER BY sort_index ASC, created_at ASC"
        ).fetchall()]
        for item in lists:
            item["items"] = [
                dict(row)
                for row in self.connection.execute(
                    "SELECT instrument_id, sort_index, created_at FROM watchlist_items WHERE watchlist_id=? ORDER BY sort_index ASC",
                    (item["watchlist_id"],),
                ).fetchall()
            ]
        return lists

    def replace_watchlist_items(self, watchlist_id: str, instrument_ids: list[str]) -> None:
        now = _ns()
        with self.connection.transaction():
            self.connection.execute("DELETE FROM watchlist_items WHERE watchlist_id=?", (watchlist_id,))
            for index, instrument_id in enumerate(instrument_ids):
                self.connection.execute(
                    """
                    INSERT INTO watchlist_items(watchlist_id, instrument_id, sort_index, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (watchlist_id, instrument_id.upper(), index, now),
                )
            self.connection.execute(
                "UPDATE watchlists SET updated_at=? WHERE watchlist_id=?",
                (now, watchlist_id),
            )

    def record_recent_instrument(self, instrument_id: str) -> None:
        now = _ns()
        key = instrument_id.upper()
        with self.connection.transaction():
            self.connection.execute(
                """
                INSERT INTO recent_instruments(instrument_id, last_seen_at, sort_rank)
                VALUES (?, ?, 0)
                ON CONFLICT(instrument_id) DO UPDATE SET last_seen_at=excluded.last_seen_at
                """,
                (key, now),
            )
            rows = self.connection.execute(
                "SELECT instrument_id FROM recent_instruments ORDER BY last_seen_at DESC, rowid DESC"
            ).fetchall()
            for rank, row in enumerate(rows):
                if rank >= RECENT_INSTRUMENT_LIMIT:
                    self.connection.execute(
                        "DELETE FROM recent_instruments WHERE instrument_id=?",
                        (row["instrument_id"],),
                    )
                else:
                    self.connection.execute(
                        "UPDATE recent_instruments SET sort_rank=? WHERE instrument_id=?",
                        (rank, row["instrument_id"]),
                    )

    def list_recent_instruments(self) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.connection.execute(
                "SELECT instrument_id, last_seen_at, sort_rank FROM recent_instruments ORDER BY sort_rank ASC"
            ).fetchall()
        ]

    def save_workspace(self, layout: dict[str, Any], *, workspace_id: str | None = None, name: str = "Active") -> dict[str, Any]:
        now = _ns()
        ident = workspace_id or "active"
        known = {
            "collapsed_panels",
            "layout_schema_version",
            "open_panels",
            "panel_order",
            "research_lane",
            "selected_instrument",
            "timeframe",
        }
        filtered = {key: value for key, value in layout.items() if key in known}
        filtered.setdefault("layout_schema_version", LAYOUT_SCHEMA_VERSION)
        blob = json.dumps(filtered, sort_keys=True, separators=(",", ":"))
        self.connection.execute(
            """
            INSERT INTO saved_workspaces(
                workspace_id, name, is_active, layout_schema_version, layout_json, created_at, updated_at
            ) VALUES (?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(workspace_id) DO UPDATE SET
                layout_json=excluded.layout_json,
                layout_schema_version=excluded.layout_schema_version,
                updated_at=excluded.updated_at,
                is_active=1
            """,
            (ident, name, int(filtered["layout_schema_version"]), blob, now, now),
        )
        return {"workspace_id": ident, "layout": filtered}

    def load_active_workspace(self) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM saved_workspaces WHERE is_active=1 ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        layout = json.loads(row["layout_json"])
        if int(layout.get("layout_schema_version") or 0) > LAYOUT_SCHEMA_VERSION:
            return {
                "workspace_id": row["workspace_id"],
                "fallback": True,
                "layout": {"layout_schema_version": LAYOUT_SCHEMA_VERSION, "open_panels": []},
            }
        return {"workspace_id": row["workspace_id"], "layout": layout, "fallback": False}

    def set_preference(self, key: str, value: Any) -> None:
        reject_secret_key(key)
        if isinstance(value, str):
            reject_secret_key(value)
        self.connection.execute(
            """
            INSERT INTO operator_preferences(pref_key, pref_value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(pref_key) DO UPDATE SET pref_value=excluded.pref_value, updated_at=excluded.updated_at
            """,
            (key, json.dumps(value, sort_keys=True, separators=(",", ":")), _ns()),
        )

    def get_preferences(self) -> dict[str, Any]:
        rows = self.connection.execute("SELECT pref_key, pref_value FROM operator_preferences").fetchall()
        return {str(row["pref_key"]): json.loads(row["pref_value"]) for row in rows}

    def upsert_capture(self, row: dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT INTO capture_catalog(
                capture_id, manifest_path, events_path, provider, status, quality_summary_json,
                instruments_json, start_time_ns, end_time_ns, bytes_on_disk, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(capture_id) DO UPDATE SET
                manifest_path=excluded.manifest_path,
                events_path=excluded.events_path,
                provider=excluded.provider,
                status=excluded.status,
                quality_summary_json=excluded.quality_summary_json,
                instruments_json=excluded.instruments_json,
                start_time_ns=excluded.start_time_ns,
                end_time_ns=excluded.end_time_ns,
                bytes_on_disk=excluded.bytes_on_disk,
                indexed_at=excluded.indexed_at
            """,
            (
                row["capture_id"],
                row["manifest_path"],
                row.get("events_path"),
                row.get("provider"),
                row["status"],
                json.dumps(row.get("quality_summary") or {}, sort_keys=True, separators=(",", ":")),
                json.dumps(row.get("instruments") or [], sort_keys=True, separators=(",", ":")),
                row.get("start_time_ns"),
                row.get("end_time_ns"),
                row.get("bytes_on_disk"),
                _ns(),
            ),
        )

    def list_captures(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM capture_catalog ORDER BY indexed_at DESC"
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["quality_summary"] = json.loads(item.pop("quality_summary_json") or "{}")
            item["instruments"] = json.loads(item.pop("instruments_json") or "[]")
            result.append(item)
        return result

    def record_research_run(self, *, kind: str, summary: dict[str, Any]) -> str:
        run_id = uuid4().hex
        self.connection.execute(
            "INSERT INTO research_runs(run_id, kind, created_at, summary_json) VALUES (?, ?, ?, ?)",
            (run_id, kind, _ns(), json.dumps(summary, sort_keys=True, separators=(",", ":"))),
        )
        return run_id

    def list_research_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM research_runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["summary"] = json.loads(item.pop("summary_json"))
            result.append(item)
        return result
