import unittest
from datetime import UTC, datetime
from market_platform_foundation.market_data.freshness_contract import evaluate, eligible_evidence
from market_platform_foundation.ui_api.screener_freshness import project_screener_response
from market_platform_foundation.market_data.current_bars import freshness

NOW = '2026-10-02T18:32:00Z'

class DecisionFreshnessTests(unittest.TestCase):
    def test_delivery_is_separate_from_age_and_admissibility(self):
        for mode, expected in [('REALTIME', 'ADMISSIBLE'), ('DELAYED', 'DEGRADED'), ('SNAPSHOT', 'ADMISSIBLE')]:
            with self.subTest(mode=mode):
                result = evaluate(capability='quote', source='provider', delivery_mode=mode, as_of='2026-10-02T18:31:45Z', now=NOW, stale_after_ms=60000, policy='quote/v1', basis='PROVIDER_AS_OF')
                self.assertEqual(result['freshness_status'], 'CURRENT')
                self.assertEqual(result['decision_admissibility'], expected)
                self.assertEqual(result['eligible_for_current_decision'], mode != 'DELAYED')

    def test_stale_and_unknown_fail_closed(self):
        for fields, reason in [({'as_of':'2026-10-02T18:30:00Z','stale_after_ms':60000}, 'AGE_EXCEEDS_POLICY'), ({'as_of':None,'stale_after_ms':60000}, 'NO_OBSERVATION_TIME'), ({'as_of':NOW}, 'UNKNOWN_FRESHNESS_POLICY'), ({'as_of':'2026-10-03T18:32:00Z','stale_after_ms':60000}, 'FUTURE_OBSERVATION_TIME')]:
            result = evaluate(capability='quote', source='provider', delivery_mode='REALTIME', now=NOW, policy='quote/v1', basis='PROVIDER_AS_OF', **fields)
            self.assertFalse(result['eligible_for_current_decision'])
            self.assertIn(reason, result['reason_codes'])

    def test_publication_with_unknown_cadence_can_only_be_reference(self):
        result = evaluate(capability='rates', source='Treasury', delivery_mode='PUBLICATION_BASED', as_of='2026-10-01', now=NOW, policy='publication/unknown', basis='OBSERVATION_DATE', reference=True)
        self.assertEqual(result['freshness_status'], 'UNKNOWN')
        self.assertTrue(result['eligible_for_reference'])
        self.assertFalse(result['eligible_for_current_decision'])

    def test_source_authority_and_closed_session(self):
        for state, status in [('STALE','STALE'), ('UNAVAILABLE','UNAVAILABLE'), ('SESSION_CLOSED','SESSION_CLOSED')]:
            result = evaluate(capability='flow', source='provider', delivery_mode='REALTIME', as_of=NOW, now=NOW, stale_after_ms=30000, policy='flow/v1', basis='EVENT_TIME', state=state)
            self.assertEqual(result['freshness_status'],status)
            self.assertFalse(result['eligible_for_current_decision'])

    def test_reference_publication_authority(self):
        result = evaluate(capability='short_interest', source='FINRA', delivery_mode='PUBLICATION_BASED', as_of='2026-09-15', now=NOW, policy='FINRA_PUBLICATION', basis='PUBLICATION_DATE', state='PUBLICATION_CURRENT', reference=True)
        self.assertEqual(result['freshness_status'],'CURRENT')
        self.assertTrue(result['eligible_for_reference'])
        self.assertFalse(result['eligible_for_current_decision'])

    def test_maturity_is_never_freshness_and_fetch_never_realtime(self):
        payload = {'schema_version':'screener-bond-preview/1.0.0','generated_at':NOW, 'market_session':'PUBLICATION_BASED', 'instrument':{'instrument_id':'bond', 'maturity':'2027-02-15'}, 'sections':[{'id':'market','items':[{'id':'yield','label':'Auction yield','value':4.2,'source':'Treasury','as_of':'2026-09-30','class':'OBSERVED'}]}]}
        result = project_screener_response('/screener/preview', payload, now=NOW)
        evidence = result['decision_inputs'][0]
        self.assertEqual(evidence['as_of'],'2026-09-30')
        self.assertEqual(evidence['delivery_mode'],'PUBLICATION_BASED')
        self.assertNotIn('2027-02-15', str(result['decision_inputs']))
        self.assertFalse(evidence['eligible_for_current_decision'])

    def test_recent_fetch_does_not_rescue_old_option_snapshot(self):
        payload = {'state':'STALE', 'provider':{'id':'Finviz','delivery':'SNAPSHOT'},'clock':{'fetched_at':NOW,'provider_as_of':'2026-10-01T12:00:00Z','latest_contract_trade_at':'2026-09-30T12:00:00Z','stale_after_s':600},'underlying':{'as_of':'2026-10-02T18:31:55Z'}}
        result = project_screener_response('/screener/options',payload,now=NOW)
        evidence = result['decision_inputs'][0]
        self.assertEqual(evidence['freshness_status'],'STALE')
        self.assertEqual(evidence['fetched_at'],NOW)
        self.assertEqual(evidence['provider_as_of'],payload['clock']['provider_as_of'])
        self.assertEqual(evidence['latest_trade_at'],payload['clock']['latest_contract_trade_at'])
        self.assertEqual(result['underlying'],payload['underlying'])

    def test_completed_bar_timeframe(self):
        ns=lambda text: int(datetime.fromisoformat(text.replace('Z','+00:00')).timestamp()*1e9)
        self.assertEqual(freshness(ns('2026-10-02T18:30:00Z'),now_ns=ns('2026-10-02T18:34:00Z'),scope='RTH',timeframe='5m')[0],'CURRENT')
        self.assertEqual(freshness(ns('2026-10-02T18:30:00Z'),now_ns=ns('2026-10-02T18:42:00Z'),scope='RTH',timeframe='5m')[0],'STALE')

    def test_filter_retains_valid_lane_only(self):
        current=evaluate(capability='quote',source='p',delivery_mode='REALTIME',as_of=NOW,now=NOW,stale_after_ms=60000,policy='q',basis='EVENT_TIME')
        stale=evaluate(capability='flow',source='p',delivery_mode='REALTIME',as_of='2026-10-02T18:30:00Z',now=NOW,stale_after_ms=30000,policy='f',basis='EVENT_TIME')
        self.assertEqual(eligible_evidence([current,stale], now=NOW),[current])

    def test_cached_booleans_rechecked_at_cutoff(self):
        item=evaluate(capability='quote',source='p',delivery_mode='REALTIME',as_of=NOW,now=NOW,stale_after_ms=60000,policy='q',basis='EVENT_TIME')
        self.assertEqual(eligible_evidence([item],now='2026-10-02T18:34:00Z'),[])

    def test_direction_requires_fresh_source_not_healthy_feed(self):
        from market_platform_foundation.ui_api.screener_connectivity import compare_direction
        item={'state':'CURRENT','source':'p','as_of':'2026-10-02T18:31:55Z','window_start':'2026-10-02T18:31:00Z','window_end':'2026-10-02T18:31:55Z','basis':'RETURN_1M','value':1,'decision_evidence':{'eligible_for_current_decision':False,'freshness_status':'STALE'}}
        self.assertEqual(compare_direction(item,item,cutoff=NOW)['state'],'UNKNOWN')
    def test_symbol_silence_blocks_flow_even_if_feed_is_healthy(self):
        from market_platform_foundation.ui_api.screener_specialist import ScreenerSpecialistService
        service=object.__new__(ScreenerSpecialistService)
        service._session=lambda:'REGULAR'
        service._feed_silent=lambda runtime:False
        service._now_ns=lambda:int(datetime.fromisoformat(NOW.replace('Z','+00:00')).timestamp()*1e9)
        old=service._now_ns()-31_000_000_000
        self.assertEqual(service._live_state(None,True,latest_event_ns=old)[0],'STALE')
        self.assertEqual(service._live_state(None,False)[1],'AWAITING_DATA')

    def test_cutoff_cannot_precede_evidence_evaluation(self):
        item=evaluate(capability='quote',source='p',delivery_mode='REALTIME',as_of='2026-10-02T18:31:55Z',now=NOW,stale_after_ms=60000)
        self.assertEqual(eligible_evidence([item],now='2026-10-02T18:31:56Z'),[])

    def test_row_mixed_clocks_and_states_are_not_collapsed(self):
        payload={'rows':[{'fields':{'price':{'value':12,'state':'LIVE','source':'p','as_of':NOW},'volume':{'value':None,'state':'UNAVAILABLE','source':'p','as_of':NOW},'change_pct':{'value':2,'state':'STALE','source':'p','as_of':'2026-10-01T18:32:00Z'}}}]}
        result=project_screener_response('/screener',payload,now=NOW)
        self.assertEqual([i['freshness_status'] for i in result['rows'][0]['decision_inputs']],['CURRENT','UNAVAILABLE','STALE'])
        self.assertNotIn('decision_inputs',payload['rows'][0])

    def test_expired_future_contract_cannot_be_admitted_as_reference(self):
        payload={'futures':{'items':[{'root':'ES','contract':{'state':'EXPIRED'},'quote':{'state':'LIVE','provider':'p','as_of':NOW}}]}}
        evidence=project_screener_response('/screener/futures-context',payload,now=NOW)['decision_inputs'][0]
        self.assertFalse(evidence['eligible_for_reference'])
        self.assertEqual(evidence['freshness_status'],'UNAVAILABLE')

    def test_partial_book_cannot_confirm_current_liquidity(self):
        evidence=evaluate(capability='level2',source='p',delivery_mode='REALTIME',as_of=NOW,now=NOW,stale_after_ms=5000,state='PARTIAL')
        self.assertFalse(evidence['eligible_for_current_decision'])
        self.assertIn('INSUFFICIENT_SOURCE_EVIDENCE',evidence['reason_codes'])

    def test_missing_price_blocks_quote_despite_fresh_clock(self):
        payload={'quotes':{'AAPL':{'state':'LIVE','fields':{'price':{'value':None,'source':'p','provider_as_of':NOW}}}}}
        evidence=project_screener_response('/screener/window',payload,now=NOW)['quotes']['AAPL']['decision_inputs'][0]
        self.assertEqual(evidence['freshness_status'],'UNAVAILABLE')
        self.assertFalse(evidence['eligible_for_current_decision'])

    def test_row_preserves_event_clocks_and_covered_fields(self):
        now_ns=int(datetime.fromisoformat(NOW.replace('Z','+00:00')).timestamp()*1e9)
        payload={'rows':[{'fields':{'price':{'value':12,'state':'LIVE','source':'p','event_time_ns':now_ns,'as_of':NOW},'volume':{'value':100,'state':'LIVE','source':'p','event_time_ns':now_ns-120_000_000_000,'as_of':NOW}}}]}
        evidence=project_screener_response('/screener',payload,now=NOW)['rows'][0]['decision_inputs']
        self.assertEqual([item['freshness_status'] for item in evidence],['CURRENT','STALE'])
        self.assertEqual([item['covered_fields'] for item in evidence],[['price'],['volume']])
