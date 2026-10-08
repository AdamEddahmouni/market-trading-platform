"""Bounded internal evidence synthesis. No retrieval, strategy or execution authority."""
from __future__ import annotations

import json
import math
import re
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from ...market_data.freshness_contract import eligible_evidence, evaluate, timestamp
from .anthropic_synthesis import estimate_tokens
from .config import IntelligenceInferenceConfig
from .contracts import IntelligenceTaskType
from .hashing import input_hash_from_dict
from .prompts import PromptRegistry
from .run_progress import report_stage
from .screener_synthesis import unsupported_certainty

PROMPT_ID = 'screener.ai_candidate_reduction.v3'
SCHEMA_VERSION = 'ai-screener-output/1.0.0'
# The provider wire (packet indices in, compact picks out). The stored result stays SCHEMA_VERSION.
WIRE_SCHEMA_VERSION = 'ai-screener-wire/3.0.0'
MAX_INTAKE = 50
MAX_SELECTED = 5
MAX_PACKET_BYTES = 320000
CAPABILITIES = ('QUOTE', 'TECHNICALS', 'ORDER_FLOW', 'CVD', 'LEVEL2', 'OPTIONS', 'FUTURES', 'CROSS_ASSET', 'SQUEEZE', 'FUNDAMENTALS', 'NEWS', 'SENTIMENT', 'RATES')
_PROHIBITED = re.compile(r'\b(?:buy|sell|enter|exit|hold|close|reduce|target|stop|guaranteed|certain|obvious winner)\b|price target|expected returns?|profit|will (?:rise|fall|rally|crash)|can.t lose', re.I)


def packet_candidates(candidates: list[dict]) -> list[dict]:
    """The inference projection: no duplicated aliases, plus the packet-local wire indices.

    ``candidate_key`` is the candidate's position; ``reference_index`` is an evidence item's position in
    that candidate's own list (current market first, then reference). The canonical candidates are not mutated.
    """
    result = []
    for index, c in enumerate(candidates):
        item = {k: v for k, v in c.items() if k not in ('blocked_evidence', 'missing_evidence', 'weak_evidence')}
        item['candidate_key'] = index
        offset = len(c['current_market_evidence'])
        item['current_market_evidence'] = [{**e, 'reference_index': i} for i, e in enumerate(c['current_market_evidence'])]
        item['reference_evidence'] = [{**e, 'reference_index': offset + i} for i, e in enumerate(c['reference_evidence'])]
        result.append(item)
    return result


def bounded_facts(value: Any, *, depth: int = 0) -> Any:
    """Bound whitelisted facts; reject non-finite numbers; never serialize objects."""
    if depth > 5:
        return None
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return value[:320]
    if isinstance(value, list):
        return [bounded_facts(x, depth=depth + 1) for x in value[:6]]
    if isinstance(value, dict):
        return {str(k)[:64]: bounded_facts(v, depth=depth + 1) for k, v in list(value.items())[:24]}
    return None


def build_candidate(instrument: dict, observations: list[tuple], *, now: str) -> dict:
    """Gate each value at the synthesis cutoff, separating current and reference.

    Observations are server-whitelisted (family, OCT1-03 status, facts, quality reasons).
    Blocked facts are discarded before any packet or identity hash is constructed.
    """
    identity = {key: str(instrument[key])[:120] for key in ('instrument_id', 'symbol', 'universe', 'asset_class', 'venue_id', 'company') if key in instrument and instrument[key] is not None}
    result = dict(instrument=identity, current_market_evidence=[], reference_evidence=[], blocked=[], missing=[], weak=[])
    seen = set()
    for family, status, facts, quality in observations[:40]:
        seen.add(family)
        reference = status.get('decision_role') == 'REFERENCE_CONTEXT'
        admitted = eligible_evidence([status], now=now, reference=reference)
        checked = evaluate(capability=status['capability'], source=status.get('source'), delivery_mode=status['delivery_mode'],
                           now=now, as_of=status.get('as_of'), stale_after_ms=status.get('stale_after_ms'),
                           policy=status['policy'], basis=status['basis'], state=status.get('source_state'), reference=reference)
        if not admitted or not facts:
            result['blocked'].append(dict(capability=family, role=checked['decision_role'], source=checked['source'],
                as_of=checked['as_of'], reason_codes=checked['reason_codes'] or ['NO_USABLE_FACTS'],
                freshness_status=checked['freshness_status'], decision_admissibility='BLOCKED'))
            continue
        weakness = list(quality)
        if checked['decision_admissibility'] == 'DEGRADED':
            weakness.append('DEGRADED_REFERENCE')
        item = dict(capability=family, instrument_id=identity['instrument_id'], role=checked['decision_role'],
                    source=checked['source'], as_of=checked['as_of'], received_at=status.get('received_at'), delivery_mode=checked['delivery_mode'],
                    freshness_status=checked['freshness_status'], decision_admissibility=checked['decision_admissibility'],
                    valid_until=checked['valid_until'], policy=checked['policy'], basis=checked['basis'],
                    weak_reasons=list(dict.fromkeys(weakness)), facts=bounded_facts(facts))
        item['evidence_id'] = 'EV:' + input_hash_from_dict(item)[:32]
        result['reference_evidence' if reference else 'current_market_evidence'].append(item)
        if weakness:
            result['weak'].append(dict(evidence_id=item['evidence_id'], capability=family, reason_codes=item['weak_reasons']))
    result['missing'] = [dict(capability=c, reason='NO_INTERNAL_EVIDENCE') for c in CAPABILITIES if c not in seen]
    strong = [e for e in result['current_market_evidence'] if not e['weak_reasons']]
    result['sufficient'] = bool(identity.get('instrument_id') and any(e['capability'] == 'QUOTE' and e['facts'].get('price') is not None for e in strong)
                               and any(e['capability'] != 'QUOTE' and not e['weak_reasons'] for e in (*result['current_market_evidence'], *result['reference_evidence'])))
    # Explicit aliases keep the packet self-describing for the UI while the
    # shorter keys remain compatible with the recovered test-first work.
    result['blocked_evidence'] = result['blocked']
    result['missing_evidence'] = result['missing']
    result['weak_evidence'] = result['weak']
    return result


def candidate_metadata(candidate: dict) -> dict:
    """Fixed metadata bound by the candidate's packet-local index."""
    evidence = (*candidate['current_market_evidence'], *candidate['reference_evidence'])
    return dict(instrument_id=candidate['instrument']['instrument_id'],
        weak_refs=sorted(e['evidence_id'] for e in evidence if e['weak_reasons']),
        missing_capabilities=sorted({x['capability'] for x in candidate['missing']}))


def reference_ids(candidate: dict) -> list[str]:
    """One candidate's evidence ids in wire order; ``reference_index`` is a position in this list."""
    return [e['evidence_id'] for e in (*candidate['current_market_evidence'], *candidate['reference_evidence'])]


WIRE_KEYS = frozenset({'candidate_key', 'rank', 'rationale', 'supporting_refs', 'conflicting_refs', 'uncertainties'})


def decode_wire_pick(pick: dict, candidates: list[dict]) -> tuple[dict | None, str | None]:
    """Exact decode of one compact pick to the canonical shape. It maps valid indices and nothing else:
    an index that is not this candidate's own is a failure, never clamped, dropped or looked up elsewhere."""
    key = pick['candidate_key']
    if type(key) is not int or not 0 <= key < len(candidates):
        return None, 'WIRE_CANDIDATE_KEY_INVALID'
    own = reference_ids(candidates[key])
    decoded = {**candidate_metadata(candidates[key]), **{k: v for k, v in pick.items() if k != 'candidate_key'}}
    for name in ('supporting_refs', 'conflicting_refs'):
        indices = pick[name]
        if not isinstance(indices, list) or any(type(i) is not int or not 0 <= i < len(own) for i in indices):
            return None, 'WIRE_REFERENCE_INDEX_INVALID'
        decoded[name] = [own[i] for i in indices]
    return decoded, None


def rejection_stage(reason: str | None) -> str | None:
    """Which gate rejected the output: the wire decode, or the canonical validator that follows it."""
    if reason is None:
        return None
    return 'DECODE' if reason == 'MALFORMED_JSON' or reason.startswith('WIRE_') else 'CANONICAL_VALIDATION'


def output_schema(candidates: list[dict]) -> dict:
    # Flat and instrument-independent: per-instrument branches and long reference enums exceed the vendor
    # grammar compiler. Evidence positions are candidate-local, so the enum is the largest single list.
    refs = list(range(max((len(reference_ids(c)) for c in candidates), default=0))) or [0]
    ref_list = dict(type='array', items={'type': 'integer', 'enum': refs}, description='reference_index values of the selected candidate only; at most 12 distinct.')
    properties = dict(candidate_key={'type': 'integer', 'enum': list(range(len(candidates))) or [0],
            'description': 'The candidate_key of the selected candidate. It binds the instrument and its fixed weak and missing lists.'},
        rank={'type': 'integer', 'enum': list(range(1, MAX_SELECTED+1))}, rationale={'type': 'string'},
        supporting_refs={**ref_list, 'minItems': 1, 'description': 'reference_index values of the selected candidate: at least two strong references including a current quote; at most 12 distinct.'},
        conflicting_refs=ref_list, uncertainties={'type': 'array', 'items': {'type': 'string'}, 'description': 'At most 12 distinct strings.'})
    items = dict(type='object', additionalProperties=False, required=list(properties), properties=properties)
    return dict(type='object', additionalProperties=False, required=['schema_version', 'candidates', 'limitations'],
                properties=dict(schema_version={'type': 'string', 'enum': [SCHEMA_VERSION]},
                    candidates=dict(type='array', items=items, description=f'Zero to {MAX_SELECTED} distinct candidates, in rank order.'),
                    limitations=dict(type='array', items={'type': 'string'}, description='At most 12 limitations; required when no candidates are selected.')))


def rejection_details(raw: str, candidates: list[dict], reason: str | None) -> dict:
    """Retain only canonical identities/capabilities, never raw model text or provider error bodies."""
    if reason != 'MISSING_EVIDENCE_MISMATCH':
        return {}
    # Reached only by the legacy full-identifier shape: the compact wire never carries a missing list.
    parsed = json.loads(raw)  # this reason is reached only after JSON and candidate identity validation
    by_id = {c['instrument']['instrument_id']: c for c in candidates}
    for pick in parsed['candidates']:
        c = by_id.get(pick.get('instrument_id'))
        if c is None:
            continue
        expected = {x['capability'] for x in c['missing']}
        declared = pick['missing_capabilities']
        if isinstance(declared, str):
            declared = json.loads(declared)
        if set(declared) != expected:
            return {'instrument_id': c['instrument']['instrument_id'], 'expected_missing': sorted(expected),
                    'declared_missing': sorted(x for x in declared if x in CAPABILITIES),
                    'unknown_capability_count': sum(x not in CAPABILITIES for x in declared)}
    return {}


def parse_reduction(raw: str, candidates: list[dict]) -> tuple[dict | None, str | None]:
    try:
        result = json.loads(raw)
    except (ValueError, TypeError):
        return None, 'MALFORMED_JSON'
    if not isinstance(result, dict) or set(result) != {'schema_version', 'candidates', 'limitations'} or result['schema_version'] != SCHEMA_VERSION:
        return None, 'SCHEMA_INVALID'
    selected = result['candidates']
    if not isinstance(selected, list) or len(selected) > MAX_SELECTED:
        return None, 'CANDIDATE_BOUND_EXCEEDED'
    def strings(value):
        return isinstance(value, list) and len(value) <= 12 and all(isinstance(x, str) and len(x) <= 1200 for x in value)
    if not strings(result['limitations']) or not selected and not result['limitations']:
        return None, 'INVALID_LIMITATIONS'
    texts = list(result['limitations'])
    by_id = {c['instrument']['instrument_id']: c for c in candidates}
    used = set()
    for rank, pick in enumerate(selected, 1):
        if isinstance(pick, dict) and set(pick) == WIRE_KEYS:
            # Decode the compact wire first; every canonical gate below then runs on the decoded pick.
            pick, reason = decode_wire_pick(pick, candidates)
            if reason:
                return None, reason
            selected[rank-1] = pick
        if not isinstance(pick, dict) or set(pick) != {'instrument_id', 'rank', 'rationale', 'supporting_refs', 'conflicting_refs', 'weak_refs', 'missing_capabilities', 'uncertainties'}:
            return None, 'SCHEMA_INVALID'
        for name in ('weak_refs', 'missing_capabilities'):
            if isinstance(pick[name], str):
                try:
                    pick[name] = json.loads(pick[name])
                except ValueError:
                    return None, 'SCHEMA_INVALID'
        identifier = pick['instrument_id']
        if not isinstance(identifier, str) or identifier not in by_id or identifier in used:
            return None, 'UNKNOWN_OR_DUPLICATE_CANDIDATE'
        c = by_id[identifier]
        if not c['sufficient']:
            return None, 'INSUFFICIENT_EVIDENCE'
        if type(pick['rank']) is not int or pick['rank'] != rank:
            return None, 'INVALID_RANK'
        used.add(identifier)
        if not isinstance(pick['rationale'], str) or not pick['rationale'].strip() or len(pick['rationale']) > 1200:
            return None, 'INVALID_RATIONALE'
        refs = {e['evidence_id']: e for e in (*c['current_market_evidence'], *c['reference_evidence'])}
        for name in ('supporting_refs', 'conflicting_refs', 'weak_refs', 'missing_capabilities', 'uncertainties'):
            if not strings(pick[name]) or len(pick[name]) != len(set(pick[name])):
                return None, 'INVALID_' + name.upper()
        for name in ('supporting_refs', 'conflicting_refs', 'weak_refs'):
            if any(ref not in refs for ref in pick[name]):
                return None, 'UNKNOWN_OR_UNRELATED_REF'
        if set(pick['supporting_refs']) & set(pick['conflicting_refs']):
            return None, 'CONFLICTING_SUPPORT'
        if len(pick['supporting_refs']) < 2 or any(refs[r]['weak_reasons'] for r in pick['supporting_refs']):
            return None, 'WEAK_OR_INSUFFICIENT_SUPPORT'
        if not any(refs[r]['capability'] == 'QUOTE' and refs[r]['role'] == 'CURRENT_MARKET' for r in pick['supporting_refs']) or not any(refs[r]['capability'] != 'QUOTE' for r in pick['supporting_refs']):
            return None, 'NO_CURRENT_MARKET_BASIS'
        actual_weak = {r for r, e in refs.items() if e['weak_reasons']}
        if set(pick['weak_refs']) != actual_weak:
            return None, 'WEAK_EVIDENCE_NOT_IDENTIFIED'
        missing = {x['capability'] for x in c['missing']}
        if set(pick['missing_capabilities']) != missing:
            return None, 'MISSING_EVIDENCE_MISMATCH'
        for family, pattern in [('NEWS', r'\b(?:news|headline|story|stories)\b'), ('SENTIMENT', r'\b(?:sentiment|FinBERT)\b')]:
            if re.search(pattern, pick['rationale'], re.I) and not any(refs[r]['capability'] == family for r in (*pick['supporting_refs'], *pick['conflicting_refs'], *pick['weak_refs'])):
                return None, 'UNGROUNDED_NEWS_CLAIM'
        required_conflicts = {ref for item in c.get('alignments', []) if item['result'] == 'CONFLICTING' for ref in item['sentiment_refs']}
        if not required_conflicts <= set(pick['conflicting_refs']):
            return None, 'NEWS_CONFLICT_NOT_DISCLOSED'
        texts.extend([pick['rationale'], *pick['uncertainties']])
    if any(unsupported_certainty(t) or _PROHIBITED.search(t) for t in texts):
        return None, 'UNSUPPORTED_CERTAINTY_OR_ACTION'
    return result, None


@dataclass(frozen=True)
class ScreenerEvidencePacket:
    """Sibling of IntelligenceInputPacket; never encodes market facts as articles."""
    task_type: IntelligenceTaskType
    input_id: str
    input_hash: str
    as_of: str
    scope: dict
    candidates: list[dict]
    output_schema: dict


class CandidateReducer:
    def __init__(self, *, provider=None, clock=time.time, not_configured_reason='NO_SYNTHESIS_PROVIDER_CONFIGURED'):
        self.provider = provider
        self.clock = clock
        self.reason = not_configured_reason
        self.config = IntelligenceInferenceConfig(max_tokens=2600, timeout_seconds=300 if getattr(provider, 'runtime', '') == 'LOCAL_MODEL' else 45,
                                                   prompt_id=PROMPT_ID, default_task_type=IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION)
        self.registry = PromptRegistry()
        self.lock = threading.Lock()
        self.cache = OrderedDict()
        self.inflight = {}

    def _prepare(self, scope, candidates, now):
        if len(candidates) > MAX_INTAKE:
            raise ValueError('INTAKE_BOUND_EXCEEDED')
        prompt = self.registry.get_by_id(PROMPT_ID)
        # Evaluation clocks are recorded in the receipt, not volatile cache identity.
        def stable(value):
            if isinstance(value, dict):
                return {k:stable(v) for k,v in value.items() if k not in ('cutoff','snapshot_at','evaluated_at','age_ms')}
            if isinstance(value, list):
                return [stable(v) for v in value]
            return value
        material = dict(scope=scope, candidates=stable(candidates), prompt_hash=prompt.content_hash,
                        wire_schema_version=WIRE_SCHEMA_VERSION,
                        output_schema_hash=input_hash_from_dict(output_schema(candidates)),
                        provider_id=getattr(self.provider, 'provider_id', None), model_id=getattr(self.provider, 'model_id', None))
        digest = input_hash_from_dict(material)
        # cutoff is recorded but not used as a volatile cache key: admitted facts and deadlines are hashed.
        encoded = json.dumps(dict(scope=scope, decision_cutoff=now, candidates=packet_candidates(candidates)), ensure_ascii=False, sort_keys=True)
        if len(encoded.encode('utf-8')) > MAX_PACKET_BYTES:
            raise ValueError('EVIDENCE_PACKET_BOUND_EXCEEDED')
        rendered = prompt.template.replace('{{evidence_json}}', encoded).replace('{{output_schema}}', json.dumps(output_schema(candidates)))
        return digest, rendered, prompt, len(encoded.encode('utf-8'))

    def contract(self):
        """Whether the selected engine's model can carry this task's request contract; None where it states none."""
        check = getattr(self.provider, 'request_contract', None)
        return check(IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION) if callable(check) else None

    def estimate(self, scope, candidates, now):
        digest, rendered, _, size = self._prepare(scope, candidates, now)
        with self.lock:
            entry = self.cache.get(digest)
            cached = entry is not None and entry[0] > self.clock()
        worst = getattr(self.provider, 'worst_case_tokens', None)
        return dict(intake_count=len(candidates), sufficient_count=sum(c['sufficient'] for c in candidates),
                    packet_bytes=size, input_tokens=estimate_tokens(rendered, getattr(self.provider, 'model_id', None)),
                    tokens=worst(rendered, self.config) if callable(worst) else None, cached=cached, input_hash=digest)

    def preflight(self, scope, candidates, now):
        """The engine's own free count of this exact request, or None where it offers none. Spends nothing."""
        check = getattr(self.provider, 'preflight', None)
        if not callable(check):
            return None
        digest, rendered, _, _ = self._prepare(scope, candidates, now)
        packet = ScreenerEvidencePacket(IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION, 'preflight', digest, now, scope, candidates, output_schema(candidates))
        return check(packet, rendered_prompt=rendered, config=self.config)

    def reduce(self, scope, candidates, now):
        report_stage('PACKET')
        digest, rendered, prompt, size = self._prepare(scope, candidates, now)
        report_stage('PACKET', packet_bytes=size, intake_count=len(candidates), sufficient_count=sum(bool(c['sufficient']) for c in candidates))
        deadlines = [timestamp(e['valid_until']).timestamp() for c in candidates for e in (*c['current_market_evidence'], *c['reference_evidence']) if e['valid_until']]
        expiry = min([self.clock() + 1800, *deadlines])
        base = dict(schema_version=SCHEMA_VERSION, run_id=uuid.uuid4().hex, decision_cutoff=now, generated_at=now,
                    scope=scope, provider_id=getattr(self.provider, 'provider_id', None), model_id=getattr(self.provider, 'model_id', None),
                    runtime=getattr(self.provider, 'runtime', 'PAID_API') if self.provider else None,
                    prompt_id=prompt.prompt_id, prompt_version=prompt.version, prompt_hash=prompt.content_hash,
                    wire_schema_version=WIRE_SCHEMA_VERSION,
                    output_schema_hash=input_hash_from_dict(output_schema(candidates)),
                    input_hash=digest, packet_bytes=size, evidence=candidates, candidates=[], limitations=[], cache='MISS', simulated=False,
                    valid_until=datetime.fromtimestamp(expiry, UTC).isoformat().replace('+00:00', 'Z'),
                    coverage=dict(candidate_intake=len(candidates), selected=0, evidence_items=sum(len(c['current_market_evidence']) + len(c['reference_evidence']) for c in candidates),
                                  blocked_items=sum(len(c['blocked']) for c in candidates), missing_items=sum(len(c['missing']) for c in candidates)))
        if self.provider is None:
            return {**base, 'state': 'NOT_CONFIGURED', 'reason': self.reason}
        contract = self.contract()
        if contract is not None and not contract['supported']:
            # Refused before any reservation or request. The selected model stays on the receipt; nothing replaces it.
            return {**base, 'state': 'UNAVAILABLE', 'reason': contract['reason'],
                    'compatibility': {k: contract[k] for k in ('selected_model', 'required_contract', 'unsupported_capability')}}
        if not any(c['sufficient'] for c in candidates):
            return {**base, 'state': 'NO_GROUNDED_CANDIDATES', 'reason': 'INSUFFICIENT_EVIDENCE', 'limitations': ['No admissible current price plus additional strong evidence.']}
        with self.lock:
            cached = self.cache.get(digest)
            if cached and cached[0] > self.clock():
                return {**cached[1], 'cache': 'HIT'}
            waiter = self.inflight.get(digest)
            if waiter is None:
                self.inflight[digest] = threading.Event()
        if waiter is not None:
            # Another caller already holds this exact packet's model call; this run waits for that answer.
            report_stage('MODEL_CALL', shared=True)
            waiter.wait(self.config.timeout_seconds + 5)
            with self.lock:
                cached = self.cache.get(digest)
            return {**cached[1], 'cache': 'HIT'} if cached and cached[0] > self.clock() else {**base, 'state': 'UNAVAILABLE', 'reason': 'SYNTHESIS_IN_PROGRESS_OR_EXPIRED'}
        try:
            packet = ScreenerEvidencePacket(IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION, base['run_id'], digest, now, scope, candidates, output_schema(candidates))
            if not getattr(self.provider, 'reports_stages', False):
                report_stage('MODEL_CALL')
            response = self.provider.infer(packet, rendered_prompt=rendered, config=self.config)
            base.update(provider_id=response.provider_id, model_id=response.model_id, tokens_input=response.tokens_input,
                        tokens_output=response.tokens_output, latency_ms=response.latency_ms, provider_request_id=response.provider_request_id,
                        provider_response_id=response.provider_response_id, simulated=response.simulated,
                        generated_at=datetime.fromtimestamp(self.clock(), UTC).isoformat().replace('+00:00', 'Z'))
            if response.error_code:
                # Only stable reason codes; provider error bodies can include private information.
                message = response.error_message
                reason = message if re.fullmatch(r'[A-Z][A-Z0-9_]*', message or '') else response.error_code.value
                result = {**base, 'state': 'UNAVAILABLE', 'reason': reason}
            else:
                report_stage('VALIDATION')
                parsed, reason = parse_reduction(response.raw_text, candidates)
                if parsed and parsed['candidates']:
                    # Unselected observations cannot shorten the lifetime of valid selected evidence.
                    by_id = {c['instrument']['instrument_id']: c for c in candidates}
                    selected_evidence = [e for pick in parsed['candidates']
                        for e in (*by_id[pick['instrument_id']]['current_market_evidence'], *by_id[pick['instrument_id']]['reference_evidence'])
                        if e['evidence_id'] in (*pick['supporting_refs'], *pick['conflicting_refs'], *pick['weak_refs'])]
                    selected_deadlines = [timestamp(e['valid_until']).timestamp() for e in selected_evidence if e['valid_until']]
                    expiry = min([self.clock() + 1800, *selected_deadlines])
                    base['valid_until'] = datetime.fromtimestamp(expiry, UTC).isoformat().replace('+00:00', 'Z')
                result = {**base, **(parsed or {}), 'state': 'INVALID_OUTPUT' if reason else 'EXPIRED' if self.clock() >= expiry else 'CURRENT' if parsed['candidates'] else 'NO_GROUNDED_CANDIDATES', 'reason': reason}
                if reason:
                    result['validation'] = {'stage': rejection_stage(reason), **rejection_details(response.raw_text, candidates, reason)}
                result['coverage']['selected'] = len(result['candidates'])
            # Cache failures too: repeated explicit clicks never automatically re-bill invalid output.
            with self.lock:
                self.cache[digest] = (min(expiry, self.clock() + (60 if result['state'] == 'UNAVAILABLE' else 1800)), result)
                while len(self.cache) > 64:
                    self.cache.popitem(last=False)
            return result
        finally:
            with self.lock:
                self.inflight.pop(digest).set()
