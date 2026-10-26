"""October 15 BILLY failure: current quote/change, weak volume, no stories.

Engineering fixtures only. Real model replay/operational evidence lives separately.
"""
import json
import unittest

from market_platform_foundation.intelligence.inference.candidate_reduction import (
    build_candidate, output_schema, parse_reduction,
)
from market_platform_foundation.market_data.freshness_contract import evaluate
from tests.intelligence.test_candidate_wire_contract import pick, wire

NOW = '2026-10-15T22:10:16.177408Z'


def crypto(name='BILLY/USD'):
    def status(reference=False):
        return evaluate(capability='market_snapshot', source='KRAKEN_SPOT_PUBLIC', delivery_mode='SNAPSHOT',
            now=NOW, as_of='2026-10-15T22:10:16.131398Z', stale_after_ms=None if reference else 60000,
            policy='UNKNOWN_POLICY' if reference else 'SNAPSHOT_REFRESH_V1', basis='PROVIDER_AS_OF',
            state='AVAILABLE', reference=reference)
    return build_candidate({'instrument_id': name, 'asset_class':'CRYPTO', 'venue_id':'KRAKEN'}, [
        ('QUOTE', status(), {'price':0.001863,'bid':0.001801,'ask':0.001865}, []),
        ('TECHNICALS', status(), {'change_pct':4.194630872483218}, []),
        ('TECHNICALS', status(True), {'base_volume':340951.85151,'quote_volume':624.9124758989935,'trade_count':23.0}, []),
    ], now=NOW)


class CryptoGroundingTests(unittest.TestCase):
    def test_generation_schema_excludes_weak_volume_from_support(self):
        schema=output_schema([crypto()])['properties']['candidates']['items']['properties']
        self.assertEqual(schema['supporting_refs']['items']['enum'], [0,1])
        self.assertEqual(schema['conflicting_refs']['items']['enum'], [0,1,2])
        self.assertEqual(schema['supporting_refs']['minItems'], 1)  # Shared strict-provider grammar limit; parser requires two.

    def test_market_only_selection_passes_without_invented_news(self):
        result,reason=parse_reduction(wire(pick(0)),[crypto()])
        self.assertIsNone(reason)
        self.assertEqual(result['candidates'][0]['instrument_id'],'BILLY/USD')

    def test_original_weak_support_remains_rejected(self):
        result,reason=parse_reduction(wire(pick(0,supporting=(0,1,2))),[crypto()])
        self.assertIsNone(result)
        self.assertEqual(reason,'WEAK_OR_INSUFFICIENT_SUPPORT')

    def test_strong_support_does_not_license_absent_news_or_sentiment(self):
        for rationale in ('The admitted story cluster is reviewed.', 'FinBERT counts support review.'):
            value=pick(0); value['rationale']=rationale
            result,reason=parse_reduction(wire(value),[crypto()])
            self.assertIsNone(result)
            self.assertEqual(reason,'UNGROUNDED_NEWS_CLAIM')

    def test_missing_and_cross_instrument_references_remain_rejected(self):
        for refs,expected in (((0,),'WEAK_OR_INSUFFICIENT_SUPPORT'),((0,3),'WIRE_REFERENCE_INDEX_INVALID')):
            result,reason=parse_reduction(wire(pick(1,supporting=refs)),[crypto(),crypto('ETH/USD')])
            self.assertIsNone(result)
            self.assertEqual(reason,expected)

    def test_no_action_with_limitations_is_valid(self):
        result,reason=parse_reduction(wire(limitations=('Evidence is insufficient for a grounded review.',)),[crypto()])
        self.assertIsNone(reason)
        self.assertEqual(result['candidates'],[])
