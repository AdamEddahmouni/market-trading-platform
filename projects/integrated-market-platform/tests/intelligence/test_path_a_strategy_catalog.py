"""Real (non-fixture) Paper/Demo baseline strategy catalog for Path A.

Proves the empty-catalog software gap is closed (item 7 of the provider
activation DoD): the honesty invoke now registers real strategies backed by
the existing production ``interpret_strategy`` evaluator, and — because no
preregistration authority is wired into this one-shot hop — every entry
legitimately abstains rather than minting a fabricated MATCHED row.
"""

from __future__ import annotations

import inspect
import unittest

from market_platform_foundation.intelligence.contracts import StrategyMatchDisposition
from market_platform_foundation.strategy import path_a_strategy_catalog
from market_platform_foundation.strategy.path_a_prospective import build_paper_demo_path_a_invoke
from market_platform_foundation.strategy.path_a_scan_caller import PathAScanCallerError
from market_platform_foundation.strategy.scanning import StrategyRegistration

T = 1_700_000_000_000_000_000


class PathAStrategyCatalogTests(unittest.TestCase):
    def test_catalog_is_non_empty(self) -> None:
        catalog = path_a_strategy_catalog.build_paper_demo_strategy_catalog()
        self.assertIsInstance(catalog, tuple)
        self.assertGreater(len(catalog), 0)
        self.assertTrue(all(isinstance(row, StrategyRegistration) for row in catalog))

    def test_catalog_strategy_ids_are_unique_and_stable(self) -> None:
        first = path_a_strategy_catalog.build_paper_demo_strategy_catalog()
        second = path_a_strategy_catalog.build_paper_demo_strategy_catalog()
        first_ids = tuple(sorted(row.strategy_id for row in first))
        second_ids = tuple(sorted(row.strategy_id for row in second))
        self.assertEqual(first_ids, second_ids)
        self.assertEqual(len(first_ids), len(set(first_ids)))

    def test_catalog_is_not_a_hardcoded_lambda_fixture(self) -> None:
        source = inspect.getsource(path_a_strategy_catalog)
        self.assertNotIn("lambda", source)
        self.assertIn("interpret_strategy", source)
        self.assertIn("preregistration=None", source)

    def test_honesty_invoke_registers_real_catalog(self) -> None:
        invoke = build_paper_demo_path_a_invoke("AAPL", mode="paper", as_of_time_ns=T)
        self.assertGreater(len(invoke.scan_request.strategies), 0)
        registered_ids = {row.strategy_id for row in invoke.scan_request.strategies}
        catalog_ids = {
            row.strategy_id
            for row in path_a_strategy_catalog.build_paper_demo_strategy_catalog()
        }
        self.assertEqual(registered_ids, catalog_ids)

    def test_real_evaluation_abstains_honestly_without_preregistration(self) -> None:
        """No preregistration authority is wired into the one-shot hop, so a
        genuine evaluation against real strategies still legitimately
        abstains — never a fabricated MATCHED."""
        invoke = build_paper_demo_path_a_invoke("AAPL", mode="paper", as_of_time_ns=T)
        scan = invoke.caller.scanner.run(invoke.scan_request)
        self.assertTrue(scan.matches)
        for match in scan.matches:
            self.assertEqual(match.disposition, StrategyMatchDisposition.ABSTAINED)
            self.assertIn("ABSTAIN_NO_PREREGISTRATION", match.abstention_reasons)
        result = invoke.caller.run(invoke.scan_request)
        self.assertEqual(result.status, "EMPTY")
        self.assertEqual(result.reason_codes, ("NO_MATCHED_STRATEGY",))
        self.assertEqual(result.matched_count, 0)

    def test_real_evaluation_abstains_even_with_a_real_quote_price(self) -> None:
        """A real observed quote price must not be enough, by itself, to flip
        a baseline_only interpretation into a fabricated MATCHED."""
        quote_event = {
            "raw_payload": {"last_price": 190.1},
            "clocks": {"event_time_ns": T - 1_000_000_000},
        }
        invoke = build_paper_demo_path_a_invoke(
            "AAPL", mode="paper", as_of_time_ns=T, quote_event=quote_event
        )
        self.assertIn("quote", invoke.scan_request.capability_snapshot.context)
        scan = invoke.caller.scanner.run(invoke.scan_request)
        self.assertTrue(
            all(
                match.disposition == StrategyMatchDisposition.ABSTAINED
                for match in scan.matches
            )
        )

    def test_demo_mode_also_loads_real_catalog(self) -> None:
        invoke = build_paper_demo_path_a_invoke("AAPL", mode="demo", as_of_time_ns=T)
        self.assertGreater(len(invoke.scan_request.strategies), 0)
        result = invoke.caller.run(invoke.scan_request)
        self.assertEqual(result.status, "EMPTY")

    def test_live_mode_still_refused(self) -> None:
        with self.assertRaisesRegex(PathAScanCallerError, "LIVE_SCAN_CALLER_FORBIDDEN"):
            build_paper_demo_path_a_invoke("AAPL", mode="live", as_of_time_ns=T)


if __name__ == "__main__":
    unittest.main()
