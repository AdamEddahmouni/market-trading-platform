"""Setup's "Which AI decides" status: engine, caps, spend, prices, benchmark. Calls no model; never carries a key."""
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from market_platform_foundation.intelligence.inference.paid_spend import ledger_for
from market_platform_foundation.intelligence.inference.synthesis_engines import SynthesisSettings
from market_platform_foundation.local_state.external_cache import write_json_atomic
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload
from market_platform_foundation.platform.security.route_policy import policy_for_route
from market_platform_foundation.ui_api.operator_config import ProviderConfigStore
from market_platform_foundation.ui_api.setup_ai import BENCHMARK_RELATIVE, setup_ai_status

KEY = 'sk-ant-api03-' + 'x' * 40


class SetupAiTests(unittest.TestCase):
    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.root = Path(self._folder.name)
        self.cache = self.root / 'cache'
        self.store = ProviderConfigStore(private_path=self.root / 'providers.env', environ={}, external=frozenset())

    def tearDown(self):
        self._folder.cleanup()

    def status(self, values, **kwargs):
        return setup_ai_status(settings=SynthesisSettings(values.get, self.cache), value=values.get, cache_dir=self.cache,
                               store=self.store, now=datetime(2026, 10, 24, tzinfo=UTC), **kwargs)

    def test_automatic_is_local_and_paid_is_off_without_caps(self):
        payload = self.status({'ANTHROPIC_API_KEY': KEY})
        self.assertEqual((payload['engine'], payload['resolved_engine'], payload['source']), ('auto', 'local', 'AUTOMATIC'))
        self.assertEqual((payload['caps']['set'], payload['caps']['daily_usd'], payload['spend']['state']),
                         (False, 0.0, 'CAP_NOT_SET'))
        anthropic = next(e for e in payload['engines'] if e['id'] == 'anthropic')
        self.assertEqual((anthropic['state'], anthropic['reason']), ('NOT_CONFIGURED', 'PAID_AI_CAP_NOT_SET'))
        self.assertNotIn(KEY, json.dumps(payload))
        assert_no_secrets_in_payload(payload)
        self.assertIs(payload['secrets_included'], False)

    def test_caps_spend_prices_and_benchmark_are_reported(self):
        values = {'ANTHROPIC_API_KEY': KEY, 'IMP_PAID_AI_DAILY_USD': '1.50', 'IMP_PAID_AI_MONTHLY_USD': '20'}
        ledger = ledger_for(values.get, self.cache)
        amount, _ = ledger.reserve('claude-haiku-5-5', 1000, 1000)
        ledger.settle(amount, 'claude-haiku-5-5', 1000, 1000)
        write_json_atomic(self.cache / BENCHMARK_RELATIVE, {'generated_at': 'x', 'local_winner': 'm', 'paid_pick': 'claude-haiku-5-5',
                                                            'runs': []})
        payload = self.status(values, engine_lock={'locked': True, 'reason': 'REEVALUATION_LOOP_RUNNING'})
        self.assertEqual((payload['caps']['daily_usd'], payload['caps']['monthly_usd'], payload['caps']['set']), (1.5, 20.0, True))
        self.assertEqual(payload['spend']['spent_today_usd'], 0.0006)
        haiku = next(p for p in payload['prices'] if p['model'] == 'claude-haiku-5-5')
        self.assertEqual((haiku['input_per_mtok'], haiku['output_per_mtok'], haiku['priced']), (0.10, 0.50, True))
        self.assertTrue(all(p['priced'] for p in payload['prices']))
        self.assertEqual(payload['benchmark']['paid_pick'], 'claude-haiku-5-5')
        self.assertTrue(payload['engine_lock']['locked'])

    def test_caps_are_written_only_through_the_registered_provider(self):
        result = self.store.write('paid_ai', {'IMP_PAID_AI_DAILY_USD': '2', 'IMP_PAID_AI_MONTHLY_USD': '25.50'})
        self.assertEqual(sorted(result['saved']), ['IMP_PAID_AI_DAILY_USD', 'IMP_PAID_AI_MONTHLY_USD'])
        for bad in ('-1', 'abc', '1.234', '20000'):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'SPENDING_CAP_INVALID'):
                self.store.write('paid_ai', {'IMP_PAID_AI_DAILY_USD': bad})

    def test_routes_keep_their_capabilities(self):
        self.assertEqual(policy_for_route('GET', '/screener/setup/ai').capability, 'state.read')
        self.assertEqual(policy_for_route('POST', '/operator/config/provider').capability, 'security.config.write')
        self.assertEqual(policy_for_route('POST', '/screener/news/synthesis/engine').capability, 'state.write')


if __name__ == '__main__':
    unittest.main()
