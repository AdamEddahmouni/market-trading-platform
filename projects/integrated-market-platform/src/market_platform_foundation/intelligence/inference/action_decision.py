"""OCT1-06 bounded proposals and deterministic position-aware action policy.

No order construction, sizing, broker access, risk mutation, or submission.
Conditions are server facts: models select IDs, never executable expressions.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from enum import StrEnum

from ...market_data.freshness_contract import timestamp
from .hashing import input_hash_from_dict
from .screener_synthesis import unsupported_certainty

PROMPT_ID = 'screener.action_decision.v1'
POLICY_ID = 'action-decision-policy/1.0.0'
SCHEMA = 'action-decision/1.0.0'
PROPOSAL_SCHEMA = 'action-proposal/1.0.0'


class ActionState(StrEnum):
    NO_ACTION = 'NO_ACTION'
    CONSIDER_ENTRY = 'CONSIDER_ENTRY'
    ENTER = 'ENTER'
    HOLD = 'HOLD'
    EXIT = 'EXIT'
    REVALIDATION_REQUIRED = 'REVALIDATION_REQUIRED'


@dataclass(frozen=True, slots=True)
class ActionDecisionV1:
    """Canonical JSON prevents mutable nested objects escaping a frozen record."""
    canonical_json: str

    @classmethod
    def from_dict(cls, value):
        if value.get('schema_version') != SCHEMA:
            raise ValueError('ACTION_SCHEMA_INVALID')
        ActionState(value['action_state'])
        return cls(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False))

    def to_dict(self):
        return json.loads(self.canonical_json)


def snapshot_evidence(candidate, now):
    """Do not admit facts with future or unknown clocks; retain absence codes."""
    cutoff = timestamp(now)
    if cutoff is None:
        raise ValueError('INVALID_DECISION_CLOCK')
    result = copy.deepcopy(candidate)
    for group in ('current_market_evidence', 'reference_evidence'):
        admitted = []
        for e in result[group]:
            clocks = [e.get('as_of')]
            # News publication alone is insufficient: availability is also PIT.
            for source in e.get('facts', {}).get('sources', []):
                clocks.extend(source.get(k) for k in ('available_at', 'retrieved_at', 'ingested_at') if source.get(k))
            if all(timestamp(t) is not None and timestamp(t) <= cutoff for t in clocks):
                admitted.append(e)
            else:
                result['blocked'].append(dict(capability=e['capability'], reason_codes=['AFTER_CUTOFF_OR_UNKNOWN_CLOCK']))
        result[group] = admitted
    return result


def _current(e, now):
    cutoff, source, end = timestamp(now), timestamp(e.get('as_of')), timestamp(e.get('valid_until'))
    return bool(cutoff and source and end and source <= cutoff < end
                and e.get('decision_admissibility') not in ('BLOCKED', 'UNAVAILABLE')
                and not e.get('weak_reasons'))


def build_conditions(candidate, context, now):
    evidence = [*candidate['current_market_evidence'], *candidate['reference_evidence']]
    current = [e for e in evidence if _current(e, now)]
    quote = next((e for e in current if e['capability'] == 'QUOTE' and e['role'] == 'CURRENT_MARKET'
                  and isinstance(e['facts'].get('price'), (int, float)) and e['facts']['price'] > 0), None)
    # Only observed signed flow or price change establishes directional support.
    basis = next((e for e in current if e['capability'] == 'ORDER_FLOW' and e['facts'].get('net_signed_volume')), None)
    field = 'net_signed_volume'
    if basis is None:
        basis = next((e for e in current if e['capability'] == 'TECHNICALS' and e['facts'].get('change_pct')), None)
        field = 'change_pct'
    observed = 'LONG' if basis and basis['facts'][field] > 0 else 'SHORT' if basis else None
    position = context['position']['state']
    end = context.get('candidate_valid_until')

    def condition(identifier, met, refs=(), **values):
        return dict(condition_id=identifier, condition_type=identifier, operator='IS',
                    status='MET' if met else 'NOT_MET', evidence_refs=list(refs),
                    source='SERVER_ACTION_POLICY', reason_codes=[] if met else [identifier + '_NOT_MET'],
                    valid_until=end, **values)

    return [condition('CURRENT_QUOTE', bool(quote), [quote['evidence_id']] if quote else [],
                      field='price', source_value=quote['facts']['price'] if quote else None,
                      as_of=quote.get('as_of') if quote else None, entry_method='MARKET_NOW_IF_GATES_PASS'),
            condition('DIRECTION_SUPPORTED', bool(observed), [basis['evidence_id']] if basis else [],
                      field=field, source_value=basis['facts'][field] if basis else None, direction=observed),
            condition('THESIS_CONTINUES', position != 'FLAT' and observed == position,
                      [basis['evidence_id']] if basis else [], field=field, direction=observed),
            condition('THESIS_REVERSED', position != 'FLAT' and observed is not None and observed != position,
                      [basis['evidence_id']] if basis else [], field=field, direction=observed),
            condition('DECISION_EXPIRED', bool(timestamp(end) and timestamp(now) >= timestamp(end)),
                      field='valid_until', source_value=end)]


def output_schema(candidate, conditions):
    refs = [e['evidence_id'] for e in (*candidate['current_market_evidence'], *candidate['reference_evidence'])]
    strings = dict(type='array', items=dict(type='string'), maxItems=24)
    ref_array = dict(type='array', items=dict(type='string', enum=refs or ['NO_EVIDENCE']), maxItems=24)
    condition_array = dict(type='array', items=dict(type='string', enum=[c['condition_id'] for c in conditions]), maxItems=5)
    properties = dict(schema_version=dict(type='string', enum=[PROPOSAL_SCHEMA]),
                      proposal_state=dict(type='string', enum=[s.value for s in ActionState if s != ActionState.REVALIDATION_REQUIRED]),
                      direction=dict(type=['string', 'null'], enum=['LONG', 'SHORT', None]),
                      rationale=dict(type='string', maxLength=1200),
                      supporting_refs=ref_array, conflicting_refs=ref_array, weak_refs=ref_array,
                      missing_capabilities=strings, uncertainties=strings,
                      entry_conditions=condition_array, hold_conditions=condition_array, exit_conditions=condition_array)
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def parse_proposal(raw, candidate, conditions):
    try:
        if len(raw.encode('utf-8')) > 24000:
            return None, 'OUTPUT_BOUND_EXCEEDED'
        value = json.loads(raw)
        schema = output_schema(candidate, conditions)
        if not isinstance(value, dict) or set(value) != set(schema['required']) or value['schema_version'] != PROPOSAL_SCHEMA:
            return None, 'SCHEMA_INVALID'
        if value['proposal_state'] not in schema['properties']['proposal_state']['enum'] or value['direction'] not in ('LONG','SHORT',None):
            return None, 'STATE_OR_DIRECTION_INVALID'
        if not isinstance(value['rationale'], str) or not value['rationale'].strip() or len(value['rationale']) > 1200:
            return None, 'RATIONALE_INVALID'
        for name in ('supporting_refs','conflicting_refs','weak_refs','missing_capabilities','uncertainties',
                     'entry_conditions','hold_conditions','exit_conditions'):
            items = value[name]
            if not isinstance(items, list) or len(items) > 24 or any(not isinstance(x,str) or len(x)>400 for x in items) or len(set(items)) != len(items):
                return None, 'LIST_INVALID'
        refs = {e['evidence_id']:e for e in (*candidate['current_market_evidence'], *candidate['reference_evidence'])}
        for name in ('supporting_refs','conflicting_refs','weak_refs'):
            if any(ref not in refs for ref in value[name]):
                return None, 'UNKNOWN_EVIDENCE_REF'
        if set(value['supporting_refs']) & set(value['conflicting_refs']) or any(refs[r].get('weak_reasons') for r in value['supporting_refs']):
            return None, 'INVALID_SUPPORT'
        conflicts = {r for a in candidate.get('alignments',[]) if a['result']=='CONFLICTING' for r in a['sentiment_refs']}
        if not conflicts <= set(value['conflicting_refs']):
            return None, 'NEWS_CONFLICT_NOT_DISCLOSED'
        if set(value['weak_refs']) != {r for r,e in refs.items() if e.get('weak_reasons')}:
            return None, 'WEAK_EVIDENCE_MISMATCH'
        if set(value['missing_capabilities']) != {e['capability'] for e in candidate['missing']}:
            return None, 'MISSING_EVIDENCE_MISMATCH'
        allowed = {'entry_conditions':{'CURRENT_QUOTE','DIRECTION_SUPPORTED'}, 'hold_conditions':{'THESIS_CONTINUES'},
                   'exit_conditions':{'THESIS_REVERSED','DECISION_EXPIRED'}}
        if any(not set(value[k]) <= ids for k,ids in allowed.items()):
            return None, 'UNSUPPORTED_CONDITION'
        import re
        for text in [value['rationale'], *value['uncertainties']]:
            if unsupported_certainty(text) or re.search(r'\b(?:quantity|notional|leverage|broker|account|stop|trailing|SMA|guaranteed|profit|shares|units|size|cash|balance|submit|limits|dollars?|cents?|euros?|hundred|thousand|million|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b|\d|[$€£]', text, re.I):
                return None, 'UNSUPPORTED_EXECUTION_OR_LEVEL'
        return value, None
    except (ValueError, TypeError, KeyError):
        return None, 'SCHEMA_INVALID'


def gate_proposal(proposal, candidate, context, *, now):
    conditions = build_conditions(candidate, context, now)
    by_id = {c['condition_id']:c for c in conditions}
    blockers = []
    state = proposal['proposal_state'] if proposal else 'REVALIDATION_REQUIRED'
    position = context['position']
    legal = {'FLAT':{'NO_ACTION','CONSIDER_ENTRY','ENTER'}, 'LONG':{'HOLD','EXIT'}, 'SHORT':{'HOLD','EXIT'}}
    if state not in legal.get(position['state'],set()):
        blockers.append('ILLEGAL_POSITION_ACTION'); state = 'REVALIDATION_REQUIRED'
    cutoff, snapshot = timestamp(now), timestamp(position.get('snapshot_at'))
    deadline = timestamp(context.get('candidate_valid_until'))
    if not cutoff or not deadline or cutoff >= deadline:
        blockers.append('CANDIDATE_EXPIRED'); state = 'REVALIDATION_REQUIRED'
    if not snapshot or not cutoff or not 0 <= (cutoff-snapshot).total_seconds() <= 30:
        blockers.append('POSITION_SNAPSHOT_STALE'); state = 'REVALIDATION_REQUIRED'
    if position.get('pending'):
        blockers.append('PENDING_ORDER_REVALIDATION'); state = 'REVALIDATION_REQUIRED'
    if state in ('ENTER','HOLD','EXIT') and by_id['CURRENT_QUOTE']['status'] != 'MET':
        blockers.append('QUOTE_STALE_OR_UNAVAILABLE'); state = 'REVALIDATION_REQUIRED'
    if state == 'ENTER':
        refs = {e['evidence_id']:e for e in (*candidate['current_market_evidence'], *candidate['reference_evidence'])}
        support = proposal['supporting_refs']
        grounded = len(support)>=2 and all(r in refs and _current(refs[r],now) for r in support)
        grounded = grounded and any(refs[r]['capability']=='QUOTE' for r in support) and any(refs[r]['capability']!='QUOTE' for r in support)
        if not grounded:
            blockers.append('SUPPORT_UNAVAILABLE'); state = 'CONSIDER_ENTRY'
        if proposal['direction'] is None or by_id['DIRECTION_SUPPORTED'].get('direction') != proposal['direction']:
            blockers.append('DIRECTION_UNSUPPORTED'); state = 'CONSIDER_ENTRY'
        if set(proposal['entry_conditions']) != {'CURRENT_QUOTE','DIRECTION_SUPPORTED'}:
            blockers.append('ENTRY_PLAN_UNAVAILABLE'); state = 'CONSIDER_ENTRY'
        if not proposal['exit_conditions']:
            blockers.append('EXIT_PLAN_UNAVAILABLE'); state = 'CONSIDER_ENTRY'
    if state == 'HOLD' and (proposal['hold_conditions'] != ['THESIS_CONTINUES'] or by_id['THESIS_CONTINUES']['status'] != 'MET' or not proposal['exit_conditions']):
        blockers.append('HOLD_BASIS_UNAVAILABLE'); state = 'REVALIDATION_REQUIRED'
    if state == 'EXIT' and not any(by_id[c]['status']=='MET' for c in proposal['exit_conditions']):
        blockers.append('EXIT_CONDITION_NOT_MET'); state = 'REVALIDATION_REQUIRED'
    if not context.get('opportunity') and state == 'ENTER': blockers.append('NO_GOVERNED_OPPORTUNITY')
    if context.get('opportunity') and state=='ENTER' and context['opportunity'].get('side') != proposal['direction']:
        blockers.append('OPPORTUNITY_DIRECTION_MISMATCH')
    if not context.get('authority'): blockers.append('PAPER_AUTHORITY_UNAVAILABLE')
    if proposal and proposal['direction']=='SHORT' and state=='ENTER' and not context.get('allow_short'):
        blockers.append('SHORT_NOT_ALLOWED')
    readiness = 'PREVIEW_ALLOWED' if state in ('ENTER','EXIT') and not blockers else 'BLOCKED' if blockers else 'NOT_PREVIEWED'
    return dict(action_state=state, execution_readiness=readiness, blocker_codes=blockers,
                conditions=conditions, policy_id=POLICY_ID,
                reason_codes=blockers or ['BOUNDED_PROPOSAL_ACCEPTED'], input_hash=input_hash_from_dict(dict(candidate=candidate,context=context,policy=POLICY_ID)))
