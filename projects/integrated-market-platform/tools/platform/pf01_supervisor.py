"""Explicit portable headless PF-01 supervisor. Never registers a task/service.

Plan is the default and read-only. Run requires separately approved deployment,
schema13 migration, sources/rights and activation. No private .env is loaded.

--status prints the persisted supervision evidence without taking ownership.
--preflight reports each operational prerequisite as READY, BLOCKED, UNKNOWN or
NOT VERIFIED. It is read-only, contacts no provider and starts nothing; exit 0
only when every check is READY, 1 when any is BLOCKED, 2 when a fact could not
be read (UNKNOWN), 3 when only operator-evidence items remain (NOT VERIFIED).
--reset-restart-budget is the operator recovery for a latched restart block; it
is refused while a supervisor owns the lease and starts nothing.
"""
from __future__ import annotations
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'src'))
from market_platform_foundation.news.supervision import (CollectionSupervisor, collection_only_reason,
    require_current_schema, reset_restart_budget, supervision_status, child_stop_bound_seconds, LEASE_SECONDS, RESTART_LIMIT,
    RESTART_WINDOW_SECONDS, HEALTHY_RESET_SECONDS, COOLDOWN_LIMIT, AI_CREDENTIAL_PREFIXES)
from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.market_data.headless_supply import supply_status, validate_supply
from tools.platform.pf01_preflight import EXIT_CODES as PREFLIGHT_EXIT_CODES, preflight

OWNER_WAIT_SECONDS=LEASE_SECONDS+30  # one full lease interval of a dead owner, plus margin
TERMINATE_WAIT_SECONDS=5

def storage_path(env) -> Path:
    directory=env.get('IMP_STATE_DIR','')
    if not directory or not Path(directory).is_absolute(): raise ValueError('EXPLICIT_STATE_DIR_REQUIRED')
    path=Path(directory)/'imp-state.sqlite3'
    if not path.is_file(): raise ValueError('EXISTING_STORAGE_REQUIRED')
    require_current_schema(path)
    return path

class OwnedProcess:
    """The child is given its own full stop bound before it is terminated; the wait stays finite."""
    def __init__(self, process, *, stop_seconds=None):
        self.process=process
        self.stop_seconds=child_stop_bound_seconds() if stop_seconds is None else stop_seconds
    def poll(self): return self.process.poll()
    def stop(self):
        if self.poll() is not None: return
        try:
            self.process.stdin.write('stop\n'); self.process.stdin.flush()
            self.process.wait(timeout=self.stop_seconds)
        except (OSError,ValueError,subprocess.TimeoutExpired):  # ValueError: stdin already closed by an interrupted stop
            if self.poll() is None: self.process.terminate()
            self.process.wait(timeout=TERMINATE_WAIT_SECONDS)
        finally:
            if self.process.stdin is not None: self.process.stdin.close()

def child_log_dir(env) -> Path | None:
    directory=env.get('IMP_PF01_CHILD_LOG_DIR','')
    if not directory: return None
    if not Path(directory).is_absolute(): raise ValueError('CHILD_LOG_DIR_NOT_ABSOLUTE')
    return Path(directory)

def child_output(env):
    """Where the child's stdout and stderr go: a daily append-only file when IMP_PF01_CHILD_LOG_DIR is set.

    Discarded output left the 2026-10-22 20:03Z exit code 1 without a cause; the child prints its reason codes.
    """
    directory=child_log_dir(env)
    if directory is None: return subprocess.DEVNULL
    directory.mkdir(parents=True,exist_ok=True)
    return open(directory/time.strftime('child-%Y%m%d.log',time.gmtime()),'ab')  # noqa: SIM115 - closed after spawn

def market_source_demand(env) -> str:
    """What the child would be asked to hold. Read-only; rights and provider state are decided in the child."""
    try: return 'EXPLICIT_TARGETS_CONFIGURED' if validate_supply(env) else 'DISABLED'
    except ValueError as exc: return str(exc)

def plan(env) -> dict:
    return {'activation_requested':False,'enabled':env.get('IMP_PF01_SUPERVISION_ENABLED')=='1',
            'collection_only_blocker':collection_only_reason(env),'services_registered':False,
            'market_source_demand':market_source_demand(env),'restart_limit':RESTART_LIMIT,
            'restart_window_seconds':RESTART_WINDOW_SECONDS,'healthy_reset_seconds':HEALTHY_RESET_SECONDS,
            'cooldown_limit':COOLDOWN_LIMIT,
            'default_action':'READ_ONLY_PLAN','execution_authority':'NONE','ai_required':False}

def own(connection, spawn, *, wait=OWNER_WAIT_SECONDS, sleep=time.sleep, clock=time.monotonic) -> CollectionSupervisor:
    """A previous supervisor that died keeps its lease for at most one interval; wait that long, no longer."""
    deadline=clock()+wait; announced=False
    while True:
        try: return CollectionSupervisor(connection,spawn=spawn,env=os.environ)
        except ValueError as exc:
            if str(exc)!='SUPERVISOR_OWNER_ACTIVE' or clock()>=deadline: raise
            if not announced:
                print(json.dumps({'state':'WAITING','reason':'SUPERVISOR_OWNER_ACTIVE','wait_seconds':wait}),flush=True)
                announced=True
            sleep(5)

def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--run',action='store_true')
    group.add_argument('--status',action='store_true')
    group.add_argument('--preflight',action='store_true')
    group.add_argument('--reset-restart-budget',action='store_true')
    args=parser.parse_args(argv)
    if args.status:
        print(json.dumps({**supervision_status(os.environ),'market_supply':supply_status(os.environ)})); return 0
    if args.preflight:
        report=preflight(os.environ)
        print(json.dumps(report,indent=2)); return PREFLIGHT_EXIT_CODES[report['overall']]
    if args.reset_restart_budget:
        with LocalStateConnection(storage_path(os.environ),require_existing=True) as connection:
            print(json.dumps(reset_restart_budget(connection)))
        return 0
    if not args.run:
        print(json.dumps(plan(os.environ))); return 0
    if os.environ.get('IMP_PF01_SUPERVISION_ENABLED')!='1': raise ValueError('SUPERVISION_DISABLED')
    reason=collection_only_reason(os.environ)
    if reason: raise ValueError(reason)
    child_log_dir(os.environ)  # a misconfigured log location is refused before anything is owned
    path=storage_path(os.environ)  # Refuse automatic migration by this entrypoint.
    with LocalStateConnection(path,require_existing=True) as connection:
        supervisor=None
        def spawn():
            env=dict(os.environ)
            env['IMP_PF01_SUPERVISOR_OWNER']=supervisor.owner
            # Raw acquisition uses no AI credentials; do not forward those secrets.
            for key in list(env):
                if key.startswith(AI_CREDENTIAL_PREFIXES): env.pop(key)
            output=child_output(env)
            try:
                process=subprocess.Popen([sys.executable,'-B',str(ROOT/'tools/ui1/run_ui_api.py'),'--collect-only'],
                    cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=output,stderr=output,
                    text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            finally:
                if output is not subprocess.DEVNULL: output.close()  # the child holds its own handle
            return OwnedProcess(process)
        supervisor=own(connection,spawn)
        try:
            while True:
                supervisor.tick()
                status=supervisor.status()
                if status['state'] in {'BLOCKED','DISABLED'}:
                    print(json.dumps(status)); return 1
                time.sleep(1)
        except KeyboardInterrupt: pass
        finally: supervisor.stop()
        # The stop itself decides the result: a child that did not confirm its drain is not a clean exit.
        status=supervisor.status()
        if status['reason']!='OPERATOR_STOP': print(json.dumps(status)); return 1
        return 0

if __name__=='__main__':
    try: raise SystemExit(main())
    except (ValueError,sqlite3.Error,OSError) as exc:
        reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
        print(json.dumps({'state':'BLOCKED','reason':reason})); raise SystemExit(1)
