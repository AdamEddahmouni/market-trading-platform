"""Read-only Paper strategy profitability observability contracts."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.platform.security.route_policy import (  # noqa: E402
    AccountScopeKind,
    policy_for_route,
)
from market_platform_foundation.ui_api.strategy_runtime_projections import (  # noqa: E402
    build_strategy_profitability_payload,
)

from tests.intelligence.test_equity_paper_runtime import (  # noqa: E402
    _runtime_fixture,
    _strategy_request,
)


class StrategyRuntimeObservabilityTests(unittest.TestCase):
    def test_profitability_route_is_audit_read_scoped_to_paper_ledger(self) -> None:
        policy = policy_for_route("GET", "/paper/strategy-profitability")

        self.assertEqual(policy.capability, "audit.read")
        self.assertEqual(policy.account_scope, AccountScopeKind.PAPER_LEDGER)

    def test_projection_reconstructs_lineage_without_summing_attribution(self) -> None:
        runtime, repository, _, _ = _runtime_fixture()
        result = runtime.run_entry(_strategy_request())

        payload = build_strategy_profitability_payload(
            repository=repository,
            ledger=runtime.ledger,
            account_id="acct-paper",
            mode="PAPER",
            allocation_decision_id=result.ids["allocation_decision_id"],
        )

        self.assertEqual(payload["authority_boundary"], "PAPER_OBSERVABILITY_READ_ONLY")
        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertEqual(item["allocation"]["allocation_decision_id"], result.ids["allocation_decision_id"])
        self.assertEqual(item["strategy_match"]["match_id"], result.ids["strategy_match_id"])
        self.assertEqual(item["forecast"]["forecast_id"], result.ids["forecast_id"])
        self.assertIsNotNone(item["proposal"])
        self.assertIsNotNone(item["risk_decision"])
        self.assertEqual(item["fills"][0]["fill_id"], result.fill_ids[0])
        self.assertEqual(item["attribution"]["materialization_semantics"], "CUMULATIVE")
        self.assertEqual(item["attribution"]["trading_outcome"]["realized_pnl_minor"], 0)

    def test_projection_lists_only_the_scoped_paper_allocations(self) -> None:
        runtime, repository, _, _ = _runtime_fixture()
        result = runtime.run_entry(_strategy_request())

        payload = build_strategy_profitability_payload(
            repository=repository,
            ledger=runtime.ledger,
            account_id="acct-paper",
            mode="PAPER",
        )

        self.assertEqual(payload["total_count"], 1)
        self.assertEqual(
            payload["items"][0]["allocation"]["allocation_decision_id"],
            result.ids["allocation_decision_id"],
        )

    def test_projection_is_point_in_time_and_does_not_include_future_fills(self) -> None:
        runtime, repository, _, _ = _runtime_fixture()
        result = runtime.run_entry(_strategy_request())
        fill_time_ns = int(runtime.ledger.project_fills()[0]["fill_time"])
        outcomes_before = repository.get_outcomes_by_forecast(result.ids["forecast_id"])
        event_count_before = len(runtime.ledger.events)

        payload = build_strategy_profitability_payload(
            repository=repository,
            ledger=runtime.ledger,
            account_id="acct-paper",
            mode="PAPER",
            allocation_decision_id=result.ids["allocation_decision_id"],
            as_of_ns=fill_time_ns - 1,
        )

        item = payload["items"][0]
        self.assertEqual(item["fills"], [])
        self.assertIsNone(item["attribution"])
        self.assertEqual(repository.get_outcomes_by_forecast(result.ids["forecast_id"]), outcomes_before)
        self.assertEqual(len(runtime.ledger.events), event_count_before)

    def test_detail_scope_fails_closed_for_another_account(self) -> None:
        runtime, repository, _, _ = _runtime_fixture()
        result = runtime.run_entry(_strategy_request())

        with self.assertRaisesRegex(ValueError, "STRATEGY_PROFITABILITY_SCOPE_MISMATCH"):
            build_strategy_profitability_payload(
                repository=repository,
                ledger=runtime.ledger,
                account_id="another-paper-account",
                mode="PAPER",
                allocation_decision_id=result.ids["allocation_decision_id"],
            )

    def test_default_projection_as_of_is_deterministic_for_a_ledger_snapshot(self) -> None:
        runtime, repository, _, _ = _runtime_fixture()
        result = runtime.run_entry(_strategy_request())
        kwargs = {
            "repository": repository,
            "ledger": runtime.ledger,
            "account_id": "acct-paper",
            "mode": "PAPER",
            "allocation_decision_id": result.ids["allocation_decision_id"],
        }

        self.assertEqual(
            build_strategy_profitability_payload(**kwargs),
            build_strategy_profitability_payload(**kwargs),
        )

    def test_projection_marks_missing_lineage_without_inventing_ownership(self) -> None:
        runtime, repository, _, _ = _runtime_fixture()
        result = runtime.run_entry(_strategy_request())

        class IncompleteRepository:
            def __getattr__(self, name: str):
                return getattr(repository, name)

            def get_strategy_match(self, match_id: str):
                return None

            def get_forecast(self, forecast_id: str):
                return None

            def get_strategy_attributions_by_allocation(self, *args, **kwargs):
                return ()

        payload = build_strategy_profitability_payload(
            repository=IncompleteRepository(),
            ledger=runtime.ledger,
            account_id="acct-paper",
            mode="PAPER",
            allocation_decision_id=result.ids["allocation_decision_id"],
        )

        item = payload["items"][0]
        self.assertIsNone(item["strategy_match"])
        self.assertIsNone(item["forecast"])
        self.assertIsNone(item["attribution"])

    def test_detail_point_in_time_rejects_an_allocation_from_the_future(self) -> None:
        runtime, repository, _, _ = _runtime_fixture()
        result = runtime.run_entry(_strategy_request())
        allocation = repository.get_allocation_decision(result.ids["allocation_decision_id"])

        with self.assertRaisesRegex(ValueError, "ALLOCATION_AFTER_POINT_IN_TIME"):
            build_strategy_profitability_payload(
                repository=repository,
                ledger=runtime.ledger,
                account_id="acct-paper",
                mode="PAPER",
                allocation_decision_id=result.ids["allocation_decision_id"],
                as_of_ns=allocation.decision_time_ns - 1,
            )


if __name__ == "__main__":
    unittest.main()
