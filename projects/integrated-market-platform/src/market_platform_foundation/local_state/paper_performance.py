"""Account-scoped, append-only step 8 evidence on existing local-state storage."""
import json
import threading

from .connection import CRITICAL_WRITE_RETRY_SECONDS
from contextlib import nullcontext

def encode(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)

class PerformanceRepository:
    def __init__(self,connection=None):
        self.connection=connection
        self.lock=threading.RLock()
        self.memory={}
        if connection:
            with connection.transaction(retry_seconds=CRITICAL_WRITE_RETRY_SECONDS):
                connection.execute("CREATE TABLE IF NOT EXISTS paper_performance_records ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT,account_id TEXT NOT NULL,run_id TEXT NOT NULL,"
                    "kind TEXT NOT NULL,artifact_key TEXT NOT NULL,payload TEXT NOT NULL,"
                    "UNIQUE(account_id,run_id,kind,artifact_key))")
                connection.execute("CREATE INDEX IF NOT EXISTS paper_performance_run "
                                   "ON paper_performance_records(account_id,run_id,kind,id)")
                connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS paper_performance_experiment "
                                   "ON paper_performance_records(account_id,artifact_key) WHERE kind='run'")

    @property
    def durability(self):
        return "SQLITE_LOCAL_STATE" if self.connection else "INTENTIONAL_EPHEMERAL"

    def append(self,account,run_id,kind,key,payload):
        encoded=encode(payload)
        if len(encoded.encode())>4_000_000:
            raise ValueError("PERFORMANCE_ARTIFACT_TOO_LARGE")
        with self.lock, (self.connection.transaction(retry_seconds=CRITICAL_WRITE_RETRY_SECONDS) if self.connection else nullcontext()):
            if self.connection:
                prior=self.connection.fetchone("SELECT payload FROM paper_performance_records "
                    "WHERE account_id=? AND run_id=? AND kind=? AND artifact_key=?",(account,run_id,kind,key))
                previous=prior[0] if prior else None
            else:
                previous=self.memory.get((account,run_id,kind,key))
            if previous is not None:
                if previous!=encoded:
                    raise ValueError("PERFORMANCE_ARTIFACT_IMMUTABLE")
                return False
            if kind=="run" and any(r["experiment_id"]==payload["experiment_id"] for r in self.runs(account)):
                raise ValueError("EXPERIMENT_ALREADY_ENROLLED")
            if self.connection:
                self.connection.execute("INSERT INTO paper_performance_records "
                    "(account_id,run_id,kind,artifact_key,payload) VALUES (?,?,?,?,?)",(account,run_id,kind,key,encoded))
            else:
                self.memory[(account,run_id,kind,key)]=encoded
            return True

    def rows(self,account,run_id,kind=None):
        with self.lock:
            if self.connection:
                suffix=" AND kind=?" if kind else ""
                params=(account,run_id,kind) if kind else (account,run_id)
                rows=self.connection.fetchall("SELECT payload FROM paper_performance_records "
                    "WHERE account_id=? AND run_id=?"+suffix+" ORDER BY id LIMIT 100001",params)
                if len(rows)>100000:
                    raise ValueError("PERFORMANCE_EVIDENCE_BOUND_EXCEEDED")
                return [json.loads(r[0]) for r in rows]
            values=[json.loads(v) for (a,r,k,_),v in self.memory.items() if a==account and r==run_id and (kind is None or k==kind)]
            if len(values)>100000:
                raise ValueError("PERFORMANCE_EVIDENCE_BOUND_EXCEEDED")
            return values

    def runs(self,account):
        with self.lock:
            if self.connection:
                rows=self.connection.fetchall("SELECT payload FROM paper_performance_records "
                    "WHERE account_id=? AND kind='run' ORDER BY id DESC LIMIT 101",(account,))
                if len(rows)>100:
                    raise ValueError("PERFORMANCE_RUN_BOUND_EXCEEDED")
                return [json.loads(r[0]) for r in rows]
            return [json.loads(v) for (a,_,k,_),v in reversed(list(self.memory.items())) if a==account and k=="run"]

    def latest(self,account,run_id,kind):
        with self.lock:
            if self.connection:
                row=self.connection.fetchone("SELECT payload FROM paper_performance_records "
                    "WHERE account_id=? AND run_id=? AND kind=? ORDER BY id DESC LIMIT 1",(account,run_id,kind))
                return json.loads(row[0]) if row else None
            rows=self.rows(account,run_id,kind)
            return rows[-1] if rows else None
