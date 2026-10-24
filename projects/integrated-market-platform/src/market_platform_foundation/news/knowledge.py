"""Read stored PF-01 news as it was known, without providers or AI.

Uses schema13's existing records. Publication is a filter, never the knowledge
clock. Legacy rows are readable; corrections already discarded before this
extension cannot be reconstructed. Saved provenance is returned verbatim.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any

from ..local_state.connection import LocalStateConnection
from .contracts import NewsArticleEvent
from .dedupe import dedupe_identity_key


def article_identity(article: NewsArticleEvent) -> str:
    identity = (article.provider_id, article.source_id, *dedupe_identity_key(article))
    return hashlib.sha256(json.dumps(identity).encode()).hexdigest()


def semantic_payload(payload: dict) -> str:
    """Compare evidence content/rights, excluding per-poll observation identifiers."""
    article = {k: v for k, v in payload['article'].items()
               if k not in {'event_id', 'retrieved_time', 'raw_reference'}}
    provenance = {k: v for k, v in payload.get('provenance', {}).items()
                  if k not in {'available_time', 'ingested_time', 'retrieved_time'}}
    return json.dumps({'article': article, 'provenance': provenance}, sort_keys=True)


def append_revision(connection: LocalStateConnection, identity: str, article: NewsArticleEvent,
                    payload_json: str, ingested_time: float) -> int:
    """Called in collector's batch transaction; unchanged re-observation is a no-op.

    Preserve original identity IDs for compatibility. Predecessor-based revision
    IDs retain A -> B -> A reversions; no old row or timestamp is rewritten.
    """
    payload = json.loads(payload_json)
    prior = connection.fetchone(
        "SELECT record_id,payload_json FROM news_collection_records WHERE record_id=? "
        "OR (record_id>=? AND record_id<?) ORDER BY rowid DESC LIMIT 1",
        (identity, identity + ':', identity + ';'))
    if prior is not None and semantic_payload(json.loads(prior['payload_json'])) == semantic_payload(payload):
        return 0
    predecessor = prior['record_id'] if prior is not None else None
    record_id = (identity + ':' + hashlib.sha256(
                 json.dumps([identity, predecessor, semantic_payload(payload)]).encode()).hexdigest()
                 if predecessor else identity)
    payload['knowledge'] = {'article_id': identity, 'supersedes_record_id': predecessor}
    cursor = connection.execute("INSERT OR IGNORE INTO news_collection_records VALUES (?,?,?,?,?,?,?)",
        (record_id, article.provider_id, article.source_id, article.published_time, article.retrieved_time,
         ingested_time, json.dumps(payload, sort_keys=True)))
    return cursor.rowcount


def _timestamp(value: Any) -> int | None:
    """Strict timezone-aware ISO time; unknown and malformed evidence stays withheld."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return None
        return int(parsed.timestamp() * 1_000_000_000)
    except (ValueError, OverflowError, OSError):
        return None


def _iso(value_ns: int) -> str:
    return datetime.fromtimestamp(value_ns / 1_000_000_000, timezone.utc).isoformat().replace('+00:00', 'Z')


def _stored_identity(article: dict) -> str:
    # Only these fields participate in the established dedupe identity helper.
    from .contracts import PublicationTimeQuality
    event = NewsArticleEvent(event_id=article['event_id'], provider_id=article['provider_id'],
        provider_native_id=article.get('provider_native_id', ''), source_id=article['source_id'],
        published_time=article.get('published_time', ''), published_time_quality=PublicationTimeQuality.UNKNOWN,
        retrieved_time=article.get('retrieved_time', ''), headline=article.get('headline', ''), url=article.get('url', ''))
    return article_identity(event)


class StoredNewsRepository:
    """Read-only repository over an explicitly supplied existing connection.

    Latest revision is chosen at the cutoff BEFORE symbol/publication filters;
    an older superseded linkage must not resurrect an article. Results include
    immutable evidence IDs and conservative token estimates for context planning.
    ``limit`` bounds output; ``max_scan_records`` bounds history materialization.
    Exceeding the configurable scan bound refuses the read without partial latest
    evidence. It neither trims nor deletes history.
    No storage factory, serving process, collector or inference is started here.
    """
    def __init__(self, connection: LocalStateConnection) -> None:
        self.connection = connection

    def retrieve(self, *, as_of: str, symbol: str | None = None, source_id: str | None = None,
                 provider_id: str | None = None, published_after: str | None = None,
                 published_before: str | None = None, include_revisions: bool = False,
                 limit: int = 100, max_scan_records: int = 10000) -> list[dict[str, Any]]:
        cutoff = _timestamp(as_of)
        after = _timestamp(published_after) if published_after is not None else None
        before = _timestamp(published_before) if published_before is not None else None
        if cutoff is None or (published_after is not None and after is None) or (published_before is not None and before is None):
            raise ValueError('NEWS_KNOWLEDGE_TIME_INVALID')
        if after is not None and before is not None and after > before:
            raise ValueError('NEWS_KNOWLEDGE_RANGE_INVALID')
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('NEWS_KNOWLEDGE_LIMIT_INVALID')
        if type(max_scan_records) is not int or max_scan_records <= 0:
            raise ValueError('NEWS_KNOWLEDGE_SCAN_LIMIT_INVALID')
        clauses, params = ['ingested_time<=?'], [cutoff / 1_000_000_000]
        for column, value in (('provider_id', provider_id), ('source_id', source_id)):
            if value is not None:
                clauses.append(f'{column}=?')
                params.append(value)
        where = ' AND '.join(clauses)
        count = self.connection.fetchone('SELECT count(*) FROM news_collection_records WHERE ' + where, tuple(params))[0]
        if count > max_scan_records:
            raise ValueError('NEWS_KNOWLEDGE_SCAN_BOUND')
        # Cap even if another collector inserts between the count and this read.
        rows = self.connection.fetchall('SELECT rowid,* FROM news_collection_records WHERE ' +
                                       where + ' ORDER BY rowid LIMIT ?', tuple(params) + (max_scan_records + 1,))
        if len(rows) > max_scan_records:
            raise ValueError('NEWS_KNOWLEDGE_SCAN_BOUND')
        visible = []
        first_observed = {}
        for row in rows:
            try:
                payload = json.loads(row['payload_json'])
                article, provenance = payload['article'], payload.get('provenance', {})
                observed = _timestamp(row['retrieved_time'])
                # Both row and saved article observation clocks must be known.
                saved_observed = _timestamp(article.get('retrieved_time'))
                ingested = float(row['ingested_time'])
                if observed is None or saved_observed is None or not math.isfinite(ingested):
                    continue
                times = [observed, saved_observed, int(ingested * 1_000_000_000)]
                for name in ('available_time', 'ingested_time'):
                    if provenance.get(name) is not None:
                        stamp = _timestamp(provenance[name])
                        if stamp is None:
                            break
                        times.append(stamp)
                else:
                    available = max(times)
                    if available > cutoff:
                        continue
                    identity = _stored_identity(article)
                    observation = max(observed, saved_observed)
                    first_observed[identity] = min(first_observed.get(identity, observation), observation)
                    visible.append((available, row['rowid'], identity, row, payload))
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                continue  # malformed evidence is not invented or repaired during a read
        if not include_revisions:
            latest = {item[2]: item for item in visible}
            visible = list(latest.values())
        visible.sort(key=lambda r: (r[0], r[1]))
        results = []
        for available, _, identity, row, payload in reversed(visible):
            article = payload['article']
            if symbol is not None and not any(symbol.upper() in
                {str(link.get('provider_symbol', '')).upper(), str(link.get('instrument_id', '')).upper()}
                for link in article.get('instrument_linkages', [])):
                continue
            publication = _timestamp(row['published_time'])
            if (after is not None or before is not None) and publication is None:
                continue
            if after is not None and publication < after or before is not None and publication > before:
                continue
            results.append({'record_id': row['record_id'], 'revision_id': row['record_id'],
                'article_id': identity, 'article': article, 'provenance': payload.get('provenance', {}),
                'supersedes_record_id': payload.get('knowledge', {}).get('supersedes_record_id'),
                'first_observed_time': _iso(first_observed[identity]), 'available_at_ns': available,
                'ingested_time': row['ingested_time'], 'execution_authority': 'NONE',
                'token_estimate_scope': 'STORED_CONTENT_BYTES_ONLY',
                'estimated_tokens': len(json.dumps(payload).encode('utf-8'))})
            if len(results) >= limit:
                break
        return results


__all__ = ['StoredNewsRepository']
