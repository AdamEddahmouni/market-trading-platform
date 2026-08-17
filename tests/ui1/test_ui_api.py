"""UI-001 acceptance and API contract tests."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import canonical_bytes, load_json_strict
from market_platform_foundation.ui1_assertions import MANDATORY_IDS, aggregate_status, build_registry, evaluate_run
from market_platform_foundation.ui_api.projections import (
    build_attention_page,
    build_capabilities,
    build_context_payload,
    build_explain_payload,
    build_inspect_payload,
)
from market_platform_foundation.ui_api.server import canonical_response_bytes
from market_platform_foundation.ui_api.store import ReplayStore
from tools.ui1.run_ui_api import build_evidence

COLLECTION_ROOT = ROOT.parent
REGISTRY_PATH = ROOT / "manifests/ui1/assertion-predicates.json"


class Ui1ApiTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=COLLECTION_ROOT)
        cls.store.load()

    def test_registry_mandatory_ids(self) -> None:
        registry = build_registry(REGISTRY_PATH)
        self.assertEqual(set(registry["mandatory_ids"]), set(MANDATORY_IDS))

    def test_context_replay_mode(self) -> None:
        ctx = build_context_payload(self.store)
        as_of = ctx["as_of_context"]
        self.assertIsInstance(as_of, dict)
        self.assertEqual(as_of["mode"], "REPLAY")
        self.assertTrue(as_of["as_of_time"])
        self.assertEqual(as_of["timezone"], "America/New_York")

    def test_capabilities_fail_closed(self) -> None:
        caps = build_capabilities(self.store)
        by_id = {row["capability_id"]: row for row in caps}
        self.assertEqual(by_id["bars.intraday_1m"]["state"], "AVAILABLE")
        self.assertEqual(by_id["depth.L2"]["state"], "UNSUPPORTED")
        self.assertEqual(by_id["whale.disclosure"]["state"], "AVAILABLE")
        whale_rows = [row for row in caps if str(row["capability_id"]).startswith("whale.")]
        self.assertTrue(whale_rows)
        self.assertEqual(by_id["whale.regulatory_disclosure"]["state"], "AVAILABLE")
        self.assertEqual(by_id["whale.order_flow"]["state"], "AVAILABLE")
        unsupported = [
            row
            for row in whale_rows
            if row["capability_id"]
            not in {"whale.disclosure", "whale.regulatory_disclosure", "whale.order_flow"}
        ]
        self.assertTrue(all(row["state"] == "UNSUPPORTED" for row in unsupported))

    def test_attention_explain_chain(self) -> None:
        page = build_attention_page(self.store)
        for item in page["items"]:
            ref = item["explanation_ref"]
            if ref.startswith("explain:squeeze:"):
                continue
            build_explain_payload(self.store, ref)
            build_inspect_payload(self.store, ref.replace("explain:", "inspect:", 1))

    def test_squeeze_explain_with_mock(self) -> None:
        from unittest.mock import patch

        with patch(
            "market_platform_foundation.donor_bridge.projections.build_workspace_squeeze_payload",
            return_value={
                "available": True,
                "ignition_state": "INSUFFICIENT_EVIDENCE",
                "outcome_status": "UNKNOWN",
                "evidence_coverage": "15 / 25",
                "disclaimer": "Research only.",
            },
        ):
            payload = build_explain_payload(self.store, "explain:squeeze:BIYA")
        self.assertEqual(payload["explanation"]["ref"], "explain:squeeze:BIYA")

    def test_determinism(self) -> None:
        index = self.store.cursor_index
        first = canonical_response_bytes(build_context_payload(self.store))
        self.store.set_cursor_index(max(0, index - 1))
        self.store.set_cursor_index(index)
        second = canonical_response_bytes(build_context_payload(self.store))
        self.assertEqual(first, second)

    def test_pipeline_aggregate_pass(self) -> None:
        output_dir = ROOT / "evidence/ui1/.pytest-run"
        if output_dir.exists():
            for child in output_dir.iterdir():
                child.unlink()
        else:
            output_dir.mkdir(parents=True)
        try:
            report = build_evidence(output_dir)
            self.assertEqual(report["aggregate_status"], "PASS")
            results_doc = load_json_strict(output_dir / "assertion-results.json")
            statuses = {row["assertion_id"]: row["status"] for row in results_doc["results"]}
            for assertion_id in MANDATORY_IDS:
                self.assertEqual(statuses[assertion_id], "PASS")
        finally:
            if output_dir.exists():
                for child in output_dir.iterdir():
                    child.unlink()
                output_dir.rmdir()


    def test_publication_verifier_passes(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools/ui1/verify_ui1_publication.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_assistant_read_only_flow(self) -> None:
        from market_platform_foundation.ui_api.assistant_projections import (
            build_assistant_status,
            create_assistant_conversation,
            submit_assistant_prompt,
        )

        status = build_assistant_status(self.store)
        self.assertEqual(status["authority_boundary"], "READ_ONLY_NO_EXECUTION")
        conversation = create_assistant_conversation(self.store, title="UI test session")
        conversation_id = str(conversation["conversation_id"])
        prompt_result = submit_assistant_prompt(self.store, conversation_id, "Why is BIYA here?")
        self.assertTrue(prompt_result["assistant_message"]["provenance"]["abstained"])


if __name__ == "__main__":
    unittest.main()
