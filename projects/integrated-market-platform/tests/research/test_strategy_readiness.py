"""Executable strategy-readiness vector (STRATEGY_READINESS_MODEL)."""

from __future__ import annotations

import unittest

from market_platform_foundation.research.strategy_readiness import (
    ReadinessAxis,
    ReadinessAxisState,
    StrategyReadinessError,
    StrategyReadinessRegistry,
    builtin_family_catalog,
    derive_summary_label,
    live_eligibility_state,
    validate_readiness_vector,
)


def _all_planned(**overrides: object) -> dict[str, object]:
    payload = {axis.value: {"state": "PLANNED"} for axis in ReadinessAxis}
    payload.update(overrides)
    return payload


class StrategyReadinessContractTests(unittest.TestCase):
    def test_ten_axes_required(self) -> None:
        payload = _all_planned()
        payload.pop(ReadinessAxis.LIVE_ELIGIBILITY.value)
        with self.assertRaises(StrategyReadinessError) as ctx:
            validate_readiness_vector("SHORT_SQUEEZE", payload)
        self.assertIn("READINESS_AXIS_MISSING", str(ctx.exception))

    def test_unknown_maturity_field_rejected(self) -> None:
        payload = _all_planned(maturity="RESEARCH_READY")
        with self.assertRaises(StrategyReadinessError) as ctx:
            validate_readiness_vector("SHORT_SQUEEZE", payload)
        self.assertIn("READINESS_MATURITY_FIELD_FORBIDDEN", str(ctx.exception))

    def test_validated_requires_evidence_refs(self) -> None:
        payload = _all_planned(
            **{
                ReadinessAxis.SIGNAL_STRATEGY_IMPLEMENTATION.value: {
                    "state": "VALIDATED",
                }
            }
        )
        with self.assertRaises(StrategyReadinessError) as ctx:
            validate_readiness_vector("SHORT_SQUEEZE", payload)
        self.assertIn("READINESS_VALIDATED_EVIDENCE_REQUIRED", str(ctx.exception))

    def test_live_not_inferred_from_other_validated_axes(self) -> None:
        payload = {
            axis.value: {
                "state": "VALIDATED",
                "evidence_refs": (f"docs/research/{axis.value}.md",),
            }
            for axis in ReadinessAxis
            if axis is not ReadinessAxis.LIVE_ELIGIBILITY
        }
        payload[ReadinessAxis.LIVE_ELIGIBILITY.value] = {"state": "BLOCKED"}
        vector = validate_readiness_vector("SHORT_SQUEEZE", payload)
        self.assertEqual(live_eligibility_state(vector), ReadinessAxisState.BLOCKED)
        self.assertNotEqual(derive_summary_label(vector), "LIVE_ELIGIBLE")
        self.assertEqual(vector.axes[ReadinessAxis.LIVE_ELIGIBILITY].state, ReadinessAxisState.BLOCKED)

    def test_paper_ready_blocked_when_calibration_blocking(self) -> None:
        payload = _all_planned(
            **{
                ReadinessAxis.RESEARCH_MATURITY.value: {"state": "IMPLEMENTED"},
                ReadinessAxis.DATA_READINESS_AND_RIGHTS.value: {"state": "IMPLEMENTED"},
                ReadinessAxis.SIGNAL_STRATEGY_IMPLEMENTATION.value: {"state": "IMPLEMENTED"},
                ReadinessAxis.HISTORICAL_OOS_VALIDATION.value: {"state": "IMPLEMENTED"},
                ReadinessAxis.PROSPECTIVE_SHADOW.value: {"state": "IMPLEMENTED"},
                ReadinessAxis.PAPER_EXECUTION.value: {"state": "IMPLEMENTED"},
                ReadinessAxis.EXECUTION_MODEL_CALIBRATION.value: {"state": "BLOCKED"},
                ReadinessAxis.LIVE_ELIGIBILITY.value: {"state": "BLOCKED"},
            }
        )
        vector = validate_readiness_vector("NEWS_CATALYST", payload)
        self.assertEqual(derive_summary_label(vector), "SHADOW_READY")

    def test_builtin_catalog_does_not_claim_live_or_oos_edge(self) -> None:
        catalog = builtin_family_catalog()
        squeeze = catalog.require("SHORT_SQUEEZE")
        news = catalog.require("NEWS_CATALYST")
        self.assertEqual(
            squeeze.axes[ReadinessAxis.LIVE_ELIGIBILITY].state,
            ReadinessAxisState.BLOCKED,
        )
        self.assertEqual(
            news.axes[ReadinessAxis.LIVE_ELIGIBILITY].state,
            ReadinessAxisState.BLOCKED,
        )
        self.assertNotEqual(
            squeeze.axes[ReadinessAxis.HISTORICAL_OOS_VALIDATION].state,
            ReadinessAxisState.VALIDATED,
        )
        self.assertEqual(
            squeeze.axes[ReadinessAxis.SIGNAL_STRATEGY_IMPLEMENTATION].state,
            ReadinessAxisState.IMPLEMENTED,
        )
        self.assertTrue(
            squeeze.axes[ReadinessAxis.SIGNAL_STRATEGY_IMPLEMENTATION].evidence_refs
        )
        crypto = catalog.require("CRYPTO_ONCHAIN")
        self.assertIn(
            crypto.axes[ReadinessAxis.SIGNAL_STRATEGY_IMPLEMENTATION].state,
            (ReadinessAxisState.NOT_STARTED, ReadinessAxisState.PLANNED),
        )
        # OOS harness/lab exists; INCONCLUSIVE/fixture is IMPLEMENTED, never VALIDATED.
        self.assertEqual(derive_summary_label(squeeze), "OOS_READY")
        self.assertEqual(derive_summary_label(news), "OOS_READY")

    def test_unknown_family_fails_closed(self) -> None:
        catalog = StrategyReadinessRegistry()
        with self.assertRaises(StrategyReadinessError) as ctx:
            catalog.require("INVENTED_EDGE")
        self.assertIn("UNKNOWN_STRATEGY_FAMILY", str(ctx.exception))

    def test_round_trip_dict(self) -> None:
        vector = builtin_family_catalog().require("SHORT_SQUEEZE")
        restored = validate_readiness_vector(vector.family_id, vector.to_dict()["axes"])
        self.assertEqual(restored.to_dict(), vector.to_dict())

    def test_package_reexport(self) -> None:
        from market_platform_foundation import research

        self.assertIs(research.validate_readiness_vector, validate_readiness_vector)
        self.assertEqual(research.READINESS_SCHEMA_VERSION, "research/strategy_readiness/1.0.0")


if __name__ == "__main__":
    unittest.main()
