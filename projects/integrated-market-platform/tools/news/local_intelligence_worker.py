"""Operator CLI for the scheduled local intelligence worker (no paid inference, no orders).

  run     tick every --interval seconds until STOP.request appears in the output directory
  once    one tick
  status  print the read-only view

Requires an explicit existing ``IMP_STATE_DIR`` store (read-only here) and ``IMP_LOCAL_INTELLIGENCE_DIR``.
One worker per directory: a second instance exits at once.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / 'src'):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from market_platform_foundation.news.local_intelligence import (  # noqa: E402
    DIRECTORY_ENV, DerivedEvidenceLog, LocalIntelligenceWorker, ReadOnlyStore, read_view,
)

LOCK_NAME = 'worker.lock'
STOP_NAME = 'STOP.request'
TORCH_THREADS = 4  # leave the workstation responsive; FinBERT batches of 16 headlines need no more


def _paths() -> tuple[Path, Path]:
    state, out = os.environ.get('IMP_STATE_DIR', ''), os.environ.get(DIRECTORY_ENV, '')
    if not state or not Path(state).is_absolute() or not out or not Path(out).is_absolute():
        raise SystemExit('IMP_STATE_DIR and IMP_LOCAL_INTELLIGENCE_DIR must be explicit absolute paths')
    return Path(state) / 'imp-state.sqlite3', Path(out)


def _scorer():
    from market_platform_foundation.news.finbert_sentiment import FinbertSentiment, default_model_path

    try:
        import torch  # type: ignore[import-not-found]
        torch.set_num_threads(TORCH_THREADS)
    except ImportError:
        pass
    path, source = default_model_path()
    return FinbertSentiment(model_path=path or '', model_source=source)


def _lock(directory: Path):
    import msvcrt

    directory.mkdir(parents=True, exist_ok=True)
    handle = open(directory / LOCK_NAME, 'a+')
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'once', 'status'))
    parser.add_argument('--interval', type=float, default=60.0)
    args = parser.parse_args(argv)
    store_path, directory = _paths()
    if args.command == 'status':
        print(json.dumps(read_view(directory, limit=5), indent=2, default=str))
        return 0
    if not 15.0 <= args.interval <= 3600.0:
        raise SystemExit('interval must be within 15..3600 seconds')
    lock = _lock(directory)
    if lock is None:
        print(json.dumps({'state': 'NOT_STARTED', 'reason': 'WORKER_ALREADY_RUNNING'}), flush=True)
        return 0
    worker = LocalIntelligenceWorker(ReadOnlyStore(store_path), DerivedEvidenceLog(directory), scorer_factory=_scorer)
    stop = directory / STOP_NAME
    stop.unlink(missing_ok=True)
    try:
        while True:
            try:
                result = worker.tick()
            except (OSError, ValueError) as exc:  # a store or drive problem is reported; the loop stays bounded
                result = {'state': 'ERROR', 'reason': f'{type(exc).__name__}: {str(exc)[:200]}'}
                try:
                    DerivedEvidenceLog(directory).status({**result, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
                except OSError:
                    pass
            print(json.dumps({k: result.get(k) for k in ('at', 'state', 'reason', 'processed', 'scored', 'backlog',
                                                         'cpu_seconds', 'wall_seconds')}), flush=True)
            if args.command == 'once' or not store_path.is_file():
                return 0 if store_path.is_file() else 1
            deadline = time.monotonic() + args.interval
            while time.monotonic() < deadline:
                if stop.exists():
                    print(json.dumps({'state': 'STOPPED', 'reason': 'OPERATOR_STOP'}), flush=True)
                    return 0
                time.sleep(1.0)
    finally:
        lock.close()


if __name__ == '__main__':
    raise SystemExit(main())
