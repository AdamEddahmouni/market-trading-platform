"""Experimental results and receipts live outside operational candidate records."""
from __future__ import annotations
import json
import threading
from contextlib import nullcontext
from .ai_screener_coverage import CoverageLedger
from .paths import persistence_enabled
from .startup import open_local_state

class StagedLedger(CoverageLedger):
    def __init__(self, connection=None):
        super().__init__(connection, table="ai_screener_staged_records")

class StagedRepository:
    def __init__(self,connection=None):
        self.connection,self.lock,self._memory=connection,threading.RLock(),{}
        if connection:
            with connection.transaction():
                connection.execute("CREATE TABLE IF NOT EXISTS ai_screener_experimental_results (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    def get(self,identifier):
        with self.connection._lock if self.connection else nullcontext(),self.lock:
            row=self.connection.execute("SELECT payload FROM ai_screener_experimental_results WHERE id=?",(identifier,)).fetchone() if self.connection else None
            encoded=row[0] if row else self._memory.get(identifier)
            return json.loads(encoded) if encoded else None
    def put(self,result):
        if result.get("method")!="STAGED_LOCAL_FIRST_EXPERIMENTAL" or result.get("operationally_approved") is not False:
            raise ValueError("EXPERIMENTAL_RESULT_AUTHORITY_INVALID")
        encoded=json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False)
        if len(encoded.encode())>512000:
            raise ValueError("EXPERIMENTAL_RESULT_BOUND_EXCEEDED")
        identifier=result["run_id"]
        with self.connection._lock if self.connection else nullcontext(),self.lock:
            old=self.get(identifier)
            if old is not None:
                if old!=result: raise ValueError("IMMUTABLE_EXPERIMENTAL_RESULT_COLLISION")
                return
            if self.connection:
                self.connection.execute("INSERT INTO ai_screener_experimental_results VALUES (?,?)",(identifier,encoded))
            else:
                self._memory[identifier]=encoded
    def finalize(self,ledger,run_id,result,terminal):
        if self.connection is not ledger.connection:
            raise ValueError("EXPERIMENTAL_FINALIZATION_STORE_MISMATCH")
        with self.connection._lock if self.connection else nullcontext(),self.lock,ledger.lock:
            memory,records=dict(self._memory),list(ledger._memory)
            try:
                with self.connection.transaction() if self.connection else nullcontext():
                    self.put(result)
                    ledger.append(run_id,"terminal",terminal)
            except Exception:
                self._memory,self_records=memory,records
                ledger._memory=self_records
                raise

_STORES=None
_KEY=None

def staged_stores():
    global _STORES,_KEY
    local=open_local_state() if persistence_enabled() else None
    connection=local.connection if local else None
    key=id(connection) if connection else None
    if _STORES is None or key!=_KEY:
        _STORES=(StagedLedger(connection),StagedRepository(connection))
        _KEY=key
    return _STORES
