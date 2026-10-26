"""AUTO-01 autonomous Paper automation state on the existing local-state DB.

Policies and audit events are immutable; one controller row per Paper account carries
the lease; one intent row per Action Decision makes a Paper submission unrepeatable.
Persist-off keeps the same contract in process memory (INTENTIONAL_EPHEMERAL).
"""
from __future__ import annotations

import json
import threading

from .connection import CRITICAL_WRITE_RETRY_SECONDS

from .paths import persistence_enabled
from .startup import open_local_state

MAX_HISTORY = 200
MAX_EVENT_BYTES = 32000


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class PaperAutomationRepository:
    def __init__(self, connection=None):
        self.connection = connection
        self.lock = threading.RLock()
        self._policies, self._controllers, self._events, self._intents = {}, {}, [], {}
        if connection is not None:
            with connection.transaction(retry_seconds=CRITICAL_WRITE_RETRY_SECONDS):
                connection.execute('CREATE TABLE IF NOT EXISTS paper_automation_policies (policy_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, created_at REAL NOT NULL, payload TEXT NOT NULL)')
                connection.execute('CREATE TABLE IF NOT EXISTS paper_automation_controllers (account_id TEXT PRIMARY KEY, updated_at REAL NOT NULL, owner_id TEXT, lease_until REAL, payload TEXT NOT NULL)')
                connection.execute('CREATE TABLE IF NOT EXISTS paper_automation_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT NOT NULL, at REAL NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL)')
                connection.execute('CREATE INDEX IF NOT EXISTS paper_automation_event_history ON paper_automation_events(account_id,sequence)')
                connection.execute('CREATE TABLE IF NOT EXISTS paper_automation_intents (intent_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, decision_id TEXT NOT NULL, state TEXT NOT NULL, updated_at REAL NOT NULL, payload TEXT NOT NULL)')
                connection.execute('CREATE UNIQUE INDEX IF NOT EXISTS paper_automation_intent_decision ON paper_automation_intents(account_id,decision_id)')

    @property
    def durability(self):
        return 'SQLITE_LOCAL_STATE' if self.connection else 'INTENTIONAL_EPHEMERAL'

    def _write(self, operation):
        with self.lock:
            if self.connection and not self.connection.in_transaction:
                with self.connection.transaction(retry_seconds=CRITICAL_WRITE_RETRY_SECONDS):
                    return operation()
            return operation()

    # --- immutable policy versions ------------------------------------------------
    def put_policy(self, policy, *, now):
        encoded = _encode(policy)

        def write():
            previous = self.get_policy(policy['policy_id'])
            if previous is not None:
                if _encode(previous) != encoded:
                    raise ValueError('AUTOMATION_POLICY_IMMUTABLE')
                return
            if self.connection:
                self.connection.execute('INSERT INTO paper_automation_policies VALUES (?,?,?,?)',
                                        (policy['policy_id'], policy['account_id'], now, encoded))
            else:
                self._policies[policy['policy_id']] = encoded
        self._write(write)

    def get_policy(self, policy_id):
        with self.lock:
            if self.connection:
                row = self.connection.execute('SELECT payload FROM paper_automation_policies WHERE policy_id=?', (policy_id,)).fetchone()
                encoded = row[0] if row else None
            else:
                encoded = self._policies.get(policy_id)
            return json.loads(encoded) if encoded else None

    # --- controller state and lease -----------------------------------------------
    def _row(self, account_id):
        if self.connection:
            row = self.connection.execute('SELECT owner_id, lease_until, payload FROM paper_automation_controllers WHERE account_id=?', (account_id,)).fetchone()
            return (row[0], row[1], json.loads(row[2])) if row else None
        return self._controllers.get(account_id)

    def get_controller(self, account_id):
        with self.lock:
            row = self._row(account_id)
            return dict(row[2], owner_id=row[0], lease_until=row[1]) if row else None

    def armed_controllers(self):
        """Accounts whose persisted controller is armed, for startup recovery. Reads only."""
        with self.lock:
            if self.connection:
                rows = [json.loads(r[0]) for r in self.connection.execute('SELECT payload FROM paper_automation_controllers').fetchall()]
            else:
                rows = [row[2] for row in self._controllers.values()]
            return [row for row in rows if row.get('arming')]

    def _store(self, payload, owner, lease):
        payload = {k: v for k, v in payload.items() if k not in ('owner_id', 'lease_until')}
        if self.connection:
            self.connection.execute('INSERT INTO paper_automation_controllers VALUES (?,?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET updated_at=excluded.updated_at, owner_id=excluded.owner_id, lease_until=excluded.lease_until, payload=excluded.payload',
                                    (payload['account_id'], payload['updated_epoch'], owner, lease, _encode(payload)))
        else:
            self._controllers[payload['account_id']] = (owner, lease, json.loads(_encode(payload)))

    def save_controller(self, payload, *, owner_id=None):
        """Persist controller state. With owner_id the write requires that owner to hold the lease."""
        def write():
            row = self._row(payload['account_id'])
            if owner_id is not None and (row is None or row[0] != owner_id):
                raise ValueError('AUTOMATION_LEASE_LOST')
            self._store(payload, row[0] if row else None, row[1] if row else None)
        self._write(write)

    def acquire_lease(self, account_id, owner_id, *, now, lease_seconds):
        """Atomic single owner per account. An expired lease is recoverable without manual cleanup."""
        def write():
            row = self._row(account_id)
            if row is None:
                raise ValueError('AUTOMATION_NOT_CONFIGURED')
            if row[0] and row[0] != owner_id and row[1] is not None and row[1] > now:
                raise ValueError('AUTOMATION_ALREADY_OWNED')
            self._store(row[2], owner_id, now + lease_seconds)
        self._write(write)

    def heartbeat(self, account_id, owner_id, *, now, lease_seconds):
        def write():
            row = self._row(account_id)
            if row is None or row[0] != owner_id:
                raise ValueError('AUTOMATION_LEASE_LOST')
            self._store(dict(row[2], heartbeat_at=now), owner_id, now + lease_seconds)
        self._write(write)

    def release_lease(self, account_id, owner_id):
        def write():
            row = self._row(account_id)
            if row is not None and row[0] == owner_id:
                self._store(row[2], None, None)
        self._write(write)

    # --- append-only audit ----------------------------------------------------------
    def append_event(self, account_id, kind, payload, *, now):
        encoded = _encode(payload)
        if len(encoded.encode('utf-8')) > MAX_EVENT_BYTES:
            raise ValueError('AUTOMATION_EVENT_BOUND_EXCEEDED')

        def write():
            if self.connection:
                cursor = self.connection.execute('INSERT INTO paper_automation_events (account_id, at, kind, payload) VALUES (?,?,?,?)',
                                                 (account_id, now, kind, encoded))
                return int(cursor.lastrowid)
            self._events.append((len(self._events) + 1, account_id, now, kind, encoded))
            return len(self._events)
        return self._write(write)

    def events(self, account_id, *, limit=50, before=None, kinds=None):
        """Newest first, bounded, cursor by sequence."""
        limit = max(1, min(int(limit), MAX_HISTORY))
        kinds = list(kinds or [])
        with self.lock:
            if self.connection:
                sql, params = 'SELECT sequence, at, kind, payload FROM paper_automation_events WHERE account_id=?', [account_id]
                if before is not None:
                    sql += ' AND sequence<?'; params.append(int(before))
                if kinds:
                    sql += ' AND kind IN (%s)' % ','.join('?' * len(kinds)); params.extend(kinds)
                rows = self.connection.execute(sql + ' ORDER BY sequence DESC LIMIT ?', (*params, limit)).fetchall()
            else:
                rows = [(s, at, kind, payload) for s, account, at, kind, payload in reversed(self._events)
                        if account == account_id and (before is None or s < int(before)) and (not kinds or kind in kinds)][:limit]
            return [dict(sequence=row[0], at=row[1], kind=row[2], **json.loads(row[3])) for row in rows]

    def event_counts(self, account_id, *, since=None):
        with self.lock:
            if self.connection:
                rows = self.connection.execute('SELECT kind, COUNT(*) FROM paper_automation_events WHERE account_id=? AND at>=? GROUP BY kind',
                                               (account_id, float(since or 0))).fetchall()
                return {row[0]: int(row[1]) for row in rows}
            counts = {}
            for _, account, at, kind, _payload in self._events:
                if account == account_id and at >= float(since or 0):
                    counts[kind] = counts.get(kind, 0) + 1
            return counts

    # --- one intent per Action Decision ---------------------------------------------
    def get_intent(self, intent_id):
        with self.lock:
            if self.connection:
                row = self.connection.execute('SELECT payload FROM paper_automation_intents WHERE intent_id=?', (intent_id,)).fetchone()
                encoded = row[0] if row else None
            else:
                encoded = self._intents.get(intent_id)
            return json.loads(encoded) if encoded else None

    def put_intent(self, intent, *, now):
        """Create or advance an intent. A submitted intent is terminal: it can never be reopened."""
        encoded = _encode(intent)

        def write():
            previous = self.get_intent(intent['intent_id'])
            if previous is not None:
                if previous['decision_id'] != intent['decision_id'] or previous['account_id'] != intent['account_id']:
                    raise ValueError('AUTOMATION_INTENT_IDENTITY_CONFLICT')
                if previous['state'] == 'SUBMITTED' and intent['state'] != 'SUBMITTED':
                    raise ValueError('AUTOMATION_INTENT_TERMINAL')
            if self.connection:
                self.connection.execute('INSERT INTO paper_automation_intents VALUES (?,?,?,?,?,?) ON CONFLICT(intent_id) DO UPDATE SET state=excluded.state, updated_at=excluded.updated_at, payload=excluded.payload',
                                        (intent['intent_id'], intent['account_id'], intent['decision_id'], intent['state'], now, encoded))
            else:
                self._intents[intent['intent_id']] = encoded
        self._write(write)

    def intents(self, account_id, *, limit=50, states=None):
        limit = max(1, min(int(limit), MAX_HISTORY))
        states = list(states or [])
        with self.lock:
            if self.connection:
                sql, params = 'SELECT payload FROM paper_automation_intents WHERE account_id=?', [account_id]
                if states:
                    sql += ' AND state IN (%s)' % ','.join('?' * len(states)); params.extend(states)
                rows = self.connection.execute(sql + ' ORDER BY updated_at DESC, rowid DESC LIMIT ?', (*params, limit)).fetchall()
                return [json.loads(row[0]) for row in rows]
            values = [json.loads(v) for v in self._intents.values()]
            values = [v for v in values if v['account_id'] == account_id and (not states or v['state'] in states)]
            return sorted(values, key=lambda v: v['updated_epoch'], reverse=True)[:limit]


_REPOSITORY = None
_KEY = None


def paper_automation_repository():
    global _REPOSITORY, _KEY
    local = open_local_state() if persistence_enabled() else None
    key = id(local.connection) if local else None
    if _REPOSITORY is None or key != _KEY:
        _REPOSITORY = PaperAutomationRepository(local.connection if local else None)
        _KEY = key
    return _REPOSITORY
