"""OCT1-08 stop policies, per-position stop state and stop events on the existing local-state DB.

Policies and events are immutable. Stop state advances, but a write that would
move an active stop away from protection, or revive a terminal state, is
refused here as well as in the policy. Persist-off keeps the same contract in
process memory (INTENTIONAL_EPHEMERAL).
"""
from __future__ import annotations

import json
import threading

from ..risk.sma_trailing_stop import TERMINAL, loosens
from .paths import persistence_enabled
from .startup import open_local_state

MAX_HISTORY = 100
_KINDS = ('policy', 'config', 'state', 'watch')


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class SmaStopRepository:
    def __init__(self, connection=None):
        self.connection = connection
        self.lock = threading.RLock()
        self._records, self._events = {}, []
        if connection is not None:
            with connection.transaction():
                connection.execute('CREATE TABLE IF NOT EXISTS sma_stop_records (kind TEXT NOT NULL, id TEXT NOT NULL, account_id TEXT, instrument_id TEXT, updated_at INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(kind,id))')
                connection.execute('CREATE INDEX IF NOT EXISTS sma_stop_record_scope ON sma_stop_records(kind,account_id,instrument_id,updated_at)')
                connection.execute('CREATE TABLE IF NOT EXISTS sma_stop_events (id INTEGER PRIMARY KEY AUTOINCREMENT, stop_state_id TEXT NOT NULL, account_id TEXT NOT NULL, instrument_id TEXT NOT NULL, payload TEXT NOT NULL)')
                connection.execute('CREATE INDEX IF NOT EXISTS sma_stop_event_history ON sma_stop_events(account_id,instrument_id,id)')

    @property
    def durability(self):
        return 'SQLITE_LOCAL_STATE' if self.connection else 'INTENTIONAL_EPHEMERAL'

    def _write(self, operation):
        with self.lock:
            if self.connection and not self.connection.in_transaction:
                with self.connection.transaction():
                    return operation()
            return operation()

    def get(self, kind, identifier):
        with self.lock:
            if self.connection:
                row = self.connection.execute('SELECT payload FROM sma_stop_records WHERE kind=? AND id=?', (kind, identifier)).fetchone()
                encoded = row[0] if row else None
            else:
                encoded = self._records.get((kind, identifier), (None,))[-1]
            return json.loads(encoded) if encoded else None

    def put(self, kind, identifier, value, *, updated_at=0):
        if kind not in _KINDS:
            raise ValueError('STOP_RECORD_KIND_INVALID')
        encoded = _encode(value)
        if len(encoded.encode('utf-8')) > 16000:
            raise ValueError('STOP_RECORD_BOUND_EXCEEDED')

        def write():
            previous = self.get(kind, identifier)
            if kind == 'policy' and previous is not None:
                if previous != value:
                    raise ValueError('IMMUTABLE_STOP_POLICY_COLLISION')
                return
            if kind == 'state' and previous is not None:
                if previous['status'] == 'CLOSED' and previous != value:
                    raise ValueError('STOP_STATE_TERMINAL')
                if previous['status'] in TERMINAL and value['status'] not in TERMINAL:
                    raise ValueError('STOP_STATE_TERMINAL')
                if loosens(previous['side'], previous['active_stop'], value['active_stop']):
                    raise ValueError('STOP_LOOSENING_REJECTED')
            scope = (value.get('account_id'), value.get('instrument_id'))
            if self.connection:
                self.connection.execute('INSERT INTO sma_stop_records VALUES (?,?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET updated_at=excluded.updated_at, payload=excluded.payload',
                                        (kind, identifier, *scope, int(updated_at), encoded))
            else:
                self._records.pop((kind, identifier), None)  # re-insert keeps newest-last ordering
                self._records[kind, identifier] = (*scope, int(updated_at), encoded)
        self._write(write)

    def latest_state(self, account_id, instrument_id, *, open_only=True):
        """Newest stop state for one account and instrument; ticker alone never selects one."""
        with self.lock:
            if self.connection:
                rows = self.connection.execute('SELECT payload FROM sma_stop_records WHERE kind=? AND account_id=? AND instrument_id=? ORDER BY updated_at DESC, rowid DESC LIMIT 20',
                                               ('state', account_id, instrument_id)).fetchall()
                values = [json.loads(row[0]) for row in rows]
            else:
                values = [json.loads(v[-1]) for (kind, _), v in self._records.items() if kind == 'state' and v[0] == account_id and v[1] == instrument_id]
                values = list(reversed(values))
            return next((v for v in values if not open_only or v['status'] != 'CLOSED'), None)

    def episode_states(self, account_id, instrument_id, episode_id):
        """Exact canonical episode lookup, including closed stop activations."""
        with self.lock:
            if self.connection:
                rows = self.connection.execute(
                    "SELECT payload FROM sma_stop_records WHERE kind='state' AND account_id=? AND instrument_id=? "
                    "AND json_extract(payload, '$.episode_id')=? ORDER BY updated_at DESC, rowid DESC LIMIT 20",
                    (account_id, instrument_id, episode_id)).fetchall()
                return [json.loads(row[0]) for row in rows]
            return [json.loads(v[-1]) for (kind, _), v in reversed(self._records.items())
                    if kind == 'state' and v[0] == account_id and v[1] == instrument_id
                    and json.loads(v[-1]).get('episode_id') == episode_id][:20]

    def open_states(self, account_id):
        with self.lock:
            if self.connection:
                rows = self.connection.execute('SELECT payload FROM sma_stop_records WHERE kind=? AND account_id=? ORDER BY updated_at DESC LIMIT 200', ('state', account_id)).fetchall()
                values = [json.loads(row[0]) for row in rows]
            else:
                values = [json.loads(v[-1]) for (kind, _), v in self._records.items() if kind == 'state' and v[0] == account_id]
            return [v for v in values if v['status'] != 'CLOSED']

    def append_events(self, events, *, account_id, instrument_id):
        """Append-only. Rows are never edited or deleted."""
        def write():
            for item in events:
                encoded = _encode(item)
                if len(encoded.encode('utf-8')) > 8000:
                    raise ValueError('STOP_EVENT_BOUND_EXCEEDED')
                if self.connection:
                    self.connection.execute('INSERT INTO sma_stop_events (stop_state_id,account_id,instrument_id,payload) VALUES (?,?,?,?)',
                                            (item['stop_state_id'], account_id, instrument_id, encoded))
                else:
                    self._events.append((len(self._events) + 1, account_id, instrument_id, encoded))
        if events:
            self._write(write)

    def events(self, account_id, instrument_id, *, limit=20, before=None):
        """Newest first, bounded, cursor by event sequence."""
        limit = max(1, min(int(limit), MAX_HISTORY))
        with self.lock:
            if self.connection:
                sql, params = 'SELECT id, payload FROM sma_stop_events WHERE account_id=? AND instrument_id=?', [account_id, instrument_id]
                if before is not None:
                    sql += ' AND id<?'; params.append(int(before))
                rows = self.connection.execute(sql + ' ORDER BY id DESC LIMIT ?', (*params, limit)).fetchall()
            else:
                rows = [(i, e) for i, a, n, e in reversed(self._events)
                        if a == account_id and n == instrument_id and (before is None or i < int(before))][:limit]
            return [dict(json.loads(encoded), sequence=identifier) for identifier, encoded in rows]

    def event_count(self, account_id, instrument_id):
        with self.lock:
            if self.connection:
                return int(self.connection.execute('SELECT COUNT(*) FROM sma_stop_events WHERE account_id=? AND instrument_id=?', (account_id, instrument_id)).fetchone()[0])
            return sum(1 for _, a, n, _ in self._events if a == account_id and n == instrument_id)


_REPOSITORY = None
_KEY = None


def sma_stop_repository():
    global _REPOSITORY, _KEY
    local = open_local_state() if persistence_enabled() else None
    key = id(local.connection) if local else None
    if _REPOSITORY is None or key != _KEY:
        _REPOSITORY = SmaStopRepository(local.connection if local else None)
        _KEY = key
    return _REPOSITORY
