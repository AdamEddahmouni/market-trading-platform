"""UI-002 expanded research UI acceptance tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.ui_api.projections import (
    build_research_models_payload,
    build_research_simulation_payload,
    build_workspace_institutional_flow_payload,
)
from market_platform_foundation.ui_api.server import canonical_response_bytes
from market_platform_foundation.ui_api.store import ReplayStore
from tools.ui2.run_ui2_evidence import build_evidence


class Ui2ApiTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=COLLECTION_ROOT)
        cls.store.load()

    def test_institutional_flow_eight_families(self) -> None:
        payload = build_workspace_institutional_flow_payload(self.store, self.store.instrument_id)
        families = payload["families"]
        self.assertEqual(len(families), 8)
        family_ids = {row["family_id"] for row in families}
        self.assertEqual(
            family_ids,
            {
                "regulatory_disclosure",
                "large_transactions",
                "order_flow",
                "order_book",
                "options",
                "futures_positioning",
                "fund_etf_cross_asset",
                "public_catalyst",
            },
        )

    def test_models_and_simulation_determinism(self) -> None:
        index = self.store.cursor_index
        models_a = canonical_response_bytes(build_research_models_payload(self.store))
        sim_a = canonical_response_bytes(build_research_simulation_payload(self.store))
        self.store.set_cursor_index(max(0, index - 1))
        self.store.set_cursor_index(index)
        models_b = canonical_response_bytes(build_research_models_payload(self.store))
        sim_b = canonical_response_bytes(build_research_simulation_payload(self.store))
        self.assertEqual(models_a, models_b)
        self.assertEqual(sim_a, sim_b)

    def test_simulation_read_only_boundary(self) -> None:
        payload = build_research_simulation_payload(self.store)
        self.assertEqual(payload["authority_boundary"], "READ_ONLY_SIMULATION")
        self.assertEqual(payload["mode_label"], "SIMULATION")

    def test_pit_filtering_excludes_future_rows(self) -> None:
        models = build_research_models_payload(self.store)
        cutoff = self.store.prediction_cutoff()
        for row in models["interpretations"]:
            obs_time = row.get("observation_time", row.get("prediction_cutoff"))
            self.assertIsNotNone(obs_time)
            self.assertLessEqual(int(obs_time), cutoff)

    def test_pipeline_aggregate_pass(self) -> None:
        output_dir = ROOT / "evidence/ui2/.pytest-run"
        if output_dir.exists():
            for child in output_dir.iterdir():
                if child.is_file():
                    child.unlink()
        else:
            output_dir.mkdir(parents=True)
        try:
            report = build_evidence(output_dir)
            self.assertEqual(report["aggregate_status"], "PASS")
        finally:
            if output_dir.exists():
                for child in output_dir.iterdir():
                    if child.is_file():
                        child.unlink()
                output_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
