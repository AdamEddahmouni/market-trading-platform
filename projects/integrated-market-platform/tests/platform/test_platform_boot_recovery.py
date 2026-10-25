"""Boot recovery: before the Paper controller resumes, the serving process closes the AI runs a dead process left
open, so none of them holds the shared AI slot (2026-10-20: a stuck run held it for 3.7 h). Offline fixtures."""
import io
import os
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from market_platform_foundation.ui_api.screener_ai_runs import AiScreenerRuns
from tools.ui1 import run_ui_api


class BootRecoveryTests(unittest.TestCase):
    def test_serve_closes_interrupted_runs_before_the_controller_resumes(self):
        order = []
        store = SimpleNamespace(data_mode='LIVE_OBSERVATIONAL', instrument_id='AAPL')
        with patch.dict(os.environ, {'IMP_NEWS_COLLECTION_ENABLED': '0', 'IMP_MARKET_PERSISTENCE_ENABLED': '0'}), \
             patch.object(run_ui_api, '_install_process_diagnostics'), patch.object(run_ui_api, '_load_store', return_value=store), \
             patch.object(run_ui_api, 'SingleBindHTTPServer', return_value=MagicMock()), \
             patch.object(run_ui_api, 'start_screener_warmup'), \
             patch.object(run_ui_api, 'recover_interrupted_runs', side_effect=lambda: order.append('recover') or {}), \
             patch.object(run_ui_api, 'resume_paper_automation', side_effect=lambda _store: order.append('resume') or {}), \
             patch('market_platform_foundation.market_data.persistence.start_persistence', return_value=None), \
             patch('market_platform_foundation.news.collection.start_collection', side_effect=ValueError('fixture: stop here')), \
             redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):
                run_ui_api.serve(host='127.0.0.1', port=0)
        self.assertEqual(order, ['recover', 'resume'])

    def test_recovery_reports_the_runs_it_closed_and_never_blocks_serving(self):
        with patch('market_platform_foundation.ui_api.screener_ai_runs.ai_screener_runs') as factory:
            factory.return_value.recover_at_boot.return_value = [{'run_id': 'r1'}, {'run_id': 'r2'}]
            self.assertEqual(run_ui_api.recover_interrupted_runs(), {'interrupted_runs': 2, 'run_ids': ['r1', 'r2']})
            factory.return_value.recover_at_boot.side_effect = RuntimeError('ledger unreadable')
            self.assertEqual(run_ui_api.recover_interrupted_runs(), {'interrupted_runs': None, 'reason': 'RuntimeError'})

    def test_recover_at_boot_returns_only_what_this_call_closed(self):
        self.assertEqual(AiScreenerRuns(service=SimpleNamespace()).recover_at_boot(), [])  # no AI service: nothing to close
        runs = AiScreenerRuns(service=SimpleNamespace(run_universe=lambda *args, **kwargs: None))
        runs._recovered.append({'run_id': 'earlier'})
        with patch.object(runs, '_recover', side_effect=lambda service: runs._recovered.append({'run_id': 'now'})):
            self.assertEqual(runs.recover_at_boot(), [{'run_id': 'now'}])


if __name__ == '__main__':
    unittest.main()
