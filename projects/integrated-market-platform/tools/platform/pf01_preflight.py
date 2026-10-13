"""Read-only PF-01 operational preflight.

Reports each prerequisite as READY, BLOCKED, UNKNOWN or NOT VERIFIED from the
given environment, the existing store (opened ``mode=ro``) and the existing
capability-report file. It opens no provider connection, takes no lease or
write lock, migrates nothing and starts nothing. The read-only open takes
SQLite's ordinary shared read lock briefly and, on a WAL store with no open
reader, may create the ``-shm`` (and an empty ``-wal``) sidecar. A configured key, an open port or a
passing check here is never account-entitlement evidence: anything this tool
cannot establish without contacting a provider stays NOT VERIFIED.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping

from market_platform_foundation.market_data.capacity import capacity_status
from market_platform_foundation.market_data.headless_supply import collection_session, validate_supply
from market_platform_foundation.market_data.persistence import configured_selection, validate_capture_selection
from market_platform_foundation.news.collection import configured_jobs
from market_platform_foundation.news.supervision import (
    AI_CREDENTIAL_PREFIXES, EXECUTION_GATES, LEASE_SECONDS, child_stop_bound_seconds, collection_only_reason, require_current_schema,
    supervision_status,
)

READY, BLOCKED, UNKNOWN, NOT_VERIFIED = 'READY', 'BLOCKED', 'UNKNOWN', 'NOT VERIFIED'
ROOT = Path(__file__).resolve().parents[2]
MANIFEST_MAX_BYTES = 4 * 1024**2
SHA256 = re.compile('[0-9a-f]{64}')
# UNKNOWN: a fact this tool should have read but could not. NOT VERIFIED: only the operator's own evidence can settle it.
EXIT_CODES = {READY: 0, BLOCKED: 1, UNKNOWN: 2, NOT_VERIFIED: 3}
# Outside this tool's reach by design; listed for the operator, never judged and never part of the overall state.
NOT_INSPECTED = ('HOST_POWER_AND_SLEEP_POLICY', 'PROVIDER_ACCOUNT_AND_SUBSCRIPTION_QUOTA', 'PROVIDER_TERMS_FOR_LOCAL_ARCHIVAL')


def _check(name: str, state: str, reason: str | None = None, **detail: Any) -> dict[str, Any]:
    return {'check': name, 'state': state, 'reason': reason, **detail}


def _build_identity(env: Mapping[str, str]) -> dict[str, Any]:
    """Compare this source tree with the approved release's own file hashes, when the operator supplies them."""
    manifest = env.get('IMP_PF01_RELEASE_MANIFEST', '')
    if not manifest:
        return _check('build_identity', NOT_VERIFIED, 'RELEASE_MANIFEST_NOT_PROVIDED')
    try:
        with open(manifest, 'rb') as handle:
            encoded = handle.read(MANIFEST_MAX_BYTES + 1)
        files = json.loads(encoded)['files'] if len(encoded) <= MANIFEST_MAX_BYTES else None
        if not isinstance(files, dict) or not files:
            raise ValueError
        different = []
        for name, expected in files.items():
            if not isinstance(expected, str) or not SHA256.fullmatch(expected):
                raise ValueError  # a manifest that does not state a hash cannot confirm a file
            path = (ROOT / name).resolve()
            current = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_relative_to(ROOT) and path.is_file() else None
            if current != expected:
                different.append(name)
    except (OSError, ValueError, KeyError, TypeError):
        return _check('build_identity', UNKNOWN, 'RELEASE_MANIFEST_UNREADABLE')
    if different:
        return _check('build_identity', BLOCKED, 'RELEASE_MANIFEST_MISMATCH', files_different=len(different), first=sorted(different)[:5])
    return _check('build_identity', READY, files=len(files))


def _storage(env: Mapping[str, str]) -> tuple[Path | None, dict[str, Any]]:
    directory = env.get('IMP_STATE_DIR', '')
    if not directory or not Path(directory).is_absolute():
        return None, _check('storage', BLOCKED, 'EXPLICIT_STATE_DIR_REQUIRED')
    path = Path(directory) / 'imp-state.sqlite3'
    if not path.is_file():
        return None, _check('storage', BLOCKED, 'EXISTING_STORAGE_REQUIRED')
    # The volume serial lets the operator confirm the intended drive; it is reported, not judged.
    return path, _check('storage', READY, volume_serial=path.stat().st_dev)


def _schema(path: Path) -> dict[str, Any]:
    try:
        require_current_schema(path)
    except ValueError as exc:
        unreadable = str(exc) == 'SCHEMA_CHECK_STORAGE_UNAVAILABLE'
        return _check('schema', UNKNOWN if unreadable else BLOCKED, str(exc))
    return _check('schema', READY)


def _capacity(path: Path) -> dict[str, Any]:
    try:
        wal = Path(str(path) + '-wal')
        status = capacity_status(path.stat().st_size, wal_bytes=wal.stat().st_size if wal.is_file() else 0,
                                 free_disk_bytes=shutil.disk_usage(path.parent).free)
    except (OSError, ValueError) as exc:
        return _check('capacity', UNKNOWN, str(exc) if isinstance(exc, ValueError) else 'CAPACITY_UNAVAILABLE')
    state, reason = {'READY': (READY, None), 'WARNING': (NOT_VERIFIED, 'CAPACITY_WARNING_OPERATOR_REVIEW')}.get(
        status['state'], (BLOCKED, 'CAPACITY_STOP_REQUIRED'))
    return _check('capacity', state, reason, used_bytes=status['used_bytes'], max_database_bytes=status['max_database_bytes'],
                  remaining_bytes=status['remaining_bytes'], binding_limit=status['binding_limit'],
                  forecast='NOT_MODELLED_HERE_USE_tools/market_data_capacity.py')


def _owners(path: Path, env: Mapping[str, str], now: float) -> list[dict[str, Any]]:
    status = supervision_status(env, clock=lambda: now)
    if status.get('state') == 'UNKNOWN':
        supervisor = _check('supervisor_owner', UNKNOWN, status.get('reason'))
    elif status.get('enabled') and status.get('lease_until', 0) > now:
        supervisor = _check('supervisor_owner', BLOCKED, 'SUPERVISOR_OWNER_ACTIVE')
    elif status.get('latched'):
        supervisor = _check('supervisor_owner', BLOCKED, 'SUPERVISION_LATCHED_RESET_REQUIRED', recorded_reason=status.get('reason'))
    else:
        supervisor = _check('supervisor_owner', READY)
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.1)) as db:
            held = db.execute('SELECT COUNT(*) FROM market_stream_runs WHERE closed_ns IS NULL AND lease_until_ns>?',
                              (int(now * 1e9),)).fetchone()[0]
        writer = _check('market_writer_owner', BLOCKED, 'MARKET_CAPTURE_OWNER_ACTIVE') if held else _check('market_writer_owner', READY)
    except (sqlite3.Error, OSError):
        writer = _check('market_writer_owner', UNKNOWN, 'MARKET_RUNS_UNREADABLE')
    return [supervisor, writer]


def _moomoo_entitlement(capabilities: set[str]) -> dict[str, Any]:
    """The same file verdict the child applies before it contacts OpenD. The probe itself is never run here."""
    from market_platform_foundation.market_data.capability_registry import VerifiedCapabilityRegistry
    from market_platform_foundation.market_data.live_config import probe_report_path, probe_staleness_seconds

    try:
        registry = VerifiedCapabilityRegistry.from_probe_file(probe_report_path(), max_staleness_seconds=probe_staleness_seconds())
    except Exception:  # any unreadable or malformed report is the same answer: the file verdict is not known
        return _check('moomoo_entitlement', UNKNOWN, 'ENTITLEMENT_PROBE_UNREADABLE')
    if registry.load_error:
        return _check('moomoo_entitlement', BLOCKED, 'ENTITLEMENT_PROBE_MISSING')
    if registry.is_stale:
        return _check('moomoo_entitlement', BLOCKED, 'ENTITLEMENT_PROBE_STALE')
    missing = sorted(name for name in capabilities if not getattr(registry.get(name), 'account_entitled', False))
    if missing:
        return _check('moomoo_entitlement', BLOCKED, 'ENTITLEMENT_NOT_VERIFIED', capabilities=missing)
    return _check('moomoo_entitlement', NOT_VERIFIED, 'RECORDED_PROBE_REPORT_ONLY_NOT_RECHECKED', capabilities=sorted(capabilities))


def _demand(env: Mapping[str, str], now: float) -> list[dict[str, Any]]:
    checks = []
    if env.get('IMP_NEWS_COLLECTION_ENABLED') == '1':
        try:
            checks.append(_check('news_jobs', READY, jobs=len(configured_jobs(env))))
            checks.append(_check('news_provider_access', NOT_VERIFIED, 'NOT_CONTACTED_BY_PREFLIGHT'))
        except ValueError as exc:
            checks.append(_check('news_jobs', BLOCKED, str(exc) if str(exc).startswith('COLLECTION_') else 'COLLECTION_INTERVAL_INVALID'))
    if env.get('IMP_MARKET_PERSISTENCE_ENABLED') == '1':
        sources, symbols = configured_selection(env)
        try:
            validate_capture_selection(sources, symbols)
        except ValueError as exc:  # the child would refuse this selection permanently at start
            checks.append(_check('market_persistence', BLOCKED, str(exc), sources=len(sources), symbols=len(symbols)))
        else:
            checks.append(_check('market_persistence', READY, sources=sorted(sources), symbols=len(symbols)))
    try:
        targets = validate_supply(env)
    except ValueError as exc:
        return checks + [_check('market_targets', BLOCKED, str(exc))]
    if not targets:
        return checks + [_check('market_targets', READY, 'NO_MARKET_DEMAND_CONFIGURED', targets=0)]
    sources = sorted({target.source for target in targets})
    checks.append(_check('market_targets', READY, targets=len(targets), sources=sources))
    attested = {item.strip() for item in env.get('IMP_MARKET_SUPPLY_ENTITLED_SOURCES', '').split(',') if item.strip()}
    unconfirmed = [source for source in sources if source not in attested]
    checks.append(_check('data_rights', BLOCKED, 'ENTITLEMENT_NOT_CONFIRMED', sources=unconfirmed) if unconfirmed else
                  _check('data_rights', NOT_VERIFIED, 'OPERATOR_ATTESTATION_NOT_CHECKABLE_BY_TOOL', sources=sources))
    if 'moomoo' in sources:
        checks.append(_moomoo_entitlement({name for target in targets if target.source == 'moomoo' for name in target.capabilities}))
    checks.append(_check('provider_connectivity', NOT_VERIFIED, 'NOT_CONTACTED_BY_PREFLIGHT', sources=sources))
    sessions = {source: collection_session(source, now)['label'] for source in sources}
    checks.append(_check('collection_schedule', UNKNOWN, 'CALENDAR_UNAVAILABLE', sessions=sessions)
                  if 'CALENDAR_UNAVAILABLE' in sessions.values() else _check('collection_schedule', READY, sessions=sessions))
    return checks


def preflight(env: Mapping[str, str], *, clock=time.time) -> dict[str, Any]:
    now = clock()
    reason = collection_only_reason(env)
    open_gates = sorted(gate for gate in EXECUTION_GATES if env.get(gate) == '1')
    checks = [
        _build_identity(env),
        _check('execution_gates', BLOCKED, 'EXECUTION_GATE_ENABLED', gates=open_gates) if open_gates else _check('execution_gates', READY),
        _check('supervision_gate', READY) if env.get('IMP_PF01_SUPERVISION_ENABLED') == '1' else
        _check('supervision_gate', BLOCKED, 'SUPERVISION_DISABLED'),
        _check('collection_mode', BLOCKED, reason) if reason and reason != 'EXECUTION_GATE_ENABLED' else _check('collection_mode', READY),
    ]
    path, storage = _storage(env)
    checks.append(storage)
    if path is not None:
        schema = _schema(path)
        checks += [schema, _capacity(path)]
        # Owner rows exist only at the current schema; an older store is reported by the schema check.
        checks += _owners(path, env, now) if schema['state'] == READY else []
    checks += _demand(env, now)
    states = {check['state'] for check in checks}
    overall = next(state for state in (BLOCKED, UNKNOWN, NOT_VERIFIED, READY) if state in states)
    return {'kind': 'PF01_OPERATIONAL_PREFLIGHT', 'overall': overall, 'checks': checks,
            'child_stop_bound_seconds': child_stop_bound_seconds(), 'supervisor_lease_seconds': LEASE_SECONDS,
            'activation_requested': False, 'providers_contacted': False, 'execution_authority': 'NONE', 'ai_required': False,
            'ai_credentials_forwarded_to_child': False, 'ai_credential_prefixes_withheld': list(AI_CREDENTIAL_PREFIXES),
            'not_inspected': list(NOT_INSPECTED), 'emergency_stop': 'CTRL_C_ONCE_IN_SUPERVISOR_TERMINAL'}
