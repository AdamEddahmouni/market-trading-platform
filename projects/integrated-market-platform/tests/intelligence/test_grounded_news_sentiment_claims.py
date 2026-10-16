"""Grounded news/sentiment attribution regressions for the local candidate-reduction wire.

Cases are derived from the 2026-10-14 19:01 UTC failure: the DELL batch cited QUOTE,
TECHNICALS and NEWS (reference_index 0,1,2) but wrote a bare sentiment claim, so the
validator rejected it (UNGROUNDED_NEWS_CLAIM). Each case pins one contract behaviour
without weakening the validator: an unsupported claim must stay rejected, an honest
no-action must stay valid, and citations must use this candidate's own indices only.
No network, no downloaded models, no synthetic passes for real gates.
"""
import json
import unittest

from market_platform_foundation.intelligence.inference.candidate_reduction import (
    SCHEMA_VERSION, build_candidate, output_schema, parse_reduction, reference_ids,
)
from market_platform_foundation.market_data.freshness_contract import evaluate
from tests.intelligence.test_ai_screener import NOW, output

FUTURE = '2026-10-02T23:00:00Z'  # after NOW: never admissible at the decision cutoff


def status(capability, *, now=NOW, as_of=None, reference=False, ttl=30000):
    return evaluate(capability=capability, source='IMP_TEST', delivery_mode='REALTIME', now=now,
                    as_of=as_of or now, stale_after_ms=ttl, reference=reference,
                    policy='CONTROLLED', basis='EVENT_TIME')


def make_candidate(*, symbol='A', now=NOW, technicals=True, news=True, sentiment=True):
    observations = [('QUOTE', status('quote'), {'price': 123.0, 'spread_pct': 0.11}, [])]
    if technicals:
        observations.append(('TECHNICALS', status('bars'), {'change_pct': 1.2, 'volume': 9000000.0}, []))
    if news:
        observations.append(('NEWS', status('news', as_of='2026-10-02T14:00:00Z', ttl=7200000),
                             {'headline': 'Published sector note', 'categories': []}, []))
    if sentiment:
        observations.append(('SENTIMENT', status('sentiment', as_of='2026-10-02T14:00:00Z', ttl=7200000),
                             {'dominant': 'NEGATIVE', 'counts': {'negative': 1, 'positive': 0, 'neutral': 0}}, []))
    return build_candidate({'instrument_id': f'EQ:{symbol}', 'symbol': symbol}, observations, now=now)


def wire_output(picks, limitations=('Candidate reduction only.',)):
    return json.dumps({'schema_version': SCHEMA_VERSION, 'candidates': list(picks),
                       'limitations': list(limitations)})


def pick(supporting, rationale, *, conflicting=(), candidate_key=0, rank=1, uncertainties=('Coverage is limited.',)):
    return {'candidate_key': candidate_key, 'rank': rank, 'rationale': rationale,
            'supporting_refs': list(supporting), 'conflicting_refs': list(conflicting),
            'uncertainties': list(uncertainties)}


class GroundedClaimTests(unittest.TestCase):
    def test_case_a_market_only_rationale_needs_no_news_citation(self):
        c = make_candidate()
        parsed, reason = parse_reduction(wire_output([pick([0, 1], 'Current quote and volume statistics support review.')]), [c])
        self.assertIsNone(reason)
        self.assertEqual(parsed['candidates'][0]['instrument_id'], 'EQ:A')

    def test_case_b_supported_news_and_sentiment_claims_pass(self):
        c, other = make_candidate(symbol='A'), make_candidate(symbol='B')
        parsed, reason = parse_reduction(wire_output([
            pick([0, 2], 'The reported note is news that matches the review basis.'),
            pick([0, 2, 3], 'News coverage is cited together with the negative FinBERT sentiment counts.',
                 candidate_key=1, rank=2),
        ]), [c, other])
        self.assertIsNone(reason)
        self.assertEqual([p['rank'] for p in parsed['candidates']], [1, 2])

    def test_case_c_unsupported_news_wording_rejected(self):
        c = make_candidate()
        for rationale in ('A headline catalyst stands out for review.',
                          'Breaking stories describe the sector, supporting review.'):
            with self.subTest(rationale=rationale):
                self.assertEqual(parse_reduction(wire_output([pick([0, 1], rationale)]), [c])[1],
                                 'UNGROUNDED_NEWS_CLAIM')

    def test_case_d_bare_sentiment_claim_without_sentiment_ref_rejected(self):
        # Exact 2026-10-14 DELL shape: news cited, sentiment asserted without the SENTIMENT index.
        c = make_candidate()
        self.assertEqual(parse_reduction(wire_output([
            pick([0, 1, 2], 'The sentiment is negative, and the news is negative, aligning with the observed direction.'),
        ]), [c])[1], 'UNGROUNDED_NEWS_CLAIM')

    def test_case_e_future_evidence_is_blocked_and_unshowable(self):
        c = build_candidate({'instrument_id': 'EQ:A', 'symbol': 'A'}, [
            ('QUOTE', status('quote'), {'price': 123.0}, []),
            ('TECHNICALS', status('bars', as_of=FUTURE), {'change_pct': 1.2}, []),
        ], now=NOW)
        self.assertFalse(any(e['as_of'] == FUTURE for e in (*c['current_market_evidence'], *c['reference_evidence'])))
        self.assertFalse(any(e['capability'] == 'TECHNICALS' for e in (*c['current_market_evidence'], *c['reference_evidence'])))
        # With the future technicals blocked, the candidate no longer clears sufficiency:
        # it cannot be selected, and it was never showable at the decision cutoff.
        self.assertEqual(parse_reduction(json.dumps(output(c)), [c])[1], 'INSUFFICIENT_EVIDENCE')

    def test_case_f_unrelated_evidence_identity_rejected(self):
        a, b = make_candidate(symbol='A'), make_candidate(symbol='B')
        foreign = a['current_market_evidence'][0]['evidence_id']
        value = output(b)
        value['candidates'][0]['supporting_refs'].append(foreign)
        self.assertEqual(parse_reduction(json.dumps(value), [a, b])[1], 'UNKNOWN_OR_UNRELATED_REF')
        # Wire shape: candidate B has only its own two evidence items; index 2 exists only in A's list.
        b_small = make_candidate(symbol='B', technicals=False, news=False, sentiment=False)
        self.assertEqual(
            parse_reduction(wire_output([pick([0, 2], 'Grounded in current market data.', candidate_key=1)]), [a, b_small])[1],
            'WIRE_REFERENCE_INDEX_INVALID')

    def test_case_g_honest_no_action_stays_valid_and_needs_limitations(self):
        c = make_candidate()
        parsed, reason = parse_reduction(wire_output([], limitations=['No candidate has admissible additional evidence.']), [c])
        self.assertIsNone(reason)
        self.assertEqual(parsed['candidates'], [])
        self.assertEqual(parse_reduction(wire_output([], limitations=()), [c])[1], 'INVALID_LIMITATIONS')

    def test_case_h_schema_remains_representable_and_compact_under_context_pressure(self):
        c = make_candidate()
        schema = output_schema([c])
        ids = reference_ids(c)
        enum = schema['properties']['candidates']['items']['properties']['supporting_refs']['items']['enum']
        self.assertEqual(enum, list(range(len(ids))))
        from market_platform_foundation.intelligence.inference.prompts import PromptRegistry
        prompt = PromptRegistry().get_by_id('screener.ai_candidate_reduction.v3')
        # The revised v3 wording must keep the journaled 2026-10-14 DELL batch inside the exact
        # local gate: that packet measured 4594 exact input tokens with v3.0.0 against the
        # 8192-token window with a 2600-token output allowance.
        self.assertLess(len(prompt.template.encode('utf-8')), 6600)
        self.assertEqual(prompt.version, '3.4.1')


class ReductionContractTests(unittest.TestCase):
    def test_unsupported_certainty_and_actions_still_rejected(self):
        c = make_candidate()
        for rationale in ('It will rise. Guaranteed.', 'Buy this candidate now.'):
            with self.subTest(rationale=rationale):
                reason = parse_reduction(wire_output([pick([0, 1, 2], rationale)]), [c])[1]
                self.assertEqual(reason, 'UNSUPPORTED_CERTAINTY_OR_ACTION')

    def test_selected_output_binds_all_weak_refs_and_missing_capabilities(self):
        c = make_candidate()
        weak = sorted(e['evidence_id'] for e in (*c['current_market_evidence'], *c['reference_evidence']) if e['weak_reasons'])
        parsed, reason = parse_reduction(wire_output([pick([0, 1], 'Market statistics only.')]), [c])
        self.assertIsNone(reason)
        self.assertEqual(sorted(parsed['candidates'][0]['weak_refs']), weak)
        self.assertEqual(sorted(parsed['candidates'][0]['missing_capabilities']),
                         sorted(x['capability'] for x in c['missing']))


if __name__ == '__main__':
    unittest.main()
