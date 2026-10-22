"""Immutable evaluation artifacts on canonical local-state (no new database)."""
import json
import threading

from .paths import persistence_enabled
from .startup import open_local_state
from ..evaluation.prospective import encode


class EvaluationRepository:
    def __init__(self, connection=None):
        self.connection=connection
        self.lock=threading.RLock()
        self.memory={}
        if connection:
            with connection.transaction():
                connection.execute('CREATE TABLE IF NOT EXISTS prospective_evaluation_runs '
                                   '(id TEXT PRIMARY KEY, account_id TEXT NOT NULL, cutoff TEXT NOT NULL, payload TEXT NOT NULL)')
                connection.execute('CREATE INDEX IF NOT EXISTS prospective_evaluation_account ON prospective_evaluation_runs(account_id,cutoff)')

    @property
    def durability(self):
        return 'SQLITE_LOCAL_STATE' if self.connection else 'INTENTIONAL_EPHEMERAL'

    def get(self, identifier, account_id):
        with self.lock:
            if self.connection:
                row=self.connection.execute('SELECT payload FROM prospective_evaluation_runs WHERE id=? AND account_id=?',
                                            (identifier,account_id)).fetchone()
                return json.loads(row[0]) if row else None
            value=self.memory.get((identifier,account_id))
            return json.loads(value) if value else None

    def put(self, run, account_id):
        encoded=encode(run)
        if len(encoded.encode())>16_000_000:
            raise ValueError('EVALUATION_ARTIFACT_BOUND_EXCEEDED')
        with self.lock:
            def write():
                old=self.get(run['run_id'],account_id)
                if old is not None:
                    if encode(old)!=encoded:
                        raise ValueError('IMMUTABLE_EVALUATION_COLLISION')
                    return
                if self.connection:
                    self.connection.execute('INSERT INTO prospective_evaluation_runs VALUES (?,?,?,?)',
                                            (run['run_id'],account_id,run['cutoff'],encoded))
                else:
                    self.memory[(run['run_id'],account_id)]=encoded
            if self.connection and not self.connection.in_transaction:
                with self.connection.transaction():
                    write()
            else:
                write()

    def list(self, account_id, *, before=None, limit=25):
        limit=min(max(int(limit),1),100)
        with self.lock:
            if self.connection:
                rows=self.connection.execute('SELECT payload FROM prospective_evaluation_runs WHERE account_id=? AND cutoff<? '
                                             'ORDER BY cutoff DESC,id DESC LIMIT ?', (account_id,before or '9999',limit)).fetchall()
                values=[json.loads(r[0]) for r in rows]
            else:
                values=sorted([json.loads(v) for (_,a),v in self.memory.items() if a==account_id],key=lambda r:(r['cutoff'],r['run_id']),reverse=True)
                values=[v for v in values if v['cutoff']<(before or '9999')][:limit]
            return [dict(run_id=v['run_id'],cutoff=v['cutoff'],evidence_class=v['evidence_class'],admission=v['admission']) for v in values]


_REPOSITORY=None
_CONNECTION=None


def evaluation_repository():
    global _REPOSITORY, _CONNECTION
    state=open_local_state() if persistence_enabled() else None
    connection=state.connection if state else None
    if _REPOSITORY is None or connection is not _CONNECTION:
        _REPOSITORY=EvaluationRepository(connection)
        _CONNECTION=connection
    return _REPOSITORY
