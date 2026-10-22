"""Immutable bounded action/candidate receipts on the existing local-state DB."""
from __future__ import annotations

import json
import threading
from contextlib import nullcontext

from .paths import persistence_enabled
from .startup import open_local_state


class ActionDecisionRepository:
    def __init__(self, connection=None):
        self.connection = connection
        self._memory = {}
        self.lock = threading.RLock()
        if connection is not None:
            with connection.transaction():
                connection.execute('CREATE TABLE IF NOT EXISTS action_decision_records (kind TEXT NOT NULL, id TEXT NOT NULL, instrument_id TEXT, decision_time TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind,id))')
                connection.execute('CREATE INDEX IF NOT EXISTS action_decision_history ON action_decision_records(kind,instrument_id,decision_time)')

    def get(self, kind, identifier):
        with self.connection._lock if self.connection else nullcontext(), self.lock:
            if self.connection:
                row = self.connection.execute('SELECT payload FROM action_decision_records WHERE kind=? AND id=?', (kind,identifier)).fetchone()
                encoded = row[0] if row else None
            else:
                encoded = self._memory.get((kind,identifier))
            return json.loads(encoded) if encoded else None

    def put(self, kind, identifier, value):
        if kind not in ('candidate_run','decision'):
            raise ValueError('ACTION_RECORD_KIND_INVALID')
        encoded = json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(encoded.encode('utf-8')) > (512000 if kind=='candidate_run' else 128000):
            raise ValueError('ACTION_RECORD_BOUND_EXCEEDED')
        with self.connection._lock if self.connection else nullcontext(), self.lock:
            def insert():
                previous = self.get(kind,identifier)
                if previous is not None:
                    if previous != value: raise ValueError('IMMUTABLE_ACTION_RECORD_COLLISION')
                    return
                if self.connection:
                    self.connection.execute('INSERT INTO action_decision_records VALUES (?,?,?,?,?)',
                        (kind,identifier,value.get('instrument_id'),value.get('decision_time'),encoded))
                else: self._memory[kind,identifier] = encoded
            if self.connection and not self.connection.in_transaction:
                with self.connection.transaction(): insert()
            else: insert()

    def evaluation_decisions(self, account_id, cutoff, *, limit=10001):
        """Bounded accounting read; compare instants, never ISO lexical spelling."""
        from datetime import datetime
        instant = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00'))
        with self.connection._lock if self.connection else nullcontext(), self.lock:
            if self.connection:
                rows = self.connection.execute(
                    "SELECT payload FROM action_decision_records WHERE kind='decision' "
                    "AND json_extract(payload,'$.position.account_id')=? LIMIT ?",
                    (account_id, limit)).fetchall()
                values = [json.loads(r[0]) for r in rows]
            else:
                values = [json.loads(v) for (k, _), v in self._memory.items() if k == 'decision']
                values = [r for r in values if r['position']['account_id'] == account_id]
            if len(values) >= limit:
                raise ValueError('EVALUATION_ACCOUNT_SOURCE_BOUND_EXCEEDED')
            return sorted([r for r in values if instant(r['decision_time']) <= instant(cutoff)],
                          key=lambda r:(instant(r['decision_time']), r['decision_id']))

    def history(self, instrument_id):
        with self.connection._lock if self.connection else nullcontext(), self.lock:
            if self.connection:
                rows = self.connection.execute('SELECT payload FROM action_decision_records WHERE kind=? AND instrument_id=? ORDER BY decision_time DESC, rowid DESC LIMIT 100', ('decision',instrument_id)).fetchall()
                return [json.loads(row[0]) for row in rows]
            return list(reversed([json.loads(v) for (k,_),v in self._memory.items() if k=='decision' and json.loads(v)['instrument_id']==instrument_id]))[:100]


_REPOSITORY = None
_KEY = None


def action_repository():
    global _REPOSITORY, _KEY
    local = open_local_state() if persistence_enabled() else None
    key = id(local.connection) if local else None
    if _REPOSITORY is None or key != _KEY:
        _REPOSITORY = ActionDecisionRepository(local.connection if local else None)
        _KEY = key
    return _REPOSITORY
