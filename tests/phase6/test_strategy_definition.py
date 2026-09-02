"""Focused tests for the typed strategy-definition compatibility boundary."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from market_platform_foundation.research.forecast import build_forecast, verify_forecast_interface
from market_platform_foundation.strategy.evaluation import (
    default_forecast_momentum_spec,
    run_strategy_evaluation,
)
from market_platform_foundation.strategy.interpretation import interpret_strategy
from market_platform_foundation.strategy.preregistration import (
    build_preregistration,
    verify_preregistration,
)
from market_platform_foundation.strategy.strategy_spec import (
    StrategyDefinition,
    build_strategy_spec,
    strategy_identity_hash,
)


class StrategyDefinitionTests(unittest.TestCase):
    def test_legacy_spec_round_trips_without_identity_hash_drift(self) -> None:
        legacy = build_strategy_spec(
            alignment_type="FORECAST_MOMENTUM",
            hypothesis="test",
            evidence_requirements=["bar_derived_features"],
        )

        definition = StrategyDefinition.from_legacy_spec(legacy)

        self.assertEqual(definition.to_legacy_spec(), legacy)
        self.assertEqual(definition.identity_hash, legacy["strategy_identity_hash"])
        self.assertEqual(strategy_identity_hash(definition), legacy["strategy_identity_hash"])

    def test_definition_is_immutable_and_separates_taxonomy_fields(self) -> None:
        definition = StrategyDefinition(
            alignment_type="FORECAST_MOMENTUM",
            hypothesis="test",
            evidence_requirements=("naive_forecast", "bar_derived_features"),
            family="TREND",
            style="MOMENTUM",
            asset_class="EQUITY",
            timeframe="1D",
        )

        with self.assertRaises(FrozenInstanceError):
            definition.style = "MEAN_REVERSION"  # type: ignore[misc]

        self.assertEqual(definition.evidence_requirements, ("bar_derived_features", "naive_forecast"))
        typed = definition.to_dict()
        self.assertEqual(
            {typed["family"], typed["style"], typed["asset_class"], typed["timeframe"]},
            {"TREND", "MOMENTUM", "EQUITY", "1D"},
        )
        self.assertEqual(typed["strategy_identity_hash"], strategy_identity_hash(typed))

    def test_legacy_strategy_apis_accept_typed_definition(self) -> None:
        definition = StrategyDefinition.from_legacy_spec(default_forecast_momentum_spec())
        preregistration = build_preregistration(
            definition,
            registered_at="2026-08-16T00:00:00.000000000Z",
        )
        status, reasons = verify_preregistration(preregistration, definition)
        self.assertEqual((status, reasons), ("PASS", []))

        forecast = build_forecast(score="1.0", prediction_cutoff=100, horizon_ns=60_000_000_000)
        forecast_status, _ = verify_forecast_interface(forecast)
        interpretation = interpret_strategy(
            strategy_spec=definition,
            preregistration=preregistration,
            forecast=forecast,
            forecast_status=forecast_status,
            prediction_cutoff=100,
            observation_time=100,
        )
        self.assertEqual(interpretation["outcome"], "signal")
        self.assertEqual(interpretation["strategy_identity_hash"], definition.identity_hash)

        result = run_strategy_evaluation([], strategy_spec=definition)
        self.assertEqual(result["strategy_spec"], definition.to_legacy_spec())
