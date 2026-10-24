"""Default-off collection process supervision, using existing raw-job SQLite leases.

The reserved row is control evidence, never a provider job. No scheduler/service
registration, subscription, inference or execution dispatch lives here.

Restart policy: at most RESTART_LIMIT automatic restarts per rolling
RESTART_WINDOW_SECONDS, with doubling backoff. HEALTHY_RESET_SECONDS of
continuous child uptime restores the allowance. COOLDOWN_LIMIT exhausted
windows in a row, or a child that reports a configuration it cannot run, latch
a block that only ``reset_restart_budget`` clears. So do UNHEALTHY_FAILURE_LIMIT
child failures with no healthy period between them: a child that fails every
twenty-odd minutes never fills a window, and must not restart for ever.
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
from ..local_state.connection import LocalStateConnection, transient_storage_error
from ..market_data.capacity import DEFAULT_MAX_DATABASE_BYTES, configured_max_database_bytes

SUPERVISION_JOB = '__pf01_supervision__'
LEASE_SECONDS = 120
RESTART_LIMIT = 3
RESTART_WINDOW_SECONDS = 3600
BACKOFF_CAP_SECONDS = 900
HEALTHY_RESET_SECONDS = 1800
COOLDOWN_LIMIT = 3
# The most restarts the windows above grant a child that never stays healthy.
UNHEALTHY_FAILURE_LIMIT = RESTART_LIMIT * COOLDOWN_LIMIT
STORAGE_GRACE_SECONDS = 900
CHILD_EXIT_PERMANENT = 78  # the child refused its own configuration; restarting cannot help
# Beyond the workers' own stop bounds: the child's 1 s stop poll, one 5 s storage busy wait in the
# iteration in flight, the final evidence writes and interpreter exit.
CHILD_STOP_MARGIN_SECONDS = 8.0
PERMANENT_CHILD_REASONS = frozenset({
    'EXECUTION_GATE_ENABLED', 'REPLAY_MODE', 'DURABLE_STATE_REQUIRED', 'COLLECTION_DISABLED',
    'APPROVED_SCHEMA_MIGRATION_REQUIRED', 'SCHEMA_CHECK_STORAGE_INVALID', 'COLLECTION_ENTRYPOINT_CONFLICT',
    'MARKET_SUPPLY_TARGETS_REQUIRED', 'MARKET_SUPPLY_TARGETS_INVALID', 'MARKET_SUPPLY_REQUIRES_PERSISTENCE',
    'MARKET_SUPPLY_TARGET_NOT_PERSISTED', 'MARKET_SUPPLY_PROVIDER_GATE_CLOSED', 'MARKET_SUPPLY_PROVIDER_CONFLICT',
    'MARKET_CAPTURE_TARGETS_INVALID', 'MARKET_CAPTURE_LIMITS_INVALID',
    'MARKET_CAPTURE_STORAGE_LIMIT_INVALID', 'MARKET_CAPTURE_REQUIRES_OBSERVATIONAL_MODE',
    'MARKET_EXPLICIT_STATE_DIR_REQUIRED', 'COLLECTION_TARGETS_INVALID', 'COLLECTION_SYMBOLS_INVALID',
    'COLLECTION_SYMBOLS_REQUIRED', 'COLLECTION_INTERVAL_INVALID', 'COLLECTION_TARGET_BOUND_EXCEEDED'})
AI_CREDENTIAL_PREFIXES = ('ANTHROPIC_','OPENAI_','AZURE_OPENAI_','GEMINI_')  # never forwarded to the child
EXECUTION_GATES = ('IMP_PAPER_EXECUTION','IMP_BROKER_PAPER_EXECUTION','IMP_MOOMOO_PAPER_EXECUTION',
                   'IMP_LIVE_EXECUTION','IMP_BROKER_LIVE_EXECUTION','IMP_LIVE_INTERNAL_SIMULATION')

def require_current_schema(path: Path) -> None:
    """Read-only refusal: headless PF-01 entrypoints never migrate a store themselves."""
    from ..local_state.schema import SCHEMA_VERSION
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            version=db.execute('SELECT MAX(schema_version) FROM schema_meta').fetchone()[0]
    except sqlite3.Error as exc:
        # A store that could not be read is not a store at the wrong schema.
        if transient_storage_error(exc): raise ValueError('SCHEMA_CHECK_STORAGE_UNAVAILABLE') from None
        # A corrupt file is not waiting for a migration; only a readable store without the table is.
        if not isinstance(exc,sqlite3.OperationalError): raise ValueError('SCHEMA_CHECK_STORAGE_INVALID') from None
        version=None
    if version != SCHEMA_VERSION: raise ValueError('APPROVED_SCHEMA_MIGRATION_REQUIRED')

def collection_only_reason(env: Mapping[str, str]) -> str | None:
    if any(env.get(gate) == '1' for gate in EXECUTION_GATES): return 'EXECUTION_GATE_ENABLED'
    if env.get('IMP_CONTROLLED_REPLAY','').lower() in {'1','true','yes'}: return 'REPLAY_MODE'
    if env.get('IMP_PERSIST_STATE') != '1': return 'DURABLE_STATE_REQUIRED'
    if not any(env.get(k) == '1' for k in ('IMP_NEWS_COLLECTION_ENABLED','IMP_MARKET_PERSISTENCE_ENABLED')):
        return 'COLLECTION_DISABLED'
    return None

def child_stop_bound_seconds() -> float:
    """How long a requested stop may legitimately take in the collection-only child.

    Its workers stop one after another (producers, then the writer's final drain), each within its
    own bound. A parent that waits less terminates a healthy drain and leaves an unknown tail, so
    the supervisor's wait is derived from the same constants instead of chosen separately.
    """
    from ..market_data import headless_supply, persistence
    from . import collection
    return (headless_supply.stop_bound_seconds() + collection.WORKER_JOIN_SECONDS
            + persistence.WORKER_JOIN_SECONDS + persistence.FINAL_DRAIN_SECONDS + CHILD_STOP_MARGIN_SECONDS)

def child_exit_code(reason: str) -> int:
    return CHILD_EXIT_PERMANENT if reason in PERMANENT_CHILD_REASONS else 1

def _defaults(evidence: dict[str,Any]) -> dict[str,Any]:
    """Rows written before the rolling budget carry only a lifetime crash count."""
    for key,value in (('crashes',0),('next_start',0),('events',[]),('restarts',[]),('cooldowns',0),
                      ('pending_restart',False),('running_since',None),('latched',None),
                      ('unhealthy_failures',0)):
        evidence.setdefault(key,value)
    return evidence

class CollectionSupervisor:
    def __init__(self, connection: LocalStateConnection, *, spawn: Callable[[], Any],
                 env: Mapping[str,str], clock: Callable[[],float] = time.time) -> None:
        self.connection,self.spawn,self.env,self.clock = connection,spawn,env,clock
        self.owner=uuid4().hex; self.child=None; self._stopped=False
        self._unclean_stop=False
        self._outage_since=None; self._outage_reason=None; self._outage_stopped_child=False
        stat=connection.path.stat(); self._identity=(stat.st_dev,stat.st_ino)
        self._evidence=_defaults({'state':'DISABLED','reason':None})
        self._saved_at=self.clock()
        self._max_bytes=DEFAULT_MAX_DATABASE_BYTES
        if env.get('IMP_PF01_SUPERVISION_ENABLED') != '1': return
        self._max_bytes=configured_max_database_bytes(env)  # malformed or unapproved: refuse to supervise
        directory=env.get('IMP_STATE_DIR','')
        if not directory or not Path(directory).is_absolute() or (Path(directory)/'imp-state.sqlite3').resolve()!=connection.path.resolve():
            raise ValueError('SUPERVISOR_STORAGE_MISMATCH')
        now=self.clock()
        if not self._storage_ok(): raise ValueError('SUPERVISOR_STORAGE_UNAVAILABLE')
        with connection.transaction():
            row=connection.execute('SELECT * FROM news_collection_jobs WHERE job_id=?',(SUPERVISION_JOB,)).fetchone()
            if row and row['lease_owner'] and row['lease_until']>now: raise ValueError('SUPERVISOR_OWNER_ACTIVE')
            if row:
                self._evidence=_defaults(json.loads(row['payload_json']))
                if row['lease_owner']:
                    self._event('UNCLEAN_SUPERVISOR_RESTART')
                    # The orphaned child may hold its own leases for one more interval.
                    self._evidence['next_start']=max(self._evidence['next_start'],now+LEASE_SECONDS)
            self._evidence.update(state='WAITING',reason=None,running_since=None)
            connection.execute('INSERT OR REPLACE INTO news_collection_jobs VALUES (?,?,?,?,?)',
                (SUPERVISION_JOB,json.dumps(self._evidence),0,self.owner,now+LEASE_SECONDS))

    def _event(self, reason: str, **detail: Any) -> None:
        self._evidence['events']=(self._evidence.get('events',[])+[{'at':self.clock(),'reason':reason,**detail}])[-32:]

    def _save(self, *, reacquire: bool = False) -> None:
        if not self._storage_ok(): raise OSError('SUPERVISOR_STORAGE_UNAVAILABLE')
        now=self.clock()
        with self.connection.transaction():
            row=self.connection.execute('SELECT lease_owner,lease_until FROM news_collection_jobs WHERE job_id=?',(SUPERVISION_JOB,)).fetchone()
            if row is None or row['lease_owner']!=self.owner: raise ValueError('OWNERSHIP_LOST')
            # A lapsed lease that nobody else claimed may only be renewed after the child is stopped.
            if row['lease_until']<now and not reacquire: raise ValueError('LEASE_LAPSED')
            self.connection.execute('UPDATE news_collection_jobs SET payload_json=?,lease_until=? WHERE job_id=? AND lease_owner=?',
                (json.dumps(self._evidence),now+LEASE_SECONDS,SUPERVISION_JOB,self.owner))
        self._saved_at=now

    def _stop_child(self) -> bool:
        if self.child is None: return False
        child=self.child; self._evidence['running_since']=None
        try: child.stop(); exit_code=child.poll()
        except Exception: exit_code=None; failed=True  # the handle could not confirm the stop either way
        except BaseException:
            # An interrupted stop proves nothing about the child. Keep the handle so the next stop finishes it.
            self._event('CHILD_STOP_EXIT_GAP_UNVERIFIED'); self._unclean_stop=True
            raise
        else: failed=False
        self.child=None
        # Exit 0 is the child's only confirmation that producers drained and the final commit landed.
        if failed or exit_code!=0:
            self._event('CHILD_STOP_EXIT_GAP_UNVERIFIED',**({'exit_code':exit_code} if isinstance(exit_code,int) else {}))
            self._unclean_stop=True
        return True

    def _halt(self, reason: str, state: str = 'BLOCKED') -> None:
        self._stop_child()
        self._evidence.update(state=state,reason=reason)

    def _storage_fault(self) -> str | None:
        try:
            path=self.connection.path; stat=path.stat(); wal=Path(str(path)+'-wal')
            size=stat.st_size+(wal.stat().st_size if wal.is_file() else 0)
        except OSError: return 'STORAGE_UNAVAILABLE'  # possibly a drive that returns
        if (stat.st_dev,stat.st_ino)!=self._identity: return 'STORAGE_REPLACED'
        if size+8*1024*1024>self._max_bytes: return 'STORAGE_BOUND_EXCEEDED'
        return None

    def _storage_ok(self) -> bool:
        return self._storage_fault() is None

    def _outage(self, reason: str) -> None:
        """Bounded wait. The child is stopped and nothing restarts until evidence can be written again."""
        now=self.clock()
        if self._outage_since is None: self._outage_since,self._outage_reason=now,reason
        self._outage_stopped_child=self._stop_child() or self._outage_stopped_child
        expired=now-self._outage_since>STORAGE_GRACE_SECONDS
        self._evidence.update(state='BLOCKED' if expired else 'STORAGE_WAIT',reason=self._outage_reason)

    def _failure(self, event: str, reason: str, *, child_fault: bool = True, **detail: Any) -> None:
        """Account one unplanned child stop against the rolling restart budget."""
        now=self.clock()
        self._evidence['crashes']+=1
        self._evidence['running_since']=None
        self._event(event,**detail)
        if child_fault:
            # Spaced-out failures never exhaust a window; the streak since the last healthy period does.
            self._evidence['unhealthy_failures']+=1
            if self._evidence['unhealthy_failures']>=UNHEALTHY_FAILURE_LIMIT:
                self._evidence['pending_restart']=False
                self._latch('PERSISTENT_CHILD_FAILURE'); return
        # A clock set backwards must not keep old restarts inside the window forever.
        recent=[min(at,now) for at in self._evidence['restarts'] if now-min(at,now)<RESTART_WINDOW_SECONDS]
        self._evidence.update(restarts=recent,pending_restart=True)
        if len(recent)<RESTART_LIMIT:
            self._evidence.update(state='BACKOFF',reason=reason,
                next_start=now+min(BACKOFF_CAP_SECONDS,LEASE_SECONDS*2**len(recent)))
            return
        self._evidence['cooldowns']+=1
        if self._evidence['cooldowns']>=COOLDOWN_LIMIT:
            self._latch('PERSISTENT_CHILD_FAILURE')
            return
        self._event('RESTART_LIMIT_EXCEEDED')
        self._evidence.update(state='COOLDOWN',reason='RESTART_LIMIT_EXCEEDED',
            next_start=max(now+LEASE_SECONDS,recent[0]+RESTART_WINDOW_SECONDS))

    def _latch(self, reason: str) -> None:
        self._event(reason)
        self._evidence.update(state='BLOCKED',reason=reason,latched=reason)

    def tick(self) -> None:
        if self._stopped: return
        if self.env.get('IMP_PF01_SUPERVISION_ENABLED') != '1':
            self._halt('SUPERVISION_DISABLED','DISABLED'); return
        if not self._storage_ok():
            fault=self._storage_fault() or 'STORAGE_UNAVAILABLE'
            if fault=='STORAGE_UNAVAILABLE': self._outage(fault)
            else: self._halt(fault)  # a replaced or full store is an operator decision
            return
        now=self.clock()
        try:
            try:
                self._save(reacquire=self._outage_since is not None)
            except ValueError as exc:
                if str(exc)!='LEASE_LAPSED': raise
                # Suspend/resume or a long stall: the child may not continue on a lapsed parent lease.
                self._outage_since,self._outage_reason=self._saved_at,'SUPERVISOR_LEASE_LAPSED'
                self._outage_stopped_child=self._stop_child()
                self._save(reacquire=True)
            if self._outage_since is not None:
                since,reason,stopped=self._outage_since,self._outage_reason,self._outage_stopped_child
                self._outage_since=self._outage_reason=None; self._outage_stopped_child=False
                if stopped: self._failure('SUPERVISION_OUTAGE_GAP_UNVERIFIED',reason,child_fault=False,outage_start=since)
                else:
                    self._event('SUPERVISION_OUTAGE_RECOVERED',outage_start=since)
                    if self._evidence['state'] in {'STORAGE_WAIT','BLOCKED'}: self._evidence.update(state='WAITING',reason=None)
                self._save(); return
            reason=collection_only_reason(self.env)
            if reason: self._halt(reason); self._save(); return
            if self._evidence['latched']:
                self._halt(self._evidence['latched']); self._save(); return
            if self.child is not None:
                exit_code=self.child.poll()
                if exit_code is None:
                    since=self._evidence['running_since']
                    if (since is not None and now-since>=HEALTHY_RESET_SECONDS
                            and (self._evidence['restarts'] or self._evidence['cooldowns']
                                 or self._evidence['unhealthy_failures'])):
                        self._evidence.update(restarts=[],cooldowns=0,unhealthy_failures=0)
                        self._event('RESTART_BUDGET_RESET_AFTER_HEALTHY_PERIOD'); self._save()
                    return
                self.child=None
                # Child output is discarded; its exit code is the only durable cause evidence.
                detail={'exit_code':exit_code} if isinstance(exit_code,int) else {}
                if exit_code==CHILD_EXIT_PERMANENT:
                    self._evidence['crashes']+=1; self._evidence['running_since']=None
                    self._event('CHILD_PROCESS_EXIT_GAP_UNVERIFIED',**detail)
                    self._latch('CHILD_CONFIGURATION_REJECTED')
                else: self._failure('CHILD_PROCESS_EXIT_GAP_UNVERIFIED','CHILD_PROCESS_EXIT',**detail)
                self._save(); return
            if now<self._evidence['next_start']: return
            self._evidence.update(state='STARTING',reason=None); self._event('CHILD_START_ATTEMPT')
            if self._evidence['pending_restart']:
                self._evidence['restarts']=self._evidence['restarts']+[now]; self._evidence['pending_restart']=False
            self._save()
            try:
                self.child=self.spawn()
            except Exception:
                self._failure('CHILD_START_FAILED','CHILD_START_FAILED')
            else: self._evidence.update(state='RUNNING',reason=None,running_since=self.clock())
            self._save()
        except Exception as exc:
            if isinstance(exc,ValueError) and str(exc)=='OWNERSHIP_LOST': self._halt('OWNERSHIP_LOST')
            # Brief contention: the lease is still valid and the child keeps its own checks.
            elif self.child is not None and transient_storage_error(exc) and isinstance(exc,sqlite3.Error) \
                    and now-self._saved_at<LEASE_SECONDS/2: pass
            else: self._outage('SUPERVISION_EVIDENCE_UNAVAILABLE')

    def status(self) -> dict[str,Any]:
        now=self.clock()
        return json.loads(json.dumps({**self._evidence,'restart_limit':RESTART_LIMIT,'lease_seconds':LEASE_SECONDS,
            'restart_window_seconds':RESTART_WINDOW_SECONDS,'healthy_reset_seconds':HEALTHY_RESET_SECONDS,
            'cooldown_limit':COOLDOWN_LIMIT,'unhealthy_failure_limit':UNHEALTHY_FAILURE_LIMIT,
            'restarts_in_window':sum(now-at<RESTART_WINDOW_SECONDS for at in self._evidence['restarts']),
            'process_alive':self.child is not None and self.child.poll() is None,
            'execution_authority':'NONE','ai_required':False}))

    def stop(self) -> None:
        if self._stopped: return
        self._unclean_stop=False  # only this stop's own child exit decides its reason
        if self._evidence['state'] in {'BLOCKED','DISABLED'}:
            self._halt(self._evidence['reason'],self._evidence['state'])
        else:
            self._halt('OPERATOR_STOP','STOPPED')
            if self._unclean_stop: self._evidence['reason']='OPERATOR_STOP_CHILD_EXIT_UNVERIFIED'
        self._stopped=True
        try:
            if not self._storage_ok(): return
            self.connection.execute('UPDATE news_collection_jobs SET payload_json=?,lease_owner=NULL,lease_until=0 WHERE job_id=? AND lease_owner=?',
                (json.dumps(self._evidence),SUPERVISION_JOB,self.owner))
        except Exception: pass  # An expired unclosed lease remains crash evidence.


def reset_restart_budget(connection: LocalStateConnection, *, clock: Callable[[],float] = time.time) -> dict[str,Any]:
    """Operator recovery: clear the restart window and any latched block. Refused while a supervisor owns the row."""
    now=clock()
    with connection.transaction():
        row=connection.execute('SELECT * FROM news_collection_jobs WHERE job_id=?',(SUPERVISION_JOB,)).fetchone()
        if row is None: raise ValueError('SUPERVISION_EVIDENCE_MISSING')
        if row['lease_owner'] and row['lease_until']>now: raise ValueError('SUPERVISOR_OWNER_ACTIVE')
        evidence=_defaults(json.loads(row['payload_json']))
        evidence['events']=(evidence['events']+[{'at':now,'reason':'OPERATOR_RESTART_BUDGET_RESET',
            'cleared':evidence['latched'] or evidence.get('reason')}])[-32:]
        evidence.update(state='STOPPED',reason='OPERATOR_RESTART_BUDGET_RESET',restarts=[],cooldowns=0,unhealthy_failures=0,
                        pending_restart=False,latched=None,next_start=0,running_since=None)
        connection.execute('UPDATE news_collection_jobs SET payload_json=? WHERE job_id=?',(json.dumps(evidence),SUPERVISION_JOB))
    return evidence


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
