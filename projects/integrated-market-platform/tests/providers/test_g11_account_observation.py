"""G11 read-only account observation tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.market_data.runtime_composition import (
    ObservationalRuntimeComposition,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.portfolio import CanonicalPortfolio, PortfolioKey
from market_platform_foundation.providers.ibkr_observational.account_observation import (
    READ_ONLY_OBSERVATIONAL,
    normalize_ibkr_account_discovery,
)

from ibkr_observational_support import FakeQueryProvider


class G11AccountObservationTests(unittest.TestCase):
    def test_normalization(self) -> None:
        observation = normalize_ibkr_account_discovery(
            {"accounts": ["DU111", "DU222"]},
            received_time_ns=1,
        )
        self.assertEqual(observation.authority, READ_ONLY_OBSERVATIONAL)
        self.assertEqual(observation.account_ids, ("DU111", "DU222"))

    def test_missing_value(self) -> None:
        observation = normalize_ibkr_account_discovery({})
        self.assertEqual(observation.account_ids, ())

    def test_two_accounts_isolated_in_provider_payload(self) -> None:
        provider = FakeQueryProvider(
            accounts_payload={"accounts": ["DU111", "DU222"]}
        )
        composition = ObservationalRuntimeComposition()
        composition.attach_ibkr_query_service(provider)
        first = composition.fetch_account_observation()
        provider.accounts_payload = {"accounts": ["DU333"]}
        second = composition.fetch_account_observation()
        self.assertEqual(first.observation.account_ids, ("DU111", "DU222"))
        self.assertEqual(second.observation.account_ids, ("DU333",))

    def test_no_canonical_portfolio_mutation(self) -> None:
        portfolio = CanonicalPortfolio(PortfolioKey(account_id="paper-1", mode="PAPER"))
        before = portfolio.positions
        provider = FakeQueryProvider()
        composition = ObservationalRuntimeComposition()
        composition.attach_ibkr_query_service(provider)
        composition.fetch_account_observation()
        after = portfolio.positions
        self.assertEqual(before, after)

    def test_no_paper_ledger_mutation(self) -> None:
        ledger = PaperExecutionLedger(paper_account_id="paper-1", session_id="sess-1")
        before = len(ledger.events)
        provider = FakeQueryProvider()
        composition = ObservationalRuntimeComposition()
        composition.attach_ibkr_query_service(provider)
        composition.fetch_account_observation()
        after = len(ledger.events)
        self.assertEqual(before, after)

    def test_repeated_query_deterministic(self) -> None:
        provider = FakeQueryProvider()
        composition = ObservationalRuntimeComposition()
        composition.attach_ibkr_query_service(provider)
        first = composition.fetch_account_observation(received_time_ns=100)
        second = composition.fetch_account_observation(received_time_ns=100)
        self.assertEqual(first.observation.to_dict(), second.observation.to_dict())

    def test_provider_error(self) -> None:
        class FailingProvider(FakeQueryProvider):
            def fetch_portfolio_accounts(self) -> dict[str, object]:
                raise RuntimeError("provider down")

        composition = ObservationalRuntimeComposition()
        composition.attach_ibkr_query_service(FailingProvider())
        result = composition.fetch_account_observation()
        self.assertFalse(result.accepted)
        self.assertIn("PROVIDER_ERROR", result.reason or "")


if __name__ == "__main__":
    unittest.main()
