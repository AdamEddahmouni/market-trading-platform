"""BUILD 09 detector engine and bounded-state tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import (
    DetectionSeverity,
    ForecastEstimate,
    ForecastTarget,
    ForecastV1,
    QualityState,
    QualitySummary,
    SemanticEventType,
    TimeHorizonNs,
)
from market_platform_foundation.intelligence.quality import DecisionAction
from market_platform_foundation.intelligence.routing import (
    DetectionFrame,
    DetectionPolicyV1,
    DetectorSupportStatus,
    EventDetectorEngine,
    RegimeContext,
)
from tests.intelligence.routing_fixtures import (
    T,
    WINDOW_NS,
    event,
    quality_decision,
    signal,
    snapshot,
)


class EventDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = EventDetectorEngine()

    def _frame(self, index: int, *, nss: float | None = None, spread_bps: float | None = None):
        snap = snapshot(f"snap-{index}", decision_time_ns=T + index)
        signals = []
        if nss is not None:
            signals.append(signal(snap, f"nss-{index}", "net_signed_share", nss, window_ns=WINDOW_NS))
        if spread_bps is not None:
            signals.append(signal(snap, f"spread-{index}", "spread_bps", spread_bps))
        return DetectionFrame(
            snapshot=snap,
            signals=tuple(reversed(signals)),
            quality_decision=quality_decision(decision_time_ns=snap.decision_time_ns),
        )

    def test_bullish_and_bearish_reversals_are_edge_triggered(self) -> None:
        self.assertEqual(self.engine.detect(self._frame(1, nss=-0.20)).detections, ())
        bullish = self.engine.detect(self._frame(2, nss=0.20)).detections
        self.assertEqual(len(bullish), 1)
        self.assertEqual(bullish[0].semantic_event_type, SemanticEventType.ORDER_FLOW_REVERSAL)
        self.assertEqual(bullish[0].reason_codes, ("NSS_NEGATIVE_TO_POSITIVE",))
        self.assertEqual(self.engine.detect(self._frame(3, nss=0.40)).detections, ())
        bearish = self.engine.detect(self._frame(4, nss=-0.40)).detections
        self.assertEqual(bearish[0].reason_codes, ("NSS_POSITIVE_TO_NEGATIVE",))

    def test_deadband_noise_does_not_replace_last_material_state(self) -> None:
        self.engine.detect(self._frame(1, nss=-0.20))
        self.assertEqual(self.engine.detect(self._frame(2, nss=0.01)).detections, ())
        detected = self.engine.detect(self._frame(3, nss=0.20)).detections
        self.assertEqual(len(detected), 1)

    def test_wrong_window_missing_and_degraded_nss_do_not_trigger(self) -> None:
        first = self._frame(1, nss=-0.20)
        wrong_signal = signal(first.snapshot, "wrong", "net_signed_share", -0.30, window_ns=60_000_000_000)
        result = self.engine.detect(
            DetectionFrame(
                snapshot=first.snapshot,
                signals=(wrong_signal,),
                quality_decision=first.quality_decision,
            )
        )
        self.assertIn("ORDER_FLOW_REVERSAL:MISSING_REQUIRED_SIGNAL", result.diagnostics)
        degraded_snap = snapshot("degraded", decision_time_ns=T + 2)
        degraded = signal(
            degraded_snap,
            "degraded-nss",
            "net_signed_share",
            0.40,
            window_ns=WINDOW_NS,
            quality=QualityState.DEGRADED,
        )
        rejected = self.engine.detect(
            DetectionFrame(
                snapshot=degraded_snap,
                signals=(degraded,),
                quality_decision=quality_decision(decision_time_ns=degraded_snap.decision_time_ns),
            )
        )
        self.assertIn("ORDER_FLOW_REVERSAL:INPUT_QUALITY_REJECTED", rejected.diagnostics)

    def test_liquidity_hysteresis_recovery_and_reentry(self) -> None:
        self.engine.detect(self._frame(1, spread_bps=20.0))
        entered = self.engine.detect(self._frame(2, spread_bps=60.0)).detections
        self.assertEqual(entered[0].semantic_event_type, SemanticEventType.LIQUIDITY_EVENT)
        self.assertEqual(self.engine.detect(self._frame(3, spread_bps=80.0)).detections, ())
        self.assertEqual(self.engine.detect(self._frame(4, spread_bps=40.0)).detections, ())
        self.assertEqual(self.engine.detect(self._frame(5, spread_bps=25.0)).detections, ())
        reentered = self.engine.detect(self._frame(6, spread_bps=70.0)).detections
        self.assertEqual(len(reentered), 1)

    def test_invalid_numeric_signal_domains_do_not_change_state(self) -> None:
        self.engine.detect(self._frame(1, spread_bps=20.0, nss=-0.20))
        invalid = self.engine.detect(self._frame(2, spread_bps=-5.0, nss=1.20))
        self.assertIn("LIQUIDITY_EVENT:INVALID_SIGNAL_VALUE", invalid.diagnostics)
        self.assertIn("ORDER_FLOW_REVERSAL:INVALID_SIGNAL_VALUE", invalid.diagnostics)
        valid = self.engine.detect(self._frame(3, spread_bps=60.0, nss=0.20))
        self.assertEqual(
            {row.semantic_event_type for row in valid.detections},
            {SemanticEventType.ORDER_FLOW_REVERSAL, SemanticEventType.LIQUIDITY_EVENT},
        )

    def test_short_interest_change_requires_prior_canonical_observation(self) -> None:
        first_snap = snapshot("borrow-1", decision_time_ns=T + 1, event_ids=("si-1",))
        first = event(first_snap, "si-1", "SHORT_INTEREST", {"current_short_position_quantity": 100.0})
        first_result = self.engine.detect(
            DetectionFrame(
                snapshot=first_snap,
                events=(first,),
                quality_decision=quality_decision(decision_time_ns=first_snap.decision_time_ns),
            )
        )
        self.assertEqual(first_result.detections, ())
        second_snap = snapshot("borrow-2", decision_time_ns=T + 2, event_ids=("si-2",))
        second = event(second_snap, "si-2", "SHORT_INTEREST", {"current_short_position_quantity": 125.0})
        detected = self.engine.detect(
            DetectionFrame(
                snapshot=second_snap,
                events=(second,),
                quality_decision=quality_decision(decision_time_ns=second_snap.decision_time_ns),
            )
        ).detections
        self.assertEqual(detected[0].semantic_event_type, SemanticEventType.BORROW_CHANGE)
        self.assertNotIn("sentiment", detected[0].metadata)

    def test_invalid_short_interest_does_not_poison_prior_state(self) -> None:
        first_snap = snapshot("si-valid-1", decision_time_ns=T + 1, event_ids=("si-valid-1",))
        first = event(first_snap, "si-valid-1", "SHORT_INTEREST", {"current_short_position_quantity": 100.0})
        self.engine.detect(
            DetectionFrame(
                snapshot=first_snap,
                events=(first,),
                quality_decision=quality_decision(decision_time_ns=first_snap.decision_time_ns),
            )
        )
        bad_snap = snapshot("si-invalid", decision_time_ns=T + 2, event_ids=("si-invalid",))
        bad = event(bad_snap, "si-invalid", "SHORT_INTEREST", {"current_short_position_quantity": float("nan")})
        rejected = self.engine.detect(
            DetectionFrame(
                snapshot=bad_snap,
                events=(bad,),
                quality_decision=quality_decision(decision_time_ns=bad_snap.decision_time_ns),
            )
        )
        self.assertEqual(rejected.detections, ())
        self.assertIn("BORROW_CHANGE:INVALID_SHORT_INTEREST_VALUE", rejected.diagnostics)
        final_snap = snapshot("si-valid-2", decision_time_ns=T + 3, event_ids=("si-valid-2",))
        final = event(final_snap, "si-valid-2", "SHORT_INTEREST", {"current_short_position_quantity": 125.0})
        detected = self.engine.detect(
            DetectionFrame(
                snapshot=final_snap,
                events=(final,),
                quality_decision=quality_decision(decision_time_ns=final_snap.decision_time_ns),
            )
        )
        self.assertEqual(len(detected.detections), 1)

    def test_regime_shift_uses_external_context_only(self) -> None:
        snap = snapshot("regime", decision_time_ns=T + 1)
        result = self.engine.detect(
            DetectionFrame(
                snapshot=snap,
                quality_decision=quality_decision(decision_time_ns=snap.decision_time_ns),
                regime_context=RegimeContext(
                    previous_regime_key="TREND",
                    current_regime_key="HIGH_VOL",
                    source_context_version="fixture-regime/1",
                ),
            )
        )
        self.assertEqual(result.detections[0].semantic_event_type, SemanticEventType.REGIME_SHIFT)
        unchanged = self.engine.detect(
            DetectionFrame(
                snapshot=snapshot("regime-2", decision_time_ns=T + 2),
                quality_decision=quality_decision(decision_time_ns=T + 2),
                regime_context=RegimeContext("HIGH_VOL", "HIGH_VOL", "fixture-regime/1"),
            )
        )
        self.assertEqual(unchanged.detections, ())

    def test_support_matrix_is_explicit(self) -> None:
        support = {row.semantic_event_type: row for row in self.engine.support_matrix()}
        self.assertEqual(support[SemanticEventType.UNUSUAL_OPTIONS_ACTIVITY].status, DetectorSupportStatus.INACTIVE_INPUT_UNAVAILABLE)
        self.assertEqual(support[SemanticEventType.NEWS_EVENT].status, DetectorSupportStatus.INACTIVE_INPUT_UNAVAILABLE)
        self.assertEqual(support[SemanticEventType.REGIME_SHIFT].status, DetectorSupportStatus.IMPLEMENTED_WITH_EXTERNAL_CONTEXT)

    def test_identity_state_determinism_isolation_and_reset(self) -> None:
        def run(engine: EventDetectorEngine):
            outputs = []
            for frame in (self._frame(1, nss=-0.30), self._frame(2, nss=0.30)):
                outputs.extend(engine.detect(frame).detections)
            return tuple(row.detection_id for row in outputs), engine.state_snapshot()

        left = run(EventDetectorEngine())
        right = run(EventDetectorEngine())
        self.assertEqual(left, right)
        isolated = EventDetectorEngine()
        self.assertEqual(isolated.state_snapshot().scope_count, 0)
        isolated.detect(self._frame(1, nss=-0.30))
        isolated.reset()
        self.assertEqual(isolated.state_snapshot().scope_count, 0)

    def test_stale_or_duplicate_frame_cannot_rewrite_detector_visible_history(self) -> None:
        self.engine.detect(self._frame(1, nss=-0.30))
        current = self.engine.detect(self._frame(2, nss=0.30))
        self.assertEqual(len(current.detections), 1)

        stale = self.engine.detect(self._frame(1, nss=-0.40))
        duplicate = self.engine.detect(self._frame(2, nss=-0.40))

        self.assertEqual(stale.detections, ())
        self.assertEqual(duplicate.detections, ())
        self.assertIn("FRAME_DECISION_TIME_NOT_MONOTONIC", stale.diagnostics)
        self.assertIn("FRAME_DECISION_TIME_NOT_MONOTONIC", duplicate.diagnostics)

    def test_detection_identity_binds_full_policy_parameters(self) -> None:
        strict = EventDetectorEngine(DetectionPolicyV1(order_flow_threshold=0.20))
        permissive = EventDetectorEngine(DetectionPolicyV1(order_flow_threshold=0.15))
        for engine in (strict, permissive):
            engine.detect(self._frame(1, nss=-0.30))

        strict_detection = strict.detect(self._frame(2, nss=0.30)).detections[0]
        permissive_detection = permissive.detect(self._frame(2, nss=0.30)).detections[0]

        self.assertNotEqual(strict.policy.identity, permissive.policy.identity)
        self.assertNotEqual(strict_detection.detection_id, permissive_detection.detection_id)
        self.assertNotEqual(
            strict_detection.metadata["detector_policy_identity"],
            permissive_detection.metadata["detector_policy_identity"],
        )

    def test_fail_closed_frame_produces_no_detection(self) -> None:
        snap = snapshot("blocked", decision_time_ns=T + 1)
        frame = DetectionFrame(
            snapshot=snap,
            signals=(signal(snap, "blocked-nss", "net_signed_share", -0.5, window_ns=WINDOW_NS),),
            quality_decision=quality_decision(
                action=DecisionAction.FAIL_CLOSED,
                decision_time_ns=snap.decision_time_ns,
            ),
        )
        result = self.engine.detect(frame)
        self.assertEqual(result.detections, ())
        self.assertIn("FRAME_QUALITY_FAIL_CLOSED", result.diagnostics)

    def test_invalid_snapshot_produces_no_detection_or_state_update(self) -> None:
        bad = snapshot("invalid-snapshot", decision_time_ns=T + 1, quality=QualityState.INVALID)
        result = self.engine.detect(
            DetectionFrame(
                snapshot=bad,
                signals=(signal(bad, "invalid-nss", "net_signed_share", -0.5, window_ns=WINDOW_NS),),
                quality_decision=quality_decision(decision_time_ns=bad.decision_time_ns),
            )
        )
        self.assertEqual(result.detections, ())
        self.assertEqual(self.engine.state_snapshot().scope_count, 0)
        self.assertIn("FRAME_SNAPSHOT_QUALITY_INVALID", result.diagnostics)

    def test_baseline_forecasts_are_same_snapshot_only_and_do_not_fuse(self) -> None:
        snap = snapshot("baseline-frame", decision_time_ns=T + 1)

        def forecast(snapshot_id: str, forecast_id: str) -> ForecastV1:
            return ForecastV1(
                forecast_id=forecast_id,
                schema_version="1",
                scope=snap.scope,
                decision_time_ns=snap.decision_time_ns,
                snapshot_id=snapshot_id,
                target=ForecastTarget(
                    target_kind="direction_up_down",
                    instrument_id="US:XYZ",
                    parameters={},
                ),
                horizon=TimeHorizonNs(60_000_000_000),
                estimate=ForecastEstimate(estimate_kind="classification_probability", probability=0.9),
                quality=QualitySummary(state=QualityState.GOOD),
            )

        with self.assertRaisesRegex(ValueError, "FORECAST_SNAPSHOT_MISMATCH"):
            DetectionFrame(
                snapshot=snap,
                quality_decision=quality_decision(decision_time_ns=snap.decision_time_ns),
                baseline_forecasts=(forecast("other-snapshot", "forecast-wrong"),),
            )

        prior = self._frame(1, nss=-0.30)
        current = self._frame(2, nss=0.30)
        plain = EventDetectorEngine()
        contextual = EventDetectorEngine()
        plain.detect(prior)
        contextual.detect(prior)
        plain_detection = plain.detect(current).detections
        contextual_detection = contextual.detect(
            DetectionFrame(
                snapshot=current.snapshot,
                signals=current.signals,
                quality_decision=current.quality_decision,
                baseline_forecasts=(forecast(current.snapshot.snapshot_id, "forecast-current"),),
            )
        ).detections
        self.assertEqual(plain_detection, contextual_detection)

    def test_policy_validation_and_severity_are_not_probability(self) -> None:
        with self.assertRaisesRegex(ValueError, "LIQUIDITY_EXIT_MUST_BE_BELOW_ENTRY"):
            DetectionPolicyV1(liquidity_entry_bps=30.0, liquidity_exit_bps=30.0)
        self.engine.detect(self._frame(1, nss=-0.9))
        detected = self.engine.detect(self._frame(2, nss=0.9)).detections[0]
        self.assertEqual(detected.severity, DetectionSeverity.CRITICAL)
        self.assertNotIn("probability", detected.metadata)
        for invalid in (float("nan"), float("inf")):
            with self.assertRaisesRegex(ValueError, "ORDER_FLOW_THRESHOLD_INVALID"):
                DetectionPolicyV1(order_flow_threshold=invalid)
        for invalid in (True, 1.5):
            with self.assertRaisesRegex(ValueError, "ORDER_FLOW_WINDOW_NS_INVALID"):
                DetectionPolicyV1(order_flow_window_ns=invalid)
        with self.assertRaisesRegex(ValueError, "DETECTION_POLICY_IDENTITY_INVALID"):
            DetectionPolicyV1(policy_version="")


if __name__ == "__main__":
    unittest.main()
