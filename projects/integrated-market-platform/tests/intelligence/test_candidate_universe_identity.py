"""Candidates carry the screener universe that the Paper policy gate and the crypto handoff read."""

import copy
import unittest

from market_platform_foundation.intelligence.inference.paper_automation import decision_permitted
from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
from tests.support.coverage_universe import NOW, NOW_ISO, News, PagingReader, row


def _policy(*universes):
    return dict(risk=dict(allow_entries=True, allow_long=True, allow_short=False, allowed_universes=list(universes)))


def _enter(instrument):
    return dict(action_state='ENTER', direction='LONG', instrument=instrument)


class CandidateUniverseIdentityTests(unittest.TestCase):
    def setUp(self):
        self.service = ScreenerAiService(reader=PagingReader([]), news=News(None), clock=lambda: NOW)

    def _candidate(self, universe, source_row):
        self.assertNotIn('universe', source_row['instrument'])  # the production provider shape
        candidates, _ = self.service._candidates(universe, {}, [source_row], market=None, now=NOW_ISO, include_flow=False)
        return candidates[0]

    def test_equity_candidate_carries_its_universe_through_the_policy_gate(self):
        source = copy.deepcopy(row(0))
        # screener_projections emits equity identity without a universe; the shared fixture adds one.
        source['instrument'] = {'instrument_id': source['instrument']['instrument_id'], 'venue_id': 'XNYS',
                                'asset_class': 'EQUITY', 'instrument_kind': 'TRADABLE_SECURITY'}
        candidate = self._candidate('US_EQUITIES', source)
        self.assertEqual(candidate['instrument']['universe'], 'US_EQUITIES')
        self.assertIsNone(decision_permitted(_policy('US_EQUITIES', 'CRYPTO'), _enter(candidate['instrument'])))
        self.assertEqual(decision_permitted(_policy('CRYPTO'), _enter(candidate['instrument'])),
                         'AUTOMATION_INSTRUMENT_NOT_ALLOWED')

    def test_crypto_candidate_carries_its_universe_through_the_policy_gate(self):
        source = copy.deepcopy(row(0))
        source['instrument'] = {'instrument_id': source['instrument']['instrument_id'], 'venue_id': 'KRAKEN',
                                'asset_class': 'CRYPTO', 'instrument_kind': 'CRYPTO_PAIR', 'tradability': 'DISCOVERY_ONLY'}
        candidate = self._candidate('CRYPTO', source)
        self.assertEqual(candidate['instrument']['universe'], 'CRYPTO')
        self.assertIsNone(decision_permitted(_policy('US_EQUITIES', 'CRYPTO'), _enter(candidate['instrument'])))
        self.assertEqual(decision_permitted(_policy('US_EQUITIES'), _enter(candidate['instrument'])),
                         'AUTOMATION_INSTRUMENT_NOT_ALLOWED')

    def test_missing_universe_still_fails_closed(self):
        self.assertEqual(decision_permitted(_policy('US_EQUITIES', 'CRYPTO'), _enter({'instrument_id': 'X'})),
                         'AUTOMATION_INSTRUMENT_NOT_ALLOWED')


if __name__ == '__main__':
    unittest.main()
