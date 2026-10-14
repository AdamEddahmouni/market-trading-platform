"""Offline local context and no-paid journal regressions; no model or network."""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from market_platform_foundation.intelligence.inference.local_provider import LocalChatInferenceProvider
from market_platform_foundation.intelligence.inference.config import IntelligenceInferenceConfig
from market_platform_foundation.intelligence.inference.contracts import IntelligenceTaskType
from tests.platform.test_screener_ai_coverage import Harness
from tests.support.coverage_universe import universe


class Transport:
    def __init__(self, count=5500, tokenizer_status=200, tokens=None):
        self.count, self.tokenizer_status, self.tokens = count, tokenizer_status, tokens
        self.requests = []

    def __call__(self, url, body, timeout):
        request = json.loads(body)
        self.requests.append((url, request))
        if url.endswith('/apply-template'):
            return 200, json.dumps({'prompt': 'SERIALIZED CHAT'}).encode()
        if url.endswith('/tokenize'):
            return self.tokenizer_status, json.dumps({'tokens': self.tokens if self.tokens is not None else [1] * self.count}).encode()
        return 200, json.dumps({'choices': [{'message': {'content': '{"schema_version":"ai-screener-output/1.0.0","candidates":[],"limitations":["Candidate reduction only."]}'}}],
                                'usage': {'prompt_tokens': self.count, 'completion_tokens': 20}}).encode()


def provider(transport, context=8192):
    server = SimpleNamespace(manifest=SimpleNamespace(context=context, revision='', runtime_version=''), running=lambda: True,
        ensure_running=lambda: None, touch=lambda: None, stop=lambda: None)
    return LocalChatInferenceProvider(base_url='http://127.0.0.1:19999', model_id='fixture', server=server, poster=transport)


def packet(task=IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION):
    return SimpleNamespace(task_type=task, output_schema={'type': 'object'})


class LocalContextTests(unittest.TestCase):
    def test_baseline_reduction_measures_serialized_chat_before_generation(self):
        transport = Transport(count=5592)
        value = provider(transport).infer(packet(), rendered_prompt='FULL BASELINE EVIDENCE', config=IntelligenceInferenceConfig(max_tokens=2600))
        self.assertFalse(value.error_code)
        self.assertEqual([url.rsplit('/', 1)[-1] for url, _ in transport.requests], ['apply-template', 'tokenize', 'completions'])
        self.assertEqual(transport.requests[0][1]['messages'][1]['content'], 'FULL BASELINE EVIDENCE')
        self.assertEqual(transport.requests[1][1], {'content': 'SERIALIZED CHAT', 'add_special': True})
        self.assertEqual(transport.requests[2][1]['max_tokens'], 2600)

    def test_overflow_never_dispatches_candidate_or_action_generation(self):
        for task in (IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION, IntelligenceTaskType.SCREENER_ACTION_DECISION):
            transport = Transport(count=5593)
            value = provider(transport).infer(packet(task), rendered_prompt='FULL', config=IntelligenceInferenceConfig(max_tokens=2600))
            self.assertEqual(value.error_message, 'LOCAL_CONTEXT_EXCEEDED')
            self.assertFalse(value.inference_dispatched)
            self.assertEqual(len(transport.requests), 2)

    def test_unavailable_or_malformed_exact_count_fails_closed(self):
        for status, tokens in ((404, None), (200, []), (200, ['invalid']), (200, [True])):
            transport = Transport(tokenizer_status=status, tokens=tokens)
            value = provider(transport).infer(packet(), rendered_prompt='FULL', config=IntelligenceInferenceConfig(max_tokens=2600))
            self.assertEqual(value.error_message, 'LOCAL_CONTEXT_PREFLIGHT_FAILED')
            self.assertFalse(value.inference_dispatched)
            self.assertEqual(len(transport.requests), 2)

    def test_preflight_counts_without_generation(self):
        transport = Transport(count=5500)
        local = provider(transport)
        self.assertTrue(callable(getattr(local, 'preflight', None)), 'Local provider must expose an exact count-only preflight')
        value = local.preflight(packet(), rendered_prompt='FULL', config=IntelligenceInferenceConfig(max_tokens=2600))
        self.assertTrue(value['accepted'])
        self.assertEqual(value['input_tokens'], 5500)
        self.assertEqual(value['context_window'], 8192)
        self.assertEqual(len(transport.requests), 2)

    def test_missing_manifest_context_cannot_dispatch(self):
        local = LocalChatInferenceProvider(base_url='http://127.0.0.1:19999', model_id='fixture', poster=Transport())
        value = local.infer(packet(), rendered_prompt='FULL', config=IntelligenceInferenceConfig(max_tokens=2600))
        self.assertEqual(value.error_message, 'LOCAL_CONTEXT_PREFLIGHT_FAILED')
        self.assertFalse(value.inference_dispatched)

    def test_count_only_overflow_keeps_owned_runtime_for_next_split(self):
        from tests.intelligence.test_local_synthesis_provider import ServerLifecycleTests, FakeProcess
        from market_platform_foundation.intelligence.inference.local_provider import SERVER_ALIAS
        from market_platform_foundation.intelligence.inference import local_resources as resources
        harness = ServerLifecycleTests()
        harness.setUp()
        try:
            server = harness.server(lambda *a: (200, json.dumps({'data': [{'id': SERVER_ALIAS}]}).encode()),
                lambda *a, **k: self.fail('count bisection must reuse owned runtime'))
            process = FakeProcess()
            server._process = process
            server.enforce_admission = True
            transport = Transport(count=6000)
            local = LocalChatInferenceProvider(base_url=server.base_url, model_id='fixture', server=server, poster=transport)
            self.assertTrue(callable(getattr(local, 'preflight', None)))
            sample = {'available_bytes': 12 * resources.GIB, 'commit_available_bytes': 12 * resources.GIB,
                'process_bytes': resources.GIB, 'process_commit_bytes': resources.GIB}
            with patch('market_platform_foundation.intelligence.inference.local_runtime.readiness', return_value={'rejection_reason': None}), \
                 patch.object(resources, 'memory_sample', return_value=sample):
                too_big = local.preflight(packet(), rendered_prompt='FULL', config=IntelligenceInferenceConfig(max_tokens=2600))
                self.assertFalse(too_big['context_fit'])
                self.assertTrue(server.running())
                transport.count = 5500
                fitting = local.preflight(packet(), rendered_prompt='SMALLER GROUP', config=IntelligenceInferenceConfig(max_tokens=2600))
                self.assertTrue(fitting['accepted'])
                self.assertTrue(server.running())
                self.assertEqual(len(transport.requests), 4)
            server.stop()
        finally:
            harness.tearDown()


class CoverageContextTests(unittest.TestCase):
    def test_conservative_estimate_does_not_exclude_exactly_fitting_baseline(self):
        transport = Transport(count=5500)
        h = Harness(universe(1), provider(transport))
        with patch('market_platform_foundation.intelligence.inference.candidate_reduction.estimate_tokens', return_value=6073):
            h.run()
        self.assertEqual(h.block['status'], 'COMPLETE_NO_SELECTION')
        self.assertEqual(h.block['ai_evaluated_count'], 1)
        self.assertEqual(h.block['plan']['expected_input_tokens'], 5500)
        self.assertTrue(any(url.endswith('/completions') for url, _ in transport.requests))

    def test_exact_overflow_accounts_row_without_generation(self):
        transport = Transport(count=5593)
        h = Harness(universe(1), provider(transport))
        h.run()
        self.assertEqual(h.block['counts']['unprocessed'], 1)
        self.assertFalse(any(url.endswith('/completions') for url, _ in transport.requests))

    def test_tokenizer_unavailable_does_not_fall_back_to_estimate(self):
        transport = Transport(count=1, tokenizer_status=404)
        h = Harness(universe(1), provider(transport))
        h.run()
        self.assertEqual(h.block['ai_evaluated_count'], 0)
        self.assertFalse(any(url.endswith('/completions') for url, _ in transport.requests))

    def test_failed_tokenizer_is_not_retried_during_bisection(self):
        transport = Transport(tokenizer_status=404)
        h = Harness(universe(4), provider(transport))
        h.run()
        self.assertEqual(h.block['counts']['unprocessed'], 4)
        self.assertEqual(len(transport.requests), 2)


if __name__ == '__main__':
    unittest.main()
