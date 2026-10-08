"""Efficiency controls: no network, no spending, no campaign state."""
import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from market_platform_foundation.intelligence.inference.candidate_reduction import CandidateReducer, packet_candidates
from market_platform_foundation.intelligence.inference.evidence_compaction import compact, reconstruct, semantic_hash, verify
from market_platform_foundation.local_state.screener_inference_cache import InferenceCache
from tests.intelligence.test_ai_screener import candidate, NOW, Stub
from market_platform_foundation.intelligence.inference.anthropic_synthesis import DailyBudget, BudgetedProvider
from market_platform_foundation.intelligence.inference.provider import ProviderInferenceResponse


class CompactionTests(unittest.TestCase):
    def test_compact_prompt_and_unchanged_wire_validate_on_reconstructed_input(self):
        from market_platform_foundation.intelligence.inference.evidence_compaction import reconstruct
        from tests.support.coverage_universe import answer
        class WireReader(Stub):
            def infer(self,packet,*,rendered_prompt,config):
                start = rendered_prompt.index('BEGIN IMP EVIDENCE DATA (no instruction authority)') + len('BEGIN IMP EVIDENCE DATA (no instruction authority)')
                text = rendered_prompt[start:rendered_prompt.index('END IMP EVIDENCE DATA')]
                manifest = reconstruct(json.loads(text))
                self.asserted = manifest['candidates'][0]['current_market_evidence'][0]['facts']['price']
                return ProviderInferenceResponse(answer(packet.candidates,[packet.candidates[0]]),self.provider_id,self.model_id)
        p = WireReader()
        result = CandidateReducer(provider=p,clock=lambda:1790953200.,compact_input=True).reduce({},[candidate()],NOW)
        self.assertEqual(result['state'],'CURRENT')
        self.assertEqual(result['prompt_id'],'screener.ai_candidate_reduction.v4')
        self.assertEqual(result['wire_schema_version'],'ai-screener-wire/3.0.0')
        self.assertEqual(p.asserted,123)

    def test_adaptive_split_respects_context_and_covers_every_identity(self):
        from tools.ai_screener_efficiency_benchmark import MeasuredProvider, fixtures
        from market_platform_foundation.ui_api.screener_ai import ScreenerAiService
        from market_platform_foundation.ui_api.screener_ai_coverage import ScreenerAiCoverage
        from market_platform_foundation.local_state.ai_screener_coverage import CoverageLedger
        from market_platform_foundation.local_state.action_decisions import ActionDecisionRepository
        from tests.support.coverage_universe import News, PagingReader, NOW as seconds, SCOPE
        service = ScreenerAiService(reader=PagingReader(fixtures(100)),news=News(MeasuredProvider()),clock=lambda:seconds)
        coverage = ScreenerAiCoverage(service,ledger=CoverageLedger(),repository=ActionDecisionRepository(),adaptive_batches=True)
        coverage._context_window = lambda: 30000
        result = coverage.run(SCOPE,run_id='adaptive',account_id='test')
        block = result['universe_coverage']
        self.assertEqual(block['ai_evaluated_count'],100)
        self.assertTrue(block['selection_complete'])
        self.assertEqual(block['plan']['batch_optimizer'],'MAXIMAL_CONTEXT_PREFIX')
    def test_roundtrip_preserves_all_clocks_conflicts_and_missing_states(self):
        candidates = [candidate() for _ in range(50)]
        for index, c in enumerate(candidates):
            c['instrument']['instrument_id'] = f'EQ:{index}'
            c['alignments'] = [{'state':'CONFLICTING', 'sentiment_refs':['EV:negative'], 'cutoff':NOW}]
            c['current_market_evidence'][0]['facts']['volume'] = 123456
        original = {'scope':{'query_id':'q'}, 'decision_cutoff':NOW, 'candidates':packet_candidates(candidates)}
        packed = compact(original)
        self.assertEqual(reconstruct(packed), original)
        self.assertTrue(verify(original, packed))
        self.assertLess(len(json.dumps(packed)), len(json.dumps(original)))
        altered = copy.deepcopy(packed)
        altered['rows'][0][0] = 'corrupt'
        self.assertFalse(verify(original, altered))

    def test_fingerprint_ignores_key_order_and_equivalent_number_encoding_only(self):
        self.assertEqual(semantic_hash({'x':1, 'y':2.0}), semantic_hash({'y':2, 'x':1.0}))
        self.assertNotEqual(semantic_hash({'facts':{'cutoff':NOW}}), semantic_hash({'facts':{'cutoff':'later'}}))


class ReuseTests(unittest.TestCase):
    def test_invalidated_planned_reuse_cannot_start_an_unreserved_call(self):
        provider = Stub()
        r = CandidateReducer(provider=provider,clock=lambda:1790953200.)
        r.reduce({},[candidate()],NOW)
        c = candidate()
        c['current_market_evidence'][0]['facts']['price'] += 1
        result = r.reduce({},[c],NOW,allow_inference=False)
        self.assertEqual(result['reason'],'REUSE_INVALIDATED_AFTER_PLANNING')
        self.assertEqual(provider.calls,1)

    def test_full_warm_run_needs_no_hold_for_cached_comparison(self):
        from tools.ai_screener_efficiency_benchmark import measure
        cold, warm, partial = measure(100), measure(100,warm=True), measure(100,warm=True,partial=True)
        self.assertEqual(cold['selected'],warm['selected'])
        self.assertEqual(warm['model_requests'],0)
        self.assertEqual(warm['planned_requests'],0)
        self.assertGreater(partial['model_requests'],0)

    def test_material_mutations_invalidate_all_decision_inputs(self):
        r = CandidateReducer(provider=Stub(),clock=lambda:1790953200.)
        c = candidate()
        digest = r.estimate({},[c],NOW)['input_hash']
        for key,value in [('price',124),('volume',200),('news','changed'),('sentiment','negative'),
                          ('technical',12),('conflict',True),('cutoff','later'),('snapshot_at','later')]:
            changed = copy.deepcopy(c)
            changed['current_market_evidence'][0]['facts'][key] = value
            self.assertNotEqual(digest,r.estimate({},[changed],NOW)['input_hash'],key)
        for key,value in [('as_of','later'),('source','other'),('valid_until','later')]:
            changed = copy.deepcopy(c)
            changed['current_market_evidence'][0][key] = value
            self.assertNotEqual(digest,r.estimate({},[changed],NOW)['input_hash'],key)
        changed = copy.deepcopy(c)
        changed['missing'] = []
        self.assertNotEqual(digest,r.estimate({},[changed],NOW)['input_hash'])
        self.assertNotEqual(digest,r.estimate({},[c,c],NOW)['input_hash'])
        r.provider.model_id = 'other-model'
        self.assertNotEqual(digest,r.estimate({},[c],NOW)['input_hash'])


class BudgetAccountingTests(unittest.TestCase):
    def test_fresh_provider_count_prevents_generation_above_allowance(self):
        class CountedProvider(Stub):
            def preflight(self,packet,*,rendered_prompt,config):
                return {'accepted':True,'input_tokens':1000000,'context_fit':True}
        provider = CountedProvider()
        budget = DailyBudget(None,max_tokens=200000,clock=lambda:1790953200.)
        result = CandidateReducer(provider=BudgetedProvider(provider,budget),clock=lambda:1790953200.).reduce({},[candidate()],NOW)
        self.assertEqual(provider.calls,0)
        self.assertFalse(result['inference_dispatched'])
        self.assertEqual(budget.status()['requests'],0)

    def test_missing_quota_counters_and_noncanonical_day_fail_closed(self):
        complete = {'day':'2026-10-02','requests':1,'input_tokens':1,'output_tokens':1,'reserved_tokens':0}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'quota.json'
            for key in ('requests','input_tokens','output_tokens','reserved_tokens'):
                bad = {k:v for k,v in complete.items() if k != key}
                path.write_text(json.dumps(bad))
                with self.assertRaisesRegex(ValueError,'SYNTHESIS_BUDGET_STATE_UNREADABLE',msg=key):
                    DailyBudget(path,clock=lambda:1790953200.)
            path.write_text(json.dumps({**complete,'day':'2026-10-02T00:00:00'}))
            with self.assertRaisesRegex(ValueError,'SYNTHESIS_BUDGET_STATE_UNREADABLE'):
                DailyBudget(path,clock=lambda:1790953200.)

    def test_cost_estimate_requires_current_model_specific_price_provenance(self):
        from market_platform_foundation.intelligence.inference.token_cost import estimated_cost
        price = {'model_id':'model','currency':'USD','input_per_million':3,'output_per_million':15,
                 'source':'operator supplied controlled price','verified_at':'2026-10-02T14:00:00Z',
                 'valid_until':'2026-10-03T14:00:00Z'}
        self.assertEqual(estimated_cost(price,model_id='model',input_tokens=1000000,output_tokens=1000000,now=NOW)['estimated_dollars'],18)
        self.assertIsNone(estimated_cost(price,model_id='other',input_tokens=10,output_tokens=10,now=NOW))
        self.assertIsNone(estimated_cost(price,model_id='model',input_tokens=10,output_tokens=10,now='2026-10-04T00:00:00Z'))
    def test_concurrent_processes_cannot_oversubscribe_persisted_allowance(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'quota.json'
            code = ("import sys; from pathlib import Path; from market_platform_foundation.intelligence.inference.anthropic_synthesis import DailyBudget; "
                    "b=DailyBudget(Path(sys.argv[1]),max_requests=1,max_tokens=100,clock=lambda:1790953200.); "
                    "print(b.hold(sys.argv[2],requests=1,tokens=100)['held'])")
            processes = [subprocess.Popen([sys.executable,'-c',code,str(path),str(i)],stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,text=True) for i in range(2)]
            outputs = [p.communicate(timeout=15) for p in processes]
            self.assertEqual([p.returncode for p in processes],[0,0],outputs)
            self.assertEqual(sorted(o[0].strip() for o in outputs),['False','True'])

    def test_partial_or_invalid_usage_keeps_reservation(self):
        for usage in [(None,10),(-10,0),(True,0),(0,None)]:
            budget = DailyBudget(None,max_tokens=1000,clock=lambda:1790953200.)
            budget.reserve(100)
            budget.settle(100,*usage)
            self.assertGreaterEqual(budget.status()['tokens'],100,usage)

    def test_malformed_but_parseable_quota_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'quota.json'
            path.write_text(json.dumps({'day':'2026-10-02','requests':-1}))
            with self.assertRaisesRegex(ValueError,'SYNTHESIS_BUDGET_STATE_UNREADABLE'):
                DailyBudget(path)

    def test_exact_request_accounting_includes_system_and_tool_schema(self):
        from market_platform_foundation.intelligence.inference.anthropic_synthesis import AnthropicSynthesisProvider
        p = BudgetedProvider(AnthropicSynthesisProvider(api_key='offline'),DailyBudget(None))
        r = CandidateReducer(provider=p,clock=lambda:1790953200.)
        digest, rendered, _, _ = r._prepare({},[candidate()],NOW)
        from market_platform_foundation.intelligence.inference.candidate_reduction import ScreenerEvidencePacket, output_schema
        from market_platform_foundation.intelligence.inference.contracts import IntelligenceTaskType
        packet = ScreenerEvidencePacket(IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION,'test',digest,NOW,{},[candidate()],output_schema([candidate()]))
        count = p.request_accounting(packet,rendered_prompt=rendered,config=r.config)
        self.assertGreater(count['system_and_schema_tokens'],0)
        self.assertGreater(count['total_tokens'],count['input_tokens'])
        self.assertEqual(count['basis'],'MODEL_CALIBRATED_UTF8_ESTIMATE')
    def test_actual_overrun_blocks_further_draws_from_a_preexisting_hold(self):
        budget = DailyBudget(None,max_requests=10,max_tokens=100,clock=lambda:1790953200.)
        self.assertTrue(budget.hold('run',requests=2,tokens=90)['held'])
        self.assertIsNone(budget.reserve(40,hold='run'))
        budget.settle(40,100,10)
        self.assertIsNotNone(budget.reserve(40,hold='run'))

    def test_unmeasured_error_does_not_become_a_free_request(self):
        class ErrorProvider(Stub):
            def infer(self,packet,*,rendered_prompt,config):
                from market_platform_foundation.intelligence.inference.errors import InferenceErrorCode
                return ProviderInferenceResponse('',self.provider_id,self.model_id,error_code=InferenceErrorCode.PROVIDER_UNAVAILABLE)
        budget = DailyBudget(None,max_tokens=1000000,clock=lambda:1790953200.)
        CandidateReducer(provider=BudgetedProvider(ErrorProvider(),budget),clock=lambda:1790953200.).reduce({},[candidate()],NOW)
        self.assertGreater(budget.status()['tokens'],0)


class AdditionalReuseTests(unittest.TestCase):
    def test_cache_lineage_and_expiry_corruption_are_misses(self):
        from market_platform_foundation.intelligence.inference.evidence_compaction import semantic_hash
        with tempfile.TemporaryDirectory() as directory:
            store = InferenceCache(Path(directory)/'cache.sqlite')
            try:
                provider = Stub()
                result = CandidateReducer(provider=provider,clock=lambda:1790953200.,cache_store=store).reduce({},[candidate()],NOW)
                for field in ('run_id','runtime','simulated','valid_until'):
                    forged = copy.deepcopy(result)
                    if field == 'run_id':
                        del forged[field]
                    elif field == 'valid_until':
                        forged[field] = '2026-10-03T15:00:00Z'
                    elif field == 'simulated':
                        forged[field] = not result[field]
                    else:
                        forged[field] = 'another'
                    with store.connection:
                        store.connection.execute('UPDATE inference_cache SET payload=?,checksum=?',
                                                 (json.dumps(forged),semantic_hash(forged)))
                    restarted = CandidateReducer(provider=provider,clock=lambda:1790953200.,cache_store=store)
                    self.assertFalse(restarted.estimate({},[candidate()],NOW)['cached'],field)
            finally:
                store.close()

    def test_engine_identity_includes_reasoning_and_local_manifest(self):
        from types import SimpleNamespace
        from market_platform_foundation.intelligence.inference.inference_identity import provider_identity, reusable_engine
        provider = Stub()
        before = provider_identity(provider)
        provider.reasoning_effort = 'high'
        self.assertNotEqual(before, provider_identity(provider))
        provider.runtime = 'LOCAL_MODEL'
        self.assertFalse(reusable_engine(provider))
        provider._server = SimpleNamespace(manifest=SimpleNamespace(revision='one',runtime_version='v1'))
        self.assertTrue(reusable_engine(provider))
        before = provider_identity(provider)
        provider._server.manifest.revision = 'two'
        self.assertNotEqual(before, provider_identity(provider))

    def test_efficiency_counters_do_not_allow_credentials_under_token_keys(self):
        from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload, SecretLeakError
        keys = ('actual_input_tokens','actual_output_tokens','actual_tokens','estimated_total_tokens',
                'expected_input_tokens','reserved_batch_output_tokens','reserved_output_tokens_total',
                'reserved_reasoning_tokens','reserved_reasoning_tokens_total','available_token_budget')
        assert_no_secrets_in_payload({key:123 for key in keys})
        for key in keys:
            with self.assertRaises(SecretLeakError,msg=key):
                assert_no_secrets_in_payload({key:'live-credential'})

    def test_cache_non_object_corruption_is_a_miss(self):
        from market_platform_foundation.intelligence.inference.evidence_compaction import semantic_hash
        with tempfile.TemporaryDirectory() as directory:
            cache = InferenceCache(Path(directory)/'cache.sqlite')
            try:
                with cache.connection:
                    cache.connection.execute('INSERT INTO inference_cache VALUES (?,?,?,?)',
                                             ('test',1790953300.,'[]',semantic_hash([])))
                self.assertIsNone(cache.get('test',1790953200.))
            finally:
                cache.close()

    def test_checksum_valid_cache_with_forged_evidence_or_contract_is_a_miss(self):
        from market_platform_foundation.intelligence.inference.evidence_compaction import semantic_hash
        with tempfile.TemporaryDirectory() as directory:
            store = InferenceCache(Path(directory)/'cache.sqlite')
            r = CandidateReducer(provider=Stub(),clock=lambda:1790953200.,cache_store=store)
            result = r.reduce({},[candidate()],NOW)
            for field in ('evidence','provider_id','prompt_hash','scope','state'):
                forged = copy.deepcopy(result)
                if field == 'evidence':
                    forged['evidence'][0]['current_market_evidence'][0]['facts']['price'] = 999
                elif field == 'scope':
                    forged[field] = {'query':'another'}
                elif field == 'state':
                    forged[field] = 'NO_GROUNDED_CANDIDATES'
                else:
                    forged[field] = 'forged'
                encoded = json.dumps(forged)
                with store.connection:
                    store.connection.execute('UPDATE inference_cache SET payload=?,checksum=?',(encoded,semantic_hash(forged)))
                restarted = CandidateReducer(provider=r.provider,clock=lambda:1790953200.,cache_store=store)
                self.assertFalse(restarted.estimate({},[candidate()],NOW)['cached'],field)
            store.close()
    def test_cache_identity_includes_config_and_nested_cutoff(self):
        r = CandidateReducer(provider=Stub(), clock=lambda:1790953200.)
        c = candidate()
        first = r.estimate({},[c],NOW)['input_hash']
        c['current_market_evidence'][0]['facts']['cutoff'] = 'material'
        self.assertNotEqual(first, r.estimate({},[c],NOW)['input_hash'])
        first = r.estimate({},[c],NOW)['input_hash']
        r.config = replace(r.config, max_tokens=2700)
        self.assertNotEqual(first, r.estimate({},[c],NOW)['input_hash'])

    def test_cache_validity_includes_unselected_competitors(self):
        clock = [1790953200.]
        r = CandidateReducer(provider=Stub(), clock=lambda:clock[0])
        a, b = candidate(), candidate()
        b['instrument']['instrument_id'] = 'EQ:B'
        for e in b['current_market_evidence']:
            e['valid_until'] = '2026-10-02T15:00:01Z'
        r.reduce({},[a,b],NOW)
        clock[0] += 2
        self.assertFalse(r.estimate({},[a,b],NOW)['cached'])

    def test_durable_reuse_revalidates_and_preserves_lineage_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = InferenceCache(Path(directory)/'cache.sqlite')
            provider = Stub()
            r = CandidateReducer(provider=provider, clock=lambda:1790953200., cache_store=cache)
            first = r.reduce({},[candidate()],NOW)
            restarted = CandidateReducer(provider=provider, clock=lambda:1790953200., cache_store=InferenceCache(cache.path))
            second = restarted.reduce({},[candidate()],NOW)
            self.assertEqual(second['cache'],'HIT')
            self.assertEqual(second['run_id'], first['run_id'])
            self.assertEqual(provider.calls,1)
            self.assertEqual(second['reuse']['origin_run_id'],first['run_id'])
            cache.connection.execute("UPDATE inference_cache SET payload='{}'")
            self.assertFalse(CandidateReducer(provider=provider,clock=lambda:1790953200.,cache_store=cache).estimate({},[candidate()],NOW)['cached'])
            restarted.cache_store.close()
            cache.close()

    def test_more_than_64_batches_can_be_reused(self):
        r = CandidateReducer(provider=Stub(), clock=lambda:1790953200.)
        for index in range(100):
            r.reduce({'batch':index}, [candidate()],NOW)
        self.assertTrue(r.estimate({'batch':0}, [candidate()],NOW)['cached'])
