"""Tests for SHARED P4 opportunity fusion."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.evidence import (  # noqa: E402
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    validate_evidence_dag,
)
from market_platform_foundation.cross_lane.fusion import (  # noqa: E402
    FUSION_METHOD,
    build_opportunity_snapshot,
    fuse_opportunity_v1,
    load_opportunity_fixture,
)
from market_platform_foundation.cross_lane.extractors import (  # noqa: E402
    extract_liquidity_input,
    extract_payoff_input,
    extract_probability_input,
    is_squeeze_aligned_template,
)
from market_platform_foundation.cross_lane.opportunity import (  # noqa: E402
    OPPORTUNITY_VERSION,
    OpportunityQualityFlag,
)
from market_platform_foundation.donor_bridge.opportunity_adapter import (  # noqa: E402
    build_opportunity_fusion_bundle,
    opportunity_evidence_from_snapshot,
)
from market_platform_foundation.options.strategy import build_strategy_snapshot  # noqa: E402

STRATEGY_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "options" / "nvda_strategy_optimizer_slice.json"
OPPORTUNITY_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "opportunity" / "nvda_opportunity_fusion_expected.json"


class OpportunityFusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.strategy_fixture = json.loads(STRATEGY_FIXTURE.read_text(encoding="utf-8"))
        cls.opportunity_fixture = json.loads(OPPORTUNITY_FIXTURE.read_text(encoding="utf-8"))

    def _bullish_strategy_snapshot(self) -> dict:
        scenario = self.strategy_fixture["scenarios"]["bullish_directional"]
        return build_strategy_snapshot(
            self.strategy_fixture["symbol"],
            self.strategy_fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=self.strategy_fixture["physical_forecast"],
            chain_rows=self.strategy_fixture["chain_rows"],
            friction=scenario["friction"],
        )

    def test_squeeze_aligned_template_detection(self) -> None:
        self.assertTrue(is_squeeze_aligned_template("long_call_atm", "ACTIVE_SQUEEZE"))
        self.assertFalse(is_squeeze_aligned_template("long_straddle", "ACTIVE_SQUEEZE"))
        self.assertFalse(is_squeeze_aligned_template("long_call_atm", "NEUTRAL"))

    def test_extract_payoff_from_strategy(self) -> None:
        strategy = self._bullish_strategy_snapshot()
        payoff = extract_payoff_input(strategy)
        self.assertTrue(payoff.available)
        self.assertEqual(payoff.template, "long_call_atm")
        self.assertIsNotNone(payoff.expected_pnl)

    def test_fail_closed_without_strategy(self) -> None:
        payoff = extract_payoff_input(None)
        self.assertFalse(payoff.available)
        snapshot = build_opportunity_snapshot(
            "NVDA",
            self.strategy_fixture["as_of_time"],
            strategy_snapshot=None,
        )
        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["outcome"], "UNAVAILABLE")

    def test_bullish_active_squeeze_fusion_golden(self) -> None:
        scenario = self.strategy_fixture["scenarios"]["bullish_directional"]
        strategy = self._bullish_strategy_snapshot()
        expected = self.opportunity_fixture["expected"]
        snapshot = build_opportunity_snapshot(
            "NVDA",
            self.strategy_fixture["as_of_time"],
            strategy_snapshot=strategy,
            physical_forecast=self.strategy_fixture["physical_forecast"],
            cross_lane_snapshot=self.opportunity_fixture["cross_lane_snapshot"],
            execution_friction=scenario["friction"],
        )
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["outcome"], expected["outcome"])
        self.assertEqual(snapshot["status"], expected["status"])
        self.assertEqual(snapshot["fused_net_ev"], expected["fused_net_ev"])
        self.assertEqual(snapshot["fusion"]["occurrence_weight"], expected["occurrence_weight"])
        self.assertEqual(snapshot["fusion"]["liquidity_factor"], expected["liquidity_factor"])
        self.assertEqual(snapshot["fusion"]["gross_ev_before_weights"], expected["gross_ev_before_weights"])
        self.assertEqual(snapshot["fusion"]["template"], expected["template"])
        self.assertEqual(snapshot["fusion"]["squeeze_aligned"], expected["squeeze_aligned"])
        self.assertEqual(snapshot["method"], FUSION_METHOD)
        self.assertEqual(snapshot["model_version"], OPPORTUNITY_VERSION)
        self.assertEqual(snapshot["replay_hash"], expected["replay_hash"])
        self.assertNotIn("universal_score", snapshot)

    def test_liquidity_blocked_zeroes_fusion(self) -> None:
        from market_platform_foundation.contracts.options_quality import OptionQualityFlag

        strategy = self._bullish_strategy_snapshot()
        strategy = dict(strategy)
        strategy["quality_flags"] = list(strategy.get("quality_flags", [])) + [
            OptionQualityFlag.STRATEGY_LIQUIDITY_BLOCKED.value
        ]
        strategy["reason"] = "ALL_CANDIDATES_LIQUIDITY_BLOCKED"
        liquidity = extract_liquidity_input(strategy_snapshot=strategy)
        self.assertFalse(liquidity.gates_passed)
        probability = extract_probability_input(
            cross_lane_snapshot=self.opportunity_fixture["cross_lane_snapshot"],
            physical_forecast=self.strategy_fixture["physical_forecast"],
        )
        payoff = extract_payoff_input(strategy)
        from market_platform_foundation.cross_lane.extractors import extract_cost_input

        costs = extract_cost_input(strategy)
        fused = fuse_opportunity_v1(probability, payoff, costs, liquidity)
        self.assertEqual(fused["outcome"], "NO_ACTIONABLE_EDGE")
        self.assertEqual(fused["fusion"]["liquidity_factor"], 0.0)

    def test_opportunity_evidence_ranked(self) -> None:
        scenario = self.strategy_fixture["scenarios"]["bullish_directional"]
        strategy = self._bullish_strategy_snapshot()
        snapshot = build_opportunity_snapshot(
            "NVDA",
            self.strategy_fixture["as_of_time"],
            strategy_snapshot=strategy,
            physical_forecast=self.strategy_fixture["physical_forecast"],
            cross_lane_snapshot=self.opportunity_fixture["cross_lane_snapshot"],
            execution_friction=scenario["friction"],
        )
        evidence = opportunity_evidence_from_snapshot(snapshot)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["signal"], EvidenceSignal.CROSS_LANE_OPPORTUNITY_FUSED.value)
        self.assertEqual(
            evidence[0]["provenance_class"],
            EvidenceProvenanceClass.CROSS_LANE_MODEL_OUTPUT.value,
        )

    def test_opportunity_evidence_no_actionable_edge(self) -> None:
        scenario = self.strategy_fixture["scenarios"]["flat_no_edge"]
        strategy = build_strategy_snapshot(
            self.strategy_fixture["symbol"],
            self.strategy_fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=self.strategy_fixture["physical_forecast"],
            chain_rows=self.strategy_fixture["chain_rows"],
            friction=scenario["friction"],
        )
        snapshot = build_opportunity_snapshot(
            "NVDA",
            self.strategy_fixture["as_of_time"],
            strategy_snapshot=strategy,
            physical_forecast=self.strategy_fixture["physical_forecast"],
        )
        evidence = opportunity_evidence_from_snapshot(snapshot)
        if snapshot.get("outcome") == "NO_ACTIONABLE_EDGE":
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0]["signal"], EvidenceSignal.OPPORTUNITY_NO_ACTIONABLE_EDGE.value)

    def test_fusion_bundle_dag_validation(self) -> None:
        scenario = self.strategy_fixture["scenarios"]["bullish_directional"]
        strategy = self._bullish_strategy_snapshot()
        squeeze_detail = {
            "causal_intelligence": {
                "state": "ACTIVE_SQUEEZE",
                "remaining_fuel": 72.0,
            }
        }
        bundle, evidence = build_opportunity_fusion_bundle(
            "NVDA",
            self.strategy_fixture["as_of_time"],
            strategy_snapshot=strategy,
            physical_forecast=self.strategy_fixture["physical_forecast"],
            squeeze_detail=squeeze_detail,
            execution_friction=scenario["friction"],
        )
        self.assertIn("opportunity_snapshot", bundle)
        self.assertTrue(bundle["opportunity_snapshot"]["available"])
        signals = {row["signal"] for row in evidence}
        self.assertIn(EvidenceSignal.CROSS_LANE_OPPORTUNITY_FUSED.value, signals)
        normalized = [
            NormalizedLaneEvidence(
                lane=LaneId(str(row["lane"])),
                signal=EvidenceSignal(str(row["signal"])),
                strength=str(row["strength"]),
                available=bool(row["available"]),
                source_ref=str(row["source_ref"]),
                detail=str(row["detail"]),
                provenance_class=EvidenceProvenanceClass(str(row["provenance_class"])),
            )
            for row in evidence
        ]
        self.assertEqual(validate_evidence_dag(normalized), [])

    def test_fixture_loader(self) -> None:
        loaded = load_opportunity_fixture("NVDA")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["symbol"], "NVDA")

    def test_replay_hash_stable(self) -> None:
        scenario = self.strategy_fixture["scenarios"]["bullish_directional"]
        strategy = self._bullish_strategy_snapshot()
        first = build_opportunity_snapshot(
            "NVDA",
            self.strategy_fixture["as_of_time"],
            strategy_snapshot=strategy,
            physical_forecast=self.strategy_fixture["physical_forecast"],
            cross_lane_snapshot=self.opportunity_fixture["cross_lane_snapshot"],
            execution_friction=scenario["friction"],
        )
        second = build_opportunity_snapshot(
            "NVDA",
            self.strategy_fixture["as_of_time"],
            strategy_snapshot=strategy,
            physical_forecast=self.strategy_fixture["physical_forecast"],
            cross_lane_snapshot=self.opportunity_fixture["cross_lane_snapshot"],
            execution_friction=scenario["friction"],
        )
        self.assertEqual(first["replay_hash"], second["replay_hash"])


class OccurrenceSemanticsTests(unittest.TestCase):
    """Direct semantic assertions for occurrence-weight handling (not hash-only)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.strategy_fixture = json.loads(STRATEGY_FIXTURE.read_text(encoding="utf-8"))
        cls.opportunity_fixture = json.loads(OPPORTUNITY_FIXTURE.read_text(encoding="utf-8"))

    def _build(self, cross_lane_snapshot: dict, scenario_key: str = "bullish_directional") -> dict:
        scenario = self.strategy_fixture["scenarios"][scenario_key]
        strategy = build_strategy_snapshot(
            self.strategy_fixture["symbol"],
            self.strategy_fixture["as_of_time"],
            executable_edge=scenario["executable_edge"],
            physical_forecast=self.strategy_fixture["physical_forecast"],
            chain_rows=self.strategy_fixture["chain_rows"],
            friction=scenario["friction"],
        )
        return build_opportunity_snapshot(
            "NVDA",
            self.strategy_fixture["as_of_time"],
            strategy_snapshot=strategy,
            physical_forecast=self.strategy_fixture["physical_forecast"],
            cross_lane_snapshot=cross_lane_snapshot,
            execution_friction=scenario["friction"],
        )

    def test_bullish_active_squeeze_with_available_evidence(self) -> None:
        """Squeeze-aligned + present hazard evidence fuses with hazard as weight."""
        snapshot = self._build(self.opportunity_fixture["cross_lane_snapshot"])
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["outcome"], "RANKED")
        fusion = snapshot["fusion"]
        self.assertTrue(fusion["squeeze_aligned"])
        self.assertEqual(fusion["occurrence_weight"], 0.999983)
        self.assertEqual(
            snapshot["probability"]["squeeze_hazard_probability"], 0.999983
        )
        self.assertNotIn(
            OpportunityQualityFlag.OCCURRENCE_UNAVAILABLE.value,
            snapshot["quality_flags"],
        )
        expected_ev = round(
            fusion["gross_ev_before_weights"] * fusion["occurrence_weight"] * fusion["liquidity_factor"], 6
        )
        self.assertEqual(fusion["fused_net_ev"], expected_ev)

    def test_missing_occurrence_evidence_fails_closed(self) -> None:
        """Squeeze-aligned template with NO probability lane output must not fuse as full occurrence."""
        from market_platform_foundation.cross_lane.fusion import fuse_opportunity_v1
        from market_platform_foundation.cross_lane.opportunity import (
            CostInput,
            LiquidityInput,
            PayoffInput,
            ProbabilityInput,
        )

        probability = ProbabilityInput(
            available=True,
            squeeze_occurrence_probability=None,
            squeeze_hazard_probability=None,
            squeeze_state="ACTIVE_SQUEEZE",
        )
        payoff = PayoffInput(available=True, expected_pnl=100.0, template="long_call_atm")
        costs = CostInput(available=True, friction_cost=0.0)
        liquidity = LiquidityInput(available=True, gates_passed=True)
        fused = fuse_opportunity_v1(probability, payoff, costs, liquidity)
        self.assertFalse(fused["available"])
        self.assertEqual(fused["outcome"], "UNAVAILABLE")
        self.assertEqual(fused["reason"], "OCCURRENCE_UNAVAILABLE")
        self.assertIn(
            OpportunityQualityFlag.OCCURRENCE_UNAVAILABLE.value,
            fused["quality_flags"],
        )
        self.assertIsNone(fused["fusion"])

    def test_inactive_squeeze_is_not_occurrence_conditioned(self) -> None:
        """Neutral squeeze state: no occurrence weighting, no silent 1.0-as-evidence."""
        cross_lane = dict(self.opportunity_fixture["cross_lane_snapshot"])
        cross_lane["squeeze_state"] = "NEUTRAL"
        snapshot = self._build(cross_lane)
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["outcome"], "RANKED")
        fusion = snapshot["fusion"]
        self.assertFalse(fusion["squeeze_aligned"])
        self.assertIsNone(fusion["occurrence_weight"])
        self.assertEqual(fusion["fused_net_ev"], fusion["gross_ev_before_weights"])
        self.assertIn(
            OpportunityQualityFlag.OCCURRENCE_UNAVAILABLE.value,
            snapshot["quality_flags"],
        )

    def test_deterministic_identical_input_replay(self) -> None:
        """Identical inputs produce byte-identical snapshots (canonical serialization)."""
        first = self._build(self.opportunity_fixture["cross_lane_snapshot"])
        second = self._build(self.opportunity_fixture["cross_lane_snapshot"])
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual(first["replay_hash"], second["replay_hash"])

    def test_input_order_independence(self) -> None:
        """Key insertion order in lane snapshot dicts must not change the fused result."""
        forward = self.opportunity_fixture["cross_lane_snapshot"]
        reversed_snapshot = dict(reversed(list(forward.items())))
        self.assertEqual(
            self._build(forward)["replay_hash"],
            self._build(reversed_snapshot)["replay_hash"],
        )

    def test_provenance_preserved_on_fused_snapshot(self) -> None:
        """Evidence/provenance classes survive the fusion -> evidence adapter path."""
        from market_platform_foundation.cross_lane.evidence import (
            EvidenceProvenanceClass,
            EvidenceSignal,
        )
        from market_platform_foundation.donor_bridge.opportunity_adapter import (
            opportunity_evidence_from_snapshot,
        )

        snapshot = self._build(self.opportunity_fixture["cross_lane_snapshot"])
        evidence = opportunity_evidence_from_snapshot(snapshot)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["signal"], EvidenceSignal.CROSS_LANE_OPPORTUNITY_FUSED.value)
        self.assertEqual(
            evidence[0]["provenance_class"],
            EvidenceProvenanceClass.CROSS_LANE_MODEL_OUTPUT.value,
        )
        self.assertTrue(str(evidence[0]["source_ref"]))


if __name__ == "__main__":
    unittest.main()
