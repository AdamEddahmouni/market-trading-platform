"""PF-01 default-off headless market supply for the collection-only process.

The collection-only child has no browser demand, so the durable writer would
receive nothing. This module keeps explicitly configured demand alive on the
existing subscription authorities (``LiveObservationalRuntime`` for
moomoo/OpenD, ``KrakenStreamRuntime`` for Kraken) under one consumer id. It adds
no provider, transport, normalisation or storage path: records still reach the
writer through the existing ingress.

Nothing is requested unless supply is enabled, the provider's own live gate is
open, the operator has confirmed the source's data rights, and (moomoo) the
existing capability probe verifies the account entitlement. A key, a reachable
OpenD or a passing fixture is never treated as a right.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

SUPPLY_CONSUMER = 'pf01-headless-collector'
SUPPLY_JOB = '__pf01_market_supply__'  # reserved evidence row, never a provider job
SOURCE_CAPABILITIES = {'moomoo': ('US_EQUITY_L1', 'US_EQUITY_TICKS', 'US_EQUITY_DEPTH'),
                       'kraken': ('CRYPTO_TRADES', 'CRYPTO_BOOK')}
# Plain tickers only: the feed stores a dotted code (BRK.B) under another instrument id, so it would
# be subscribed and never persisted.
SYMBOL_PATTERNS = {'moomoo': re.compile(r'[A-Z][A-Z0-9]{0,9}'), 'kraken': re.compile(r'XA01:[0-9A-F]{16}')}
MAX_TARGETS = 20  # the writer's selection bound; supply can never exceed what is stored
RECONCILE_SECONDS = 5.0
STATUS_SECONDS = 30.0
STATUS_LEASE_SECONDS = 120.0
STALE_SECONDS = 300.0
PROBE_RELOAD_SECONDS = 1.0
# Stop bounds, spent one after another by stop(). The supervisor waits for their sum
# (news.supervision.child_stop_bound_seconds) so a slow drain is not cut short by its parent.
RECONCILE_JOIN_SECONDS = 10.0
MOOMOO_STOP_SECONDS = 11.0  # tools/moomoo/push_feed.py: connection join 5 s + processor drain and join 6 s
STALLED_LOCK_SECONDS = 0.25


def stop_bound_seconds() -> float:
    """Worst case of one stop(): reconcile join, then each owned provider's bounded drain."""
    from ..crypto_market.kraken_stream import DRAIN_SECONDS, RECEIVER_JOIN_SECONDS

    return RECONCILE_JOIN_SECONDS + STALLED_LOCK_SECONDS + MOOMOO_STOP_SECONDS + RECEIVER_JOIN_SECONDS + DRAIN_SECONDS


_SUPPLY: HeadlessMarketSupply | None = None
_GLOBAL_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class SupplyTarget:
    source: str
    symbol: str
    capabilities: tuple[str, ...]


def _list(env: Mapping[str, str], key: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in env.get(key, '').split(',') if item.strip())


def validate_supply(env: Mapping[str, str]) -> tuple[SupplyTarget, ...]:
    """Parse ``source:symbol@CAPABILITY+CAPABILITY`` targets. Empty unless supply is enabled.

    Every refusal here is a configuration the operator must change, so the
    child reports it as permanent. Rights are not decided here.
    """
    if env.get('IMP_MARKET_SUPPLY_ENABLED') != '1':
        return ()
    if env.get('IMP_MARKET_PERSISTENCE_ENABLED') != '1':
        raise ValueError('MARKET_SUPPLY_REQUIRES_PERSISTENCE')
    entries = _list(env, 'IMP_MARKET_SUPPLY_TARGETS')
    if not entries:
        raise ValueError('MARKET_SUPPLY_TARGETS_REQUIRED')
    stored_sources = set(_list(env, 'IMP_MARKET_PERSISTENCE_SOURCES'))
    stored_symbols = set(_list(env, 'IMP_MARKET_PERSISTENCE_SYMBOLS'))
    targets, seen = [], set()
    for entry in entries:
        source, _, rest = entry.partition(':')
        symbol, _, names = rest.rpartition('@')
        capabilities = tuple(names.split('+'))
        if (source not in SOURCE_CAPABILITIES or not SYMBOL_PATTERNS[source].fullmatch(symbol)
                or len(set(capabilities)) != len(capabilities)
                or set(capabilities) - set(SOURCE_CAPABILITIES[source]) or (source, symbol) in seen):
            raise ValueError('MARKET_SUPPLY_TARGETS_INVALID')
        if source not in stored_sources or symbol not in stored_symbols:
            raise ValueError('MARKET_SUPPLY_TARGET_NOT_PERSISTED')  # never subscribe what is not stored
        seen.add((source, symbol))
        targets.append(SupplyTarget(source, symbol, capabilities))
    if len(targets) > MAX_TARGETS:
        raise ValueError('MARKET_SUPPLY_TARGETS_INVALID')
    sources = {target.source for target in targets}
    if 'moomoo' in sources:
        if env.get('IMP_LIVE_OBSERVATIONAL') != '1' or env.get('IMP_MOOMOO_LIVE') != '1':
            raise ValueError('MARKET_SUPPLY_PROVIDER_GATE_CLOSED')
        # The shared runtime would also start these; a collection-only process must not.
        # Any other provider preference leaves the runtime with no OpenD feed, or replaying a fixture.
        if (env.get('IMP_IBKR_LIVE', '').strip() == '1'
                or env.get('IMP_OBSERVATIONAL_PROVIDER', 'auto').strip().lower() not in {'auto', 'moomoo'}
                or env.get('IMP_LIVE_FIXTURE_FEED', '').strip()
                or env.get('IMP_SHADOW_RECORDING', '').strip().lower() in {'1', 'true', 'yes'}):
            raise ValueError('MARKET_SUPPLY_PROVIDER_CONFLICT')
    if 'kraken' in sources and env.get('IMP_CRYPTO_LIVE') != '1':
        raise ValueError('MARKET_SUPPLY_PROVIDER_GATE_CLOSED')
    return tuple(targets)


def collection_session(source: str, epoch: float) -> dict[str, Any]:
    """Whether a source is expected to produce data now. Collection eligibility only; not an AI or trading window."""
    if source == 'kraken':
        return {'label': 'CONTINUOUS', 'data_expected': True}
    from .. import nyse_calendar
    from ..market_sessions import ET, us_equity_screener_session

    moment = datetime.fromtimestamp(epoch, timezone.utc).astimezone(ET)
    if not nyse_calendar.covers(moment.date()):
        return {'label': 'CALENDAR_UNAVAILABLE', 'data_expected': False}
    label = us_equity_screener_session(moment)
    if label in {'PREMARKET', 'REGULAR', 'AFTER_HOURS'} and not nyse_calendar.is_trading_day(moment.date()):
        label = 'CLOSED'
    # Overnight quotes may arrive and are stored; their absence is not a fault.
    return {'label': label, 'data_expected': label in {'PREMARKET', 'REGULAR', 'AFTER_HOURS'}}


class _MoomooSupply:
    """Demand on the process's existing OpenD runtime and its reference-counted subscription manager."""

    def __init__(self, runtime: Callable[[], Any] | None = None, close: Callable[[], None] | None = None) -> None:
        self._factory, self._close, self.runtime = runtime, close, None
        self._probe, self._probe_at = None, 0.0

    def open(self) -> bool:
        if self.runtime is None:
            if self._factory is None:
                from .live_runtime import get_live_runtime

                self.runtime = get_live_runtime(create=True)
            else:
                self.runtime = self._factory()
        return self.runtime is not None

    def entitlement(self, capability: str) -> str | None:
        """Read from the probe file itself, so it is decided before OpenD is contacted and tracks the file's age."""
        if self._probe is None or time.monotonic() - self._probe_at >= PROBE_RELOAD_SECONDS:
            from .capability_registry import VerifiedCapabilityRegistry
            from .live_config import probe_report_path, probe_staleness_seconds

            self._probe = VerifiedCapabilityRegistry.from_probe_file(probe_report_path(),
                                                                     max_staleness_seconds=probe_staleness_seconds())
            self._probe_at = time.monotonic()
        registry = self._probe
        if registry.load_error:
            return 'ENTITLEMENT_PROBE_MISSING'
        if registry.is_stale:
            return 'ENTITLEMENT_PROBE_STALE'
        row = registry.get(capability)
        return None if row is not None and row.account_entitled else 'ENTITLEMENT_NOT_VERIFIED'

    def request(self, symbol: str, capability: str) -> tuple[str, str | None]:
        from .subscription_manager import SubscriptionPriority

        result = self.runtime.subscribe(instrument_id=symbol, capabilities=[capability], consumer_id=SUPPLY_CONSUMER,
                                        priority=SubscriptionPriority.BACKGROUND_RESEARCH)[0]
        if not result['accepted']:
            return 'BLOCKED', str(result.get('reason') or 'SUBSCRIPTION_REJECTED')
        feed = self.runtime.feed
        state = feed.subscription_state(symbol, capability) if feed is not None else 'PENDING'
        if state == 'REFUSED':
            return 'REFUSED', 'PROVIDER_REFUSED_SUBSCRIPTION'
        # The feed remembers its subscriptions until the next session; without a connection none is active.
        connected = self.connection() in {'CONNECTED', 'CONNECTED_DEGRADED'}
        return ('ACTIVE', None) if state == 'ACTIVE' and connected else ('REQUESTED', None)

    def release(self, symbol: str, capability: str) -> None:
        self.runtime.unsubscribe(instrument_id=symbol, capabilities=[capability], consumer_id=SUPPLY_CONSUMER)

    def connection(self) -> str:
        return str(getattr(self.runtime.lifecycle.connection_state, 'value', self.runtime.lifecycle.connection_state))

    def prepare_stop(self) -> None:
        # Keep selected demand intact while the owned feed drains already observed callbacks.
        if self.runtime is not None and self._factory is None:
            self.runtime.stop()

    def close(self) -> None:
        if self._close is not None:
            self._close()
        elif self._factory is None:
            from .live_runtime import reset_live_runtime

            reset_live_runtime()  # closes only this process's OpenD connection
        self.runtime = None


class _KrakenSupply:
    """Demand on the process's existing Kraken selected-pair stream. Public data; no account exists to verify."""

    def __init__(self, runtime: Callable[[], Any] | None = None) -> None:
        self._factory, self.runtime = runtime, None
        self._drained = False
        #: the owned stream's own account of its last drain; None until one was attempted
        self.shutdown_status: dict[str, Any] | None = None

    def open(self) -> bool:
        if self.runtime is None:
            if self._factory is None:
                from ..ui_api.screener_crypto import _stream_runtime

                self.runtime = _stream_runtime()
            else:
                self.runtime = self._factory()
            self._drained = False
        return self.runtime is not None

    def entitlement(self, capability: str) -> str | None:
        return None

    def request(self, symbol: str, capability: str) -> tuple[str, str | None]:
        result = self.runtime.subscribe(instrument_id=symbol, capabilities=[capability], consumer_id=SUPPLY_CONSUMER)[0]
        if not result['accepted']:
            return 'BLOCKED', str(result.get('reason') or 'SUBSCRIPTION_REJECTED')
        if self.runtime.subscription_refusal(symbol, capability):
            return 'REFUSED', 'PROVIDER_REFUSED_SUBSCRIPTION'
        active = self.runtime.subscriptions.activated_at(instrument_id=symbol, capability=capability) is not None
        return ('ACTIVE', None) if active else ('REQUESTED', None)

    def release(self, symbol: str, capability: str) -> None:
        self.runtime.unsubscribe(instrument_id=symbol, capabilities=[capability], consumer_id=SUPPLY_CONSUMER)

    def connection(self) -> str:
        return str(self.runtime.lifecycle.connection_state)

    def _drain(self) -> None:
        self._drained = True  # one attempt: a second would repeat the wait and the gap evidence
        try:
            status = self.runtime.shutdown()
        except Exception:
            self.shutdown_status = {'state': 'UNVERIFIED', 'reason': 'SHUTDOWN_FAILED', 'tail_observations': 'UNKNOWN'}
            raise
        self.shutdown_status = {key: status.get(key) for key in ('state', 'reason', 'tail_observations') if key in status}
        if status.get('state') == 'UNVERIFIED':
            # The stream reports a deadline or transport failure by value; an unknown tail is not a clean stop.
            raise RuntimeError('KRAKEN_SHUTDOWN_TAIL_UNVERIFIED')

    def prepare_stop(self) -> None:
        # Drain the owned socket while routing still sees selected demand. Shared test/serving runtimes stay open.
        if self.runtime is not None and self._factory is None:
            self._drain()

    def close(self) -> None:
        try:
            if self.runtime is not None and self._factory is None and not self._drained:
                self._drain()  # only the stream this process's supply opened
        finally:
            self.runtime = None


class HeadlessMarketSupply:
    def __init__(self, path: Path, targets: tuple[SupplyTarget, ...], *, writer: Any, entitled_sources: tuple[str, ...] = (),
                 providers: Mapping[str, Any] | None = None, clock: Callable[[], float] = time.time,
                 interval: float = RECONCILE_SECONDS) -> None:
        if not targets or len(targets) > MAX_TARGETS:
            raise ValueError('MARKET_SUPPLY_TARGETS_INVALID')
        self.path, self.targets, self.writer, self.clock, self.interval = path, targets, writer, clock, interval
        # ``path`` is the state store (supply evidence, the writer's owner lock); runs and checkpoints are read where
        # the writer keeps them (stream_store.py).
        from .stream_store import stream_data_path

        self.stream_path = stream_data_path(path)
        stat = path.stat()
        self._storage_identity = (stat.st_dev, stat.st_ino)
        self.entitled_sources = frozenset(entitled_sources)
        self.providers = dict(providers) if providers is not None else {'moomoo': _MoomooSupply(), 'kraken': _KrakenSupply()}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._stopped = False
        self.shutdown_error: str | None = None
        self._standby = False
        self._errors = 0
        self._held: set[tuple[str, str, str]] = set()
        #: (source, symbol, capability) -> {'state', 'reason', 'active_since'}
        self._rows: dict[tuple[str, str, str], dict[str, Any]] = {
            (target.source, target.symbol, capability): {'state': 'PENDING', 'reason': None, 'active_since': None,
                                                         'requested_since': None}
            for target in targets for capability in target.capabilities}
        self._provider_rows: dict[str, dict[str, Any]] = {}
        self._saved_at = 0.0
        self._saved_state: str | None = None
        self._owner = f'{os.getpid()}:{id(self):x}'

    # ------------------------------------------------------------ ownership

    def _foreign_writer(self) -> bool | None:
        """True while another process holds the market writer. None when the store could not be read."""
        try:
            with closing(sqlite3.connect(self.stream_path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.1)) as db:
                rows = db.execute('SELECT run_id FROM market_stream_runs WHERE closed_ns IS NULL AND lease_until_ns>?',
                                  (time.time_ns(),)).fetchall()
        except (sqlite3.Error, OSError):
            return None
        # Read after the query, so a run this writer acquired meanwhile is recognised as its own.
        own = self.writer.run_id
        if own is not None or not rows:
            return any(row[0] != own for row in rows)
        # An open run that is not ours: a live owner, or one that died inside its lease.
        # Only the owner lock tells them apart; a dead owner must not delay recovery.
        from .persistence import owner_lock_held

        try:
            held = owner_lock_held(self.path)
        except OSError:
            return None
        # The run row is committed just before this writer records it as its own; the lock is then ours.
        return held and self.writer.run_id is None

    def _set(self, key: tuple[str, str, str], state: str, reason: str | None = None) -> None:
        row = self._rows[key]
        if state == 'ACTIVE' and row['state'] != 'ACTIVE':
            row['active_since'] = self.clock()
        elif state != 'ACTIVE':
            row['active_since'] = None
        if state not in {'REQUESTED', 'ACTIVE'}:
            row['requested_since'] = None
        elif row['requested_since'] is None:
            row['requested_since'] = self.clock()
        if state == 'REFUSED' and row['state'] != 'REFUSED':
            # Durable evidence that a selected stream was declined, written once per refusal.
            self.writer.gap('SUPPLY_SUBSCRIPTION_REFUSED', stream=f'{key[0]}:{key[1]}:{key[2]}')
        row['state'], row['reason'] = state, reason

    def _release(self, key: tuple[str, str, str]) -> None:
        if key in self._held:
            try:
                self.providers[key[0]].release(key[1], key[2])
            except Exception:  # noqa: BLE001 - one provider's failure must not keep another's demand alive
                self._errors += 1
                if self._stop.is_set():
                    self.shutdown_error = 'SUPPLY_SHUTDOWN_INCOMPLETE'
            self._held.discard(key)

    def step(self) -> None:
        """One bounded reconciliation of configured targets against the existing subscription authorities."""
        with self._lock:
            if self._stopped:
                return
            foreign = self._foreign_writer()
            if foreign is not None:
                self._standby = foreign
            for source in {target.source for target in self.targets}:
                provider, attested = self.providers.get(source), source in self.entitled_sources
                keys = [key for key in self._rows if key[0] == source]
                row = self._provider_rows.setdefault(source, {'connection': 'NOT_OPENED', 'entitlement_confirmed': attested})
                if self._standby:
                    for key in keys:
                        self._release(key)
                        self._set(key, 'STANDBY', 'MARKET_WRITER_OWNED_BY_ANOTHER_PROCESS')
                    continue
                if not attested or provider is None:
                    for key in keys:
                        self._set(key, 'BLOCKED', 'ENTITLEMENT_NOT_CONFIRMED' if provider is not None else 'PROVIDER_UNSUPPORTED')
                    continue
                try:
                    reasons = {key: provider.entitlement(key[2]) for key in keys}
                    if all(reasons.values()):
                        # Nothing is verified for this source, so no provider session is opened for it.
                        for key in keys:
                            self._release(key)
                            self._set(key, 'BLOCKED', reasons[key])
                        continue
                    if not provider.open():
                        raise LookupError
                    row['connection'] = provider.connection()
                except Exception:  # noqa: BLE001 - reported, retried on the next step
                    self._errors += 1
                    row['connection'] = 'UNAVAILABLE'
                    for key in keys:
                        self._set(key, 'BLOCKED', 'PROVIDER_RUNTIME_UNAVAILABLE')
                    continue
                for key in keys:
                    try:
                        if reasons[key] is not None:
                            self._release(key)
                            self._set(key, 'BLOCKED', reasons[key])
                            continue
                        self._held.add(key)  # before the call, so a request that fails part-way is still released
                        state, reason = provider.request(key[1], key[2])
                        if state == 'BLOCKED':
                            self._held.discard(key)  # the authority refused; nothing is held
                        self._set(key, state, reason)
                    except Exception:  # noqa: BLE001
                        self._errors += 1
                        self._set(key, 'BLOCKED', 'PROVIDER_REQUEST_FAILED')
        if not self._stop.is_set():  # a step that outlived stop() must not overwrite the final evidence
            self._save()

    # --------------------------------------------------------------- status

    def _checkpoints(self) -> dict[str, tuple[int, int]] | None:
        try:
            with closing(sqlite3.connect(self.stream_path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.1)) as db:
                return {str(row[0]).lower(): (row[1], row[2]) for row in
                        db.execute('SELECT stream_id,received_ns,commit_ns FROM market_stream_checkpoints').fetchall()}
        except (sqlite3.Error, OSError):
            return None

    def status(self) -> dict[str, Any]:
        now = self.clock()
        checkpoints = self._checkpoints()
        writer = self.writer.status()
        with self._lock:
            sessions = {source: collection_session(source, now) for source in {target.source for target in self.targets}}
            targets = []
            for (source, symbol, capability), row in sorted(self._rows.items()):
                received, committed = (checkpoints or {}).get(f'{source}:{symbol}:{capability}'.lower(), (None, None))
                active = row['state'] == 'ACTIVE'
                # Committed under this demand: an earlier run's or another process's checkpoint is not collection now.
                fresh = (committed is not None and now - committed / 1e9 <= STALE_SECONDS
                         and row['requested_since'] is not None and committed / 1e9 >= row['requested_since'])
                waited = active and now - row['active_since'] > STALE_SECONDS
                state = row['state']
                if active:
                    state = ('COLLECTING' if fresh
                             else 'ACTIVE_NO_DATA' if sessions[source]['label'] == 'CALENDAR_UNAVAILABLE'
                             else 'SESSION_CLOSED' if not sessions[source]['data_expected']
                             else 'STALE' if waited and checkpoints is not None else 'ACTIVE_NO_DATA')
                targets.append({'source': source, 'symbol': symbol, 'capability': capability, 'state': state,
                                'reason': row['reason'], 'subscription_requested': row['state'] in {'REQUESTED', 'ACTIVE', 'REFUSED'},
                                'subscription_active': active, 'last_received_ns': received, 'last_commit_ns': committed,
                                'committed_recently': fresh})
            providers = {}
            for source, row in sorted(self._provider_rows.items()):
                connection = row['connection']
                providers[source] = {**row, 'session': sessions[source],
                                     'available': connection in {'CONNECTED', 'CONNECTED_DEGRADED'},
                                     'recovery_pending': connection in {'CONNECTING', 'RECONNECTING', 'DISCONNECTED'},
                                     'maintenance': connection == 'MAINTENANCE'}
            states = [target['state'] for target in targets]
            degraded = writer['state'] in {'RETRYING', 'FAILED', 'WAITING_FOR_OWNERSHIP'}
            if self._stopped:
                state = 'BLOCKED' if self.shutdown_error else 'STOPPED'
            elif self._standby:
                state = 'STANDBY'
            elif states and all(item == 'BLOCKED' for item in states):
                state = 'BLOCKED'
            elif degraded or any(item in {'BLOCKED', 'REFUSED'} for item in states):
                state = 'DEGRADED'
            elif any(row['recovery_pending'] for row in providers.values()):
                state = 'RECOVERY_PENDING'
            elif 'STALE' in states:
                state = 'STALE'
            elif 'COLLECTING' in states:
                state = 'COLLECTING'
            elif any(item in {'ACTIVE_NO_DATA', 'SESSION_CLOSED'} for item in states):
                state = 'SUBSCRIBED_NO_DATA'
            else:
                state = 'WAITING'
            count = lambda *names: sum(item in names for item in states)  # noqa: E731
            return {'enabled': True, 'configured': True, 'state': state, 'consumer_id': SUPPLY_CONSUMER,
                    'worker_alive': bool(self._thread and self._thread.is_alive()),
                    'entitled_sources': sorted(self.entitled_sources), 'providers': providers, 'targets': targets,
                    'summary': {'streams': len(states), 'blocked': count('BLOCKED'), 'refused': count('REFUSED'),
                                'standby': count('STANDBY'), 'requested': count('REQUESTED', 'PENDING'),
                                'active': sum(target['subscription_active'] for target in targets),
                                'collecting': count('COLLECTING'), 'stale': count('STALE')},
                    'writer': {key: writer.get(key) for key in ('state', 'error', 'ownership', 'collecting', 'backlog',
                               'rejected', 'committed', 'duplicates', 'known_gaps', 'received_ns', 'last_commit_ns')},
                    'writer_degraded': degraded, 'checkpoints_readable': checkpoints is not None,
                    'reconcile_errors': self._errors, 'stale_after_seconds': STALE_SECONDS, 'updated_at': now,
                    'health_basis': 'COMMITTED_CHECKPOINTS_NOT_PROCESS_LIVENESS', 'coverage': 'OBSERVED_ONLY_NOT_COMPLETE',
                    'shutdown_incomplete': self.shutdown_error is not None, 'shutdown_error': self.shutdown_error,
                    'collection_only': True, 'execution_authority': 'NONE', 'ai_required': False}

    def _save(self, *, final: bool = False) -> None:
        """Best-effort evidence for the existing health route; never blocks or fails supply."""
        try:
            stat = self.path.stat()
            if (stat.st_dev, stat.st_ino) != self._storage_identity:
                raise OSError('SUPPLY_STATUS_STORAGE_REPLACED')
            status = self.status()
            now = self.clock()
            if not final and status['state'] == self._saved_state and now - self._saved_at < STATUS_SECONDS:
                return
            with closing(sqlite3.connect(self.path.resolve().as_uri() + '?mode=rw', uri=True, timeout=.25)) as db:
                db.execute('INSERT OR REPLACE INTO news_collection_jobs(job_id,payload_json,next_due,lease_owner,lease_until) '
                           'VALUES (?,?,0,?,?)', (SUPPLY_JOB, json.dumps(status), None if final else self._owner,
                                                  0 if final else now + STATUS_LEASE_SECONDS))
                db.commit()
            self._saved_at, self._saved_state = now, status['state']
        except Exception:  # noqa: BLE001 - status evidence is secondary to collection
            self._errors += 1

    # ------------------------------------------------------------ lifecycle

    def alive(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def unrecoverable(self) -> str | None:
        """A provider reason only a fresh process can clear (the Moomoo data-flow watchdog's last resort)."""
        moomoo = self.providers.get('moomoo')
        runtime = getattr(moomoo, 'runtime', None)
        watchdog = getattr(runtime, 'feed_watchdog', None)
        return getattr(watchdog, 'unrecoverable', None)

    def start(self) -> None:
        def run() -> None:
            while not self._stop.is_set():
                try:
                    self.step()
                except Exception:  # noqa: BLE001 - reconciliation must outlive one bad step
                    self._errors += 1
                self._stop.wait(self.interval)
        if self._stopped:
            raise ValueError('MARKET_SUPPLY_STOPPED')
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=run, name='imp-market-supply', daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Drain owned provider supply, release demand, then close the sessions this process opened."""
        if self._stopped:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=RECONCILE_JOIN_SECONDS)
        stalled = self._thread is not None and self._thread.is_alive()
        if not self._lock.acquire(timeout=STALLED_LOCK_SECONDS if stalled else -1):
            # A reconciliation still inside a provider call owns the lock and the provider sessions.
            # Waiting for it has no bound, and draining beside it would use those sessions concurrently.
            # Report the stop as incomplete and let the writer drain what was already delivered;
            # process exit closes the sessions. The saved status row expires instead of being finalised.
            self._errors += 1
            self.shutdown_error = 'SUPPLY_SHUTDOWN_INCOMPLETE'
            self.writer.gap('SUPPLY_SHUTDOWN_INCOMPLETE')
            self._stopped = True  # one attempt: a repeat would spend the bound again
            return
        try:
            for provider in self.providers.values():
                try:
                    prepare = getattr(provider, 'prepare_stop', None)
                    if prepare is not None:
                        prepare()
                except Exception:  # noqa: BLE001 - a failed drain must not keep other provider demand alive
                    self._errors += 1
                    self.shutdown_error = 'SUPPLY_SHUTDOWN_INCOMPLETE'
            for key in list(self._held):
                self._release(key)
            for key in self._rows:
                self._set(key, 'STOPPED')
            for provider in self.providers.values():
                try:
                    provider.close()
                except Exception:  # noqa: BLE001
                    self._errors += 1
                    self.shutdown_error = 'SUPPLY_SHUTDOWN_INCOMPLETE'
            for source, provider in self.providers.items():
                drained = getattr(provider, 'shutdown_status', None)
                if drained is not None and source in self._provider_rows:
                    self._provider_rows[source]['shutdown'] = dict(drained)  # which provider left the tail unknown
            self._stopped = True
        finally:
            self._lock.release()
        self._save(final=True)


def active_supply() -> HeadlessMarketSupply | None:
    return _SUPPLY


def start_supply(writer: Any, env: Mapping[str, str] | None = None, *,
                 providers: Mapping[str, Any] | None = None) -> HeadlessMarketSupply | None:
    """Collection-only entry point. Returns None unless supply is explicitly enabled."""
    global _SUPPLY
    env = os.environ if env is None else env
    targets = validate_supply(env)
    if not targets:
        return None
    if writer is None:
        raise ValueError('MARKET_SUPPLY_REQUIRES_PERSISTENCE')
    with _GLOBAL_LOCK:
        if _SUPPLY is not None:
            raise ValueError('MARKET_SUPPLY_ALREADY_STARTED')
        supply = HeadlessMarketSupply(getattr(writer, 'state_path', writer.connection.path), targets, writer=writer, providers=providers,
                                      entitled_sources=_list(env, 'IMP_MARKET_SUPPLY_ENTITLED_SOURCES'))
        supply.start()
        _SUPPLY = supply
        return supply


def stop_supply() -> None:
    global _SUPPLY
    with _GLOBAL_LOCK:
        if _SUPPLY is not None:
            _SUPPLY.stop()
            _SUPPLY = None


def supply_status(env: Mapping[str, str] | None = None, *, clock: Callable[[], float] = time.time) -> dict[str, Any]:
    """In-process status, else the evidence a headless child last saved. Read-only; never migrates."""
    supply = active_supply()
    if supply is not None:
        return supply.status()
    values = os.environ if env is None else env
    directory = values.get('IMP_STATE_DIR', '')
    path = Path(directory) / 'imp-state.sqlite3'
    if not directory or not Path(directory).is_absolute() or not path.is_file():
        return {'enabled': False, 'state': 'DISABLED'}
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.1)) as db:
            row = db.execute('SELECT payload_json,lease_owner,lease_until FROM news_collection_jobs WHERE job_id=?',
                             (SUPPLY_JOB,)).fetchone()
        if row is None:
            return {'enabled': False, 'state': 'DISABLED'}
        evidence = json.loads(row[0])
        if row[1] and row[2] < clock():
            # The child stopped reporting; its last view of subscriptions proves nothing now.
            evidence.update(state='STALE', reason='SUPPLY_STATUS_EXPIRED')
            for target in evidence.get('targets') or []:
                target.update(state='UNKNOWN', subscription_active=False, committed_recently=False)
            evidence['summary'] = {**(evidence.get('summary') or {}), 'active': 0, 'collecting': 0}
        return {**evidence, 'enabled': bool(row[1]), 'reported_by': 'HEADLESS_CHILD_EVIDENCE'}
    except Exception:  # noqa: BLE001
        return {'enabled': False, 'state': 'UNKNOWN', 'reason': 'SUPPLY_STATUS_UNAVAILABLE'}
