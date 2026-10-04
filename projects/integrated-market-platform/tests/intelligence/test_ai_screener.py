import json
import unittest
from concurrent.futures import ThreadPoolExecutor

from market_platform_foundation.market_data.freshness_contract import evaluate
from market_platform_foundation.intelligence.inference.candidate_reduction import (
    build_candidate, CandidateReducer, parse_reduction,
)
from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse

NOW = '2026-10-02T15:00:00Z'


def observation(capability='quote', *, as_of=NOW, reference=False, mode='REALTIME', ttl=30000):
    return evaluate(capability=capability, source='IMP_TEST', delivery_mode=mode, now=NOW,
                    as_of=as_of, stale_after_ms=ttl, reference=reference, policy='CONTROLLED', basis='EVENT_TIME')


def candidate():
    return build_candidate({'instrument_id': 'EQ:A', 'symbol': 'A'}, [
        ('QUOTE', observation(), {'price': 123}, []),
        ('TECHNICALS', observation('bars'), {'completed_count': 10}, []),
    ], now=NOW)


def output(c):
    return {'schema_version': 'ai-screener-output/1.0.0', 'candidates': [{
        'instrument_id': c['instrument']['instrument_id'], 'rank': 1, 'rationale': 'Candidate for review based on admitted observations.',
        'supporting_refs': [e['evidence_id'] for e in c['current_market_evidence']], 'conflicting_refs': [],
        'weak_refs': [], 'missing_capabilities': [x['capability'] for x in c['missing']], 'uncertainties': ['Coverage is limited.'],
    }], 'limitations': ['Candidate reduction only.']}


class Stub:
    provider_id = 'inference.fixture'
    model_id = 'controlled.candidate.v1'
    runtime = 'FIXTURE'

    def __init__(self):
        self.calls = 0
        self.packet = None

    def infer(self, packet, *, rendered_prompt, config):
        self.calls += 1
        self.packet = packet
        return ProviderInferenceResponse(json.dumps(output(packet.candidates[0])), self.provider_id, self.model_id,
                                         tokens_input=100, tokens_output=50, latency_ms=1, simulated=True)


class AiScreenerTests(unittest.TestCase):
    def test_stale_values_removed_at_actual_cutoff(self):
        status = observation('order_flow', as_of='2026-10-02T14:59:20Z')
        status['eligible_for_current_decision'] = True
        c = build_candidate({'instrument_id': 'EQ:A'}, [('ORDER_FLOW', status, {'net_signed_volume': 987654321}, [])], now=NOW)
        self.assertNotIn('987654321', json.dumps(c))
        self.assertEqual(c['blocked'][0]['capability'], 'ORDER_FLOW')
        self.assertIn('AGE_EXCEEDS_POLICY', c['blocked'][0]['reason_codes'])

    def test_reference_separate_and_weak(self):
        c = build_candidate({'instrument_id': 'EQ:A'}, [
            ('RATES', observation('rates', reference=True, mode='PUBLICATION_BASED', ttl=None), {'yield': 4.1}, []),
        ], now=NOW)
        self.assertEqual(c['current_market_evidence'], [])
        self.assertEqual(len(c['reference_evidence']), 1)
        self.assertTrue(c['reference_evidence'][0]['weak_reasons'])

    def test_ids_stable_and_content_sensitive(self):
        self.assertEqual(candidate(), candidate())
        c = candidate()
        changed = build_candidate(c['instrument'], [('QUOTE', observation(), {'price': 124}, [])], now=NOW)
        self.assertNotEqual(c['current_market_evidence'][0]['evidence_id'], changed['current_market_evidence'][0]['evidence_id'])

    def test_valid_and_zero(self):
        c = candidate()
        self.assertIsNone(parse_reduction(json.dumps(output(c)), [c])[1])
        zero = {'schema_version': 'ai-screener-output/1.0.0', 'candidates': [], 'limitations': ['Insufficient grounding.']}
        self.assertIsNone(parse_reduction(json.dumps(zero), [c])[1])

    def test_invalid_candidates_refs_ranks_actions(self):
        c = candidate()
        for field, value in [('instrument_id', 'FAKE'), ('supporting_refs', ['EV:FAKE']), ('rank', 2),
                             ('rationale', 'buy now'), ('rationale', 'will rally'), ('rationale', 'expected return 20%'),
                             ('rationale', '"SELL"'), ('weak_refs', ['EV:FAKE'])]:
            with self.subTest(field=field, value=value):
                raw = output(c)
                raw['candidates'][0][field] = value
                self.assertIsNotNone(parse_reduction(json.dumps(raw), [c])[1])

    def test_action_language_and_conflicting_support_rejected(self):
        c = candidate()
        for text in ('Reduce the position', 'Set a stop at 100', 'Target 150'):
            raw = output(c)
            raw['candidates'][0]['rationale'] = text
            self.assertIsNotNone(parse_reduction(json.dumps(raw), [c])[1])
        raw = output(c)
        raw['candidates'][0]['conflicting_refs'] = raw['candidates'][0]['supporting_refs'][:1]
        self.assertIsNotNone(parse_reduction(json.dumps(raw), [c])[1])

    def test_excess_duplicate_malformed_and_sparse(self):
        c = candidate()
        raw = output(c)
        raw['candidates'] *= 6
        self.assertIsNotNone(parse_reduction(json.dumps(raw), [c])[1])
        self.assertIsNotNone(parse_reduction('{bad', [c])[1])
        sparse = build_candidate(c['instrument'], [], now=NOW)
        self.assertIsNotNone(parse_reduction(json.dumps(output(c)), [sparse])[1])

    def test_weak_cannot_support(self):
        c = build_candidate({'instrument_id': 'EQ:A'}, [('QUOTE', observation(), {'price': 1}, ['PARTIAL_COVERAGE'])], now=NOW)
        raw = output(c)
        self.assertIsNotNone(parse_reduction(json.dumps(raw), [c])[1])

    def test_cache_concurrency_hash_expiry_and_preview(self):
        provider = Stub()
        clock = [1790953200.0]
        reducer = CandidateReducer(provider=provider, clock=lambda: clock[0])
        scope = {'universe': 'US_EQUITIES', 'matched_count': 100, 'snapshot': 'controlled'}
        estimate = reducer.estimate(scope, [candidate()], NOW)
        self.assertEqual(provider.calls, 0)
        self.assertGreater(estimate['packet_bytes'], 0)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: reducer.reduce(scope, [candidate()], NOW), range(4)))
        self.assertEqual(provider.calls, 1)
        self.assertTrue(all(x['state'] == 'CURRENT' for x in results))
        self.assertTrue(results[0]['simulated'])
        clock[0] += 31
        self.assertFalse(reducer.estimate(scope, [candidate()], NOW)['cached'])


if __name__ == '__main__':
    unittest.main()
