"""PF-01 opt-in raw news lifecycle on existing adapters and local_state SQLite.

One bounded job per step. No sentiment, synthesis, detector, opportunity, or
execution dispatch. Rolling provider windows are not certified complete history.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4

from ..local_state.connection import LocalStateConnection
from .dedupe import dedupe_identity_key

MAX_JOBS = 64
MAX_BATCH_BYTES = 2 * 1024 * 1024
LEASE_SECONDS = 120
INTERVALS = {"finviz": 120, "rss": 300, "newsapi": 900, "finnhub": 600, "sec_filings": 600}
UNIVERSES = ("US_EQUITIES", "US_ETFS", "FUTURES", "BONDS", "CRYPTO")


@dataclass(frozen=True)
class CollectionJob:
    provider: str
    query: str
    universe: str
    interval: float

    @property
    def id(self) -> str:
        return f"{self.provider}:{self.query}:{self.universe}"


def configured_jobs(env: Mapping[str, str]) -> list[CollectionJob]:
    def parts(name: str, default: str = "") -> list[str]:
        return list(dict.fromkeys(x.strip() for x in env.get(name, default).split(",") if x.strip()))
    providers = parts("IMP_NEWS_COLLECTION_PROVIDERS")
    universes = parts("IMP_NEWS_COLLECTION_UNIVERSES", ",".join(UNIVERSES))
    symbols = parts("IMP_NEWS_COLLECTION_SYMBOLS")
    if not providers or any(p not in INTERVALS for p in providers) or not universes or any(u not in UNIVERSES for u in universes):
        raise ValueError("COLLECTION_TARGETS_INVALID")
    if len(symbols) > 20 or any(not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}", s) for s in symbols):
        raise ValueError("COLLECTION_SYMBOLS_INVALID")
    if set(providers) & {"newsapi", "finnhub", "sec_filings"} and not symbols:
        raise ValueError("COLLECTION_SYMBOLS_REQUIRED")
    jobs = []
    for provider in providers:
        interval = float(env.get(f"IMP_NEWS_COLLECTION_{provider.upper()}_SECONDS", INTERVALS[provider]))
        if not INTERVALS[provider] <= interval <= 86400:
            raise ValueError("COLLECTION_INTERVAL_INVALID")
        targets = [("", "US_EQUITIES")] if provider == "finviz" else [("", u) for u in universes] if provider == "rss" else [(s, "US_EQUITIES") for s in symbols]
        jobs.extend(CollectionJob(provider, query, universe, interval) for query, universe in targets)
    if len(jobs) > MAX_JOBS:
        raise ValueError("COLLECTION_TARGET_BOUND_EXCEEDED")
    return jobs


class NewsCollector:
    def __init__(self, connection: LocalStateConnection, jobs: list[CollectionJob],
                 fetch: Callable[[CollectionJob], tuple[list, dict]], *, clock: Callable[[], float] = time.time,
                 max_database_bytes: int = 512 * 1024 * 1024) -> None:
        if not jobs or len(jobs) > MAX_JOBS or len({j.id for j in jobs}) != len(jobs):
            raise ValueError("COLLECTION_TARGETS_INVALID")
        self.connection, self.jobs, self.fetch, self.clock = connection, jobs, fetch, clock
        self.max_database_bytes = max_database_bytes
        self.owner = uuid4().hex
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._step_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._state, self._reason = "READY", None
        self._heartbeat: float | None = None
        self._owns_connection = False
        stat = connection.path.stat()
        self._storage_identity = (stat.st_dev, stat.st_ino)
        with connection.transaction():
            for job in jobs:
                connection.execute("INSERT OR IGNORE INTO news_collection_jobs(job_id,payload_json,next_due) VALUES (?,?,?)",
                                   (job.id, json.dumps({"state": "PENDING", "failures": 0, "coverage_start": self.clock()}), 0))

    def _storage_ok(self) -> bool:
        path = self.connection.path
        if not path.is_file():
            return False
        stat = path.stat()
        if (stat.st_dev, stat.st_ino) != self._storage_identity:
            return False
        wal = Path(str(path) + "-wal")
        size = stat.st_size + (wal.stat().st_size if wal.is_file() else 0)
        # Payload bytes alone omit page/index/WAL overhead. Match the market
        # writer's conservative reserve; the configured acquisition limit stays.
        return size + 4 * MAX_BATCH_BYTES <= self.max_database_bytes

    def _set_state(self, state: str, reason: str | None = None) -> None:
        with self._state_lock:
            self._state, self._reason = state, reason

    def step(self) -> None:
        if self._stop.is_set() or not self._step_lock.acquire(blocking=False):
            return
        try:
            self._heartbeat = self.clock()
            if not self._storage_ok():
                self._set_state("BLOCKED", "STORAGE_UNAVAILABLE_OR_BOUND_EXCEEDED")
                return
            now = self.clock()
            selected = None
            with self.connection.transaction():
                due = []
                for job in self.jobs:
                    row = self.connection.execute("SELECT * FROM news_collection_jobs WHERE job_id=?", (job.id,)).fetchone()
                    saved = json.loads(row['payload_json'])
                    owned_pending = row['lease_owner'] == self.owner and saved.get('state') == 'PENDING'
                    if owned_pending:
                        # Renew even when an unattempted target outranks this poll.
                        self.connection.execute("UPDATE news_collection_jobs SET lease_until=? WHERE job_id=? AND lease_owner=?",
                            (now + LEASE_SECONDS, job.id, self.owner))
                    if row['next_due'] <= now and (row['lease_until'] <= now or owned_pending):
                        due.append((row['next_due'], job.id, job, saved))
                if due:
                    _, _, job, state = min(due)
                    state.update(last_attempt=now, state="COLLECTING")
                    last = state.get("last_success")
                    boundary = last if last is not None else state.get('coverage_start', now)
                    if now > boundary + 2 * job.interval:
                        gap = state.get("gap") or {"start": boundary + job.interval if last is not None else boundary}
                        state['gap'] = {**gap, "end": now, "state": "UNVERIFIED_ROLLING_WINDOW"}
                    self.connection.execute("UPDATE news_collection_jobs SET payload_json=?,lease_owner=?,lease_until=? WHERE job_id=?",
                        (json.dumps(state), self.owner, now + LEASE_SECONDS, job.id))
                    selected = job, state
            if selected is None:
                self._set_state("WAITING")
                return
            job, state = selected
            previous_success = state.get('last_success')
            self._set_state("COLLECTING")
            try:
                articles, receipt = self.fetch(job)
                if len(articles) > 1000:
                    raise ValueError("COLLECTION_BATCH_BOUND_EXCEEDED")
                encoded = []
                for article, provenance in articles:
                    identity = (article.provider_id, article.source_id, *dedupe_identity_key(article))
                    record_id = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
                    payload = json.dumps({'article': article.to_dict(), 'provenance': provenance}, sort_keys=True)
                    encoded.append((record_id, article, payload))
                if sum(len(payload.encode()) for _, _, payload in encoded) > MAX_BATCH_BYTES:
                    raise ValueError("COLLECTION_BATCH_BOUND_EXCEEDED")
                if not self._storage_ok():
                    raise OSError("COLLECTION_STORAGE_UNAVAILABLE")
                provider_state = receipt.get('state', 'ERROR')
                success = provider_state in {'CURRENT', 'DELAYED'} and not receipt.get('rejected_count')
                pending = provider_state == 'PENDING'
                state.update(provider_state=provider_state, state='HEALTHY' if success else 'PENDING' if pending else 'BACKOFF',
                             last_received=receipt.get('fetched_at'), rejected_count=receipt.get('rejected_count', 0),
                             failures=0 if success else state.get('failures', 0) + (0 if pending else 1),
                             reason=None if success else 'PROVIDER_PENDING' if pending else 'PROVIDER_UNAVAILABLE_OR_PARTIAL')
                if success:
                    state['last_success'] = self.clock()
                delay = job.interval if success else 5 if pending else min(86400, max(job.interval, 60) * 2 ** min(state['failures'], 8))
                # One catch-up request to the adapter's bounded existing rolling window.
                # A successful response never closes an uncertified historical gap.
                next_due = self.clock() + delay
                inserted = 0
                with self.connection.transaction():
                    row = self.connection.execute("SELECT lease_owner,lease_until FROM news_collection_jobs WHERE job_id=?", (job.id,)).fetchone()
                    if row['lease_owner'] != self.owner:
                        return
                    if row['lease_until'] < self.clock():
                        state.pop('last_success', None)
                        if previous_success is not None:
                            state['last_success'] = previous_success
                        state.update(state='BACKOFF', reason='COLLECTION_LEASE_EXPIRED')
                        self.connection.execute('UPDATE news_collection_jobs SET payload_json=?,next_due=?,lease_owner=NULL,lease_until=0 WHERE job_id=? AND lease_owner=?',
                            (json.dumps(state), self.clock()+job.interval, job.id, self.owner))
                        self._set_state('BLOCKED', 'COLLECTION_LEASE_EXPIRED')
                        return
                    for record_id, article, payload in encoded:
                        cursor = self.connection.execute("INSERT OR IGNORE INTO news_collection_records VALUES (?,?,?,?,?,?,?)",
                            (record_id, article.provider_id, article.source_id, article.published_time, article.retrieved_time, self.clock(), payload))
                        inserted += cursor.rowcount
                    state['inserted_count'] = inserted
                    state['duplicate_count'] = len(encoded) - inserted
                    self.connection.execute("UPDATE news_collection_jobs SET payload_json=?,next_due=?,lease_owner=?,lease_until=? WHERE job_id=?",
                        (json.dumps(state), next_due, self.owner if pending else None,
                         self.clock() + LEASE_SECONDS if pending else 0, job.id))
                self._set_state("WAITING")
            except Exception:
                # Do not expose exception text, which can contain provider credentials.
                if previous_success is None:
                    state.pop('last_success', None)
                else:
                    state['last_success'] = previous_success
                state.update(state="BACKOFF", reason="COLLECTION_FETCH_OR_WRITE_FAILED", failures=state.get('failures', 0) + 1)
                self.connection.execute("UPDATE news_collection_jobs SET payload_json=?,next_due=?,lease_owner=NULL,lease_until=0 WHERE job_id=? AND lease_owner=?",
                    (json.dumps(state), self.clock() + min(86400, job.interval * 2 ** min(state['failures'], 8)), job.id, self.owner))
                self._set_state("WAITING")
        except Exception:
            self._set_state("BLOCKED", "COLLECTION_STORAGE_OR_CHECKPOINT_FAILED")
        finally:
            self._step_lock.release()

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            state, reason = self._state, self._reason
        rows = []
        try:
            for job in self.jobs:
                row = self.connection.execute("SELECT * FROM news_collection_jobs WHERE job_id=?", (job.id,)).fetchone()
                rows.append({"id": job.id, "provider": job.provider, "interval": job.interval, "next_due": row['next_due'],
                             "lease_until": row['lease_until'], **json.loads(row['payload_json'])})
        except Exception:
            state, reason = "BLOCKED", "COLLECTION_STATUS_STORAGE_FAILED"
        if self._stop.is_set() and self._thread is not None and self._thread.is_alive():
            state, reason = 'BLOCKED', 'COLLECTION_SHUTDOWN_INCOMPLETE'
        elif self._stop.is_set():
            state = "PAUSED"
        elif self._thread is not None and not self._thread.is_alive():
            state, reason = "BLOCKED", "COLLECTION_WORKER_STOPPED"
        elif self._heartbeat is not None and self.clock() - self._heartbeat > LEASE_SECONDS:
            state, reason = "STALE", "COLLECTION_HEARTBEAT_STALE"
        return {"enabled": True, "state": state, "reason": reason, "worker_alive": bool(self._thread and self._thread.is_alive()),
                "last_heartbeat": self._heartbeat, "jobs": rows, "pending_count": sum(j['next_due'] <= self.clock() for j in rows),
                "storage": "DURABLE_SQLITE", "ai_required": False, "execution_authority": "NONE"}

    def start(self) -> None:
        if self._thread is not None:
            return
        def run() -> None:
            while not self._stop.is_set():
                self.step()
                self._stop.wait(1)
        self._thread = threading.Thread(target=run, name="raw-news-collection", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=10)
        if self._thread is not None and self._thread.is_alive():
            self._set_state('BLOCKED', 'COLLECTION_SHUTDOWN_INCOMPLETE')
            return
        self._set_state("PAUSED")
        if self._owns_connection:
            self.connection.close()
            self._owns_connection = False


_COLLECTOR: NewsCollector | None = None
_STARTUP_STATUS: dict[str, Any] = {"enabled": False, "state": "DISABLED"}
_STARTUP_LOCK = threading.RLock()


def validate_collection_storage(env: Mapping[str, str]) -> Path:
    """Enabled collection cannot create a replacement empty DB after SSD loss."""
    directory = env.get('IMP_STATE_DIR', '')
    path = Path(directory) / 'imp-state.sqlite3'
    if not directory or not Path(directory).is_absolute() or not path.is_file():
        raise ValueError("COLLECTION_EXISTING_EXPLICIT_STORAGE_REQUIRED")
    return path.resolve()


def start_collection(data_mode: str, *, env: Mapping[str, str] | None = None) -> NewsCollector | None:
    with _STARTUP_LOCK:
        return _start_collection(data_mode, env=env)


def _start_collection(data_mode: str, *, env: Mapping[str, str] | None = None) -> NewsCollector | None:
    import os
    global _COLLECTOR, _STARTUP_STATUS
    values = os.environ if env is None else env
    if values.get('IMP_NEWS_COLLECTION_ENABLED') != '1':
        return None
    if data_mode not in {'LIVE_OBSERVATIONAL', 'BROKER_DELAYED'} or values.get('IMP_CONTROLLED_REPLAY', '').lower() in {'1', 'true', 'yes'}:
        _STARTUP_STATUS = {'enabled': True, 'state': 'BLOCKED', 'reason': 'COLLECTION_LIVE_DATA_MODE_REQUIRED'}
        return None
    if _COLLECTOR is not None:
        return _COLLECTOR
    try:
        path = validate_collection_storage(values)
        stat = path.stat()
        identity = (stat.st_dev, stat.st_ino)
        jobs = configured_jobs(values)
        # Never call the create-capable global startup factory after validation.
        connection = LocalStateConnection(path, require_existing=True, expected_identity=identity)
        from ..ui_api.screener_news import news_service
        service = news_service()
        def fetch(job: CollectionJob):
            records, status = service.collect_raw(job.provider, job.query, job.universe)
            return [(r.event, {'source_type': r.source_type, 'cik': r.cik, 'available_time': r.available_time,
                               'ingested_time': r.ingested_time}) for r in records], status
        collector = NewsCollector(connection, jobs, fetch)
        collector._owns_connection = True
        collector.start()
        _COLLECTOR = collector
        return collector
    except Exception:
        if 'collector' in locals():
            collector.stop()
            if collector.status()['worker_alive']:
                _COLLECTOR = collector
        elif 'connection' in locals():
            connection.close()
        _STARTUP_STATUS = {'enabled': True, 'state': 'BLOCKED', 'reason': 'COLLECTION_CONFIGURATION_OR_STORAGE_INVALID'}
        return None


def collection_status() -> dict[str, Any]:
    return _COLLECTOR.status() if _COLLECTOR is not None else dict(_STARTUP_STATUS)


def stop_collection() -> None:
    global _COLLECTOR, _STARTUP_STATUS
    with _STARTUP_LOCK:
        if _COLLECTOR is not None:
            _COLLECTOR.stop()
            if _COLLECTOR.status()['worker_alive']:
                return
            _COLLECTOR = None
        _STARTUP_STATUS = {'enabled': False, 'state': 'DISABLED'}
