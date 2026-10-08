"""Complete enumeration of the active Screener query for one AI Screener run.

The Screener serves windows of at most ``MAX_PAGE_LIMIT`` rows. This reads every window of one pinned
result set, in order, and refuses to return anything it cannot prove complete: a result set that moved, a
repeated instrument, a short page or a total that does not add up each end the run. Sort decides the order
rows are read in; it never decides which rows are read.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .screener_query import MAX_PAGE_LIMIT

# A defensive ceiling on pages, far above any served universe (US ETFs: 6,306 rows = 13 pages).
MAX_PAGES = 400


class UniverseEnumerationError(ValueError):
    """Enumeration could not be proven complete. ``code`` is stable; no partial universe is returned."""

    def __init__(self, code: str, **detail: Any) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class EnumeratedUniverse:
    rows: list[dict[str, Any]]
    result_count: int
    result_set: str | None
    query_id: str | None
    universe_as_of: Any
    screener_as_of: Any
    pages: int
    # The first page without its rows: what the freshness projection needs beside the rows themselves.
    envelope: dict[str, Any]


def enumerate_universe(reader: Any, query: dict[str, Any], *, page_limit: int = MAX_PAGE_LIMIT) -> EnumeratedUniverse:
    """Every row of ``query``, once, from one result set."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    pinned = query.get('result_set')
    total: int | None = None
    envelope: dict[str, Any] = {}
    pages = 0
    while True:
        if pages >= MAX_PAGES:
            raise UniverseEnumerationError('PAGE_BOUND_EXCEEDED', pages=pages)
        try:
            page = reader.read(universe=query['universe'], search=query['search'], sort=query['sort'],
                               descending=query['descending'], offset=len(rows), limit=page_limit,
                               filters=query['filters'], result_set=pinned)
        except ValueError as exc:
            if str(exc) == 'RESULT_SET_CHANGED':
                raise UniverseEnumerationError('RESULT_SET_CHANGED', offset=len(rows)) from exc
            raise
        pages += 1
        count = int(page.get('result_count') or 0)
        if pages == 1:
            total, envelope = count, {key: value for key, value in page.items() if key != 'rows'}
            # Later pages must come from the result set the first page was read from.
            pinned = page.get('result_set_id') or pinned
        elif count != total:
            raise UniverseEnumerationError('RESULT_COUNT_CHANGED', expected=total, found=count)
        elif page.get('result_set_id') != envelope.get('result_set_id'):
            raise UniverseEnumerationError('RESULT_SET_CHANGED', offset=len(rows))
        batch = list(page.get('rows') or [])
        if len(batch) > page_limit:
            raise UniverseEnumerationError('PAGE_OVERSIZED', offset=len(rows), returned=len(batch))
        for row in batch:
            identifier = (row.get('instrument') or {}).get('instrument_id')
            if not isinstance(identifier, str) or not identifier:
                raise UniverseEnumerationError('ROW_IDENTITY_MISSING', offset=len(rows))
            if identifier in seen:
                raise UniverseEnumerationError('DUPLICATE_INSTRUMENT', instrument_id=identifier)
            seen.add(identifier)
            rows.append(row)
        if len(rows) >= total:
            break
        if not batch:
            raise UniverseEnumerationError('SHORT_PAGE', expected=total, enumerated=len(rows))
    if len(rows) != total:
        raise UniverseEnumerationError('RESULT_COUNT_MISMATCH', expected=total, enumerated=len(rows))
    return EnumeratedUniverse(rows=rows, result_count=total, result_set=envelope.get('result_set_id'),
                              query_id=envelope.get('query_id'), universe_as_of=envelope.get('universe_as_of'),
                              screener_as_of=envelope.get('screener_as_of'), pages=pages, envelope=envelope)


__all__ = ['EnumeratedUniverse', 'MAX_PAGES', 'UniverseEnumerationError', 'enumerate_universe']
