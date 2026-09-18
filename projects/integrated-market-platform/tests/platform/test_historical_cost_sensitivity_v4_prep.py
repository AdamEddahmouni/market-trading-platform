"""Cost sensitivity v4 freeze prep — no OpenD execution."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from market_platform_foundation.intelligence.historical_research_harness.baseline_pack import (
    compute_experiment_definition_hash,
    verify_frozen_experiment_definition,
)
from market_platform_foundation.intelligence.historical_research_harness.cost_sensitivity_v4 import (
    HISTORICAL_COST_SENSITIVITY_V4_EXPERIMENT_ID,
    build_frozen_cost_sensitivity_v4_definition,
    load_pre_registered_methodology,
)

ROOT = Path(__file__).resolve().parents[2]
V3_HASH = "81EFC1B1E2650010962F81F5B58B7E614E1AC1C2232E7862890CBB37BF5F3F61"


class HistoricalCostSensitivityV4PrepTests(unittest.TestCase):
    def test_pre_registered_methodology_present(self) -> None:
        spec = load_pre_registered_methodology(ROOT)
        self.assertTrue(spec["spec_ready"])
        self.assertEqual(spec["proposed_experiment_id"], HISTORICAL_COST_SENSITIVITY_V4_EXPERIMENT_ID)
        self.assertEqual(len(spec["cost_slippage_bps_grid"]), spec["cost_slippage_bps_grid_size_max"])

    def test_frozen_definition_hash_verifies(self) -> None:
        frozen = build_frozen_cost_sensitivity_v4_definition(repository_root=ROOT, code_sha="lane-e-test-sha")
        self.assertEqual(frozen["parent_experiment_definition_hash"], V3_HASH)
        verify = verify_frozen_experiment_definition(frozen)
        self.assertTrue(verify["ok"])
        recomputed = compute_experiment_definition_hash(frozen)
        self.assertEqual(recomputed, frozen["experiment_definition_hash"])

    def test_frozen_definition_grid_matches_methodology(self) -> None:
        spec = load_pre_registered_methodology(ROOT)
        frozen = build_frozen_cost_sensitivity_v4_definition(repository_root=ROOT, code_sha="lane-e-test-sha")
        self.assertEqual(
            frozen["run_parameters"]["cost_slippage_bps_grid"],
            spec["cost_slippage_bps_grid"],
        )


if __name__ == "__main__":
    unittest.main()
