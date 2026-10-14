"""Scheduled no-cost local intelligence over stored PF-01 news (derived evidence, never authority).

What runs: the existing deterministic event taxonomy on every stored revision, and the existing local FinBERT
scorer on news headlines (official filings are classified, not sentiment-scored). Nothing here calls a paid
model, a provider or a broker, and nothing writes to the canonical store: records are read through a read-only
SQLite connection and outputs are appended to an explicit derived-evidence directory with a checkpoint of the
revisions already processed. The outputs can be rebuilt from the stored records.

When it runs is decided by the existing ``inference_session`` policy (America/New_York, existing holiday table):
no scheduled inference in the 20:00-03:30 pause, on weekends or holidays; the 03:30-04:00 window is the morning
catch-up, which takes the overnight backlog first, ranked instrument-linked and official sources first, then
newest. Work beyond the per-tick bound stays queued and is reported as backlog, never dropped.

Language sentiment describes a headline. It is not a forecast, a signal, or a decision.
"""
from __future__ import annotations

import gc
import hashlib
import json
import os
import sqlite3
import time
from contextlib import closing
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from .event_taxonomy import TAXONOMY_VERSION, classify_text
from .knowledge import StoredNewsRepository

SCHEMA = 'imp-local-intelligence/1'
WORKER_VERSION = 'news/local-intelligence/1.0.0'
DIRECTORY_ENV = 'IMP_LOCAL_INTELLIGENCE_DIR'
MAX_PER_TICK = 256
MAX_SCAN_RECORDS = 50_000
MAX_DIRECTORY_BYTES = 256 * 1024 * 1024  # derived evidence bound; the worker stops writing, never deletes
SENTIMENT_PROVIDERS = frozenset({'rss', 'finnhub', 'newsapi', 'finviz'})
OFFICIAL_SOURCE_TYPES = frozenset({'OFFICIAL_FILING', 'OFFICIAL_RELEASE'})


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace('+00:00', 'Z')


def trading_day(day: date) -> bool | None:
    """The existing holiday table's answer, or None for a year it does not cover."""
    from ..intelligence.forward_qualification.evidence01.continuity import _DEFAULT_HOLIDAYS, is_trading_day

    if not any(holiday.startswith(f'{day.year}-') for holiday in _DEFAULT_HOLIDAYS):
        return None
    return is_trading_day(day)


def session_at(instant: datetime) -> dict[str, Any]:
    from zoneinfo import ZoneInfo

    from ..intelligence.scheduling.local_plan import inference_session

    return inference_session(instant, trading_day(instant.astimezone(ZoneInfo('America/New_York')).date()))


class ReadOnlyStore:
    """The canonical store opened ``mode=ro``: the reader surface StoredNewsRepository uses, and nothing else."""

    def __init__(self, path: Path) -> None:
        if not path.is_file():
            raise ValueError('CANONICAL_STORE_MISSING')
        self.path = path

    def _run(self, method: str, sql: str, params: tuple) -> Any:
        with closing(sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute(sql, params)
            return cursor.fetchone() if method == 'one' else cursor.fetchall()

    def fetchone(self, sql: str, params: tuple = ()) -> Any:
        return self._run('one', sql, params)

    def fetchall(self, sql: str, params: tuple = ()) -> list:
        return self._run('all', sql, params)


class DerivedEvidenceLog:
    """Append-only JSONL outputs per UTC day, a run log, a status file and a processed-revision checkpoint.

    The checkpoint is replaced atomically only after the outputs it covers were flushed to disk, so a crash
    can repeat a revision (identical deterministic output, deduplicated on read) but never skip one.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path = directory / 'checkpoint.json'

    def processed(self) -> set[str]:
        if not self.checkpoint_path.is_file():
            return set()
        data = json.loads(self.checkpoint_path.read_text(encoding='utf-8'))
        if data.get('schema') != SCHEMA or not isinstance(data.get('processed_revision_ids'), list):
            raise ValueError('LOCAL_INTELLIGENCE_CHECKPOINT_INVALID')
        return set(data['processed_revision_ids'])

    def _replace(self, path: Path, payload: dict) -> None:
        temp = path.with_suffix(path.suffix + '.tmp')
        with open(temp, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)

    def bytes_used(self) -> int:
        return sum(p.stat().st_size for p in self.directory.glob('*') if p.is_file())

    def append(self, name: str, rows: list[dict]) -> None:
        if not rows:
            return
        with open(self.directory / name, 'a', encoding='utf-8') as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + '\n')
            handle.flush()
            os.fsync(handle.fileno())

    def commit(self, outputs: list[dict], processed: set[str], at: float) -> None:
        self.append(f"outputs-{_iso(at)[:10]}.jsonl", outputs)
        self._replace(self.checkpoint_path, dict(schema=SCHEMA, updated_at=_iso(at),
                                                 processed_revision_ids=sorted(processed)))

    def status(self, payload: dict) -> None:
        self._replace(self.directory / 'status.json', payload)

    def outputs(self, *, as_of: float | None = None, limit: int = 200) -> list[dict]:
        """Latest-first outputs whose processing finished by ``as_of``; a repeated revision is reported once."""
        seen, rows = set(), []
        for path in sorted(self.directory.glob('outputs-*.jsonl'), reverse=True):
            for line in reversed(path.read_text(encoding='utf-8').splitlines()):
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get('revision_id') in seen or (as_of is not None and row.get('processed_at_s', 0) > as_of):
                    continue
                seen.add(row.get('revision_id'))
                rows.append(row)
                if len(rows) >= limit:
                    return rows
        return rows


def rank(records: list[dict]) -> list[dict]:
    """Deterministic order: instrument-linked first, then official sources, then newest available."""
    def key(row: dict) -> tuple:
        linked = bool(row['article'].get('instrument_linkages'))
        official = row['provenance'].get('source_type') in OFFICIAL_SOURCE_TYPES
        return (not linked, not official, -row['available_at_ns'], row['revision_id'])
    return sorted(records, key=key)


def _instrument_ids(article: dict) -> list[str]:
    return sorted({str(link.get('instrument_id') or link.get('provider_symbol') or '').upper()
                   for link in article.get('instrument_linkages') or [] if link.get('instrument_id') or link.get('provider_symbol')})


class LocalIntelligenceWorker:
    """One bounded tick at a time; the caller decides the cadence. Never a busy loop."""

    def __init__(self, store: ReadOnlyStore, log: DerivedEvidenceLog, *, scorer_factory: Callable[[], Any],
                 clock: Callable[[], float] = time.time, max_per_tick: int = MAX_PER_TICK,
                 max_directory_bytes: int = MAX_DIRECTORY_BYTES) -> None:
        self.store, self.log, self.clock = store, log, clock
        self.scorer_factory = scorer_factory
        self.scorer = None
        self.max_per_tick = max_per_tick
        self.max_directory_bytes = max_directory_bytes
        self.ticks = 0
        self.started_at = clock()

    def release_model(self) -> None:
        """Outside eligible windows the model's memory is returned; it is reloaded lazily when work resumes."""
        if self.scorer is not None:
            self.scorer = None
            gc.collect()

    def tick(self) -> dict:
        now = self.clock()
        instant = datetime.fromtimestamp(now, UTC)
        self.ticks += 1
        session = session_at(instant)
        base = dict(schema=SCHEMA, worker_version=WORKER_VERSION, pid=os.getpid(), at=_iso(now), tick=self.ticks,
                    started_at=_iso(self.started_at), session=session, paid_inference_calls=0,
                    execution_authority='NONE', canonical_store_writes=0)
        processed = self.log.processed()
        records = StoredNewsRepository(self.store).retrieve(as_of=_iso(now), limit=1000,
                                                            max_scan_records=MAX_SCAN_RECORDS) \
            if session.get('allowed') or self.ticks == 1 else None
        # The repository's output bound is 1000 latest revisions; older unprocessed work is reported, not dropped.
        pending = [row for row in records or [] if row['revision_id'] not in processed]
        base['backlog'] = len(pending) if records is not None else None
        if not session.get('allowed'):
            self.release_model()
            status = dict(base, state='PAUSED', reason=session.get('reason') or session.get('window'), processed=0)
            self.log.status(status)
            return status
        used = self.log.bytes_used()
        if used >= self.max_directory_bytes:
            status = dict(base, state='BLOCKED', reason='DERIVED_EVIDENCE_BOUND_REACHED', bytes_used=used, processed=0)
            self.log.status(status)
            return status
        batch = rank(pending)[:self.max_per_tick]
        if not batch:
            status = dict(base, state='IDLE', reason='NO_NEW_EVIDENCE', processed=0, bytes_used=used)
            self.log.status(status)
            return status
        cpu, wall = time.process_time(), time.perf_counter()
        sentiment_rows = [row for row in batch if row['article'].get('provider_id') in SENTIMENT_PROVIDERS
                          and row['provenance'].get('source_type') not in OFFICIAL_SOURCE_TYPES]
        scores: dict[str, dict] = {}
        model_status = None
        if sentiment_rows:
            if self.scorer is None:
                self.scorer = self.scorer_factory()
            results = self.scorer.score([row['article'].get('headline') or '' for row in sentiment_rows])
            scores = {row['revision_id']: result for row, result in zip(sentiment_rows, results)}
            model_status = self.scorer.status()
        outputs, done = [], set(processed)
        for row in batch:
            article = row['article']
            categories = [category.id for category in classify_text(article.get('headline') or '',
                                                                    article.get('summary') or '')]
            sentiment = scores.get(row['revision_id'])
            outputs.append(dict(
                schema=SCHEMA, revision_id=row['revision_id'], record_id=row['record_id'], article_id=row['article_id'],
                provider_id=article.get('provider_id'), source_id=article.get('source_id'),
                source_type=row['provenance'].get('source_type'), url=article.get('url'),
                headline=(article.get('headline') or '')[:300], instrument_ids=_instrument_ids(article),
                published_time=article.get('published_time'),
                input_available_time=_iso(row['available_at_ns'] / 1e9), processed_at=_iso(self.clock()),
                processed_at_s=self.clock(), window=session.get('window'),
                event_categories=categories, taxonomy_version=TAXONOMY_VERSION,
                sentiment=sentiment if sentiment is not None else dict(state='NOT_APPLICABLE',
                                                                         reason='OFFICIAL_OR_NON_NEWS_SOURCE'),
                sentiment_model=dict(model_id=(model_status or {}).get('model_id'),
                                     model_revision=(model_status or {}).get('model_revision'),
                                     runtime='LOCAL_MODEL', basis='IMP_DERIVED_FINBERT') if sentiment is not None else None,
                worker_version=WORKER_VERSION, status='PROCESSED' if sentiment is None or sentiment.get('state') == 'SCORED'
                else 'PROCESSED_SENTIMENT_' + str(sentiment.get('state')), paid_inference=False,
                execution_authority='NONE'))
            # A revision whose model was still loading or failed is retried on a later tick, not acknowledged.
            if sentiment is None or sentiment.get('state') == 'SCORED':
                done.add(row['revision_id'])
        committed = [row for row in outputs if row['revision_id'] in done]
        self.log.commit(committed, done, now)
        run = dict(base, state='PROCESSED', reason=None, processed=len(committed), scored=sum(
            1 for row in committed if (row['sentiment'] or {}).get('state') == 'SCORED'),
            deferred=len(batch) - len(committed), backlog=len(pending) - len(committed),
            cpu_seconds=round(time.process_time() - cpu, 3), wall_seconds=round(time.perf_counter() - wall, 3),
            model=model_status, bytes_used=self.log.bytes_used())
        self.log.append('runs.jsonl', [run])
        self.log.status(run)
        return run


def read_view(directory: Path | None, *, as_of: float | None = None, symbol: str | None = None,
              limit: int = 200) -> dict:
    """Read-only projection for the operator: status plus latest outputs known at ``as_of``."""
    if directory is None:
        return dict(schema=SCHEMA, state='NOT_CONFIGURED', reason=f'{DIRECTORY_ENV}_NOT_SET', outputs=[])
    log_dir = Path(directory)
    if not log_dir.is_dir():
        return dict(schema=SCHEMA, state='NOT_STARTED', reason='NO_DERIVED_EVIDENCE', outputs=[])
    status_path = log_dir / 'status.json'
    status = json.loads(status_path.read_text(encoding='utf-8')) if status_path.is_file() else None
    log = DerivedEvidenceLog.__new__(DerivedEvidenceLog)
    log.directory = log_dir
    rows = log.outputs(as_of=as_of, limit=5000 if symbol else limit)
    if symbol:
        rows = [row for row in rows if symbol.upper() in row.get('instrument_ids', [])][:limit]
    counts: dict[str, int] = {}
    for row in rows:
        label = (row.get('sentiment') or {}).get('label') or (row.get('sentiment') or {}).get('state')
        counts[str(label)] = counts.get(str(label), 0) + 1
    heartbeat_age = None
    if status and status.get('at'):
        heartbeat_age = round(time.time() - datetime.fromisoformat(status['at'].replace('Z', '+00:00')).timestamp(), 1)
    return dict(schema=SCHEMA, state=(status or {}).get('state', 'UNKNOWN'), status=status,
                heartbeat_age_seconds=heartbeat_age, as_of=_iso(as_of) if as_of is not None else None,
                evidence_class='DERIVED_LOCAL_EVIDENCE_NOT_A_SIGNAL', outputs=rows, label_counts=counts,
                directory_identity=hashlib.sha256(str(log_dir.resolve()).encode()).hexdigest()[:12])


__all__ = ['DerivedEvidenceLog', 'LocalIntelligenceWorker', 'ReadOnlyStore', 'rank', 'read_view', 'session_at']
