"""Full-universe AI Screener coverage: classification, fair order, batch and round planning. Pure.

Nothing here reads a market, a provider or a clock. It turns facts the existing gates already produced
into an accounting of every Screener row, an order no page or sort can bias, and a plan of bounded model
calls. It introduces no trading threshold: a row is eligible exactly when ``build_candidate`` already
called it sufficient.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

from .candidate_reduction import MAX_INTAKE, MAX_SELECTED

METHOD_VERSION = 'ai-screener-coverage/1.0.0'
METHOD_NAME = 'FULL_UNIVERSE_TOURNAMENT_REDUCTION'
# The method every candidate run before this one used: one request over the head of the sorted result.
INTAKE_METHOD_VERSION = 'ai-screener-intake-head/1.0.0'

ELIGIBLE = 'ELIGIBLE'
INELIGIBLE = 'INELIGIBLE'
UNSUPPORTED = 'UNSUPPORTED'
EVIDENCE_STALE = 'EVIDENCE_STALE'
EVIDENCE_UNAVAILABLE = 'EVIDENCE_UNAVAILABLE'
PROVIDER_UNAVAILABLE = 'PROVIDER_UNAVAILABLE'
AWAITING_EVIDENCE = 'AWAITING_EVIDENCE'
AI_EVALUATED = 'AI_EVALUATED'
UNPROCESSED = 'UNPROCESSED'
# Where each class lands in the reconciliation. A row is in exactly one bucket.
BUCKETS = {AI_EVALUATED: 'evaluated', INELIGIBLE: 'ineligible', UNSUPPORTED: 'ineligible',
           EVIDENCE_STALE: 'evidence_blocked', EVIDENCE_UNAVAILABLE: 'evidence_blocked',
           PROVIDER_UNAVAILABLE: 'evidence_blocked', AWAITING_EVIDENCE: 'evidence_blocked',
           ELIGIBLE: 'unprocessed', UNPROCESSED: 'unprocessed'}

# Existing freshness-contract reason codes, grouped. No code is defined here.
_UNSUPPORTED = {'NOT_ENTITLED', 'NOT_CONFIGURED', 'MOOMOO_QUOTE_NOT_ENTITLED'}
_PROVIDER = {'PROVIDER_UNAVAILABLE', 'DISCONNECTED', 'UNAVAILABLE'}
_AWAITING = {'AWAITING_DATA', 'PENDING', 'CONNECTING'}
_STALE = {'STALE', 'AGE_EXCEEDS_POLICY', 'SESSION_CLOSED', 'NON_CURRENT_DELIVERY'}


def classify(candidate: dict[str, Any], *, provider_reason: str | None = None,
             refused: bool = False) -> tuple[str, list[str]]:
    """One row's class and its reason codes, from what ``build_candidate`` already decided.

    ``provider_reason`` is why the bulk quote source returned nothing at all; ``refused`` is the vendor naming
    this code as one it will not serve. Missing or stale evidence is never an economic rejection."""
    if candidate.get('sufficient'):
        return ELIGIBLE, []
    quotes = [e for e in candidate['current_market_evidence'] if e['capability'] == 'QUOTE' and e['facts'].get('price') is not None]
    if any(not e['weak_reasons'] for e in quotes):
        # The existing sufficiency rule: a current price alone, with no second non-weak item, is not enough.
        return INELIGIBLE, ['NO_SECOND_STRONG_EVIDENCE']
    if quotes:
        return INELIGIBLE, sorted({reason for e in quotes for reason in e['weak_reasons']}) or ['QUOTE_NOT_STRONG']
    if refused:
        return UNSUPPORTED, ['MOOMOO_QUOTE_NOT_ENTITLED']
    codes = sorted({code for item in candidate['blocked'] if item.get('capability') == 'QUOTE' for code in item.get('reason_codes') or []})
    found = set(codes)
    if found & _UNSUPPORTED:
        return UNSUPPORTED, codes
    if provider_reason:
        return PROVIDER_UNAVAILABLE, [provider_reason]
    if found & _PROVIDER:
        return PROVIDER_UNAVAILABLE, codes
    if found & _AWAITING:
        return AWAITING_EVIDENCE, codes
    if found & _STALE:
        return EVIDENCE_STALE, codes
    return EVIDENCE_UNAVAILABLE, codes or ['NO_QUOTE_OBSERVATION']


def fair_order(salt: str, instrument_ids: list[str]) -> list[str]:
    """An order fixed by identity alone: independent of sort, page, position, symbol length and payload size."""
    return sorted(instrument_ids, key=lambda value: (hashlib.sha256(f'{salt}|{value}'.encode('utf-8')).hexdigest(), value))


def chunks(values: list[Any], size: int = MAX_INTAKE) -> list[list[Any]]:
    size = max(1, int(size))
    return [values[index:index + size] for index in range(0, len(values), size)]


def reduction_rounds(batches: int, *, fan_in: int = MAX_INTAKE, per_batch: int = MAX_SELECTED) -> list[int]:
    """Model calls per global-reduction round, for the worst case that every batch returns its full quota.

    One batch needs none: its answer is already a comparison of every eligible row. Otherwise finalists are
    compared in groups of ``fan_in`` until a single group remains; the last entry is always 1."""
    if batches <= 1:
        return []
    rounds, pool = [], batches * per_batch
    while True:
        calls = math.ceil(pool / fan_in)
        rounds.append(calls)
        if calls <= 1:
            return rounds
        pool = calls * per_batch


def budget_requirement(batch_tokens: list[int], rounds: list[int]) -> dict[str, int]:
    """Requests and tokens the whole run must be able to pay for before its first call.

    A reduction call is reserved at the largest planned batch: its packet has the same bounds."""
    largest = max(batch_tokens, default=0)
    reduction_calls = sum(rounds)
    return {'requests': len(batch_tokens) + reduction_calls, 'tokens': sum(batch_tokens) + reduction_calls * largest,
            'batch_tokens': sum(batch_tokens), 'reduction_tokens': reduction_calls * largest, 'reduction_calls': reduction_calls}


def tally(classes: dict[str, tuple[str, list[str]]]) -> dict[str, Any]:
    """Counts by bucket and by class, and reason counts for everything not evaluated."""
    buckets = {'evaluated': 0, 'ineligible': 0, 'evidence_blocked': 0, 'unprocessed': 0}
    by_class: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for name, codes in classes.values():
        buckets[BUCKETS[name]] += 1
        by_class[name] = by_class.get(name, 0) + 1
        if name != AI_EVALUATED:
            for code in codes or [name]:
                reasons[f'{name}:{code}'] = reasons.get(f'{name}:{code}', 0) + 1
    return {**buckets, 'by_class': dict(sorted(by_class.items())), 'reasons': dict(sorted(reasons.items()))}


def reconciles(counts: dict[str, Any], universe: int) -> bool:
    return counts['evaluated'] + counts['ineligible'] + counts['evidence_blocked'] + counts['unprocessed'] == universe


__all__ = ['AI_EVALUATED', 'AWAITING_EVIDENCE', 'BUCKETS', 'ELIGIBLE', 'EVIDENCE_STALE', 'EVIDENCE_UNAVAILABLE',
           'INELIGIBLE', 'INTAKE_METHOD_VERSION', 'METHOD_NAME', 'METHOD_VERSION', 'PROVIDER_UNAVAILABLE', 'UNPROCESSED',
           'UNSUPPORTED', 'budget_requirement', 'chunks', 'classify', 'fair_order', 'reconciles', 'reduction_rounds', 'tally']
