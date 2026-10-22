import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.ui_api.screener_connectivity import compare_direction, ConnectivityService
from market_platform_foundation.xa01.registry import InstrumentRegistry
from market_platform_foundation.xa01.compatibility import register_future_family
from market_platform_foundation.xa04.memory import InMemoryCrossAssetCatalogRepository


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(instrument=dict(instrument_id='NVDA', asset_class='EQUITY', instrument_kind='TRADABLE_SECURITY'),
                        symbol='NVDA', sector='Technology', industry='Semiconductors', fields={})
        self.options = dict(instrument_id='NVDA', universe='US_EQUITIES', state='CURRENT_SNAPSHOT',
                            provider={'id': 'controlled'}, clock={'fetched_at': '2026-10-02T15:00:00Z'},
                            selected_expiration='2026-10-09', summary={'contracts': 5}, contracts=[])
        self.futures = dict(instrument={'instrument_id': 'NVDA'}, futures={'mapping_version': 'FUTURES_CONTEXT_MAP_V1',
                            'items': [dict(root='NQ', name='Nasdaq', contract={'state': 'UNRESOLVED'}, quote=None,
                                           relationship_reason='Technology/growth index context.', unavailable_reason='NOT_ENTITLED')]})

    def service(self, **kwargs):
        return ConnectivityService(row_getter=lambda *a: self.row, quote_getter=lambda *a: {'state': 'UNAVAILABLE', 'fields': {}},
                                   options_reader=lambda *a: self.options, futures_reader=lambda *a: self.futures,
                                   catalog=InMemoryCrossAssetCatalogRepository(), now=lambda: '2026-10-02T15:01:00Z', **kwargs)

    def test_structural_context_and_versioned_mapping_without_false_rates_edge(self):
        data = self.service().read('NVDA', 'US_EQUITIES')
        self.assertTrue(data['selected_instrument']['canonical_instrument_id'].startswith('XA01:'))
        self.assertEqual([e['relationship_class'] for e in data['edges']], ['STRUCTURAL', 'CONTEXTUAL_MAPPING'])
        self.assertEqual(data['edges'][0]['evidence_state'], 'CONTEXT_ONLY')
        self.assertEqual(data['edges'][1]['evidence_state'], 'UNAVAILABLE')
        self.assertEqual(data['edges'][1]['definition_version'], 'FUTURES_CONTEXT_MAP_V1')
        self.assertEqual(data['completeness']['domains']['BONDS_RATES']['reason'], 'NO_SUPPORTED_RELATIONSHIP')

    def test_wrong_underlying_and_unrelated_future_are_omitted(self):
        self.options['instrument_id'] = 'AAPL'
        self.futures['futures']['items'][0]['root'] = 'CL'
        data = self.service().read('NVDA', 'US_EQUITIES')
        self.assertEqual(data['edges'], [])
        self.assertEqual(data['completeness']['domains']['OPTIONS']['state'], 'UNAVAILABLE')

    def test_prior_instrument_response_is_rejected(self):
        self.futures['instrument']['instrument_id'] = 'AAPL'
        self.assertEqual(len(self.service().read('NVDA', 'US_EQUITIES')['edges']), 1)

    def test_failure_is_partial(self):
        def failure(*a):
            raise ConnectionError('offline')
        service = self.service()
        service.options_reader = failure
        data = service.read('NVDA', 'US_EQUITIES')
        self.assertEqual(data['completeness']['domains']['OPTIONS']['state'], 'UNAVAILABLE')
        self.assertTrue(data['nodes'])

    def test_future_family_reference_is_not_company_bond_edge(self):
        registry = InstrumentRegistry()
        family = register_future_family(family_root='ZN', registry=registry)
        self.row = dict(instrument=dict(instrument_id=family, asset_class='FUTURE', instrument_kind='FUTURE_FAMILY'),
                        symbol='ZN', root='ZN', fields={})
        data = self.service().read(family, 'FUTURES')
        reference = next(e for e in data['edges'] if e['relationship_type'] == 'MACRO_REFERENCE_FOR')
        self.assertEqual(reference['to_node'], family)
        self.assertTrue(all(not n['executable'] for n in data['nodes']))

    def test_source_clocks_and_bounded_payload_do_not_copy_chain(self):
        self.row['fields']['price'] = {'value': 100, 'source': 'stock', 'state': 'SNAPSHOT', 'as_of': '2026-10-02T14:00:00Z'}
        self.options['contracts'] = [{'irrelevant': i} for i in range(1000)]
        self.options['clock']['provider_as_of'] = '2026-10-02T14:50:00Z'
        self.futures['futures']['items'][0].update(
            contract={'state': 'CURRENT', 'contract_id': 'NQZ26', 'contract_month': '202612', 'last_trade_date': '2026-12-18'},
            quote={'price': 20000, 'provider': 'futures', 'state': 'DELAYED', 'as_of': '2026-10-02T14:45:00Z'})
        data = self.service().read('NVDA', 'US_EQUITIES')
        self.assertEqual(data['nodes'][0]['as_of'], '2026-10-02T14:00:00Z')
        option = next(n for n in data['nodes'] if n['domain'] == 'OPTIONS')
        self.assertEqual(option['as_of'], '2026-10-02T14:50:00Z')
        self.assertEqual(option['received_at'], '2026-10-02T15:00:00Z')
        self.assertTrue(any(n['as_of'] == '2026-10-02T14:45:00Z' for n in data['nodes']))
        self.assertNotIn('contracts', option['facts'])
        self.assertLessEqual(len(data['nodes']), 20)
        self.assertTrue(all(e['evidence_state'] not in ('CONFIRMING', 'CONFLICTING') for e in data['edges']))

    def test_catalog_pit_query_and_publication_clock(self):
        registry = InstrumentRegistry()
        family = register_future_family(family_root='ZN', registry=registry)
        self.row.update(instrument={'instrument_id': family, 'asset_class': 'FUTURE', 'instrument_kind': 'FUTURE_FAMILY'}, root='ZN')
        service = self.service()
        observation = Mock(available_time='2026-10-01T20:00:00Z', event_time='2026-10-01T00:00:00Z',
                           retrieval_time='2026-10-02T14:00:00Z', normalized_value=4.1, units='Percent', observation_id='admitted')
        observation.provenance.provider.value = 'FRED'
        catalog = Mock()
        catalog.list_cross_asset_relationships_for_target.return_value = ()
        catalog.latest_scalar_observation_as_of.return_value = observation
        service.catalog = catalog
        data = service.read(family, 'FUTURES')
        reference = next(n for n in data['nodes'] if n['instrument_kind'] == 'MACRO_INDICATOR')
        self.assertEqual(reference['state'], 'PUBLICATION_BASED')
        self.assertEqual(reference['as_of'], observation.event_time)
        self.assertEqual(reference['received_at'], observation.retrieval_time)
        self.assertIsNone(reference['canonical_instrument_id'])
        self.assertEqual(catalog.latest_scalar_observation_as_of.call_args.args[0], data['generated_at'])

    def test_bond_reference_preserves_existing_maturity_rule(self):
        self.row.update(instrument={'instrument_id': 'XA01:bond', 'asset_class': 'SOVEREIGN_DEBT', 'instrument_kind': 'SOVEREIGN_SECURITY'})
        data = self.service(rates_reader=lambda *a: {'selected': {'instrument_id': 'XA01:bond', 'reference': {
            'state': 'REFERENCE', 'curve': 'NOMINAL_PAR', 'tenor': '10Y', 'value': 4.1, 'publication_date': '2026-10-01'}}}).read('XA01:bond', 'BONDS')
        self.assertEqual(data['edges'][0]['basis'], 'NEAREST_PUBLISHED_TENOR')
        self.assertEqual(data['nodes'][1]['state'], 'PUBLICATION_BASED')
        self.assertTrue(all(not n['executable'] for n in data['nodes']))

    def test_missing_reference_does_not_erase_available_coverage(self):
        from dataclasses import replace
        from market_platform_foundation.xa02.catalog import build_catalog_relationships, bootstrap_xa_targets
        registry = InstrumentRegistry()
        family = register_future_family(family_root='ZN', registry=registry)
        self.row.update(instrument={'instrument_id': family, 'asset_class': 'FUTURE'}, root='ZN')
        reference = next(r for r in build_catalog_relationships(xa_targets=bootstrap_xa_targets(registry))
                         if r.target_xa_canonical_id == family and r.subject_type.value == 'CANONICAL_INDICATOR')
        missing = replace(reference, relationship_id='missing-reference', subject_id='US_2Y_TREASURY_YIELD')
        observation = Mock(available_time='2026-10-01T20:00:00Z', event_time='2026-10-01T00:00:00Z',
                           retrieval_time='2026-10-02T14:00:00Z', normalized_value=4.1, units='Percent', observation_id='admitted')
        observation.provenance.provider.value = 'FRED'
        for references in ((reference, missing), (missing, reference)):
            service = self.service()
            catalog = Mock()
            catalog.list_cross_asset_relationships_for_target.return_value = references
            catalog.latest_scalar_observation_as_of.side_effect = lambda *a, **kw: (
                observation if kw['canonical_indicator_id'] == reference.subject_id else None)
            service.catalog = catalog
            coverage = service.read(family, 'FUTURES')['completeness']['domains']['BONDS_RATES']
            self.assertEqual(coverage['state'], 'AVAILABLE')
            self.assertIn(missing.subject_id, coverage['missing_references'])

    def test_unknown_selection_and_unsupported_universe(self):
        service = self.service()
        service.row_getter = lambda *a: None
        self.assertIsNone(service.read('UNKNOWN_ALIAS', 'US_EQUITIES'))
        with self.assertRaises(ValueError):
            service.read('BTC', 'CRYPTO')

    def test_etf_has_structural_options_without_equity_sector_guess(self):
        self.row['instrument'].update(instrument_id='XA01:etf', asset_class='ETF_FUND')
        self.options.update(instrument_id='XA01:etf', universe='US_ETFS')
        data = self.service().read('XA01:etf', 'US_ETFS')
        self.assertEqual(len(data['edges']), 1)
        self.assertEqual(data['selected_instrument']['canonical_instrument_id'], 'XA01:etf')
        self.assertEqual(data['completeness']['domains']['FUTURES']['reason'], 'NO_SUPPORTED_RELATIONSHIP')

    def test_http_route_uses_guarded_read_scope(self):
        from market_platform_foundation.ui_api.server import UiApiHandler
        from market_platform_foundation.platform.security.route_policy import policy_for_route
        handler = object.__new__(UiApiHandler)
        handler.path = '/screener/connectivity?instrument=NVDA&universe=US_EQUITIES'
        handler._authorize_request = Mock(return_value=True)
        handler._send_json = Mock()
        service = self.service()
        with patch('market_platform_foundation.ui_api.screener_connectivity.ConnectivityService', return_value=service):
            handler.do_GET()
        self.assertEqual(handler._send_json.call_args.args[0]['instrument_id'], 'NVDA')
        self.assertEqual(policy_for_route('GET', '/screener/connectivity').capability, 'state.read')
        handler._authorize_request.return_value = False
        handler._send_json.reset_mock()
        handler.do_GET()
        handler._send_json.assert_not_called()

    def test_projected_comparison_requires_actual_window_evidence(self):
        observation = lambda value: dict(value=value, source='controlled', state='CURRENT', as_of='2026-10-02T15:01:00Z',
            window_start='2026-10-02T14:30:00Z', window_end='2026-10-02T15:01:00Z', basis='CONTROLLED_RETURN')
        service = self.service()
        service.quote_getter = lambda *a: {'fields': {}, 'return_observation': observation(2)}
        self.futures['futures']['items'][0].update(contract={'state': 'CURRENT', 'contract_id': 'NQZ26',
            'contract_month': '202612', 'last_trade_date': '2026-12-18'},
            quote={'provider': 'controlled', 'state': 'LIVE', 'return_observation': observation(-1)})
        result = service.read('NVDA', 'US_EQUITIES')
        edge = next(e for e in result['edges'] if e['relationship_class'] == 'DERIVED_COMPARISON')
        self.assertEqual(edge['evidence_state'], 'CONFLICTING')
        self.futures['futures']['items'][0]['quote']['return_observation'] = observation(1)
        self.assertTrue(any(e['evidence_state'] == 'CONFIRMING' for e in service.read('NVDA', 'US_EQUITIES')['edges']))
        self.futures['futures']['items'][0]['contract']['contract_id'] = 'CLZ26'
        self.assertFalse(any(e['relationship_class'] == 'DERIVED_COMPARISON' for e in service.read('NVDA', 'US_EQUITIES')['edges']))



class DirectionTests(unittest.TestCase):
    def test_comparison_requires_compatible_windows_and_provenance(self):
        def observation(value):
            return dict(value=value, source='controlled', state='CURRENT',
                        as_of='2026-10-02T15:00:00Z', window_start='2026-10-02T14:30:00Z',
                        window_end='2026-10-02T15:00:00Z', basis='RETURN')
        self.assertEqual(compare_direction(observation(2), observation(1))['state'], 'CONFIRMING')
        self.assertEqual(compare_direction(observation(2), observation(-1))['state'], 'CONFLICTING')
        self.assertEqual(compare_direction(observation(0), observation(1))['state'], 'UNKNOWN')
        self.assertEqual(compare_direction(observation(2), {**observation(1), 'state': 'STALE'})['state'], 'UNKNOWN')
        self.assertEqual(compare_direction(observation(2), {**observation(1), 'window_start': None})['state'], 'UNKNOWN')
        self.assertEqual(compare_direction(observation(2), {**observation(1), 'source': None})['state'], 'UNKNOWN')
        self.assertEqual(compare_direction(observation(2), None)['state'], 'UNAVAILABLE')
        self.assertEqual(compare_direction(observation(2), observation(1), cutoff='2026-10-02T16:00:00Z')['state'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
