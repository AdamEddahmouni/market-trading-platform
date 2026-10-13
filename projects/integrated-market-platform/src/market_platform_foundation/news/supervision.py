"""Default-off collection process supervision, using existing raw-job SQLite leases.

The reserved row is control evidence, never a provider job. No scheduler/service
registration, subscription, inference or execution dispatch lives here.
"""
from __future__ import annotations
import json
import os
import sqlite3
from contextlib import closing
import time
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4
from ..local_state.connection import LocalStateConnection

SUPERVISION_JOB = '__pf01_supervision__'
LEASE_SECONDS = 120
RESTART_LIMIT = 3
EXECUTION_GATES = ('IMP_PAPER_EXECUTION','IMP_BROKER_PAPER_EXECUTION','IMP_MOOMOO_PAPER_EXECUTION',
                   'IMP_LIVE_EXECUTION','IMP_BROKER_LIVE_EXECUTION','IMP_LIVE_INTERNAL_SIMULATION')

def require_current_schema(path: Path) -> None:
    """Read-only refusal: headless PF-01 entrypoints never migrate a store themselves."""
    from ..local_state.schema import SCHEMA_VERSION
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            version=db.execute('SELECT MAX(schema_version) FROM schema_meta').fetchone()[0]
    except sqlite3.Error:
        version=None
    if version != SCHEMA_VERSION: raise ValueError('APPROVED_SCHEMA_MIGRATION_REQUIRED')

def collection_only_reason(env: Mapping[str, str]) -> str | None:
    if any(env.get(gate) == '1' for gate in EXECUTION_GATES): return 'EXECUTION_GATE_ENABLED'
    if env.get('IMP_CONTROLLED_REPLAY','').lower() in {'1','true','yes'}: return 'REPLAY_MODE'
    if env.get('IMP_PERSIST_STATE') != '1': return 'DURABLE_STATE_REQUIRED'
    if not any(env.get(k) == '1' for k in ('IMP_NEWS_COLLECTION_ENABLED','IMP_MARKET_PERSISTENCE_ENABLED')):
        return 'COLLECTION_DISABLED'
    return None

class CollectionSupervisor:
    def __init__(self, connection: LocalStateConnection, *, spawn: Callable[[], Any],
                 env: Mapping[str,str], clock: Callable[[],float] = time.time) -> None:
        self.connection,self.spawn,self.env,self.clock = connection,spawn,env,clock
        self.owner=uuid4().hex; self.child=None; self._stopped=False
        stat=connection.path.stat(); self._identity=(stat.st_dev,stat.st_ino)
        self._evidence={'state':'DISABLED','reason':None,'crashes':0,'next_start':0,'events':[]}
        if env.get('IMP_PF01_SUPERVISION_ENABLED') != '1': return
        directory=env.get('IMP_STATE_DIR','')
        if not directory or not Path(directory).is_absolute() or (Path(directory)/'imp-state.sqlite3').resolve()!=connection.path.resolve():
            raise ValueError('SUPERVISOR_STORAGE_MISMATCH')
        now=self.clock()
        if not self._storage_ok(): raise ValueError('SUPERVISOR_STORAGE_UNAVAILABLE')
        with connection.transaction():
            row=connection.execute('SELECT * FROM news_collection_jobs WHERE job_id=?',(SUPERVISION_JOB,)).fetchone()
            if row and row['lease_owner'] and row['lease_until']>now: raise ValueError('SUPERVISOR_OWNER_ACTIVE')
            if row:
                self._evidence=json.loads(row['payload_json'])
                if row['lease_owner']:
                    self._event('UNCLEAN_SUPERVISOR_RESTART')
                    self._evidence['next_start']=now+LEASE_SECONDS
            self._evidence.update(state='WAITING',reason=None)
            connection.execute('INSERT OR REPLACE INTO news_collection_jobs VALUES (?,?,?,?,?)',
                (SUPERVISION_JOB,json.dumps(self._evidence),0,self.owner,now+LEASE_SECONDS))

    def _event(self, reason: str) -> None:
        self._evidence['events']=(self._evidence.get('events',[])+[{'at':self.clock(),'reason':reason}])[-32:]

    def _save(self) -> None:
        if not self._storage_ok(): raise OSError('SUPERVISOR_STORAGE_UNAVAILABLE')
        with self.connection.transaction():
            row=self.connection.execute('SELECT lease_owner,lease_until FROM news_collection_jobs WHERE job_id=?',(SUPERVISION_JOB,)).fetchone()
            if row is None or row['lease_owner']!=self.owner or row['lease_until']<self.clock():
                raise ValueError('OWNERSHIP_LOST')
            self.connection.execute('UPDATE news_collection_jobs SET payload_json=?,lease_until=? WHERE job_id=? AND lease_owner=?',
                (json.dumps(self._evidence),self.clock()+LEASE_SECONDS,SUPERVISION_JOB,self.owner))

    def _halt(self, reason: str, state: str = 'BLOCKED') -> None:
        if self.child is not None:
            self.child.stop(); self.child=None
        self._evidence.update(state=state,reason=reason)

    def _storage_ok(self) -> bool:
        try:
            path=self.connection.path; stat=path.stat(); wal=Path(str(path)+'-wal')
            size=stat.st_size+(wal.stat().st_size if wal.is_file() else 0)
            return (stat.st_dev,stat.st_ino)==self._identity and size+8*1024*1024<=512*1024*1024
        except OSError: return False

    def tick(self) -> None:
        if self._stopped: return
        if self.env.get('IMP_PF01_SUPERVISION_ENABLED') != '1':
            self._halt('SUPERVISION_DISABLED','DISABLED'); return
        if not self._storage_ok():
            self._halt('STORAGE_UNAVAILABLE'); return
        try:
            self._save()
            reason=collection_only_reason(self.env)
            if reason: self._halt(reason); self._save(); return
            if self._evidence['crashes']>=RESTART_LIMIT:
                self._halt('RESTART_LIMIT_EXCEEDED'); self._save(); return
            if self.child is not None:
                exit_code=self.child.poll()
                if exit_code is None: return
                self.child=None; self._evidence['crashes']+=1
                self._event('CHILD_PROCESS_EXIT_GAP_UNVERIFIED')
                # Child output is discarded; its exit code is the only durable cause evidence.
                if isinstance(exit_code,int): self._evidence['events'][-1]['exit_code']=exit_code
                self._evidence.update(state='BACKOFF',reason='CHILD_PROCESS_EXIT',next_start=self.clock()+LEASE_SECONDS)
                if self._evidence['crashes']>=RESTART_LIMIT:
                    self._evidence.update(state='BLOCKED',reason='RESTART_LIMIT_EXCEEDED')
                self._save(); return
            if self.clock()<self._evidence.get('next_start',0): return
            self._evidence.update(state='STARTING',reason=None); self._event('CHILD_START_ATTEMPT'); self._save()
            try:
                self.child=self.spawn()
            except Exception:
                self._evidence['crashes']+=1
                self._evidence.update(state='BACKOFF',reason='CHILD_START_FAILED',next_start=self.clock()+LEASE_SECONDS)
            else: self._evidence.update(state='RUNNING',reason=None)
            self._save()
        except Exception as exc:
            self._halt('OWNERSHIP_LOST' if isinstance(exc,ValueError) and str(exc)=='OWNERSHIP_LOST' else 'SUPERVISION_EVIDENCE_UNAVAILABLE')

    def status(self) -> dict[str,Any]:
        return json.loads(json.dumps({**self._evidence,'restart_limit':RESTART_LIMIT,'lease_seconds':LEASE_SECONDS,
            'process_alive':self.child is not None and self.child.poll() is None,
            'execution_authority':'NONE','ai_required':False}))

    def stop(self) -> None:
        if self._stopped: return
        if self._evidence['state'] in {'BLOCKED','DISABLED'}:
            self._halt(self._evidence['reason'],self._evidence['state'])
        else:
            self._halt('OPERATOR_STOP','STOPPED')
        self._stopped=True
        try:
            if not self._storage_ok(): return
            self.connection.execute('UPDATE news_collection_jobs SET payload_json=?,lease_owner=NULL,lease_until=0 WHERE job_id=? AND lease_owner=?',
                (json.dumps(self._evidence),SUPERVISION_JOB,self.owner))
        except Exception: pass  # An expired unclosed lease remains crash evidence.


def supervision_status(env: Mapping[str,str] | None = None, *, clock: Callable[[],float] = time.time) -> dict[str,Any]:
    """Existing health route can read headless supervision evidence without migrating."""
    values=os.environ if env is None else env
    directory=values.get('IMP_STATE_DIR','')
    if not directory or not Path(directory).is_absolute(): return {'enabled':False,'state':'DISABLED'}
    path=Path(directory)/'imp-state.sqlite3'
    if not path.is_file(): return {'enabled':False,'state':'DISABLED'}
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.1)) as db:
            row=db.execute('SELECT payload_json,lease_owner,lease_until FROM news_collection_jobs WHERE job_id=?',(SUPERVISION_JOB,)).fetchone()
        if row is None: return {'enabled':False,'state':'DISABLED'}
        evidence=json.loads(row[0])
        if row[1] and row[2]<clock(): evidence.update(state='STALE',reason='SUPERVISOR_LEASE_EXPIRED')
        return {**evidence,'enabled':bool(row[1]),'lease_until':row[2],
                'health_basis':'PERSISTED_PARENT_LEASE_NOT_SOURCE_COVERAGE','execution_authority':'NONE','ai_required':False}
    except Exception:
        return {'enabled':False,'state':'UNKNOWN','reason':'SUPERVISION_STATUS_UNAVAILABLE'}
