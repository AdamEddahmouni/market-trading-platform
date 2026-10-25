"""Opportunity shortlist score and cut: bounded parts, no invented inputs, deterministic order. Pure, no provider."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.inference import opportunity_shortlist as shortlist
from market_platform_foundation.intelligence.inference.coverage_plan import BUCKETS, NOT_SHORTLISTED, fair_order

NOW = '2026-10-02T15:00:00Z'


def evidence(capability: str, facts: dict, *, as_of: str = NOW, weak: list[str] | None = None,
             source: str = 'MOOMOO_OPEND_SNAPSHOT') -> dict:
    return {'capability': capability, 'facts': facts, 'as_of': as_of, 'weak_reasons': weak or [], 'source': source}


def candidate(*, price=50.0, change=None, volume=None, rel=None, spread=None, as_of=NOW, news=(), universe='US_EQUITIES') -> dict:
    quote = {'price': price}
    if spread is not None:
        quote['spread_pct'] = spread
    technical = {name: value for name, value in (('change_pct', change), ('volume', volume), ('rel_volume', rel)) if value is not None}
    current = [evidence('QUOTE', quote, as_of=as_of)]
    if technical:
        current.append(evidence('TECHNICALS', technical, as_of=as_of))
    return {'instrument': {'instrument_id': 'EQ:X', 'universe': universe}, 'current_market_evidence': current,
            'reference_evidence': [evidence('NEWS', {'headline': 'h'}, weak=list(w)) for w in news]}


class ScoreTests(unittest.TestCase):
    def test_every_part_is_bounded_and_the_total_is_at_most_100(self):
        top = shortlist.score(candidate(change=-40.0, volume=1e9, rel=30.0, spread=0.0, news=([], [], [])), now=NOW)
        self.assertEqual(top['parts'], {'movement': 25.0, 'volume': 25.0, 'tradability': 20.0, 'catalyst': 20.0, 'freshness': 10.0})
        self.assertEqual(top['total'], 100.0)
        self.assertEqual(top['missing'], [])

    def test_the_rules_score_what_they_say(self):
        value = shortlist.score(candidate(change=4.0, volume=200_000, price=50.0, rel=2.0, spread=0.2, news=([], ['DELAYED_OR_STALE_PROVIDER'])),
                                now='2026-10-02T15:00:30Z')
        # 4% move; 2x volume; $10M traded and a 0.2% spread; one current and one delayed story; a 30 s old quote.
        self.assertEqual(value['parts'], {'movement': 10.0, 'volume': 10.0, 'tradability': 10.5, 'catalyst': 15.0, 'freshness': 5.0})

    def test_a_missing_input_scores_zero_and_is_named(self):
        value = shortlist.score(candidate(price=50.0, as_of=None), now=NOW)
        self.assertEqual(value['total'], 0.0)
        self.assertEqual(value['missing'], ['change_pct', 'rel_volume', 'dollar_volume', 'spread_pct', 'news', 'quote_age'])
        self.assertIsNone(value['floor_reason'])

    def test_weak_evidence_is_not_read(self):
        weak = candidate(change=9.0)
        weak['current_market_evidence'][1]['weak_reasons'] = ['STALE']
        self.assertEqual(shortlist.score(weak, now=NOW)['parts']['movement'], 0.0)

    def test_relative_volume_falls_back_to_the_screener_row_and_says_so(self):
        row = {'fields': {'rel_volume': {'value': 3.0}}}
        value = shortlist.score(candidate(change=1.0), row, now=NOW)
        self.assertEqual((value['parts']['volume'], value['basis']['rel_volume']), (15.0, 'SCREENER_REFERENCE'))
        admitted = shortlist.score(candidate(change=1.0, rel=1.0), row, now=NOW)
        self.assertEqual((admitted['parts']['volume'], admitted['basis']['rel_volume']), (5.0, 'ADMITTED_EVIDENCE'))

    def test_the_snapshot_is_read_before_another_source(self):
        mixed = candidate(change=2.0)
        mixed['current_market_evidence'].insert(0, evidence('TECHNICALS', {'change_pct': 10.0}, source='FINVIZ'))
        self.assertEqual(shortlist.score(mixed, now=NOW)['parts']['movement'], 5.0)

    def test_the_tradability_floor(self):
        self.assertEqual(shortlist.score(candidate(price=0.5, volume=1e8), now=NOW)['floor_reason'], shortlist.BELOW_TRADABILITY_FLOOR)
        self.assertEqual(shortlist.score(candidate(price=10.0, volume=50_000), now=NOW)['floor_reason'], shortlist.BELOW_TRADABILITY_FLOOR)
        self.assertIsNone(shortlist.score(candidate(price=10.0, volume=200_000), now=NOW)['floor_reason'])
        # Crypto trades below a dollar; only its traded value is floored.
        self.assertIsNone(shortlist.score(candidate(price=0.5, volume=1e8, universe='CRYPTO'), now=NOW)['floor_reason'])


class ShortlistTests(unittest.TestCase):
    def test_highest_totals_first_ties_in_fair_order_floor_excluded(self):
        scored = {f'EQ:{n}': {'total': total, 'floor_reason': None} for n, total in (('A', 10.0), ('B', 30.0), ('C', 10.0), ('D', 10.0))}
        scored['EQ:E'] = {'total': 99.0, 'floor_reason': shortlist.BELOW_TRADABILITY_FLOOR}
        ties = [key for key in fair_order('set-1', list(scored)) if key in ('EQ:A', 'EQ:C', 'EQ:D')]
        self.assertEqual(shortlist.shortlist(scored, size=3, salt='set-1'), ['EQ:B', *ties[:2]])
        self.assertEqual(shortlist.shortlist(scored, size=3, salt='set-1'), shortlist.shortlist(dict(reversed(scored.items())), size=3, salt='set-1'))
        self.assertEqual(shortlist.shortlist(scored, size=0, salt='set-1'), [])

    def test_news_is_read_only_where_a_full_catalyst_could_reach_the_shortlist(self):
        def value(total, catalyst=0.0, floor=None):
            return {'total': total, 'parts': {'catalyst': catalyst}, 'floor_reason': floor}
        scored = {'EQ:A': value(50.0), 'EQ:B': value(40.0), 'EQ:C': value(25.0), 'EQ:D': value(15.0),
                  'EQ:E': value(60.0, floor=shortlist.BELOW_TRADABILITY_FLOOR), 'EQ:F': value(45.0, catalyst=20.0)}
        # Size 2: the cut is 45. C (25 + 20) can still reach it; D (15 + 20) cannot; E is floored; F already has news.
        reach, capped = shortlist.news_reach(scored, size=2, salt='s', unread={'EQ:A', 'EQ:B', 'EQ:C', 'EQ:D', 'EQ:E'})
        self.assertEqual((reach, capped), (['EQ:A', 'EQ:B', 'EQ:C'], False))
        flat = {f'EQ:{n}': value(10.0) for n in range(40)}
        reach, capped = shortlist.news_reach(flat, size=2, salt='s', unread=set(flat))
        self.assertEqual((len(reach), capped), (2 * shortlist.NEWS_READ_FACTOR, True))

    def test_size_is_sized_to_the_engine_and_the_override_is_bounded(self):
        self.assertEqual(shortlist.size_for('LOCAL_MODEL', environ={}), 20)
        self.assertEqual(shortlist.size_for('PAID_API', environ={}), 50)
        self.assertEqual(shortlist.size_for('LOCAL_MODEL', environ={'IMP_AI_SCREENER_SHORTLIST_SIZE': '7'}), 7)
        for bad in ('0', '201', 'x', '-1'):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'SHORTLIST_SIZE_INVALID'):
                shortlist.size_for('LOCAL_MODEL', environ={'IMP_AI_SCREENER_SHORTLIST_SIZE': bad})

    def test_on_by_default_and_off_only_when_switched_off(self):
        self.assertTrue(shortlist.enabled(environ={}))
        self.assertTrue(shortlist.enabled(environ={'IMP_AI_SCREENER_SHORTLIST': '1'}))
        self.assertFalse(shortlist.enabled(environ={'IMP_AI_SCREENER_SHORTLIST': '0'}))

    def test_a_screened_out_row_is_accounted_as_not_sent(self):
        self.assertEqual(BUCKETS[NOT_SHORTLISTED], 'ineligible')


if __name__ == '__main__':
    unittest.main()
