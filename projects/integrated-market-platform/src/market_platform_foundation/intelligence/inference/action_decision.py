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

PROMPT_ID = 'screener.action_decision.v4'
POLICY_ID = 'action-decision-policy/1.0.0'
# OCT1-08: a deterministic risk fact. The server establishes it; a model can neither select nor veto it.
STOP_BREACH_CONDITION = 'SMA_TRAILING_STOP_BREACHED'
RISK_CONTROL_SOURCE = 'SERVER_RISK_CONTROL'
SCHEMA = 'action-decision/1.0.0'
PROPOSAL_SCHEMA = 'action-proposal/1.0.0'
# What the model writes. ``decode_wire`` rebuilds the canonical proposal from it; ``parse_proposal`` still decides.
WIRE_SCHEMA = 'action-proposal-wire/2.0.0'
STANCES = ('SUPPORTING', 'CONFLICTING', 'CONTEXT')


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

    def risk_conditions():
        # Present only when a stop is configured for this position, so unconfigured decisions are unchanged.
        risk = context.get('risk_control')
        if not risk:
            return []
        breached = position != 'FLAT' and risk.get('status') == 'BREACHED' and risk.get('side') == position
        return [dict(condition(STOP_BREACH_CONDITION, breached, field='active_stop', source_value=risk.get('active_stop'),
                               as_of=risk.get('triggered_at'), direction=risk.get('side'), policy_id=risk.get('policy_id'),
                               stop_state_id=risk.get('stop_state_id'), trigger_price=risk.get('trigger_price')),
                     source=RISK_CONTROL_SOURCE)]

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
                      field='valid_until', source_value=end), *risk_conditions()]


def server_exit_condition(conditions):
    """The met deterministic risk exit, if any. Never derived from model output."""
    return next((c for c in conditions if c['condition_id'] == STOP_BREACH_CONDITION and c['source'] == RISK_CONTROL_SOURCE
                 and c['status'] == 'MET'), None)


# The condition ids each list may name. ``parse_proposal`` enforces exactly these; the schema states them too.
ALLOWED_CONDITIONS = {'entry_conditions': frozenset({'CURRENT_QUOTE', 'DIRECTION_SUPPORTED'}),
                      'hold_conditions': frozenset({'THESIS_CONTINUES'}),
                      'exit_conditions': frozenset({'THESIS_REVERSED', 'DECISION_EXPIRED'})}


def output_schema(candidate, conditions):
    """The proposal shape, bounded by what ``parse_proposal`` accepts and never tighter.

    A constrained decoder given only the looser shape produced answers the unchanged validator always rejects
    (October 17: condition ids outside their list, weak evidence cited as support). Each bound below is one of
    the validator's own rules, so it changes which outputs can be generated, not which outputs are accepted."""
    evidence = (*candidate['current_market_evidence'], *candidate['reference_evidence'])
    refs = [e['evidence_id'] for e in evidence]
    weak = [e['evidence_id'] for e in evidence if e.get('weak_reasons')]
    strong = [e['evidence_id'] for e in evidence if not e.get('weak_reasons')]
    strings = dict(type='array', items=dict(type='string'), maxItems=24)

    def bounded(values, limit):
        # No admissible value: the list must be empty.
        return dict(type='array', items=dict(type='string', enum=list(values)), maxItems=limit) if values else dict(type='array', maxItems=0)

    ref_array = dict(type='array', items=dict(type='string', enum=refs or ['NO_EVIDENCE']), maxItems=24)
    # Risk-control conditions are server facts the model may read but can never select.
    selectable = [c['condition_id'] for c in conditions if c['source'] != RISK_CONTROL_SOURCE]
    missing = sorted({e['capability'] for e in candidate['missing']})
    properties = dict(schema_version=dict(type='string', enum=[PROPOSAL_SCHEMA]),
                      proposal_state=dict(type='string', enum=[s.value for s in ActionState if s != ActionState.REVALIDATION_REQUIRED]),
                      direction=dict(type=['string', 'null'], enum=['LONG', 'SHORT', None]),
                      rationale=dict(type='string', maxLength=1200),
                      supporting_refs=bounded(strong, 24), conflicting_refs=ref_array, weak_refs=bounded(weak, 24),
                      missing_capabilities=bounded(missing, 24), uncertainties=strings,
                      **{name: bounded([c for c in selectable if c in ids], 5) for name, ids in ALLOWED_CONDITIONS.items()})
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def _stance_options(candidate):
    conflicts = {r for a in candidate.get('alignments', []) if a['result'] == 'CONFLICTING' for r in a['sentiment_refs']}

    def options(e):
        # The validator's rules again: a disclosed conflict stays a conflict, weak evidence is never support.
        if e['evidence_id'] in conflicts:
            return ['CONFLICTING']
        return ['CONFLICTING', 'CONTEXT'] if e.get('weak_reasons') else list(STANCES)
    return {e['evidence_id']: options(e) for e in (*candidate['current_market_evidence'], *candidate['reference_evidence'])}


def wire_schema(candidate, conditions):
    """The model's answer shape: one stance for every supplied reference instead of two free lists.

    Two independent ref lists cannot say "disjoint" in a grammar, and the model listed the same reference as
    both supporting and conflicting (every October 17-18 decision after R4 was INVALID_SUPPORT). A stance per
    reference makes that answer inexpressible. ``weak_refs`` and ``missing_capabilities`` had exactly one
    acceptable value, the candidate's own sets, so the server states them rather than asking for an echo."""
    canonical = output_schema(candidate, conditions)['properties']
    stance = _stance_options(candidate)
    properties = dict(schema_version=dict(type='string', enum=[WIRE_SCHEMA]),
                      proposal_state=canonical['proposal_state'], direction=canonical['direction'],
                      rationale=canonical['rationale'],
                      evidence_stance=dict(type='object', properties={r: dict(type='string', enum=o) for r, o in stance.items()},
                                           required=list(stance), additionalProperties=False),
                      # At temperature 0 the model repeated condition ids up to the 24-item cap and the validator
                      # rejected the duplicates (October 18, LIST_INVALID). A few distinct bounded strings.
                      uncertainties=dict(type='array', items=dict(type='string', maxLength=400), maxItems=6, uniqueItems=True),
                      **{name: canonical[name] for name in ALLOWED_CONDITIONS})
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)



REASONED_WIRE_SCHEMA = 'action-proposal-wire/3.0.0'
ASSESSMENTS = {
    'EVIDENCE_SUFFICIENT': 'The model considers the cited evidence sufficient for its proposal.',
    'EVIDENCE_INSUFFICIENT': 'The model considers the cited evidence insufficient for action.',
    'EVIDENCE_MIXED': 'The model considers the cited evidence mixed.',
    'MODEL_UNCERTAIN': 'The model remains uncertain about its proposal.',
}
UNCERTAINTIES = {
    'MODEL_UNCERTAINTY': 'The model remains uncertain.',
    'WEAK_EVIDENCE': 'The assessment has weak evidence.',
    'MISSING_EVIDENCE': 'The assessment has missing evidence.',
    'CONFLICTING_EVIDENCE': 'The assessment has conflicting evidence.',
    'CONDITION_NOT_MET': 'A supplied condition is not met.',
}
CAPABILITY_TEXT = {'QUOTE': 'quote', 'TECHNICALS': 'technical', 'ORDER_FLOW': 'order flow',
                   'NEWS': 'news', 'SENTIMENT': 'sentiment', 'FUNDAMENTALS': 'fundamental'}


def _uncertainty_options(candidate, conditions):
    evidence = (*candidate['current_market_evidence'], *candidate['reference_evidence'])
    options = ['MODEL_UNCERTAINTY']
    if any(e.get('weak_reasons') for e in evidence): options.append('WEAK_EVIDENCE')
    if candidate['missing']: options.append('MISSING_EVIDENCE')
    if any(a['result'] == 'CONFLICTING' for a in candidate.get('alignments', [])):
        options.append('CONFLICTING_EVIDENCE')
    if any(c['status'] == 'NOT_MET' for c in conditions): options.append('CONDITION_NOT_MET')
    return options


def reasoned_wire_schema(candidate, conditions):
    """A model-authored assessment with explicit basis; no free-text factual claims.

    This changes representation, not the canonical proposal or its validator. The model
    chooses every action, stance, basis and assessment. Rendering discloses those choices
    as model judgments, and does not add prices, causality, evidence or authority.
    """
    schema = wire_schema(candidate, conditions)
    props = schema['properties']
    refs = list(_stance_options(candidate))
    props['schema_version'] = dict(type='string', enum=[REASONED_WIRE_SCHEMA])
    props['rationale'] = dict(type='object', properties=dict(
        basis_refs=dict(type='array', items=dict(type='string', enum=refs), minItems=1 if refs else 0,
                        maxItems=min(6, len(refs)), uniqueItems=True) if refs else dict(type='array', maxItems=0),
        assessment=dict(type='string', enum=list(ASSESSMENTS))),
        required=['basis_refs', 'assessment'], additionalProperties=False)
    props['uncertainties'] = dict(type='array', items=dict(type='string', enum=_uncertainty_options(candidate, conditions)),
                                  maxItems=5, uniqueItems=True)
    return schema


def _render_reasoning(value, candidate, conditions):
    reasoning = value['rationale']
    refs = {e['evidence_id']: e for e in (*candidate['current_market_evidence'], *candidate['reference_evidence'])}
    if not isinstance(reasoning, dict) or set(reasoning) != {'basis_refs', 'assessment'}:
        raise ValueError('SCHEMA_INVALID')
    basis, assessment = reasoning['basis_refs'], reasoning['assessment']
    if (not isinstance(basis, list) or len(basis) > min(6, len(refs)) or
            (refs and not basis) or any(not isinstance(r, str) or r not in refs for r in basis) or
            len(set(basis)) != len(basis) or not isinstance(assessment, str) or assessment not in ASSESSMENTS):
        raise ValueError('SCHEMA_INVALID')
    if assessment in ('EVIDENCE_INSUFFICIENT', 'MODEL_UNCERTAIN') and value['proposal_state'] in ('ENTER', 'HOLD', 'EXIT'):
        raise ValueError('REASONING_ACTION_MISMATCH')
    uncertainty = value['uncertainties']
    allowed = _uncertainty_options(candidate, conditions)
    if (not isinstance(uncertainty, list) or len(uncertainty) > 5 or
            any(not isinstance(u, str) or u not in allowed for u in uncertainty) or len(set(uncertainty)) != len(uncertainty)):
        raise ValueError('SCHEMA_INVALID')
    # Never put arbitrary server/provider capability text into the canonical rationale.
    sentences = []
    for r in basis:
        capability = CAPABILITY_TEXT.get(refs[r]['capability'], 'supplied')
        stance = value['evidence_stance'][r]
        label = {'SUPPORTING': 'supporting', 'CONFLICTING': 'conflicting', 'CONTEXT': 'contextual'}[stance]
        sentences.append(f'The model treats {capability} evidence as {label}.')
    sentences.append(ASSESSMENTS[assessment])
    return ' '.join(sentences), [UNCERTAINTIES[u] for u in uncertainty]


def decode_wire(raw, candidate, conditions):
    """Canonical proposal JSON from a wire answer. Shape only: acceptance stays with ``parse_proposal``."""
    def unique(pairs):
        if len({k for k, _ in pairs}) != len(pairs):
            raise ValueError('DUPLICATE_KEY')
        return dict(pairs)
    try:
        if len(raw.encode('utf-8')) > 24000:
            return None, 'OUTPUT_BOUND_EXCEEDED'
        value = json.loads(raw, object_pairs_hook=unique)
        schema = wire_schema(candidate, conditions)
        if not isinstance(value, dict) or set(value) != set(schema['required']) or value['schema_version'] not in (WIRE_SCHEMA, REASONED_WIRE_SCHEMA):
            return None, 'SCHEMA_INVALID'
        refs = schema['properties']['evidence_stance']['required']
        stance = value['evidence_stance']
        if not isinstance(stance, dict) or set(stance) != set(refs) or any(s not in STANCES for s in stance.values()):
            return None, 'SCHEMA_INVALID'
        if value['schema_version'] == REASONED_WIRE_SCHEMA:
            rationale, uncertainties = _render_reasoning(value, candidate, conditions)
        else:
            rationale, uncertainties = value['rationale'], value['uncertainties']
        evidence = (*candidate['current_market_evidence'], *candidate['reference_evidence'])
        proposal = dict(schema_version=PROPOSAL_SCHEMA, proposal_state=value['proposal_state'], direction=value['direction'],
                        rationale=rationale,
                        supporting_refs=[r for r in refs if stance[r] == 'SUPPORTING'],
                        conflicting_refs=[r for r in refs if stance[r] == 'CONFLICTING'],
                        weak_refs=[e['evidence_id'] for e in evidence if e.get('weak_reasons')],
                        missing_capabilities=sorted({e['capability'] for e in candidate['missing']}),
                        uncertainties=uncertainties, **{name: value[name] for name in ALLOWED_CONDITIONS})
        return json.dumps(proposal), None
    except (ValueError, TypeError, KeyError, AttributeError):
        return None, 'SCHEMA_INVALID'


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
        if any(not set(value[k]) <= ids for k,ids in ALLOWED_CONDITIONS.items()):
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
    server_exit = server_exit_condition(conditions)
    state = 'EXIT' if server_exit else proposal['proposal_state'] if proposal else 'REVALIDATION_REQUIRED'
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
    if server_exit:
        # The breach stands whatever else is degraded: blockers gate the Paper preview, not the risk state.
        state = 'EXIT' if position['state'] in ('LONG','SHORT') else 'REVALIDATION_REQUIRED'
    elif state == 'EXIT' and not any(by_id[c]['status']=='MET' for c in proposal['exit_conditions']):
        blockers.append('EXIT_CONDITION_NOT_MET'); state = 'REVALIDATION_REQUIRED'
    # AI-direct (owner-authorized, internal simulation only): the gated proposal itself is the entry basis.
    if not context.get('opportunity') and state == 'ENTER' and not context.get('ai_direct'): blockers.append('NO_GOVERNED_OPPORTUNITY')
    if context.get('opportunity') and state=='ENTER' and context['opportunity'].get('side') != proposal['direction']:
        blockers.append('OPPORTUNITY_DIRECTION_MISMATCH')
    if not context.get('authority'): blockers.append('PAPER_AUTHORITY_UNAVAILABLE')
    if proposal and proposal['direction']=='SHORT' and state=='ENTER' and not context.get('allow_short'):
        blockers.append('SHORT_NOT_ALLOWED')
    readiness = 'PREVIEW_ALLOWED' if state in ('ENTER','EXIT') and not blockers else 'BLOCKED' if blockers else 'NOT_PREVIEWED'
    return dict(action_state=state, execution_readiness=readiness, blocker_codes=blockers,
                conditions=conditions, policy_id=POLICY_ID,
                reason_codes=[*([STOP_BREACH_CONDITION, 'SERVER_RISK_EXIT'] if server_exit else []), *blockers] or ['BOUNDED_PROPOSAL_ACCEPTED'], input_hash=input_hash_from_dict(dict(candidate=candidate,context=context,policy=POLICY_ID)))
