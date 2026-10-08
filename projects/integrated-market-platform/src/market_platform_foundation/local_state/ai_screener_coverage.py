"""Append-only receipts for full-universe AI Screener runs, on the existing local-state DB.

One run writes a ``run`` record, then ``rows``, ``plan``, ``batch_started`` / ``batch`` pairs, ``round``
records and exactly one ``terminal``. Nothing is updated or deleted. A run with no terminal record after a
restart was interrupted; a ``batch_started`` with no matching ``batch`` is a provider call whose outcome
this server never learned.
"""
from __future__ import annotations

import json
import threading
from typing import Any

from .paths import persistence_enabled
from .startup import open_local_state

KINDS = ('run', 'rows', 'plan', 'batch_started', 'batch', 'round', 'terminal')
MAX_RECORD_BYTES = 512000


class CoverageLedger:
    def __init__(self, connection=None):
        self.connection = connection
        self._memory: list[tuple[str, int, str, str]] = []
        self.lock = threading.RLock()
        if connection is not None:
            with connection.transaction():
                connection.execute('CREATE TABLE IF NOT EXISTS ai_screener_coverage_records (run_id TEXT NOT NULL, seq INTEGER NOT NULL, '
                                   'kind TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(run_id,seq))')
                connection.execute('CREATE INDEX IF NOT EXISTS ai_screener_coverage_kind ON ai_screener_coverage_records(kind,run_id)')

    def _rows(self, run_id: str | None = None, kind: str | None = None) -> list[tuple[str, int, str, str]]:
        if self.connection:
            clauses, values = [], []
            for column, value in (('run_id', run_id), ('kind', kind)):
                if value is not None:
                    clauses.append(f'{column}=?')
                    values.append(value)
            where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
            return [tuple(row) for row in self.connection.execute(
                'SELECT run_id,seq,kind,payload FROM ai_screener_coverage_records' + where + ' ORDER BY rowid', values).fetchall()]
        return [row for row in self._memory if (run_id is None or row[0] == run_id) and (kind is None or row[2] == kind)]

    def append(self, run_id: str, kind: str, payload: dict[str, Any]) -> None:
        if kind not in KINDS:
            raise ValueError('COVERAGE_RECORD_KIND_INVALID')
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if len(encoded.encode('utf-8')) > MAX_RECORD_BYTES:
            raise ValueError('COVERAGE_RECORD_BOUND_EXCEEDED')
        with self.lock:
            def insert():
                existing = self._rows(run_id)
                if kind in ('run', 'terminal') and any(row[2] == kind for row in existing):
                    raise ValueError('IMMUTABLE_COVERAGE_RECORD_COLLISION')
                if kind != 'run' and any(row[2] == 'terminal' for row in existing):
                    raise ValueError('COVERAGE_RUN_ALREADY_TERMINAL')
                record = (run_id, len(existing), kind, encoded)
                if self.connection:
                    self.connection.execute('INSERT INTO ai_screener_coverage_records VALUES (?,?,?,?)', record)
                else:
                    self._memory.append(record)
            if self.connection and not self.connection.in_transaction:
                with self.connection.transaction():
                    insert()
            else:
                insert()

    def records(self, run_id: str, kind: str | None = None) -> list[dict[str, Any]]:
        with self.lock:
            return [{'seq': seq, 'kind': name, **json.loads(payload)} for _, seq, name, payload in self._rows(run_id, kind)]

    def terminal(self, run_id: str) -> dict[str, Any] | None:
        found = self.records(run_id, 'terminal')
        return found[0] if found else None

    def open_runs(self) -> list[str]:
        """Runs that began and never reached a terminal record."""
        with self.lock:
            started = [row[0] for row in self._rows(kind='run')]
            ended = {row[0] for row in self._rows(kind='terminal')}
            return [run_id for run_id in started if run_id not in ended]

    def unfinished_batches(self, run_id: str) -> list[dict[str, Any]]:
        """Model calls this server started and has no outcome for."""
        finished = {item['call_id'] for item in self.records(run_id, 'batch')}
        return [item for item in self.records(run_id, 'batch_started') if item['call_id'] not in finished]

    def latest_terminal(self, account_id: str) -> dict[str, Any] | None:
        with self.lock:
            for run_id, _, _, payload in reversed(self._rows(kind='terminal')):
                value = json.loads(payload)
                if value.get('account_id') == account_id:
                    return {'run_id': run_id, **value}
        return None


_LEDGER = None
_KEY = None


def coverage_ledger() -> CoverageLedger:
    global _LEDGER, _KEY
    local = open_local_state() if persistence_enabled() else None
    key = id(local.connection) if local else None
    if _LEDGER is None or key != _KEY:
        _LEDGER = CoverageLedger(local.connection if local else None)
        _KEY = key
    return _LEDGER
