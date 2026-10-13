"""Explicit portable headless PF-01 supervisor. Never registers a task/service.

Plan is the default and read-only. Run requires separately approved deployment,
schema13 migration, sources/rights and activation. No private .env is loaded.
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
from market_platform_foundation.news.supervision import CollectionSupervisor, collection_only_reason, require_current_schema
from market_platform_foundation.local_state.connection import LocalStateConnection

def storage_path(env) -> Path:
    directory=env.get('IMP_STATE_DIR','')
    if not directory or not Path(directory).is_absolute(): raise ValueError('EXPLICIT_STATE_DIR_REQUIRED')
    path=Path(directory)/'imp-state.sqlite3'
    if not path.is_file(): raise ValueError('EXISTING_STORAGE_REQUIRED')
    require_current_schema(path)
    return path

class OwnedProcess:
    def __init__(self, process): self.process=process
    def poll(self): return self.process.poll()
    def stop(self):
        if self.poll() is not None: return
        try:
            self.process.stdin.write('stop\n'); self.process.stdin.flush()
            self.process.wait(timeout=15)
        except (OSError,subprocess.TimeoutExpired):
            if self.poll() is None: self.process.terminate()
            self.process.wait(timeout=5)
        finally:
            if self.process.stdin is not None: self.process.stdin.close()

def plan(env) -> dict:
    return {'activation_requested':False,'enabled':env.get('IMP_PF01_SUPERVISION_ENABLED')=='1',
            'collection_only_blocker':collection_only_reason(env),'services_registered':False,
            'market_source_demand':'NOT_ACQUIRED_BY_THIS_ENTRYPOINT','restart_limit':3,
            'default_action':'READ_ONLY_PLAN','execution_authority':'NONE','ai_required':False}

def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args(argv)
    if not args.run:
        print(json.dumps(plan(os.environ))); return 0
    if os.environ.get('IMP_PF01_SUPERVISION_ENABLED')!='1': raise ValueError('SUPERVISION_DISABLED')
    reason=collection_only_reason(os.environ)
    if reason: raise ValueError(reason)
    path=storage_path(os.environ)  # Refuse automatic migration by this entrypoint.
    with LocalStateConnection(path,require_existing=True) as connection:
        supervisor=None
        def spawn():
            env=dict(os.environ)
            env['IMP_PF01_SUPERVISOR_OWNER']=supervisor.owner
            # Raw acquisition uses no AI credentials; do not forward those secrets.
            for key in list(env):
                if key.startswith(('ANTHROPIC_','OPENAI_','AZURE_OPENAI_','GEMINI_')): env.pop(key)
            process=subprocess.Popen([sys.executable,'-B',str(ROOT/'tools/ui1/run_ui_api.py'),'--collect-only'],
                cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            return OwnedProcess(process)
        supervisor=CollectionSupervisor(connection,spawn=spawn,env=os.environ)
        try:
            while True:
                supervisor.tick()
                status=supervisor.status()
                if status['state'] in {'BLOCKED','DISABLED'}:
                    print(json.dumps(status)); return 1
                time.sleep(1)
        except KeyboardInterrupt: return 0
        finally: supervisor.stop()

if __name__=='__main__':
    try: raise SystemExit(main())
    except (ValueError,sqlite3.Error,OSError) as exc:
        reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
        print(json.dumps({'state':'BLOCKED','reason':reason})); raise SystemExit(1)
