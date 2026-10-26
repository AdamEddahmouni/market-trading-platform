"""PF-01B bounded opt-in market receipts in the existing local_state database.

No subscriptions, backfill, provider activation, AI or execution dispatch. A
queue receipt is not a commit. Watermarks describe stored observations only;
neither provider continuity nor exactly-once delivery is asserted.

Ownership is an OS-held owner lock plus a run lease. A writer started by
``start_persistence`` owns nothing until it has an observation or a gap to
store, and hands ownership back after ``IDLE_RELEASE_SECONDS`` without supply.
"""
from __future__ import annotations

import errno
import hashlib
import json
import math
import os
import threading
import time
from collections import deque
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from ..local_state.connection import (LocalStateConnection, lock_contention_error, lock_retry_window_seconds,
                                      transient_storage_error)
from .capacity import configured_max_database_bytes

MAX_RECORD_BYTES = 128 * 1024
MAX_BATCH_BYTES = 2 * 1024 * 1024
LEASE_NS = 120 * 1_000_000_000
IDLE_RELEASE_SECONDS = 120.0  # one lease interval without supply returns ownership
RETRY_LIMIT = 6  # consecutive recoverable failures before the writer stops
# Lock contention is retried for a window instead of a count (IMP_MARKET_WRITER_RETRY_WINDOW_SEC), with a short
# backoff so commits resume soon after the neighbour lets go.
CONTENTION_BACKOFF_CAP_SECONDS = 5
# Below WORKER_JOIN_SECONDS, so a stop requested mid-wait still joins the writer thread.
BUSY_TIMEOUT_MS = 2000
WAL_SIZE_LIMIT_BYTES = 64 * 1024 * 1024
# Stop bounds; part of news.supervision.child_stop_bound_seconds.
WORKER_JOIN_SECONDS = 5.0
FINAL_DRAIN_SECONDS = 5.0
OWNER_LOCK_SUFFIX = '.market-writer.lock'
MAX_SEEN_BARS = 2048  # per selected symbol; above the provider's 1000-bar current window
CAPABILITIES = {'US_EQUITY_L1', 'US_EQUITY_TICKS', 'US_EQUITY_DEPTH',
                'CRYPTO_TRADES', 'CRYPTO_BOOK', 'CURRENT_BAR_1M'}
_WRITER: MarketStreamWriter | None = None
_GLOBAL_LOCK = threading.Lock()


def _json(value: Any) -> str:
    def decimal(value: Any) -> str:
        if isinstance(value, Decimal) and value.is_finite():
            return str(value)
        raise TypeError('NON_JSON_PROVIDER_VALUE')
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False, default=decimal)


def _source(provider: str) -> str:
    return {'moomoo': 'moomoo', 'moomoo.opend.observational': 'moomoo',
            'moomoo_opend': 'moomoo', 'kraken': 'kraken'}.get(provider.lower(), '')


class _OwnerLock:
    """Exclusive sidecar lock held for as long as this process owns the writer.

    The operating system drops it when the process dies, which is the evidence
    that an unexpired run lease belongs to a dead writer rather than a live one.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: Any = None

    def acquire(self) -> bool:
        if self._handle is not None:
            return True
        handle = open(self.path, 'a+b')  # noqa: SIM115 - held until release; never creates the directory
        try:
            if os.name == 'nt':
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException as exc:
            handle.close()
            # Only contention means a live owner. Anything else is a storage fault for the bounded retry.
            if isinstance(exc, OSError) and exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                return False
            raise
        self._handle = handle
        return True

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is not None:
            handle.close()  # closing the handle releases the lock on every platform


def owner_lock_held(path: Path) -> bool:
    """True while a living process holds the writer's owner lock on this store.

    For a process that owns nothing: an unexpired run lease alone cannot tell a
    live owner from one that died. The lock is taken and dropped at once.
    """
    probe = _OwnerLock(Path(str(path) + OWNER_LOCK_SUFFIX))
    if not probe.acquire():
        return True
    probe.release()
    return False


def validate_capture_selection(sources: tuple[str, ...], symbols: tuple[str, ...]) -> None:
    if not sources or set(sources) - {'moomoo', 'kraken'} or not symbols or len(symbols) > 20:
        raise ValueError('MARKET_CAPTURE_TARGETS_INVALID')


def configured_selection(env: Mapping[str, str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The stored sources and symbols as the writer will read them. Parses only; nothing is opened."""
    sources, symbols = (tuple(x.strip() for x in env.get(name, '').split(',') if x.strip())
                        for name in ('IMP_MARKET_PERSISTENCE_SOURCES', 'IMP_MARKET_PERSISTENCE_SYMBOLS'))
    return sources, symbols


class MarketStreamWriter:
    def __init__(self, path: Path, *, sources: tuple[str, ...], symbols: tuple[str, ...],
                 queue_limit: int = 512, batch_limit: int = 256,
                 max_database_bytes: int | None = None, acquire: bool = True,
                 idle_release_seconds: float | None = IDLE_RELEASE_SECONDS,
                 suppress_unchanged_l1: bool | None = None, busy_timeout_ms: int = BUSY_TIMEOUT_MS,
                 lock_retry_window: float | None = None) -> None:
        validate_capture_selection(sources, symbols)
        if not 1 <= batch_limit <= 256 or not batch_limit <= queue_limit <= 4096:
            raise ValueError('MARKET_CAPTURE_LIMITS_INVALID')
        try:
            ceiling = configured_max_database_bytes()
        except ValueError:
            raise ValueError('MARKET_CAPTURE_STORAGE_LIMIT_INVALID') from None
        max_database_bytes = ceiling if max_database_bytes is None else max_database_bytes
        if not MAX_BATCH_BYTES <= max_database_bytes <= ceiling:
            raise ValueError('MARKET_CAPTURE_STORAGE_LIMIT_INVALID')
        self.sources, self.symbols = set(sources), set(symbols)
        self.queue_limit, self.batch_limit = queue_limit, batch_limit
        self.max_database_bytes = max_database_bytes
        self._queue: deque[dict[str, Any]] = deque()
        self._lock, self._flush_lock = threading.Lock(), threading.Lock()
        self._start_lock = threading.Lock()
        self._stop, self._wake = threading.Event(), threading.Event()
        self._thread: threading.Thread | None = None
        self._closed, self._accepting = False, True
        self.run_id: str | None = None  # None while this writer owns nothing
        self._owner_lock = _OwnerLock(Path(str(path) + OWNER_LOCK_SUFFIX))
        self._idle_release = idle_release_seconds
        self._active_at = time.monotonic()
        self._gaps: dict[tuple[str, str], list[int]] = {}
        self._bars_seen: dict[str, dict[int, str]] = {}
        self._state, self._error = 'IDLE', None
        self._selected_received = self._accepted = self._normalizing = 0
        self._committed = self._duplicates = self._rejected = self._peak_backlog = 0
        # Every quote receipt is its own observation by default. A storage-bounded collector may opt in
        # (IMP_MARKET_L1_SUPPRESS_UNCHANGED=1) to count a receipt whose payload and provider clocks equal the
        # stream's previous L1 receipt, e.g. the 2 s snapshot poll of an unchanged quote, as a duplicate.
        self.suppress_unchanged_l1 = (os.environ.get('IMP_MARKET_L1_SUPPRESS_UNCHANGED') == '1'
                                      if suppress_unchanged_l1 is None else bool(suppress_unchanged_l1))
        self._last_l1_revision: dict[str, str] = {}
        self._unchanged = 0
        self._last_received = self._last_commit = None
        self._max_flush_seconds = 0.0
        self._consecutive_failures = self._transient_failures = 0
        self.lock_retry_window = (lock_retry_window_seconds('IMP_MARKET_WRITER_RETRY_WINDOW_SEC')
                                  if lock_retry_window is None else lock_retry_window)
        self._retrying_since: float | None = None  # monotonic start of the current failure streak
        self._contention = False  # the latest failure was lock contention
        self._last_flush_seconds = 0.0
        self._ownership_waits = self._idle_releases = 0
        self.connection = LocalStateConnection(path, require_existing=True)
        try:
            # synchronous stays NORMAL, as for every other connection. FULL flushed the disk inside each commit,
            # while this connection held the store's only write lock. On the D: hard drive under load that took
            # seconds and locked out the platform (2026-10-21..23). In WAL mode NORMAL never corrupts the file.
            # A process crash loses nothing; a power cut can lose the last commits, shown as the unclean-restart gap.
            self.connection.execute(f'PRAGMA busy_timeout={int(busy_timeout_ms)}')
            # A backlog after contention grew the WAL to 176 MB; checkpoints now shrink it back.
            self.connection.execute(f'PRAGMA journal_size_limit={WAL_SIZE_LIMIT_BYTES}')
            stat = path.stat()
            self._identity = (stat.st_dev, stat.st_ino)
            if acquire:
                self._acquire()
                self._state = 'READY'
            self._known_gaps = self.connection.execute('SELECT COUNT(*) FROM market_stream_gaps').fetchone()[0]
            checkpoint = self.connection.execute('SELECT * FROM market_stream_checkpoints ORDER BY commit_ns DESC LIMIT 1').fetchone()
            self._last_checkpoint = dict(checkpoint) if checkpoint else None
            self._last_commit = checkpoint['commit_ns'] if checkpoint else None
        except Exception:
            self._owner_lock.release()
            self.connection.close()
            raise

    def _acquire(self) -> None:
        """Take the owner lock, then open a run. A live owner is never overridden."""
        if not self._owner_lock.acquire():
            raise ValueError('MARKET_CAPTURE_OWNER_ACTIVE')
        run_id = uuid4().hex
        try:
            now = time.time_ns()
            with self.connection.transaction():
                # Every writer holds the owner lock while its run is open, so a run
                # still open here was left by a process that no longer exists, even
                # when its lease has not yet expired. Its unstored tail is a gap.
                for row in self.connection.execute('SELECT * FROM market_stream_runs WHERE closed_ns IS NULL').fetchall():
                    self._write_gap(row['run_id'], '*', 'UNCLEAN_RESTART_NO_REPLAY', row['heartbeat_ns'], now, 1)
                    self.connection.execute('UPDATE market_stream_runs SET closed_ns=?,lease_until_ns=0 WHERE run_id=?', (now, row['run_id']))
                previous = self.connection.execute('SELECT MAX(closed_ns) FROM market_stream_runs').fetchone()[0]
                if previous is not None:
                    self._write_gap(run_id, '*', 'CAPTURE_DOWNTIME_UNVERIFIED', previous, now, 1)
                else:
                    self._write_gap(run_id, '*', 'INITIAL_COVERAGE_UNVERIFIED', now, now, 1)
                self.connection.execute('INSERT INTO market_stream_runs VALUES (?,?,?,?,NULL)', (run_id, now, now, now+LEASE_NS))
        except Exception:
            self._owner_lock.release()
            raise
        self.run_id = run_id
        self._active_at = time.monotonic()

    def _release(self) -> None:
        """Idle hand-back: a clean close, so another process may own at once."""
        self.connection.execute('UPDATE market_stream_runs SET closed_ns=?,lease_until_ns=0 WHERE run_id=?',
                                (time.time_ns(), self.run_id))
        self.run_id = None
        self._owner_lock.release()
        with self._lock:
            self._idle_releases += 1
            self._state = 'IDLE'

    def _write_gap(self, run: str, stream: str, reason: str, start: int, end: int, count: int) -> None:
        self.connection.execute('''INSERT INTO market_stream_gaps VALUES (?,?,?,?,?,?)
            ON CONFLICT(run_id,stream_id,reason) DO UPDATE SET
            start_ns=MIN(start_ns,excluded.start_ns),end_ns=MAX(end_ns,excluded.end_ns),
            observations=observations+excluded.observations''', (run, stream, reason, start, end, count))

    def gap(self, reason: str, *, stream: str = '*', received_ns: int | None = None) -> None:
        now = received_ns or time.time_ns()
        with self._lock:
            key = (stream[:160], reason[:80])
            # At most 20 targets x six capabilities plus bounded reason classes.
            if len(self._gaps) >= 256 and key not in self._gaps:
                key = ('*', 'MULTIPLE_CAPTURE_GAPS')
            if key in self._gaps:
                self._gaps[key][1] = max(self._gaps[key][1], now)
                self._gaps[key][2] += 1
            else:
                self._gaps[key] = [now, now, 1]
        self._wake.set()

    def selects(self, record: dict[str, Any]) -> bool:
        return _source(str(record.get('provider') or '')) in self.sources and bool(
            {str(record.get('instrument_id') or ''), str(record.get('provider_symbol') or '')} & self.symbols)

    def submit(self, record: dict[str, Any], quality: dict[str, Any] | None = None) -> bool:
        provider = str(record.get('provider') or '')
        symbol, provider_symbol = str(record.get('instrument_id') or ''), str(record.get('provider_symbol') or '')
        source = _source(provider)
        if source not in self.sources or not ({symbol, provider_symbol} & self.symbols):
            return False  # Out-of-scope traffic is intentionally not selected.
        with self._lock:
            self._selected_received += 1
            self._normalizing += 1
        capability = record.get('capability')
        stream = f'{provider}:{symbol}:{capability}'
        try:
            if capability not in CAPABILITIES or not symbol or not provider_symbol:
                raise ValueError('IDENTITY')
            if (source == 'kraken') != (capability in {'CRYPTO_TRADES', 'CRYPTO_BOOK'}):
                raise ValueError('SOURCE_CAPABILITY')
            clocks = record.get('clocks') or {}
            received = clocks.get('received_time_ns')
            if type(received) is not int or not 0 < received <= 9223372036854775807:
                raise ValueError('RECEIPT_TIME')
            for value in clocks.values():
                if value is not None and (type(value) is not int or not 0 <= value <= 9223372036854775807):
                    raise ValueError('CLOCK')
            payload = record.get('raw_payload')
            if not isinstance(payload, dict) or not payload:
                raise ValueError('PAYLOAD')
            if capability == 'CRYPTO_BOOK' and (quality or {}).get('checksum') != 'VALID':
                raise ValueError('BOOK_CHECKSUM_REQUIRED')
            if capability == 'US_EQUITY_L1':
                from .quality import assess_quote

                if 'INVALID_QUOTE' in assess_quote(payload):
                    raise ValueError('QUOTE_VALUES')
            if capability in {'CRYPTO_TRADES', 'US_EQUITY_TICKS'}:
                price = float(payload.get('price', 0))
                quantity = float(payload.get('qty' if capability == 'CRYPTO_TRADES' else 'volume', 0))
                if not math.isfinite(price) or not math.isfinite(quantity) or price <= 0 or quantity <= 0:
                    raise ValueError('TRADE_VALUES')
            # Runtime span handles are mutable Python objects, not provider evidence.
            snapshot = json.loads(_json({k: v for k, v in record.items() if not k.startswith('_rt01')}))
            snapshot['persistence_quality'] = quality or {}
            encoded = _json(snapshot)
            if len(encoded.encode()) > MAX_RECORD_BYTES:
                raise ValueError('RECORD_BOUND')
            # Quotes/depth have observation identities, not an exchange event ID.
            # Native trades use pair/instrument-scoped IDs plus immutable revision.
            native = payload.get('trade_id') if capability == 'CRYPTO_TRADES' else payload.get('sequence')
            if capability == 'CURRENT_BAR_1M':
                identity = f"1m:{payload['end_ns']}"
            elif capability == 'CRYPTO_BOOK':
                identity = _json(['receipt', received, record.get('subscription_id'),
                                  record.get('message_type'), record.get('message_index', 0)])
            elif capability in {'CRYPTO_TRADES', 'US_EQUITY_TICKS'} and native is not None:
                identity = f"native:{native}"
            else:
                identity = f"receipt:{received}"
            revision = hashlib.sha256(_json([payload, clocks.get('event_time_ns'), clocks.get('provider_time_ns')]).encode()).hexdigest()
            record_id = hashlib.sha256(_json([provider, symbol, provider_symbol, capability, identity, revision]).encode()).hexdigest()
            row = dict(id=record_id, provider=provider, symbol=symbol, capability=capability,
                       event=clocks.get('event_time_ns'), source_time=clocks.get('provider_time_ns'),
                       received=received, normalized=clocks.get('ingested_time_ns'), identity=identity,
                       payload=encoded, bytes=len(encoded.encode()), stream=stream)
        except (ValueError, TypeError, KeyError, OverflowError):
            with self._lock:
                self._rejected += 1
                self._normalizing -= 1
            self.gap('INVALID_OBSERVATION', stream=stream)
            return False
        with self._lock:
            self._last_received = received if self._last_received is None else max(received, self._last_received)
            accepting = self._accepting
            if (accepting and capability == 'US_EQUITY_L1' and self.suppress_unchanged_l1
                    and self._last_l1_revision.get(stream) == revision):
                # Accounted as an accepted duplicate, exactly like an INSERT OR IGNORE of a stored record.
                self._normalizing -= 1
                self._accepted += 1
                self._duplicates += 1
                self._unchanged += 1
                return True
            accepted = accepting and len(self._queue) < self.queue_limit
            self._normalizing -= 1
            if accepted:
                if capability == 'US_EQUITY_L1':
                    self._last_l1_revision[stream] = revision
                self._accepted += 1
                self._queue.append(row)
                self._peak_backlog = max(self._peak_backlog, len(self._queue))
            else:
                self._rejected += 1
        if not accepted:
            self.gap('QUEUE_OVERFLOW' if accepting else 'WRITER_STOPPED', stream=stream, received_ns=received)
        self._wake.set()
        return accepted

    def submit_bars(self, symbol: str, bars: list[Any], received_ns: int) -> None:
        provider_symbol = f'US.{symbol}'
        if not self.selects({'provider': 'MOOMOO_OPEND', 'instrument_id': symbol, 'provider_symbol': provider_symbol}):
            return
        # Each refresh returns the provider's whole rolling window. Only bars or
        # revisions not already accepted may enter the bounded queue; otherwise
        # stored duplicates overflow it and displace new observations.
        seen = self._bars_seen.setdefault(symbol, {})
        # Newest first: if the queue is still short, the current bars are kept
        # and the rejected remainder is reported through the normal overflow gap.
        for bar in sorted(bars, key=lambda item: item.end_ns, reverse=True):
            payload = {**bar.to_dict(), 'start_ns': bar.start_ns, 'end_ns': bar.end_ns,
                       'interval': '1m', 'timing_basis': 'vendor_time_key_bar_end'}
            try:
                revision = hashlib.sha256(_json(payload).encode()).hexdigest()
            except (TypeError, ValueError):
                revision = None  # submit() rejects it and records the invalid observation
            if revision is not None and seen.get(bar.end_ns) == revision:
                continue
            accepted = self.submit({'provider': 'MOOMOO_OPEND', 'instrument_id': symbol, 'provider_symbol': provider_symbol,
                                    'capability': 'CURRENT_BAR_1M', 'clocks': {'event_time_ns': bar.end_ns,
                                    'provider_time_ns': None, 'received_time_ns': received_ns},
                                    'raw_payload': payload})
            if accepted and revision is not None:
                seen[bar.end_ns] = revision
        while len(seen) > MAX_SEEN_BARS:
            del seen[min(seen)]

    def _storage_fault(self) -> str | None:
        path = self.connection.path
        try:
            stat = path.stat()
            wal = Path(str(path) + '-wal')
            size = stat.st_size + (wal.stat().st_size if wal.exists() else 0)
        except OSError:
            return 'MARKET_STORAGE_UNAVAILABLE'  # may be a drive that returns; retried, never recreated
        if (stat.st_dev, stat.st_ino) != self._identity:
            return 'MARKET_STORAGE_REPLACED'
        if size + 4*MAX_BATCH_BYTES > self.max_database_bytes:
            return 'MARKET_STORAGE_FULL'
        return None

    def _storage_ok(self) -> bool:
        return self._storage_fault() is None

    def _failed(self, exc: Exception) -> None:
        """Classify one failed flush. Nothing was committed and nothing was dequeued."""
        code = str(exc) if str(exc).startswith('MARKET_') else type(exc).__name__
        if code == 'MARKET_CAPTURE_OWNER_ACTIVE':
            with self._lock:
                self._state, self._error = 'WAITING_FOR_OWNERSHIP', code
                self._ownership_waits += 1
            return
        recoverable = code == 'MARKET_STORAGE_UNAVAILABLE' or transient_storage_error(exc)
        if code == 'MARKET_CAPTURE_LEASE_LOST':
            # This run may never commit again. Give the lock back and re-enter through
            # the normal fenced acquisition, which records the abandoned run as a gap.
            self.run_id = None
            self._owner_lock.release()
            recoverable = True
        with self._lock:
            if not self._consecutive_failures:
                self._retrying_since = time.monotonic()
            self._consecutive_failures += 1
            self._transient_failures += recoverable
            self._contention = lock_contention_error(exc)
            self._state, self._error = ('RETRYING' if recoverable else 'FAILED'), code
        if not recoverable:
            self.gap('WRITER_FAILURE')

    def flush(self) -> int:
        with self._flush_lock:
            if self._closed:
                return 0
            with self._lock:
                batch, size = [], 0
                for row in self._queue:
                    if len(batch) >= self.batch_limit or size + row['bytes'] > MAX_BATCH_BYTES:
                        break
                    batch.append(row)
                    size += row['bytes']
                gaps = {key: list(value) for key, value in self._gaps.items()}
            started = time.perf_counter()
            committed = duplicates = 0
            try:
                if self.run_id is None and not batch and not gaps:
                    # Nothing owned and nothing to store: an outage costs this writer nothing,
                    # so it must not spend the retry budget and stop before supply arrives.
                    with self._lock:
                        if self._state != 'FAILED':
                            self._state, self._error = 'IDLE', None
                            self._consecutive_failures, self._retrying_since = 0, None
                    return 0
                if not self._storage_ok():
                    raise ValueError(self._storage_fault() or 'MARKET_STORAGE_UNAVAILABLE')
                if self.run_id is None:
                    self._acquire()
                now = time.time_ns()
                with self.connection.transaction():
                    lease = self.connection.execute('SELECT lease_until_ns,closed_ns FROM market_stream_runs WHERE run_id=?', (self.run_id,)).fetchone()
                    if lease is None or lease['closed_ns'] is not None or lease['lease_until_ns'] < now:
                        raise ValueError('MARKET_CAPTURE_LEASE_LOST')
                    for row in batch:
                        cursor = self.connection.execute('INSERT OR IGNORE INTO market_stream_records VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                            (row['id'], row['provider'], row['symbol'], row['capability'], row['event'], row['source_time'],
                             row['received'], row['normalized'], now, row['identity'], row['payload']))
                        if not cursor.rowcount:
                            duplicates += 1
                            continue
                        committed += 1
                        self.connection.execute('''INSERT INTO market_stream_checkpoints VALUES (?,?,?,?,?)
                            ON CONFLICT(stream_id) DO UPDATE SET
                            event_ns=CASE WHEN event_ns IS NULL THEN excluded.event_ns
                                WHEN excluded.event_ns IS NULL THEN event_ns ELSE MAX(event_ns,excluded.event_ns) END,
                            received_ns=MAX(received_ns,excluded.received_ns),commit_ns=excluded.commit_ns,
                            last_record_id=excluded.last_record_id''', (row['stream'], row['event'], row['received'], now, row['id']))
                    for (stream, reason), (low, high, count) in gaps.items():
                        self._write_gap(self.run_id, stream, reason, low, high, count)
                    self.connection.execute('UPDATE market_stream_runs SET heartbeat_ns=?,lease_until_ns=? WHERE run_id=?', (now, now+LEASE_NS, self.run_id))
                    known_gaps = self.connection.execute('SELECT COUNT(*) FROM market_stream_gaps').fetchone()[0]
                    checkpoint = self.connection.execute('SELECT * FROM market_stream_checkpoints ORDER BY commit_ns DESC LIMIT 1').fetchone()
                with self._lock:
                    for _ in batch:
                        self._queue.popleft()
                    for key, value in gaps.items():
                        current = self._gaps.get(key)
                        if current is not None:
                            current[2] -= value[2]
                            if current[2] <= 0:
                                del self._gaps[key]
                    self._committed += committed
                    self._duplicates += duplicates
                    if committed:
                        self._last_commit = now
                    self._state, self._error = 'READY', None
                    self._consecutive_failures = self._ownership_waits = 0
                    self._retrying_since = None
                    self._last_flush_seconds = time.perf_counter()-started
                    self._max_flush_seconds = max(self._max_flush_seconds, self._last_flush_seconds)
                    self._known_gaps = known_gaps
                    self._last_checkpoint = dict(checkpoint) if checkpoint else None
                    drained = not self._queue and not self._gaps
                if batch or gaps:
                    self._active_at = time.monotonic()
                elif (drained and self._idle_release is not None
                        and time.monotonic() - self._active_at >= self._idle_release):
                    self._release()
                return committed
            except Exception as exc:
                self._failed(exc)
                return 0

    def checkpoints(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.fetchall('SELECT * FROM market_stream_checkpoints')]

    def _capacity_status(self) -> dict[str, Any]:
        """Cheap read-only resource warning; no database scan, checkpoint or retention action."""
        from .capacity import capacity_status
        import shutil

        path = self.connection.path
        try:
            stat = path.stat()
            if (stat.st_dev, stat.st_ino) != self._identity:
                return {'state': 'UNAVAILABLE', 'reason': 'MARKET_STORAGE_REPLACED'}
            wal = Path(str(path) + '-wal')
            return capacity_status(stat.st_size, wal_bytes=wal.stat().st_size if wal.exists() else 0,
                                   max_database_bytes=self.max_database_bytes,
                                   free_disk_bytes=shutil.disk_usage(path.parent).free)
        except OSError:
            return {'state': 'UNAVAILABLE', 'reason': 'MARKET_STORAGE_UNAVAILABLE'}
        except ValueError:
            # A warning that cannot be computed is reported; it never fails the status the child polls.
            return {'state': 'UNAVAILABLE', 'reason': 'MARKET_CAPACITY_BOUND_INVALID'}

    def status(self) -> dict[str, Any]:
        capacity = self._capacity_status()
        with self._lock:
            state = 'STOPPED' if self._closed and self._state != 'FAILED' else self._state
            if self._thread is not None and not self._thread.is_alive() and not self._closed and not self._stop.is_set():
                state = 'FAILED'
            return {'enabled': True, 'state': state, 'error': self._error,
                    'sources': sorted(self.sources), 'symbols': sorted(self.symbols),
                    'received_ns': self._last_received, 'last_commit_ns': self._last_commit,
                    'accepting': self._accepting,
                    'ownership': 'HELD' if self.run_id is not None and not self._closed else 'NOT_HELD',
                    'collecting': self.run_id is not None and state == 'READY',
                    'idle_release_seconds': self._idle_release, 'idle_releases': self._idle_releases,
                    'ownership_waits': self._ownership_waits, 'transient_failures': self._transient_failures,
                    'worker_alive': bool(self._thread and self._thread.is_alive()),
                    'last_checkpoint': dict(self._last_checkpoint) if self._last_checkpoint else None,
                    'received_age_seconds': (time.time_ns()-self._last_received)/1e9 if self._last_received else None,
                    'selected_received': self._selected_received, 'accepted': self._accepted,
                    'normalizing': self._normalizing,
                    'unreconciled': abs(self._selected_received-self._accepted-self._rejected-self._normalizing)
                        + abs(self._accepted-self._committed-self._duplicates-len(self._queue)),
                    'accounting_boundary': 'SELECTED_WRITER_SUBMIT_THIS_PROCESS',
                    'interruption_tail': 'UNKNOWN_NO_DURABLE_INGRESS_JOURNAL',
                    'committed': self._committed, 'duplicates': self._duplicates, 'rejected': self._rejected,
                    'unchanged_suppressed': self._unchanged, 'suppress_unchanged_l1': self.suppress_unchanged_l1,
                    'backlog': len(self._queue), 'peak_backlog': self._peak_backlog,
                    'pending_gap_classes': len(self._gaps), 'known_gaps': self._known_gaps,
                    'queue_limit': self.queue_limit, 'batch_limit': self.batch_limit,
                    'max_database_bytes': self.max_database_bytes, 'max_flush_seconds': self._max_flush_seconds,
                    'capacity': capacity,
                    'consecutive_failures': self._consecutive_failures, 'retry_limit': RETRY_LIMIT,
                    'lock_contention': self._contention and self._state == 'RETRYING',
                    'retrying_seconds': (time.monotonic()-self._retrying_since
                                         if self._retrying_since is not None else None),
                    'lock_retry_window_seconds': self.lock_retry_window,
                    'last_flush_seconds': self._last_flush_seconds,
                    'coverage': 'OBSERVED_ONLY_NOT_COMPLETE', 'recovery': 'NO_PROVIDER_REPLAY',
                    'checkpoint_semantics': 'COMMITTED_WATERMARK_NOT_REPLAY_CURSOR'}

    def start(self) -> None:
        def run() -> None:
            while not self._stop.is_set():
                self._wake.wait(1)
                self._wake.clear()
                self.flush()
                with self._lock:
                    state, failures, waits = self._state, self._consecutive_failures, self._ownership_waits
                    contention = self._contention
                    tolerated = (contention and self._retrying_since is not None
                                 and time.monotonic()-self._retrying_since < self.lock_retry_window)
                if state == 'RETRYING' and failures >= RETRY_LIMIT and not tolerated:
                    self.gap('WRITER_RETRY_LIMIT_EXCEEDED')
                    with self._lock:
                        self._state, self._error = 'FAILED', 'WRITER_RETRY_LIMIT_EXCEEDED'
                    state = 'FAILED'
                if state == 'FAILED':
                    # Not recoverable by retrying: stop accepting so the loss stays visible.
                    with self._lock:
                        self._accepting = False
                    self._stop.set()
                    return
                if state == 'RETRYING':
                    cap = CONTENTION_BACKOFF_CAP_SECONDS if contention else 30
                    self._stop.wait(min(cap, 2 ** min(failures-1, 5)))
                elif state == 'WAITING_FOR_OWNERSHIP':
                    self._stop.wait(min(30, 2 ** min(waits, 5)))  # a live owner holds the lock
                else:
                    with self._lock:
                        if self._queue:
                            self._wake.set()  # Drain bounded batches without an idle delay.
        with self._start_lock:
            if self._closed or self._stop.is_set():
                raise ValueError('MARKET_WRITER_STOPPED')
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=run, name='imp-market-persistence', daemon=True)
            self._thread.start()

    def stop(self) -> None:
        if self._closed:
            return
        with self._lock:
            self._accepting = False
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=WORKER_JOIN_SECONDS)
            if self._thread.is_alive():
                self.gap('SHUTDOWN_INCOMPLETE')
                with self._lock:
                    self._state, self._error = 'FAILED', 'SHUTDOWN_INCOMPLETE'
                return  # Never close a connection still owned by a running writer.
        deadline = time.monotonic()+FINAL_DRAIN_SECONDS
        while self._queue and time.monotonic() < deadline:
            self.flush()
            if self._state != 'READY':
                break
        self.flush()
        try:
            if self._queue or self._gaps:
                # Unstored at shutdown. The run stays open so the next owner records the gap.
                with self._lock:
                    if self._state != 'FAILED':
                        self._state, self._error = 'FAILED', 'MARKET_CAPTURE_UNPERSISTED_AT_SHUTDOWN'
            if self.run_id is None:
                pass  # owns nothing: no run to close
            elif self._state != 'FAILED':
                self.connection.execute('UPDATE market_stream_runs SET closed_ns=?,lease_until_ns=0 WHERE run_id=?', (time.time_ns(), self.run_id))
            else:
                self.connection.execute('UPDATE market_stream_runs SET lease_until_ns=0 WHERE run_id=?', (self.run_id,))
        except Exception as exc:
            with self._lock:
                self._state, self._error = 'FAILED', type(exc).__name__
            try:
                self.connection.execute('UPDATE market_stream_runs SET lease_until_ns=0 WHERE run_id=?', (self.run_id,))
            except Exception:
                pass  # An unclosed run will be diagnosed by the next valid owner.
        finally:
            self.connection.close()
            self._owner_lock.release()
            self._closed = True


def active_writer() -> MarketStreamWriter | None:
    return _WRITER


def persistence_status() -> dict[str, Any]:
    writer = active_writer()
    return writer.status() if writer is not None else {'enabled': False, 'state': 'DISABLED'}


def validate_persistence_storage(env: Mapping[str, str]) -> Path:
    override = env.get('IMP_STATE_DIR')
    if not override or not Path(override).is_absolute():
        raise ValueError('MARKET_EXPLICIT_STATE_DIR_REQUIRED')
    path = Path(override).resolve() / 'imp-state.sqlite3'
    if not path.is_file():
        raise FileNotFoundError('MARKET_STORAGE_MISSING')
    return path


def start_persistence(data_mode: str, env: Mapping[str, str] | None = None) -> MarketStreamWriter | None:
    global _WRITER
    env = os.environ if env is None else env
    if env.get('IMP_MARKET_PERSISTENCE_ENABLED') != '1':
        return None
    if data_mode not in {'LIVE_OBSERVATIONAL', 'BROKER_DELAYED'}:
        raise ValueError('MARKET_CAPTURE_REQUIRES_OBSERVATIONAL_MODE')
    path = validate_persistence_storage(env)
    sources, symbols = configured_selection(env)
    with _GLOBAL_LOCK:
        if _WRITER is not None:
            raise ValueError('MARKET_CAPTURE_ALREADY_STARTED')
        # Lazy ownership: an unsupplied process never holds the lease, and a live
        # owner elsewhere delays capture instead of failing this process's startup.
        writer = MarketStreamWriter(path, sources=sources, symbols=symbols, acquire=False)
        try:
            writer.start()
        except Exception:
            writer.stop()  # release the connection and lease this startup acquired
            raise
        _WRITER = writer
        return writer


def stop_persistence() -> None:
    global _WRITER
    with _GLOBAL_LOCK:
        if _WRITER is not None:
            _WRITER.stop()
            if _WRITER._closed:
                _WRITER = None
