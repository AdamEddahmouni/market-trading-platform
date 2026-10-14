"""Offline vertical slice acceptance across stored knowledge, policy, journal and replay."""
import importlib
import tempfile
import unittest
from pathlib import Path


class ProfessorIntegrationTests(unittest.TestCase):
    def demo(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.research.professor_integration_demo'),
                             'Integrated demonstration is missing')
        module = importlib.import_module('tools.research.professor_integration_demo')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        return module.run_offline_demo(Path(self.temp.name))

    def test_overnight_storage_morning_plan_and_restart(self):
        result = self.demo()
        self.assertEqual(result['overnight']['session']['window'], 'INFERENCE_PAUSE')
        self.assertEqual(result['overnight']['inference_calls'], 0)
        self.assertEqual(result['morning']['session']['window'], 'CATCH_UP')
        self.assertTrue(result['morning']['planned'])
        self.assertEqual(result['morning']['planned_requests'], 2)
        self.assertTrue(result['morning']['deferred'])
        self.assertEqual(result['restart']['stored_records'], result['storage']['committed_records'])
        self.assertEqual(result['restart']['inference_calls'], 0)

    def test_frozen_decision_later_outcome_and_deterministic_replay(self):
        result = self.demo()
        self.assertEqual(result['early_journal']['items'][0]['outcomes'], [])
        self.assertTrue(result['late_journal']['items'][0]['outcomes'])
        self.assertIsNone(result['late_journal']['items'][0]['realized_pnl'])
        self.assertEqual(result['early_journal']['items'][0]['decision_snapshot_hash'],
                         result['late_journal']['items'][0]['decision_snapshot_hash'])
        self.assertTrue(result['replay']['deterministic'])
        self.assertEqual(len(result['replay']['view']['decisions'][0]['policy_decisions']), 3)
        self.assertEqual(result['future_knowledge_excluded'], True)

    def test_resource_and_provider_refusals_do_not_dispatch(self):
        result = self.demo()
        self.assertEqual(result['budget_blocked']['planned'], [])
        self.assertEqual(result['provider_unverified']['planned'], [])
        self.assertFalse(result['provider_unverified']['model_route']['availability_verified'])
        self.assertEqual(result['providers_contacted'], 0)
        self.assertEqual(result['inference_calls'], 0)
        self.assertEqual(result['orders_submitted'], 0)
        self.assertEqual(result['storage']['bounded_scan_blocked'], True)


if __name__ == '__main__':
    unittest.main()
