"""OCT1-07 next-session snapshots, cycle receipts and loop leases on the existing local-state DB.

Persist-off keeps the same contract in process memory (INTENTIONAL_EPHEMERAL).
"""
from __future__ import annotations

import json
import threading

from .paths import persistence_enabled
from .startup import open_local_state

# Lifecycle fields may advance; everything else is frozen by content hash.
NEXT_SESSION_MUTABLE = frozenset({'state', 'lock_state', 'locked_at', 'validity_state', 'evaluation', 'updated_at'})
MAX_HISTORY = 100


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class ReevaluationRepository:
    def __init__(self, connection=None):
        self.connection = connection
        self.lock = threading.RLock()
        self._snapshots, self._observations, self._cycles, self._loops = {}, {}, {}, {}
        if connection is not None:
            with connection.transaction():
                connection.execute('CREATE TABLE IF NOT EXISTS next_session_records (id TEXT PRIMARY KEY, account_id TEXT NOT NULL, instrument_id TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL)')
                connection.execute('CREATE INDEX IF NOT EXISTS next_session_history ON next_session_records(account_id,instrument_id,created_at)')
                connection.execute('CREATE TABLE IF NOT EXISTS next_session_observations (id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, observed_at TEXT NOT NULL, payload TEXT NOT NULL)')
                connection.execute('CREATE INDEX IF NOT EXISTS next_session_observation_order ON next_session_observations(snapshot_id,observed_at)')
                connection.execute('CREATE TABLE IF NOT EXISTS reevaluation_cycles (id TEXT PRIMARY KEY, loop_id TEXT NOT NULL, scheduled_for REAL NOT NULL, session_date TEXT NOT NULL, model_calls INTEGER NOT NULL, payload TEXT NOT NULL)')
                connection.execute('CREATE INDEX IF NOT EXISTS reevaluation_cycle_history ON reevaluation_cycles(loop_id,scheduled_for)')
                connection.execute('CREATE TABLE IF NOT EXISTS reevaluation_loops (loop_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, updated_at REAL NOT NULL, owner_id TEXT, lease_until REAL, payload TEXT NOT NULL)')

    @property
    def durability(self):
        return 'SQLITE_LOCAL_STATE' if self.connection else 'INTENTIONAL_EPHEMERAL'

    def _write(self, operation):
        with self.lock:
            if self.connection and not self.connection.in_transaction:
                with self.connection.transaction():
                    return operation()
            return operation()

    # --- next-session snapshots -------------------------------------------------
    def get_snapshot(self, identifier):
        with self.lock:
            if self.connection:
                row = self.connection.execute('SELECT payload FROM next_session_records WHERE id=?', (identifier,)).fetchone()
                encoded = row[0] if row else None
            else:
                encoded = self._snapshots.get(identifier)
            return json.loads(encoded) if encoded else None

    def put_snapshot(self, value):
        """Drafts may be replaced; a locked snapshot's frozen fields can never change."""
        encoded = _encode(value)
        if len(encoded.encode('utf-8')) > 64000:
            raise ValueError('NEXT_SESSION_RECORD_BOUND_EXCEEDED')

        def write():
            previous = self.get_snapshot(value['snapshot_id'])
            if previous is not None and previous['lock_state'] != 'DRAFT':
                frozen = lambda record: {k: v for k, v in record.items() if k not in NEXT_SESSION_MUTABLE}
                if frozen(previous) != frozen(value) or value['lock_state'] == 'DRAFT' or previous['locked_at'] != value['locked_at']:
                    raise ValueError('NEXT_SESSION_LOCKED_IMMUTABLE')
                if previous['state'] == 'EVALUATED' and previous != value:
                    raise ValueError('NEXT_SESSION_EVALUATION_IMMUTABLE')
            if self.connection:
                self.connection.execute('INSERT INTO next_session_records VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                                        (value['snapshot_id'], value['account_id'], value['instrument_id'], value['created_at'], encoded))
            else:
                self._snapshots[value['snapshot_id']] = encoded
        self._write(write)

    def list_snapshots(self, account_id, instrument_id, limit=20):
        limit = max(1, min(int(limit), MAX_HISTORY))
        with self.lock:
            if self.connection:
                rows = self.connection.execute('SELECT payload FROM next_session_records WHERE account_id=? AND instrument_id=? ORDER BY created_at DESC, rowid DESC LIMIT ?',
                                               (account_id, instrument_id, limit)).fetchall()
                return [json.loads(row[0]) for row in rows]
            values = [json.loads(v) for v in self._snapshots.values()]
            return sorted([v for v in values if v['account_id'] == account_id and v['instrument_id'] == instrument_id],
                          key=lambda v: v['created_at'], reverse=True)[:limit]

    def append_observation(self, value):
        """Append-only: an observation id is written once and never edited."""
        encoded = _encode(value)
        if len(encoded.encode('utf-8')) > 8000:
            raise ValueError('NEXT_SESSION_OBSERVATION_BOUND_EXCEEDED')

        def write():
            if self.connection:
                row = self.connection.execute('SELECT payload FROM next_session_observations WHERE id=?', (value['observation_id'],)).fetchone()
                if row:
                    if row[0] != encoded: raise ValueError('NEXT_SESSION_OBSERVATION_IMMUTABLE')
                    return
                self.connection.execute('INSERT INTO next_session_observations VALUES (?,?,?,?)',
                                        (value['observation_id'], value['snapshot_id'], value['observed_at'], encoded))
            else:
                previous = self._observations.get(value['observation_id'])
                if previous is not None and previous != encoded: raise ValueError('NEXT_SESSION_OBSERVATION_IMMUTABLE')
                self._observations[value['observation_id']] = encoded
        self._write(write)

    def observations(self, snapshot_id, limit=MAX_HISTORY):
        with self.lock:
            if self.connection:
                rows = self.connection.execute('SELECT payload FROM next_session_observations WHERE snapshot_id=? ORDER BY observed_at, rowid LIMIT ?',
                                               (snapshot_id, limit)).fetchall()
                return [json.loads(row[0]) for row in rows]
            values = [json.loads(v) for v in self._observations.values()]
            return sorted([v for v in values if v['snapshot_id'] == snapshot_id], key=lambda v: v['observed_at'])[:limit]

    # --- reevaluation cycle receipts --------------------------------------------
    def put_cycle(self, value):
        encoded = _encode(value)
        if len(encoded.encode('utf-8')) > 32000:
            raise ValueError('REEVALUATION_RECEIPT_BOUND_EXCEEDED')

        def write():
            if self.connection:
                if self.connection.execute('SELECT 1 FROM reevaluation_cycles WHERE id=?', (value['cycle_id'],)).fetchone():
                    raise ValueError('REEVALUATION_RECEIPT_IMMUTABLE')
                self.connection.execute('INSERT INTO reevaluation_cycles VALUES (?,?,?,?,?,?)',
                                        (value['cycle_id'], value['loop_id'], value['scheduled_epoch'], value['session_date'], value['model_call_count'], encoded))
            else:
                if value['cycle_id'] in self._cycles: raise ValueError('REEVALUATION_RECEIPT_IMMUTABLE')
                self._cycles[value['cycle_id']] = encoded
        self._write(write)

    def cycles(self, loop_id, *, limit=20, before=None, session_date=None):
        """Newest first, bounded, cursor by scheduled epoch."""
        limit = max(1, min(int(limit), MAX_HISTORY))
        with self.lock:
            if self.connection:
                sql, params = 'SELECT payload FROM reevaluation_cycles WHERE loop_id=?', [loop_id]
                if before is not None: sql += ' AND scheduled_for<?'; params.append(float(before))
                if session_date: sql += ' AND session_date=?'; params.append(session_date)
                rows = self.connection.execute(sql + ' ORDER BY scheduled_for DESC, rowid DESC LIMIT ?', (*params, limit)).fetchall()
                return [json.loads(row[0]) for row in rows]
            values = [json.loads(v) for v in self._cycles.values()]
            values = [v for v in values if v['loop_id'] == loop_id and (before is None or v['scheduled_epoch'] < float(before))
                      and (not session_date or v['session_date'] == session_date)]
            return sorted(reversed(values), key=lambda v: v['scheduled_epoch'], reverse=True)[:limit]

    def model_calls_since(self, account_id, epoch):
        """Across every loop of the account: a reconfigured scope does not start a fresh budget."""
        with self.lock:
            if self.connection:
                return int(self.connection.execute(
                    'SELECT COALESCE(SUM(model_calls),0) FROM reevaluation_cycles WHERE scheduled_for>=? AND loop_id IN '
                    '(SELECT loop_id FROM reevaluation_loops WHERE account_id=?)', (epoch, account_id)).fetchone()[0])
            return sum(v['model_call_count'] for v in map(json.loads, self._cycles.values())
                       if v['account_id'] == account_id and v['scheduled_epoch'] >= epoch)

    # --- loop configuration, liveness and lease ---------------------------------
    def _loop_row(self, loop_id):
        if self.connection:
            row = self.connection.execute('SELECT owner_id, lease_until, payload FROM reevaluation_loops WHERE loop_id=?', (loop_id,)).fetchone()
            return (row[0], row[1], json.loads(row[2])) if row else None
        return self._loops.get(loop_id)

    def get_loop(self, loop_id):
        with self.lock:
            row = self._loop_row(loop_id)
            return dict(row[2], owner_id=row[0], lease_until=row[1]) if row else None

    def latest_loop(self, account_id):
        with self.lock:
            if self.connection:
                row = self.connection.execute('SELECT loop_id FROM reevaluation_loops WHERE account_id=? ORDER BY updated_at DESC, rowid DESC LIMIT 1', (account_id,)).fetchone()
                return self.get_loop(row[0]) if row else None
            rows = [(v[2]['updated_epoch'], k) for k, v in self._loops.items() if v[2]['account_id'] == account_id]
            return self.get_loop(max(rows)[1]) if rows else None

    def _store_loop(self, payload, owner, lease):
        payload = {k: v for k, v in payload.items() if k not in ('owner_id', 'lease_until')}
        if self.connection:
            self.connection.execute('INSERT INTO reevaluation_loops VALUES (?,?,?,?,?,?) ON CONFLICT(loop_id) DO UPDATE SET updated_at=excluded.updated_at, owner_id=excluded.owner_id, lease_until=excluded.lease_until, payload=excluded.payload',
                                    (payload['loop_id'], payload['account_id'], payload['updated_epoch'], owner, lease, _encode(payload)))
        else:
            self._loops[payload['loop_id']] = (owner, lease, json.loads(_encode(payload)))

    def save_loop(self, payload, *, owner_id=None):
        """Persist liveness/config. With owner_id the write requires that owner to hold the lease."""
        def write():
            row = self._loop_row(payload['loop_id'])
            if owner_id is not None and (row is None or row[0] != owner_id):
                raise ValueError('REEVALUATION_LEASE_LOST')
            self._store_loop(payload, row[0] if row else None, row[1] if row else None)
        self._write(write)

    def acquire_lease(self, loop_id, owner_id, *, now, lease_seconds):
        """Atomic single owner. An expired lease is recoverable without manual cleanup."""
        def write():
            row = self._loop_row(loop_id)
            if row is None:
                raise ValueError('REEVALUATION_NOT_CONFIGURED')
            if row[0] and row[0] != owner_id and row[1] is not None and row[1] > now:
                raise ValueError('REEVALUATION_LOOP_ALREADY_OWNED')
            recovered = bool(row[0] and row[0] != owner_id)
            self._store_loop(row[2], owner_id, now + lease_seconds)
            return recovered
        return self._write(write)

    def heartbeat(self, loop_id, owner_id, *, now, lease_seconds):
        def write():
            row = self._loop_row(loop_id)
            if row is None or row[0] != owner_id:
                raise ValueError('REEVALUATION_LEASE_LOST')
            self._store_loop(dict(row[2], heartbeat_at=now), owner_id, now + lease_seconds)
        self._write(write)

    def release_lease(self, loop_id, owner_id):
        def write():
            row = self._loop_row(loop_id)
            if row is not None and row[0] == owner_id:
                self._store_loop(row[2], None, None)
        self._write(write)


_REPOSITORY = None
_KEY = None


def reevaluation_repository():
    global _REPOSITORY, _KEY
    local = open_local_state() if persistence_enabled() else None
    key = id(local.connection) if local else None
    if _REPOSITORY is None or key != _KEY:
        _REPOSITORY = ReevaluationRepository(local.connection if local else None)
        _KEY = key
    return _REPOSITORY
