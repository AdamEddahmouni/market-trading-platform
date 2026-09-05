"""Tests for causal short-squeeze intelligence evaluator."""

from __future__ import annotations

import unittest

from squeeze_core.intelligence.contracts import SqueezeState
from squeeze_core.intelligence.evaluator import (
    AdamSnapshot,
    CrossLaneSnapshot,
    FuelHistorySnapshot,
    QualitySnapshot,
    RuleSnapshot,
    evaluate_squeeze_intelligence,
)


class CausalIntelligenceTests(unittest.TestCase):
    def test_high_si_no_ignition_is_vulnerable_not_buy_signal(self) -> None:
        rules = (
            RuleSnapshot(
                rule_id="PUBLISHED_SHORT_INTEREST_AVAILABLE",
                category="SHORT_PRESSURE_CONFIRMATION",
                outcome="PASS",
            ),
            RuleSnapshot(
                rule_id="DAYS_TO_COVER_MINIMUM",
                category="SHORT_PRESSURE_CONFIRMATION",
                outcome="PASS",
            ),
        )
        result = evaluate_squeeze_intelligence(
            rules=rules,
            adam=AdamSnapshot(pressure=72.0, ignition=20.0, classification="NOT_QUALIFIED"),
        )
        self.assertIn(result.state, (SqueezeState.VULNERABLE, SqueezeState.ARMED))
        self.assertNotEqual(result.state, SqueezeState.ACTIVE_SQUEEZE)

    def test_low_si_high_momentum_flags_non_squeeze_momentum(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=30.0, ignition=75.0, classification="WATCH"),
        )
        self.assertEqual(result.state, SqueezeState.IGNITION_WATCH)
        labels = {label.value for label in result.mechanism_labels}
        self.assertIn("NON_SQUEEZE_MOMENTUM", labels)

    def test_active_squeeze_with_gamma_and_order_flow(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=72.0, ignition=75.0, classification="WATCH"),
            cross_lane=CrossLaneSnapshot(
                order_flow_available=True,
                order_flow_aggressive_buy=True,
                order_flow_cvd_slope=5.0,
                options_available=True,
                options_gamma_amplification=True,
                options_hedging_pressure=2.0,
            ),
        )
        self.assertEqual(result.state, SqueezeState.ACTIVE_SQUEEZE)
        self.assertIsNotNone(result.reflexivity_strength)
        assert result.reflexivity_strength is not None
        self.assertGreaterEqual(result.reflexivity_strength, 70)
        self.assertIsNotNone(result.remaining_fuel)
        codes = {item.code for item in result.supporting_evidence}
        self.assertIn("REFLEXIVE_FEEDBACK_LOOP", codes)
        self.assertIn("GAMMA_AMPLIFICATION", codes)

    def test_exhaustion_on_cvd_divergence_and_fuel_depletion(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=72.0, ignition=75.0, classification="WATCH"),
            cross_lane=CrossLaneSnapshot(
                order_flow_available=True,
                order_flow_aggressive_buy=True,
                order_flow_cvd_slope=-10.0,
                options_available=True,
                options_gamma_amplification=True,
            ),
            previous_state=SqueezeState.ACTIVE_SQUEEZE,
        )
        self.assertIsNotNone(result.exhaustion_risk)
        assert result.exhaustion_risk is not None
        self.assertGreaterEqual(result.exhaustion_risk, 45)

    def test_exhaustion_with_fuel_decline_history(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=30.0, ignition=55.0, classification="WATCH"),
            cross_lane=CrossLaneSnapshot(
                order_flow_available=True,
                order_flow_aggressive_buy=True,
                order_flow_cvd_slope=-5.0,
            ),
            fuel_history=FuelHistorySnapshot(previous_remaining_fuel=60.0, previous_cvd_slope=4.0),
            previous_state=SqueezeState.ACTIVE_SQUEEZE,
        )
        self.assertIsNotNone(result.exhaustion_risk)
        assert result.exhaustion_risk is not None
        self.assertGreaterEqual(result.exhaustion_risk, 70)
        self.assertEqual(result.state, SqueezeState.EXHAUSTION)

    def test_exhaustion_with_cvd_divergence_history(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=72.0, ignition=60.0, classification="WATCH"),
            cross_lane=CrossLaneSnapshot(
                order_flow_available=True,
                order_flow_aggressive_buy=True,
                order_flow_cvd_slope=-3.0,
            ),
            fuel_history=FuelHistorySnapshot(previous_cvd_slope=5.0),
        )
        codes = {item.code for item in result.contradicting_evidence}
        self.assertIn("CVD_DIVERGENCE_HISTORY", codes)
        self.assertIsNotNone(result.exhaustion_risk)
        assert result.exhaustion_risk is not None
        self.assertGreaterEqual(result.exhaustion_risk, 65)

    def test_borrow_normalization_alone_insufficient_for_exhaustion_state(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=72.0, ignition=75.0, classification="WATCH"),
            cross_lane=CrossLaneSnapshot(
                order_flow_available=True,
                order_flow_aggressive_buy=True,
                order_flow_cvd_slope=5.0,
                borrow_normalization_score=70.0,
            ),
        )
        self.assertNotEqual(result.state, SqueezeState.EXHAUSTION)

    def test_remaining_fuel_fail_closed_without_vulnerability(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=None, ignition=60.0, classification="WATCH"),
            cross_lane=CrossLaneSnapshot(
                order_flow_available=True,
                order_flow_aggressive_buy=True,
                order_flow_cvd_slope=3.0,
            ),
        )
        self.assertIsNone(result.remaining_fuel)

    def test_order_flow_confirmation_without_structural_fuel_stays_below_active(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=40.0, ignition=60.0, classification="WATCH"),
            cross_lane=CrossLaneSnapshot(
                order_flow_available=True,
                order_flow_aggressive_buy=True,
                order_flow_cvd_slope=1.5,
            ),
        )
        self.assertIn(
            result.state,
            (SqueezeState.IGNITION_WATCH, SqueezeState.LIVE_CONFIRMATION),
        )
        self.assertNotEqual(result.state, SqueezeState.ACTIVE_SQUEEZE)

    def test_provider_conflict_is_unevaluable(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=80.0, ignition=80.0, classification="CONFLICTED"),
            quality=QualitySnapshot(provider_conflicts=True),
        )
        self.assertEqual(result.state, SqueezeState.UNEVALUABLE)

    def test_horizon_probabilities_are_research_only_not_calibrated(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(
                RuleSnapshot(
                    rule_id="PUBLISHED_SHORT_INTEREST_AVAILABLE",
                    category="SHORT_PRESSURE_CONFIRMATION",
                    outcome="PASS",
                ),
            ),
            adam=AdamSnapshot(pressure=65.0, ignition=55.0, classification="WATCH"),
        )
        self.assertTrue(result.horizon_probabilities)
        for horizon in result.horizon_probabilities:
            self.assertIsNone(horizon.value)
            self.assertEqual(horizon.status, "RESEARCH_ONLY")

    def test_calibrated_horizons_when_horizon_model_verified(self) -> None:
        from squeeze_core.intelligence.contracts import (
            HorizonModelSnapshot,
            MagnitudeEstimateSnapshot,
        )

        model = HorizonModelSnapshot(
            model_version="ss_rare_event_ensemble_v1",
            status="CALIBRATED",
            pit_verified=True,
            occurrence_probability=0.42,
            hazard_by_horizon=((1, 0.1), (5, 0.35), (10, 0.5)),
            magnitude=MagnitudeEstimateSnapshot(
                expected_move_pct=8.5,
                upside_tail_pct=12.0,
                status="RESEARCH_ONLY",
                method="PHYSICAL_FORECAST_SQUEEZE_CONTEXT_V1",
                model_version="ss_magnitude_baseline_v1",
            ),
        )
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=72.0, ignition=65.0, classification="WATCH"),
            horizon_model=model,
        )
        self.assertEqual(result.model_version, "squeeze_causal_baseline.v4")
        calibrated = [hp for hp in result.horizon_probabilities if hp.status == "CALIBRATED"]
        self.assertGreater(len(calibrated), 0)
        codes = {item.code for item in result.supporting_evidence}
        self.assertIn("CALIBRATED_HORIZON_PROBABILITY", codes)
        self.assertIn("MAGNITUDE_ESTIMATE", codes)

    def test_stale_short_interest_adds_quality_flag(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(
                RuleSnapshot(
                    rule_id="PUBLISHED_SHORT_INTEREST_AVAILABLE",
                    category="SHORT_PRESSURE_CONFIRMATION",
                    outcome="UNKNOWN",
                ),
            ),
            adam=AdamSnapshot(pressure=None, ignition=50.0, classification="UNEVALUABLE"),
            quality=QualitySnapshot(stale_fields=("published_short_interest",)),
        )
        self.assertIn("SHORT_INTEREST_STALE", result.quality_flags)

    def test_catalyst_strength_boosts_ignition(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=40.0, ignition=30.0, classification="WATCH"),
            cross_lane=CrossLaneSnapshot(
                catalyst_available=True,
                catalyst_strength=80.0,
            ),
        )
        self.assertIsNotNone(result.ignition_strength)
        assert result.ignition_strength is not None
        self.assertGreaterEqual(result.ignition_strength, 72.0)
        codes = {item.code for item in result.supporting_evidence}
        self.assertIn("CATALYST_STRENGTH", codes)

    def test_thesis_invalidation_adds_contradicting_evidence(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=40.0, ignition=30.0, classification="WATCH"),
            cross_lane=CrossLaneSnapshot(thesis_invalidation_score=70.0),
        )
        codes = {item.code for item in result.contradicting_evidence}
        self.assertIn("THESIS_INVALIDATED", codes)

    def test_lending_snapshot_sets_constraint_pressure(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=50.0, ignition=30.0, classification="WATCH"),
            cross_lane=CrossLaneSnapshot(
                lending_available=True,
                lending_fee_rate=15.0,
                lending_shares_available=25000,
            ),
        )
        self.assertIsNotNone(result.constraint_pressure)
        assert result.constraint_pressure is not None
        self.assertGreaterEqual(result.constraint_pressure, 40.0)
        codes = {item.code for item in result.supporting_evidence}
        self.assertIn("LENDING_SNAPSHOT_CONSTRAINT", codes)

    def test_attention_tags_amplified_mechanism(self) -> None:
        result = evaluate_squeeze_intelligence(
            rules=(),
            adam=AdamSnapshot(pressure=55.0, ignition=55.0, classification="WATCH"),
            cross_lane=CrossLaneSnapshot(attention_available=True, attention_acceleration=12.0),
        )
        labels = {label.value for label in result.mechanism_labels}
        self.assertIn("ATTENTION_AMPLIFIED", labels)


if __name__ == "__main__":
    unittest.main()
