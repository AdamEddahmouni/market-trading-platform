"""PF-01 opt-in raw news lifecycle on existing adapters and local_state SQLite.

One bounded job per step. No sentiment, synthesis, detector, opportunity, or
execution dispatch. Rolling provider windows are not certified complete history.

Every source is its own job: each RSS catalog feed, each per-symbol provider
query. A failing source backs off alone; the others keep their schedule.
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

from ..local_state.connection import LocalStateConnection, transient_storage_error
from .dedupe import dedupe_identity_key
from .rss_feeds import FEEDS

MAX_JOBS = 64
MAX_BATCH_BYTES = 2 * 1024 * 1024
LEASE_SECONDS = 120
RETRY_LIMIT = 6  # consecutive recoverable storage failures before the collector reports BLOCKED
WORKER_JOIN_SECONDS = 10.0  # stop bound; part of news.supervision.child_stop_bound_seconds
OUTAGE_BACKOFF_CAP = 3600  # an unreachable source is retried at least hourly
OPERATOR_BACKOFF_CAP = 86400  # credentials, quota or configuration: at most daily until corrected
_OPERATOR_STATES = {"AUTH_FAILED": "PROVIDER_AUTH_FAILED", "RATE_LIMITED": "PROVIDER_RATE_LIMITED",
                    "NOT_CONFIGURED": "PROVIDER_NOT_CONFIGURED", "LIVE_DISABLED": "PROVIDER_LIVE_DISABLED"}
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
        if provider == "rss":
            # One job per catalog feed, under the first selected universe that lists it.
            targets = [(feed.id, next(u for u in universes if u in feed.universes))
                       for feed in FEEDS if set(universes) & set(feed.universes)]
        else:
            targets = [("", "US_EQUITIES")] if provider == "finviz" else [(s, "US_EQUITIES") for s in symbols]
        jobs.extend(CollectionJob(provider, query, universe, interval) for query, universe in targets)
    if len(jobs) > MAX_JOBS:
        raise ValueError("COLLECTION_TARGET_BOUND_EXCEEDED")
    return jobs


def _backoff(interval: float, failures: int, provider_state: str) -> float:
    cap = OPERATOR_BACKOFF_CAP if provider_state in _OPERATOR_STATES else OUTAGE_BACKOFF_CAP
    return min(max(cap, interval), max(interval, 60) * 2 ** min(failures, 8))


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
        # A fetched batch whose write failed recoverably. Retried without another provider call.
        self._pending: tuple[CollectionJob, dict, list, dict] | None = None
        self._storage_failures, self._retry_at = 0, 0.0
        self._fatal: str | None = None  # a storage failure retrying cannot fix; held until restart
        self._rows: list[dict[str, Any]] = []
        stat = connection.path.stat()
        self._storage_identity = (stat.st_dev, stat.st_ino)
        with connection.transaction():
            for job in jobs:
                connection.execute("INSERT OR IGNORE INTO news_collection_jobs(job_id,payload_json,next_due) VALUES (?,?,?)",
                                   (job.id, json.dumps({"state": "PENDING", "failures": 0, "coverage_start": self.clock()}), 0))

    def _storage_fault(self) -> str | None:
        path = self.connection.path
        try:
            if not path.is_file():
                return "UNAVAILABLE"  # possibly a drive that returns; retried, never recreated
            stat = path.stat()
            wal = Path(str(path) + "-wal")
            size = stat.st_size + (wal.stat().st_size if wal.is_file() else 0)
        except OSError:
            return "UNAVAILABLE"
        if (stat.st_dev, stat.st_ino) != self._storage_identity:
            return "REPLACED"
        # Payload bytes alone omit page/index/WAL overhead. Match the market
        # writer's conservative reserve; the configured acquisition limit stays.
        return None if size + 4 * MAX_BATCH_BYTES <= self.max_database_bytes else "BOUND_EXCEEDED"

    def _storage_ok(self) -> bool:
        return self._storage_fault() is None

    def _storage_failed(self, exc: BaseException) -> None:
        """Local storage, not the provider, failed: bounded retry, no provider backoff consumed."""
        if not transient_storage_error(exc):
            self._block("COLLECTION_STORAGE_OR_CHECKPOINT_FAILED")
            return
        self._storage_failures += 1
        self._retry_at = self.clock() + min(30, 2 ** (self._storage_failures - 1))
        if self._storage_failures >= RETRY_LIMIT:
            self._set_state("BLOCKED", "COLLECTION_STORAGE_RETRY_LIMIT_EXCEEDED")
        else:
            self._set_state("RETRYING", "COLLECTION_STORAGE_RETRY")

    def _block(self, reason: str) -> None:
        """Not recoverable by retrying: stop stepping so the block stays visible. A held job lease expires by itself."""
        self._pending, self._fatal = None, reason
        self._set_state("BLOCKED", reason)

    def _set_state(self, state: str, reason: str | None = None) -> None:
        with self._state_lock:
            self._state, self._reason = state, reason

    def step(self) -> None:
        if self._stop.is_set() or not self._step_lock.acquire(blocking=False):
            return
        try:
            self._heartbeat = self.clock()
            if self._fatal is not None:
                return
            if self._heartbeat < self._retry_at:
                return  # storage backoff: no provider call while a fetched batch cannot be stored
            fault = self._storage_fault()
            if fault == "UNAVAILABLE":
                raise OSError("COLLECTION_STORAGE_UNAVAILABLE")
            if fault == "REPLACED":
                self._block("STORAGE_UNAVAILABLE_OR_BOUND_EXCEEDED")
                return
            if fault is not None:  # the bound can clear when the WAL is checkpointed
                self._set_state("BLOCKED", "STORAGE_UNAVAILABLE_OR_BOUND_EXCEEDED")
                return
            if self._pending is not None:
                self._write_pending()
                self._storage_failures = 0
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
            self._storage_failures = 0  # the selection transaction committed: storage is usable
            if selected is None:
                self._set_state("WAITING")
                return
            job, state = selected
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
            except Exception:
                # The source failed, not storage. Do not expose exception text, which can contain provider credentials.
                state.update(state="BACKOFF", reason="COLLECTION_FETCH_FAILED", failures=state.get('failures', 0) + 1)
                self.connection.execute("UPDATE news_collection_jobs SET payload_json=?,next_due=?,lease_owner=NULL,lease_until=0 WHERE job_id=? AND lease_owner=?",
                    (json.dumps(state), self.clock() + _backoff(job.interval, state['failures'], 'ERROR'), job.id, self.owner))
                self._set_state("WAITING")
            else:
                self._pending = (job, state, encoded, receipt)
                self._write_pending()
        except Exception as exc:
            self._storage_failed(exc)
        finally:
            self._step_lock.release()

    def _write_pending(self) -> None:
        """Store one fetched batch and its checkpoint atomically. Safe to repeat: record IDs are idempotent."""
        job, fetched, encoded, receipt = self._pending
        if not self._storage_ok():
            raise OSError("COLLECTION_STORAGE_UNAVAILABLE")
        state = dict(fetched)  # a repeated attempt starts from the same selected state
        previous_success = state.get('last_success')
        provider_state = receipt.get('state', 'ERROR')
        rejected = receipt.get('rejected_count', 0)
        complete = provider_state in {'CURRENT', 'DELAYED'}
        success = complete and not rejected
        # Some of the source's content was stored and some was not: neither a success nor an outage.
        partial = bool(encoded) and (provider_state == 'PARTIAL' or (complete and bool(rejected)))
        pending = provider_state == 'PENDING'
        failures = 0 if success or partial else state.get('failures', 0) + (0 if pending else 1)
        state.update(provider_state=provider_state, last_received=receipt.get('fetched_at'), rejected_count=rejected,
                     state='HEALTHY' if success else 'PARTIAL' if partial else 'PENDING' if pending else 'BACKOFF',
                     failures=failures,
                     reason=None if success else 'PARTIAL_RESPONSE' if partial else 'PROVIDER_PENDING' if pending
                     else _OPERATOR_STATES.get(provider_state, 'PROVIDER_UNAVAILABLE'))
        now = self.clock()
        if success:
            state['last_success'] = now
        elif partial:
            state['last_partial'] = now
            state['rejected_total'] = state.get('rejected_total', 0) + rejected
        delay = job.interval if success or partial else 5 if pending else _backoff(job.interval, failures, provider_state)
        # One catch-up request to the adapter's bounded existing rolling window.
        # A successful response never closes an uncertified historical gap.
        inserted, expired = 0, False
        with self.connection.transaction():
            row = self.connection.execute("SELECT lease_owner,lease_until FROM news_collection_jobs WHERE job_id=?", (job.id,)).fetchone()
            if row['lease_owner'] != self.owner:
                pass  # another worker owns the job now; it will fetch the same rolling window
            elif row['lease_until'] < now:
                expired = True
                state.pop('last_success', None)
                if previous_success is not None:
                    state['last_success'] = previous_success
                state.update(state='BACKOFF', reason='COLLECTION_LEASE_EXPIRED', unpersisted_count=len(encoded))
                self.connection.execute('UPDATE news_collection_jobs SET payload_json=?,next_due=?,lease_owner=NULL,lease_until=0 WHERE job_id=? AND lease_owner=?',
                    (json.dumps(state), now + job.interval, job.id, self.owner))
            else:
                for record_id, article, payload in encoded:
                    cursor = self.connection.execute("INSERT OR IGNORE INTO news_collection_records VALUES (?,?,?,?,?,?,?)",
                        (record_id, article.provider_id, article.source_id, article.published_time, article.retrieved_time, now, payload))
                    inserted += cursor.rowcount
                state['inserted_count'] = inserted
                state['duplicate_count'] = len(encoded) - inserted
                state.pop('unpersisted_count', None)
                self.connection.execute("UPDATE news_collection_jobs SET payload_json=?,next_due=?,lease_owner=?,lease_until=? WHERE job_id=?",
                    (json.dumps(state), now + delay, self.owner if pending else None,
                     now + LEASE_SECONDS if pending else 0, job.id))
        self._pending = None
        if expired:
            self._set_state('BLOCKED', 'COLLECTION_LEASE_EXPIRED')
        else:
            self._set_state("WAITING")

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            state, reason = self._state, self._reason
        rows = []
        try:
            for job in self.jobs:
                row = self.connection.fetchone("SELECT * FROM news_collection_jobs WHERE job_id=?", (job.id,))
                rows.append({"id": job.id, "provider": job.provider, "interval": job.interval, "next_due": row['next_due'],
                             "lease_until": row['lease_until'], **json.loads(row['payload_json'])})
            self._rows = rows
        except Exception as exc:
            if transient_storage_error(exc):
                rows = list(self._rows)  # a busy read is not a blocked collector; the worker has its own retry
            else:
                state, reason = "BLOCKED", "COLLECTION_STATUS_STORAGE_FAILED"
        if self._stop.is_set() and self._thread is not None and self._thread.is_alive():
            state, reason = 'BLOCKED', 'COLLECTION_SHUTDOWN_INCOMPLETE'
        elif self._stop.is_set():
            state = "PAUSED"
        elif self._thread is not None and not self._thread.is_alive():
            state, reason = "BLOCKED", "COLLECTION_WORKER_STOPPED"
        elif self._heartbeat is not None and self.clock() - self._heartbeat > LEASE_SECONDS:
            state, reason = "STALE", "COLLECTION_HEARTBEAT_STALE"
        # Per-source health. COMPLETE only when every source's last poll was a full success.
        sources = {name: sum(j.get('state') == name for j in rows) for name in ('HEALTHY', 'PARTIAL', 'BACKOFF', 'PENDING')}
        settled = sum(sources.values()) - sources['PENDING']  # a poll in flight says nothing yet
        coverage = ('UNKNOWN' if not settled else
                    'COMPLETE' if sources['HEALTHY'] == settled == len(rows) - sum(j.get('state') == 'COLLECTING' for j in rows) else
                    'NONE' if not sources['HEALTHY'] and not sources['PARTIAL'] else 'PARTIAL')
        return {"enabled": True, "state": state, "reason": reason, "worker_alive": bool(self._thread and self._thread.is_alive()),
                "sources": sources, "coverage": coverage, "storage_failures": self._storage_failures,
                "unwritten_batch": self._pending is not None,
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
            self._thread.join(timeout=WORKER_JOIN_SECONDS)
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


def stop_collection() -> bool:
    """False when the worker outlived its bounded join; the collector then stays visible as the owner."""
    global _COLLECTOR, _STARTUP_STATUS
    with _STARTUP_LOCK:
        if _COLLECTOR is not None:
            _COLLECTOR.stop()
            if _COLLECTOR.status()['worker_alive']:
                return False
            _COLLECTOR = None
        _STARTUP_STATUS = {'enabled': False, 'state': 'DISABLED'}
        return True
