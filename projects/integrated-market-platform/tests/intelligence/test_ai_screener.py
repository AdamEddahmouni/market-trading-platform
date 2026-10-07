import json
import copy
from types import SimpleNamespace
import unittest
from concurrent.futures import ThreadPoolExecutor

from market_platform_foundation.market_data.freshness_contract import evaluate
from market_platform_foundation.intelligence.inference.candidate_reduction import (
    build_candidate, CandidateReducer, parse_reduction, output_schema, MAX_INTAKE,
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
    def test_strict_scalar_lists_decode_to_canonical_arrays_and_still_validate(self):
        c = candidate()
        value = output(c)
        for field in ('missing_capabilities', 'weak_refs'):
            value['candidates'][0][field] = json.dumps(value['candidates'][0][field])
        parsed, reason = parse_reduction(json.dumps(value), [c])
        self.assertIsNone(reason)
        self.assertEqual(parsed, output(c))
        value['candidates'][0]['missing_capabilities'] = '[]'
        self.assertEqual(parse_reduction(json.dumps(value), [c])[1], 'MISSING_EVIDENCE_MISMATCH')
        value['candidates'][0]['missing_capabilities'] = 'not JSON'
        self.assertEqual(parse_reduction(json.dumps(value), [c])[1], 'SCHEMA_INVALID')

    def test_explicit_run_acquires_provider_clocked_direction_preview_is_cache_only(self):
        from tests.platform.test_screener_s18 import Reader, News, row
        from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
        sequence = []
        class Snapshots:
            calls = 0
            cached = None
            observed = NOW
            def latest(self): return self.cached
            def current(self, rows, *, catalog_as_of, force):
                sequence.append('market')
                self.calls += 1
                self.cached = SimpleNamespace(catalog_as_of=catalog_as_of, as_of=NOW,
                    row_as_of={'EQ:A': self.observed},
                    values={'EQ:A': {'price': 123, 'volume': 100, 'change_pct': 2.0}})
                return self.cached, None
        snapshots = Snapshots()
        source = row()
        source['fields']['change_pct'] = {'value': 999, 'source': 'FINVIZ_ELITE', 'state': 'SNAPSHOT'}
        news = News(Stub())
        news.candidate_evidence = lambda **kwargs: sequence.append('news') or {}
        service = ScreenerAiService(reader=Reader([source]), news=news, clock=lambda: 1790953200.0)
        service._market_snapshots = snapshots
        service.preview({'universe': 'US_EQUITIES'})
        self.assertEqual(snapshots.calls, 0)
        _, evidence, _, _ = service._packet({'universe': 'US_EQUITIES'}, refresh_news=True)
        self.assertEqual(snapshots.calls, 1)
        self.assertEqual(sequence[-2:], ['news', 'market'])
        direction = [e for e in evidence[0]['current_market_evidence'] if e['source'] == 'MOOMOO_OPEND_SNAPSHOT' and 'change_pct' in e['facts']]
        self.assertEqual(direction[0]['facts']['change_pct'], 2.0)
        self.assertEqual(direction[0]['facts']['change_basis'], 'PREVIOUS_CLOSE')
        self.assertEqual(direction[0]['as_of'], NOW)
        self.assertNotIn('999', json.dumps(evidence))
        service.preview({'universe': 'US_EQUITIES'})
        self.assertEqual(snapshots.calls, 1)
        snapshots.observed = '2026-10-02T14:58:00Z'
        _, stale, _, _ = service._packet({'universe': 'US_EQUITIES'}, refresh_news=True)
        self.assertFalse(any(e['source'] == 'MOOMOO_OPEND_SNAPSHOT' for e in stale[0]['current_market_evidence']))
        self.assertTrue(any('AGE_EXCEEDS_POLICY' in b['reason_codes'] for b in stale[0]['blocked']))

    def test_model_schema_binds_missing_capabilities_and_refs_to_each_instrument(self):
        a = candidate()
        b = build_candidate({'instrument_id': 'EQ:B'}, [
            ('QUOTE', observation(), {'price': 42}, []),
            ('TECHNICALS', observation('bars'), {'volume': 100}, []),
            ('NEWS', observation('news', reference=True), {'story_id': 'controlled'}, []),
        ], now=NOW)
        schema = output_schema([a, b])['properties']['candidates']['items']
        choices = schema.get('anyOf', [schema])
        self.assertEqual(len(choices), 2, 'The model must choose one instrument-specific contract')
        for c, choice in zip((a, b), choices):
            props = choice['properties']
            self.assertEqual(props['instrument_id']['enum'], [c['instrument']['instrument_id']])
            self.assertEqual(props['missing_capabilities']['type'], 'string')
            self.assertEqual(json.loads(props['missing_capabilities']['const']), sorted({m['capability'] for m in c['missing']}))
            self.assertEqual(set(props['supporting_refs']['items']['enum']),
                             {e['evidence_id'] for e in (*c['current_market_evidence'], *c['reference_evidence'])})

    def test_unselected_short_deadline_does_not_expire_fresh_selected_support(self):
        fresh = candidate()
        old = build_candidate({'instrument_id': 'EQ:B'}, [
            ('QUOTE', observation(as_of='2026-10-02T14:59:35Z'), {'price': 1}, []),
            ('TECHNICALS', observation('bars', as_of='2026-10-02T14:59:35Z'), {'volume': 100}, []),
        ], now=NOW)
        clock = [1790953200.0]
        class Slow(Stub):
            def infer(self, packet, *, rendered_prompt, config):
                clock[0] += 20
                return super().infer(packet, rendered_prompt=rendered_prompt, config=config)
        result = CandidateReducer(provider=Slow(), clock=lambda: clock[0]).reduce({}, [fresh, old], NOW)
        self.assertEqual(result['state'], 'CURRENT')
        self.assertEqual(result['valid_until'], '2026-10-02T15:00:30Z')

    def test_missing_mismatch_is_rejected_and_has_bounded_diagnostic(self):
        class Wrong(Stub):
            def infer(self, packet, *, rendered_prompt, config):
                value = output(packet.candidates[0])
                value['candidates'][0]['missing_capabilities'] = []
                return ProviderInferenceResponse(json.dumps(value), self.provider_id, self.model_id)
        c = candidate()
        result = CandidateReducer(provider=Wrong(), clock=lambda: 1790953200.0).reduce({}, [c], NOW)
        self.assertEqual((result['state'], result['reason'], result['candidates']),
                         ('INVALID_OUTPUT', 'MISSING_EVIDENCE_MISMATCH', []))
        self.assertEqual(result['validation']['instrument_id'], 'EQ:A')
        self.assertEqual(result['validation']['expected_missing'], sorted({m['capability'] for m in c['missing']}))
        self.assertEqual(result['validation']['declared_missing'], [])
        self.assertNotIn('raw_text', result)

    def test_broader_intake_fits_and_remains_bounded(self):
        self.assertEqual(MAX_INTAKE, 50)
        candidates = [build_candidate({'instrument_id': f'EQ:{i}'}, [
            ('QUOTE', observation(), {'price': 123}, []),
            ('TECHNICALS', observation('bars'), {'volume': 100}, []),
        ], now=NOW) for i in range(MAX_INTAKE)]
        reducer = CandidateReducer(provider=Stub(), clock=lambda: 1790953200.0)
        self.assertEqual(reducer.estimate({}, candidates, NOW)['intake_count'], 50)
        with self.assertRaisesRegex(ValueError, 'INTAKE_BOUND_EXCEEDED'):
            reducer.reduce({}, candidates + [copy.deepcopy(candidates[0])], NOW)

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
