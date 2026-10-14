"""Offline PF-01 read-only accounting and explicit profile forecasting.

Exit 0: modeled fit / inspection ready; 2: capacity warning or insufficient;
1: blocked input or bounded-inspection failure. No activation is performed.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from market_platform_foundation.market_data.capacity import (  # noqa: E402
    DEFAULT_MAX_DATABASE_BYTES, Workload, capacity_status, forecast, inspect_storage,
)

PROFILE_MAX_BYTES = 1024**2


def _read_profile(path: Path) -> dict:
    with path.open('rb') as handle:
        encoded = handle.read(PROFILE_MAX_BYTES + 1)
    if len(encoded) > PROFILE_MAX_BYTES:
        raise ValueError('CAPACITY_PROFILE_SIZE_LIMIT')
    profile = json.loads(encoded)
    allowed = {'name', 'evidence_basis', 'workloads', 'growth_margin', 'other_bytes_per_day'}
    if not isinstance(profile, dict) or set(profile) - allowed:
        raise ValueError('CAPACITY_PROFILE_FIELDS_INVALID')
    if not isinstance(profile.get('name'), str) or not profile['name'].strip() or len(profile['name']) > 80:
        raise ValueError('CAPACITY_PROFILE_NAME_REQUIRED')
    if profile.get('evidence_basis') not in {'SYNTHETIC_ASSUMPTION', 'MEASURED_SYNTHETIC', 'MEASURED_LIVE'}:
        raise ValueError('CAPACITY_PROFILE_EVIDENCE_BASIS_REQUIRED')
    rows = profile.get('workloads')
    if not isinstance(rows, list) or not rows or len(rows) > 128:
        raise ValueError('CAPACITY_WORKLOAD_REQUIRED')
    return profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, help='Existing SQLite store to inspect read-only; never created/migrated')
    parser.add_argument('--profile', type=Path, help='Explicit JSON workload assumptions; no symbols selected')
    parser.add_argument('--hours', type=float, default=12, help='Modeled calendar window, default 12 hours')
    parser.add_argument('--max-database-bytes', type=int, default=None,
                        help='May lower the configured ceiling (IMP_PF01_MAX_DATABASE_MIB, default '
                             f'{DEFAULT_MAX_DATABASE_BYTES // 1024**2} MiB), never raise it')
    args = parser.parse_args(argv)
    if args.database is None and args.profile is None:
        parser.error('at least one of --database or --profile is required')
    try:
        report = {'kind': 'OFFLINE_CAPACITY_DRY_RUN', 'activation_authorized': False}
        if args.database is not None:
            storage = inspect_storage(args.database, max_database_bytes=args.max_database_bytes)
            report['storage'] = storage
            report['storage_basis'] = 'READ_ONLY_EXISTING_DATABASE'
            capacity = storage['capacity']
        else:
            capacity = capacity_status(0, max_database_bytes=args.max_database_bytes)
            report['storage_basis'] = 'DECLARED_EMPTY_STORE_NOT_MEASURED'
            report['capacity'] = capacity
        result_code = 0 if capacity['state'] == 'READY' else 2
        if args.profile is not None:
            profile = _read_profile(args.profile)
            workloads = tuple(Workload(**row) for row in profile['workloads'])
            result = forecast(workloads, duration_seconds=args.hours * 3600, capacity=capacity,
                              growth_margin=profile.get('growth_margin', 1.25),
                              other_bytes_per_day=profile.get('other_bytes_per_day', 0))
            report['profile'] = {'name': profile['name'], 'evidence_basis': profile['evidence_basis'],
                                 'evidence_basis_semantics': 'CALLER_DECLARATION_NOT_VERIFIED_BY_TOOL'}
            report['forecast'] = result
            if result['state'] != 'FITS_MODELED_WINDOW':
                result_code = 2
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
        return result_code
    except (OSError, ValueError, TypeError, OverflowError, sqlite3.Error) as exc:
        print(json.dumps({'kind': 'OFFLINE_CAPACITY_DRY_RUN', 'state': 'BLOCKED',
                          'reason': str(exc), 'activation_authorized': False}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
