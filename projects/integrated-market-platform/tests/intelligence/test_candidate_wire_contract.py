"""Compact inference wire contract: encode, exact decode, then the unchanged canonical validator.

The wire carries a candidate index and that candidate's own evidence positions. Nothing a model
can emit on the wire names another instrument's evidence; the decoder never repairs or invents.
"""
import copy
import json
import unittest

from market_platform_foundation.intelligence.inference.candidate_reduction import (
    MAX_INTAKE, MAX_SELECTED, SCHEMA_VERSION, CandidateReducer, build_candidate, candidate_metadata,
    output_schema, packet_candidates, parse_reduction, rejection_stage,
)
from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse
from market_platform_foundation.market_data.freshness_contract import evaluate

NOW = '2026-10-02T15:00:00Z'
WIRE_KEYS = {'candidate_key', 'rank', 'rationale', 'supporting_refs', 'conflicting_refs', 'uncertainties'}


def status(capability='quote', *, reference=False, as_of=NOW, ttl=30000):
    return evaluate(capability=capability, source='IMP_TEST', delivery_mode='REALTIME', now=NOW, as_of=as_of,
                    stale_after_ms=ttl, reference=reference, policy='CONTROLLED', basis='EVENT_TIME')


def instrument(name, *, extra=(), weak=False):
    observations = [('QUOTE', status(), {'price': 100 + len(name)}, []),
                    ('TECHNICALS', status('bars'), {'volume': 1000}, []), *extra]
    if weak:
        observations.append(('SQUEEZE', status('squeeze'), {'score': 1}, ['LOW_SAMPLE']))
    return build_candidate({'instrument_id': f'EQ:{name}', 'symbol': name}, observations, now=NOW)


def pick(key, rank=1, supporting=(0, 1), conflicting=()):
    return {'candidate_key': key, 'rank': rank, 'rationale': 'Review candidate grounded in admitted observations.',
            'supporting_refs': list(supporting), 'conflicting_refs': list(conflicting), 'uncertainties': ['Coverage is limited.']}


def wire(*picks, limitations=('Candidate reduction only.',)):
    return json.dumps({'schema_version': SCHEMA_VERSION, 'candidates': list(picks), 'limitations': list(limitations)})


def evidence_ids(candidate):
    return [e['evidence_id'] for e in (*candidate['current_market_evidence'], *candidate['reference_evidence'])]


class WireSchemaTests(unittest.TestCase):
    def test_schema_is_flat_bounded_and_free_of_per_instrument_structure(self):
        candidates = [instrument(f'S{i:02d}') for i in range(MAX_INTAKE)]
        schema = output_schema(candidates)
        text = json.dumps(schema)
        for forbidden in ('anyOf', 'oneOf', 'allOf', '$ref', 'const', 'EQ:', 'EV:'):
            self.assertNotIn(forbidden, text)
        item = schema['properties']['candidates']['items']
        self.assertEqual(set(item['properties']), WIRE_KEYS)
        self.assertEqual(item['properties']['candidate_key']['enum'], list(range(MAX_INTAKE)))
        # Evidence positions are local to a candidate: the enum is its largest evidence list, not the packet total.
        self.assertEqual(item['properties']['supporting_refs']['items']['enum'], [0, 1])
        self.assertLess(len(text), 2500)

    def test_schema_size_does_not_grow_with_the_number_of_instruments(self):
        sizes = {n: len(json.dumps(output_schema([instrument(f'S{i:02d}') for i in range(n)]))) for n in (1, 5, 20, MAX_INTAKE)}
        self.assertLess(sizes[MAX_INTAKE] - sizes[1], 4 * MAX_INTAKE)

    def test_packet_carries_the_indices_the_schema_admits(self):
        candidates = [instrument('A', weak=True), instrument('B', extra=[('NEWS', status('news', reference=True), {'story_id': 's'}, [])])]
        packet = packet_candidates(candidates)
        self.assertEqual([c['candidate_key'] for c in packet], [0, 1])
        for original, projected in zip(candidates, packet):
            listed = [*projected['current_market_evidence'], *projected['reference_evidence']]
            self.assertEqual([e['reference_index'] for e in listed], list(range(len(listed))))
            self.assertEqual([e['evidence_id'] for e in listed], evidence_ids(original))
        # Projection never mutates the canonical candidates, whose evidence ids are content hashes.
        self.assertNotIn('candidate_key', candidates[0])
        self.assertNotIn('reference_index', candidates[0]['current_market_evidence'][0])


class WireDecodeTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = instrument('A'), instrument('BB', extra=[('NEWS', status('news', reference=True), {'story_id': 's'}, [])])
        self.candidates = [self.a, self.b]

    def test_selection_decodes_to_canonical_ids_and_fixed_lists(self):
        parsed, reason = parse_reduction(wire(pick(1, supporting=(0, 1), conflicting=(2,))), self.candidates)
        self.assertIsNone(reason)
        stored = parsed['candidates'][0]
        ids = evidence_ids(self.b)
        self.assertEqual(stored['instrument_id'], 'EQ:BB')
        self.assertEqual(stored['supporting_refs'], ids[:2])
        self.assertEqual(stored['conflicting_refs'], ids[2:3])
        self.assertEqual(stored['weak_refs'], candidate_metadata(self.b)['weak_refs'])
        self.assertEqual(stored['missing_capabilities'], sorted(x['capability'] for x in self.b['missing']))
        self.assertNotIn('candidate_key', stored)

    def test_no_selection_is_valid_when_explained(self):
        parsed, reason = parse_reduction(wire(limitations=['No candidate has two strong references.']), self.candidates)
        self.assertEqual((parsed['candidates'], reason), ([], None))
        self.assertEqual(parse_reduction(wire(limitations=[]), self.candidates)[1], 'INVALID_LIMITATIONS')

    def test_multiple_selections_up_to_the_bound(self):
        many = [instrument(f'M{i}') for i in range(MAX_SELECTED + 1)]
        parsed, reason = parse_reduction(wire(*[pick(i, rank=i + 1) for i in range(MAX_SELECTED)]), many)
        self.assertIsNone(reason)
        self.assertEqual([c['instrument_id'] for c in parsed['candidates']], [f'EQ:M{i}' for i in range(MAX_SELECTED)])
        over = wire(*[pick(i, rank=i + 1) for i in range(MAX_SELECTED + 1)])
        self.assertEqual(parse_reduction(over, many)[1], 'CANDIDATE_BOUND_EXCEEDED')

    def test_weak_and_missing_lists_come_from_the_packet_never_from_the_model(self):
        weak = instrument('W', weak=True)
        parsed, reason = parse_reduction(wire(pick(0)), [weak])
        self.assertIsNone(reason)
        self.assertEqual(parsed['candidates'][0]['weak_refs'], [evidence_ids(weak)[2]])
        # Nothing missing, one missing and many missing all decode without the model restating them.
        full = build_candidate({'instrument_id': 'EQ:F'}, [(c, status(c.lower()), {'price': 1} if c == 'QUOTE' else {'v': 1}, [])
                                                         for c in ('QUOTE', 'TECHNICALS', 'ORDER_FLOW', 'CVD', 'LEVEL2', 'OPTIONS', 'FUTURES',
                                                                   'CROSS_ASSET', 'SQUEEZE', 'FUNDAMENTALS', 'NEWS', 'SENTIMENT', 'RATES')], now=NOW)
        self.assertEqual(full['missing'], [])
        self.assertEqual(parse_reduction(wire(pick(0)), [full])[0]['candidates'][0]['missing_capabilities'], [])

    def test_a_weak_reference_still_cannot_be_support(self):
        weak = instrument('W', weak=True)
        self.assertEqual(parse_reduction(wire(pick(0, supporting=(0, 2))), [weak])[1], 'WEAK_OR_INSUFFICIENT_SUPPORT')

    def test_position_outside_the_selected_instruments_own_list_is_rejected(self):
        # A has two items, B has three: index 2 is admitted by the schema enum but is not A's.
        self.assertEqual(parse_reduction(wire(pick(0, supporting=(0, 2))), self.candidates)[1], 'WIRE_REFERENCE_INDEX_INVALID')
        self.assertEqual(parse_reduction(wire(pick(0, conflicting=(9,))), self.candidates)[1], 'WIRE_REFERENCE_INDEX_INVALID')

    def test_no_wire_value_can_decode_to_another_instruments_evidence(self):
        own, other = set(evidence_ids(self.a)), set(evidence_ids(self.b))
        self.assertFalse(own & other)
        for index in range(-2, 8):
            parsed, reason = parse_reduction(wire(pick(0, supporting=(0, index))), self.candidates)
            if parsed:
                self.assertTrue(set(parsed['candidates'][0]['supporting_refs']) <= own)

    def test_invalid_wire_values_fail_closed_with_a_decode_reason(self):
        cases = [
            (pick(2), 'WIRE_CANDIDATE_KEY_INVALID'), (pick(-1), 'WIRE_CANDIDATE_KEY_INVALID'),
            (pick(True), 'WIRE_CANDIDATE_KEY_INVALID'), (pick('0'), 'WIRE_CANDIDATE_KEY_INVALID'),
            (pick(0.0), 'WIRE_CANDIDATE_KEY_INVALID'), (pick(None), 'WIRE_CANDIDATE_KEY_INVALID'),
            (pick(0, supporting=(0, '1')), 'WIRE_REFERENCE_INDEX_INVALID'),
            (pick(0, supporting=(0, True)), 'WIRE_REFERENCE_INDEX_INVALID'),
            (pick(0, supporting=(0, -1)), 'WIRE_REFERENCE_INDEX_INVALID'),
            ({**pick(0), 'supporting_refs': '[0,1]'}, 'WIRE_REFERENCE_INDEX_INVALID'),
            ({**pick(0), 'conflicting_refs': None}, 'WIRE_REFERENCE_INDEX_INVALID'),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                parsed, reason = parse_reduction(wire(value), self.candidates)
                self.assertEqual((parsed, reason), (None, expected))
                self.assertEqual(rejection_stage(reason), 'DECODE')

    def test_canonical_rejections_survive_the_wire(self):
        fabricated = {**pick(0), 'supporting_refs': ['EV:' + '0' * 32, 'EV:' + '1' * 32]}
        cases = [
            (wire(pick(0), pick(0, rank=2)), 'UNKNOWN_OR_DUPLICATE_CANDIDATE'),
            (wire(pick(0, rank=2)), 'INVALID_RANK'),
            (wire(pick(0, supporting=(0,))), 'WEAK_OR_INSUFFICIENT_SUPPORT'),
            (wire(pick(0, supporting=(0, 0))), 'INVALID_SUPPORTING_REFS'),
            (wire(pick(0, supporting=(0, 1), conflicting=(1,))), 'CONFLICTING_SUPPORT'),
            (wire({**pick(0), 'rationale': ''}), 'INVALID_RATIONALE'),
            (wire({**pick(0), 'rationale': 'A guaranteed winner.'}), 'UNSUPPORTED_CERTAINTY_OR_ACTION'),
            (wire({**pick(0), 'uncertainties': 'none'}), 'INVALID_UNCERTAINTIES'),
            (wire({k: v for k, v in pick(0).items() if k != 'rank'}), 'SCHEMA_INVALID'),
            (wire({**pick(0), 'direction': 'UP'}), 'SCHEMA_INVALID'),
            (wire({**pick(0), 'instrument_id': 'EQ:A'}), 'SCHEMA_INVALID'),
            (wire(fabricated), 'WIRE_REFERENCE_INDEX_INVALID'),
            ('{"schema_version": ', 'MALFORMED_JSON'),
            (json.dumps({'schema_version': 'other/9', 'candidates': [], 'limitations': ['x']}), 'SCHEMA_INVALID'),
        ]
        for raw, expected in cases:
            with self.subTest(expected=expected, raw=raw[:60]):
                self.assertEqual(parse_reduction(raw, self.candidates), (None, expected))

    def test_insufficient_candidate_cannot_be_selected_through_the_wire(self):
        thin = build_candidate({'instrument_id': 'EQ:T'}, [('QUOTE', status(), {'price': 1}, [])], now=NOW)
        self.assertFalse(thin['sufficient'])
        self.assertEqual(parse_reduction(wire(pick(0, supporting=(0,))), [thin])[1], 'INSUFFICIENT_EVIDENCE')

    def test_stale_evidence_is_absent_from_the_packet_and_unaddressable(self):
        stale = build_candidate({'instrument_id': 'EQ:O'}, [
            ('QUOTE', status(), {'price': 1}, []), ('TECHNICALS', status('bars'), {'volume': 1}, []),
            ('ORDER_FLOW', status('flow', as_of='2026-10-02T14:00:00Z'), {'net_signed_volume': 5}, [])], now=NOW)
        self.assertEqual(len(evidence_ids(stale)), 2)
        self.assertEqual(parse_reduction(wire(pick(0, supporting=(0, 1, 2))), [stale])[1], 'WIRE_REFERENCE_INDEX_INVALID')

    def test_decode_does_not_mutate_the_packet_candidates(self):
        before = copy.deepcopy(self.candidates)
        parse_reduction(wire(pick(1)), self.candidates)
        self.assertEqual(before, self.candidates)


class WireReducerTests(unittest.TestCase):
    class Provider:
        provider_id, model_id, runtime = 'inference.fixture', 'controlled.wire.v1', 'FIXTURE'

        def __init__(self, raw):
            self.raw, self.calls, self.prompt = raw, 0, None

        def infer(self, packet, *, rendered_prompt, config):
            self.calls += 1
            self.prompt = rendered_prompt
            return ProviderInferenceResponse(self.raw, self.provider_id, self.model_id, tokens_input=10, tokens_output=5, latency_ms=1)

    def run_reduction(self, raw, candidates):
        provider = self.Provider(raw)
        return CandidateReducer(provider=provider, clock=lambda: 1790953200.0).reduce({}, candidates, NOW), provider

    def test_valid_wire_output_is_stored_canonically(self):
        candidates = [instrument('A'), instrument('B')]
        result, provider = self.run_reduction(wire(pick(1)), candidates)
        self.assertEqual((result['state'], result['reason']), ('CURRENT', None))
        self.assertEqual(result['candidates'][0]['instrument_id'], 'EQ:B')
        self.assertEqual(result['candidates'][0]['supporting_refs'], evidence_ids(candidates[1]))
        self.assertEqual(result['coverage']['selected'], 1)
        self.assertIn('"candidate_key": 1', provider.prompt)
        self.assertIn('"reference_index": 0', provider.prompt)

    def test_rejected_output_reports_stage_and_never_the_raw_text(self):
        secret = 'PRIVATE-MODEL-TEXT-7731'
        raw = wire({**pick(5), 'rationale': secret})
        result, _ = self.run_reduction(raw, [instrument('A')])
        self.assertEqual((result['state'], result['reason']), ('INVALID_OUTPUT', 'WIRE_CANDIDATE_KEY_INVALID'))
        self.assertEqual(result['validation'], {'stage': 'DECODE'})
        self.assertEqual(result['candidates'], [])
        self.assertNotIn(secret, json.dumps(result))
        canonical, _ = self.run_reduction(wire(pick(0, rank=3)), [instrument('A')])
        self.assertEqual(canonical['validation'], {'stage': 'CANONICAL_VALIDATION'})

    def test_identical_invalid_output_is_not_billed_twice(self):
        provider = self.Provider(wire(pick(9)))
        reducer = CandidateReducer(provider=provider, clock=lambda: 1790953200.0)
        candidates = [instrument('A')]
        first = reducer.reduce({}, candidates, NOW)
        second = reducer.reduce({}, candidates, NOW)
        self.assertEqual((first['state'], second['cache'], provider.calls), ('INVALID_OUTPUT', 'HIT', 1))


if __name__ == '__main__':
    unittest.main()
