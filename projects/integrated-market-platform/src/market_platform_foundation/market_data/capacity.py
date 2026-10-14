"""PF-01 bounded capacity decisions and read-only shared-store accounting.

No migrations, checkpoint, vacuum, archive, expiry, subscriptions or sampling.
Forecasts are explicit workload models, never live-traffic qualification.
"""
from __future__ import annotations

import math
import os
import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..local_state.migrations import current_schema_version

DEFAULT_MAX_DATABASE_BYTES = 512 * 1024**2
# Owner-approved 2026-10-14: an operator may opt one store in to at most 8 GiB through
# IMP_PF01_MAX_DATABASE_MIB. Unset keeps the shipped 512 MiB ceiling everywhere.
APPROVED_MAX_DATABASE_BYTES = 8 * 1024**3
MAX_DATABASE_MIB_ENV = 'IMP_PF01_MAX_DATABASE_MIB'
STORAGE_RESERVE_BYTES = 8 * 1024**2  # existing writer's four 2 MiB batches


def configured_max_database_bytes(env: Mapping[str, str] | None = None) -> int:
    """The shared DB+WAL hard bound every PF-01 writer and check enforces.

    Fails closed: a malformed value or one above the approved ceiling raises
    instead of silently falling back to either bound.
    """
    value = (os.environ if env is None else env).get(MAX_DATABASE_MIB_ENV, '').strip()
    if not value:
        return DEFAULT_MAX_DATABASE_BYTES
    if not value.isdigit() or not 2 <= int(value):
        raise ValueError('CAPACITY_INVALID_CONFIGURED_CEILING')
    if int(value) * 1024**2 > APPROVED_MAX_DATABASE_BYTES:
        raise ValueError('CAPACITY_UNAPPROVED_HIGHER_CEILING')
    return int(value) * 1024**2
WARNING_FRACTION = 0.8
DAY_SECONDS = 86400


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f'CAPACITY_INVALID_{name}')
    return value


def _number(value: Any, name: str, minimum: float = 0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
        raise ValueError(f'CAPACITY_INVALID_{name}')
    return float(value)


def capacity_status(database_bytes: int, *, wal_bytes: int = 0,
                    max_database_bytes: int | None = None,
                    free_disk_bytes: int | None = None,
                    env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Cheap runtime warning using the same shared DB+WAL hard bound.

    Free disk is additional allocatable space, so subtract the emergency reserve
    once from it, not the existing database size again. No caller may raise the
    ceiling above configured_max_database_bytes(env) through this module.
    """
    ceiling = configured_max_database_bytes(env)
    used = _integer(database_bytes, 'DATABASE_BYTES') + _integer(wal_bytes, 'WAL_BYTES')
    maximum = _integer(ceiling if max_database_bytes is None else max_database_bytes, 'MAX_DATABASE_BYTES', 2 * 1024**2)
    if maximum > ceiling:
        raise ValueError('CAPACITY_UNAPPROVED_HIGHER_CEILING')
    budget_remaining = maximum - used - STORAGE_RESERVE_BYTES
    disk_remaining = None if free_disk_bytes is None else _integer(free_disk_bytes, 'FREE_DISK_BYTES') - STORAGE_RESERVE_BYTES
    remaining = budget_remaining if disk_remaining is None else min(budget_remaining, disk_remaining)
    binding = 'DISK_FREE' if disk_remaining is not None and disk_remaining < budget_remaining else 'DATABASE_CEILING'
    state = ('STOP_REQUIRED' if remaining < 0 else
             'WARNING' if used + STORAGE_RESERVE_BYTES >= maximum * WARNING_FRACTION or
             (disk_remaining is not None and disk_remaining <= STORAGE_RESERVE_BYTES) else 'READY')
    return {'state': state, 'database_bytes': database_bytes, 'wal_bytes': wal_bytes,
            'used_bytes': used, 'max_database_bytes': maximum,
            'reserve_bytes': STORAGE_RESERVE_BYTES, 'remaining_bytes': max(0, remaining),
            'free_disk_bytes': free_disk_bytes, 'binding_limit': binding,
            'retention_action': 'PRESERVE_ALL_STOP_BEFORE_BOUND'}


@dataclass(frozen=True, slots=True)
class Workload:
    """Operator-declared rates per target, including all revisions/updates.

    active_seconds_per_day is an upper activity bound in ANY rolling 24 hours,
    not merely each calendar date. Holidays/session alignment are not inferred.
    bytes_per_record must include measured SQLite indexes/page overhead, not only
    payload length. Sources/types are labels, not provider activation authority.
    """
    source: str
    capability: str
    targets: int
    records_per_second: float
    bytes_per_record: float
    active_seconds_per_day: float

    def __post_init__(self) -> None:
        for name in ('source', 'capability'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 80:
                raise ValueError(f'CAPACITY_INVALID_{name.upper()}')
        if _integer(self.targets, 'TARGETS', 1) > 20:
            raise ValueError('CAPACITY_INVALID_TARGETS')
        _number(self.records_per_second, 'RATE')
        _number(self.bytes_per_record, 'BYTES_PER_RECORD', 1)
        if _number(self.active_seconds_per_day, 'ACTIVE_SECONDS') > DAY_SECONDS:
            raise ValueError('CAPACITY_INVALID_ACTIVE_SECONDS')


def forecast(workloads: tuple[Workload, ...], *, duration_seconds: float,
             capacity: Mapping[str, Any], growth_margin: float = 1.25,
             other_bytes_per_day: float = 0) -> dict[str, Any]:
    """Bounded calendar-window model and continuous peak exposure.

    A partial day can contain the full session, so its activity is bounded by
    min(remainder, daily activity); multiplying by the daily average would
    understate short overnight/session windows. Other shared-store growth (news,
    Paper, runs, checkpoints, gaps) must be declared separately when not listed.
    """
    if not workloads or len(workloads) > 128 or any(not isinstance(row, Workload) for row in workloads):
        raise ValueError('CAPACITY_WORKLOAD_REQUIRED')
    duration = _number(duration_seconds, 'DURATION', 1)
    if duration > 366 * DAY_SECONDS:
        raise ValueError('CAPACITY_DURATION_LIMIT')
    margin = _number(growth_margin, 'MARGIN', 1)
    if margin > 10:
        raise ValueError('CAPACITY_MARGIN_LIMIT')
    other = _number(other_bytes_per_day, 'OTHER_GROWTH')
    remaining = _integer(capacity.get('remaining_bytes'), 'REMAINING_BYTES')
    days, remainder = divmod(duration, DAY_SECONDS)
    entries, total, peak_rate = [], 0.0, 0.0
    for row in workloads:
        active = days * row.active_seconds_per_day + min(remainder, row.active_seconds_per_day)
        rate = row.targets * row.records_per_second
        records = rate * active
        growth = records * row.bytes_per_record * margin
        if not all(math.isfinite(value) for value in (rate, records, growth)):
            raise ValueError('CAPACITY_MODEL_OVERFLOW')
        total += growth
        if row.active_seconds_per_day:
            peak_rate += rate * row.bytes_per_record
        entries.append({'source': row.source, 'capability': row.capability, 'targets': row.targets,
                        'records_per_second_per_target': row.records_per_second,
                        'bytes_per_record': row.bytes_per_record,
                        'active_seconds_per_day': row.active_seconds_per_day,
                        'modeled_active_seconds': active, 'projected_records': records,
                        'projected_growth_bytes': math.ceil(growth)})
    other_growth = other * duration / DAY_SECONDS * margin
    total += other_growth
    peak_rate = (peak_rate + other / DAY_SECONDS) * margin
    if not math.isfinite(total) or not math.isfinite(peak_rate * duration):
        raise ValueError('CAPACITY_MODEL_OVERFLOW')
    projected = math.ceil(total)
    return {'kind': 'MODELED_CAPACITY_NOT_OPERATIONAL_QUALIFICATION',
            'state': ('INSUFFICIENT_CAPACITY' if capacity.get('state') == 'STOP_REQUIRED' or projected > remaining else
                      'NO_ACTIVITY_MODELED' if not projected else 'FITS_MODELED_WINDOW'),
            'duration_seconds': duration, 'growth_margin': margin, 'workloads': entries,
            'other_bytes_per_day': other, 'other_projected_growth_bytes': math.ceil(other_growth),
            'projected_growth_bytes': projected, 'remaining_bytes': remaining,
            'shortfall_bytes': max(0, projected - remaining),
            'continuous_peak_growth_bytes': math.ceil(peak_rate * duration),
            'seconds_to_bound_at_peak_rate': remaining / peak_rate if peak_rate else None,
            'retention_action': 'PRESERVE_ALL_STOP_BEFORE_BOUND',
            'assumptions': 'DECLARED_ROLLING_24H_ACTIVITY_UPPER_BOUND_NO_HOLIDAY_OR_SESSION_ALIGNMENT_INFERRED'}


def inspect_storage(path: Path, *, max_database_bytes: int | None = None,
                    max_vm_steps: int = 5_000_000, timeout_seconds: float = 2.0) -> dict[str, Any]:
    """Read an existing SQLite snapshot with bounded query work and results.

    Opens mode=ro, never LocalStateConnection (which migrates). It may participate
    in SQLite's shared-memory read coordination but never checkpoints the WAL.
    Counts/payload sizes are exact within the transaction, physical sidecar stats
    are a separate non-atomic observation. Page/index accounting is optional when
    SQLite lacks dbstat. A timed-out scan fails explicitly instead of publishing
    zero or partial counts. Runtime status should use capacity_status instead.
    """
    path = Path(path).resolve(strict=True)
    _integer(max_vm_steps, 'VM_STEPS', 1)
    timeout = _number(timeout_seconds, 'TIMEOUT', 0.001)
    if max_vm_steps > 50_000_000 or timeout > 10:
        raise ValueError('CAPACITY_INSPECTION_LIMIT_INVALID')
    before = path.stat()
    if not path.is_file():
        raise FileNotFoundError('CAPACITY_STORAGE_MISSING')
    deadline, steps = time.monotonic() + timeout, 0
    interval = min(1000, max_vm_steps)

    def stop() -> int:
        nonlocal steps
        steps += interval
        return int(steps >= max_vm_steps or time.monotonic() >= deadline)

    conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.set_progress_handler(stop, interval)
    try:
        conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN')
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 2049")}
        if len(tables) > 2048:
            raise ValueError('CAPACITY_INSPECTION_GROUP_LIMIT')
        schema = current_schema_version(conn)
        groups = []
        if 'market_stream_records' in tables:
            groups.extend(dict(row) for row in conn.execute('''SELECT provider AS source, capability,
                COUNT(*) AS records, SUM(LENGTH(CAST(payload_json AS BLOB))) AS payload_bytes,
                MIN(received_ns) AS first_receipt_ns, MAX(received_ns) AS last_receipt_ns
                FROM market_stream_records GROUP BY provider,capability LIMIT 2049'''))
        if 'news_collection_records' in tables:
            groups.extend(dict(row) for row in conn.execute('''SELECT provider_id AS source, 'NEWS' AS capability,
                COUNT(*) AS records, SUM(LENGTH(CAST(payload_json AS BLOB))) AS payload_bytes
                FROM news_collection_records GROUP BY provider_id LIMIT 2049'''))
        if len(groups) > 2048:
            raise ValueError('CAPACITY_INSPECTION_GROUP_LIMIT')
        counts = {}
        for name in ('market_stream_checkpoints', 'market_stream_gaps', 'market_stream_runs', 'news_collection_jobs'):
            if name in tables:
                counts[name] = conn.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
        storage, page_accounting = {}, 'AVAILABLE'
        try:
            for row in conn.execute('''SELECT COALESCE(m.tbl_name,d.name) AS table_name, SUM(d.pgsize) AS bytes
                FROM dbstat AS d LEFT JOIN sqlite_master AS m ON m.name=d.name
                GROUP BY COALESCE(m.tbl_name,d.name) LIMIT 2049'''):
                storage[row['table_name']] = row['bytes']
            if len(storage) > 2048:
                raise ValueError('CAPACITY_INSPECTION_GROUP_LIMIT')
        except sqlite3.OperationalError as exc:
            if 'no such table: dbstat' not in str(exc):
                raise
            page_accounting = 'UNAVAILABLE_DBSTAT'
        page_size = conn.execute('PRAGMA page_size').fetchone()[0]
        page_count = conn.execute('PRAGMA page_count').fetchone()[0]
        free_pages = conn.execute('PRAGMA freelist_count').fetchone()[0]
        conn.rollback()
    except sqlite3.OperationalError as exc:
        if 'interrupted' in str(exc):
            raise ValueError('CAPACITY_INSPECTION_LIMIT') from exc
        raise
    finally:
        conn.close()
    after = path.stat()
    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
        raise ValueError('CAPACITY_STORAGE_REPLACED')
    wal = Path(str(path) + '-wal')
    wal_bytes = wal.stat().st_size if wal.is_file() else 0
    capacity = capacity_status(after.st_size, wal_bytes=wal_bytes, max_database_bytes=max_database_bytes,
                               free_disk_bytes=shutil.disk_usage(path.parent).free)
    return {'kind': 'READ_ONLY_STORAGE_SNAPSHOT', 'schema_version': schema,
            'database_bytes': after.st_size, 'wal_bytes': wal_bytes, 'capacity': capacity,
            'groups': groups, 'operational_counts': counts, 'table_storage_bytes': storage,
            'page_accounting': page_accounting, 'page_size': page_size, 'page_count': page_count,
            'freelist_bytes': page_size * free_pages, 'query_vm_step_upper_bound': max_vm_steps,
            'snapshot_semantics': 'SQL_COUNTS_TRANSACTIONAL_FILE_AND_DISK_STATS_NON_ATOMIC'}
