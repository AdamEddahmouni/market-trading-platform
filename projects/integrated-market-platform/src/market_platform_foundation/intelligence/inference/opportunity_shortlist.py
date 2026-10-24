"""Opportunity shortlist: a deterministic score over every eligible row, then the model-sized head. Pure.

Owner decision 5 (2026-10-23): a fast numeric screen ranks the whole market and only a shortlist reaches the
model, which makes the final pick. Nothing here reads a market, a provider or a clock. The score is computed
from evidence the existing gates already admitted for the row (Moomoo snapshot quote and technicals, attached
news) plus one reference fallback (the Screener row's relative volume). It is a coverage filter, not a signal:
it decides which rows the model sees, never what is traded, and nothing it reads is added to a model packet.
"""
from __future__ import annotations

import math
import os
from typing import Any

from ...market_data.freshness_contract import timestamp
from .candidate_reduction import MAX_INTAKE
from .coverage_plan import NOT_SHORTLISTED, fair_order

POLICY_ID = 'opportunity-shortlist/1.0.0'
METHOD_NAME = 'OPPORTUNITY_SHORTLIST_THEN_AI'
METHOD_VERSION = 'ai-screener-coverage/2.0.0'

BELOW_SHORTLIST_CUTOFF = 'BELOW_SHORTLIST_CUTOFF'
BELOW_TRADABILITY_FLOOR = 'BELOW_TRADABILITY_FLOOR'

# One local request per row takes 30-60 s and the comparison must fit an 8,192-token window; a paid request
# takes exactly one 50-row batch, so it needs no finalist tournament.
LOCAL_SIZE = 20
PAID_SIZE = MAX_INTAKE
SIZE_MIN, SIZE_MAX = 1, 200
# Keeps $5,000 positions out of names that cannot absorb them. Price applies to equities and ETFs only.
FLOOR_PRICE = 1.0
FLOOR_DOLLAR_VOLUME = 1_000_000.0
_PRICE_FLOOR_UNIVERSES = frozenset({'US_EQUITIES', 'US_ETFS'})
# The same limit the snapshot quote is admitted under (L1_EVENT_V1, 60 s).
QUOTE_STALE_SECONDS = 60.0
PARTS = ('movement', 'volume', 'tradability', 'catalyst', 'freshness')
CATALYST_MAX = 20.0
# News is matched per row against every cached story, so it is read only for rows that could still reach the
# shortlist with a full catalyst part, at most this many times the shortlist size, best first.
NEWS_READ_FACTOR = 10


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def _strong(candidate: dict[str, Any], capability: str) -> list[dict[str, Any]]:
    """Admitted, non-weak current items of one capability; the provider-clocked snapshot first."""
    items = [e for e in candidate.get('current_market_evidence') or [] if e.get('capability') == capability and not e.get('weak_reasons')]
    return sorted(items, key=lambda e: e.get('source') != 'MOOMOO_OPEND_SNAPSHOT')


def _fact(items: list[dict[str, Any]], name: str) -> float | None:
    for item in items:
        value = _number((item.get('facts') or {}).get(name))
        if value is not None:
            return value
    return None


def _row_value(row: dict[str, Any] | None, name: str) -> float | None:
    field = ((row or {}).get('fields') or {}).get(name)
    return _number(field.get('value')) if isinstance(field, dict) else None


def score(candidate: dict[str, Any], row: dict[str, Any] | None = None, *, now: str) -> dict[str, Any]:
    """Five bounded parts summing to at most 100. A missing input scores 0 and is named in ``missing``."""
    quotes, technicals = _strong(candidate, 'QUOTE'), _strong(candidate, 'TECHNICALS')
    basis: dict[str, str] = {}
    missing: list[str] = []
    parts = dict.fromkeys(PARTS, 0.0)

    change = _fact(technicals, 'change_pct')
    if change is None:
        missing.append('change_pct')
    else:
        parts['movement'] = min(25.0, abs(change) * 2.5)

    relative = _fact(technicals, 'rel_volume')
    basis['rel_volume'] = 'ADMITTED_EVIDENCE'
    if relative is None:
        relative, basis['rel_volume'] = _row_value(row, 'rel_volume'), 'SCREENER_REFERENCE'
    if relative is None or relative < 0:
        missing.append('rel_volume')
        basis.pop('rel_volume')
    else:
        parts['volume'] = min(25.0, relative * 5.0)

    price = _fact(quotes, 'price')
    volume = _fact(technicals, 'volume')
    dollars = _fact(technicals, 'quote_volume')
    basis['dollar_volume'] = 'QUOTE_VOLUME'
    if dollars is None and price is not None and volume is not None:
        dollars, basis['dollar_volume'] = price * volume, 'PRICE_X_VOLUME'
    if dollars is None or dollars < 0:
        missing.append('dollar_volume')
        basis.pop('dollar_volume')
        dollars = None
    tradability = 0.0
    if dollars is not None and dollars > 0:
        tradability += max(0.0, min(15.0, (math.log10(dollars) - 5.0) * 3.75))
    spread = _fact(quotes, 'spread_pct')
    if spread is None or spread < 0:
        missing.append('spread_pct')
    else:
        tradability += 5.0 - min(5.0, spread * 10.0)
    parts['tradability'] = tradability

    news = [e for e in candidate.get('reference_evidence') or [] if e.get('capability') == 'NEWS']
    strong_news = sum(1 for e in news if not e.get('weak_reasons'))
    parts['catalyst'] = min(CATALYST_MAX, 10.0 * strong_news + 5.0 * (len(news) - strong_news))
    if not news:
        missing.append('news')

    cutoff = timestamp(now)
    observed = timestamp(next((q.get('as_of') for q in quotes if q.get('as_of')), None))
    if cutoff is None or observed is None:
        missing.append('quote_age')
    else:
        age = max(0.0, (cutoff - observed).total_seconds())
        parts['freshness'] = max(0.0, 10.0 - age * 10.0 / QUOTE_STALE_SECONDS)

    universe = (candidate.get('instrument') or {}).get('universe')
    floor = None
    if universe in _PRICE_FLOOR_UNIVERSES and price is not None and price < FLOOR_PRICE:
        floor = BELOW_TRADABILITY_FLOOR
    if dollars is not None and dollars < FLOOR_DOLLAR_VOLUME:
        floor = BELOW_TRADABILITY_FLOOR
    parts = {key: round(value, 4) for key, value in parts.items()}
    return {'total': round(sum(parts.values()), 4), 'parts': parts, 'basis': basis, 'missing': missing, 'floor_reason': floor}


def shortlist(scored: dict[str, dict[str, Any]], *, size: int, salt: str) -> list[str]:
    """The ``size`` highest totals, best first. Ties keep the fair order; rows under the floor never qualify."""
    position = {key: index for index, key in enumerate(fair_order(salt, list(scored)))}
    qualified = [key for key, value in scored.items() if not value.get('floor_reason')]
    return sorted(qualified, key=lambda key: (-scored[key]['total'], position[key]))[:max(0, int(size))]


def news_reach(scored: dict[str, dict[str, Any]], *, size: int, salt: str, unread: set[str]) -> tuple[list[str], bool]:
    """Rows in ``unread`` that a full catalyst part could lift into the shortlist, best first, and whether the
    ``NEWS_READ_FACTOR`` bound cut that list. Without the bound the cut is exact: no row left unread could enter."""
    head = shortlist(scored, size=size, salt=salt)
    cutoff = scored[head[-1]]['total'] if len(head) >= size else float('-inf')
    position = {key: index for index, key in enumerate(fair_order(salt, list(scored)))}
    reach = sorted((key for key in unread if not scored[key].get('floor_reason')
                    and scored[key]['total'] - scored[key]['parts']['catalyst'] + CATALYST_MAX >= cutoff),
                   key=lambda key: (-scored[key]['total'], position[key]))
    limit = max(1, int(size)) * NEWS_READ_FACTOR
    return reach[:limit], len(reach) > limit


def size_for(runtime: str | None, *, environ: dict[str, str] | None = None) -> int:
    """Shortlist size for the engine that will run: ``IMP_AI_SCREENER_SHORTLIST_SIZE`` overrides, 1-200."""
    raw = (os.environ if environ is None else environ).get('IMP_AI_SCREENER_SHORTLIST_SIZE')
    if raw not in (None, ''):
        try:
            value = int(raw)
        except ValueError:
            raise ValueError('SHORTLIST_SIZE_INVALID') from None
        if not SIZE_MIN <= value <= SIZE_MAX:
            raise ValueError('SHORTLIST_SIZE_INVALID')
        return value
    return LOCAL_SIZE if runtime == 'LOCAL_MODEL' else PAID_SIZE


def enabled(*, environ: dict[str, str] | None = None) -> bool:
    """On unless ``IMP_AI_SCREENER_SHORTLIST=0``: full-universe AI sweeps are no longer the default."""
    return (os.environ if environ is None else environ).get('IMP_AI_SCREENER_SHORTLIST', '1') != '0'


__all__ = ['BELOW_SHORTLIST_CUTOFF', 'BELOW_TRADABILITY_FLOOR', 'CATALYST_MAX', 'LOCAL_SIZE', 'METHOD_NAME', 'METHOD_VERSION',
           'NEWS_READ_FACTOR', 'NOT_SHORTLISTED', 'PAID_SIZE', 'PARTS', 'POLICY_ID', 'enabled', 'news_reach', 'score', 'shortlist',
           'size_for']
