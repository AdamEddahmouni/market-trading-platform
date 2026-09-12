"""FTEP profile reference composition (docs paths + SHA binding only)."""

from __future__ import annotations

import unittest
from pathlib import Path

from market_platform_foundation.intelligence.paper_forward_bridge.ftep_profile_refs import (
    load_ftep_profile_ref,
    load_ftep_v1_001_profile_stack,
    profile_stack_to_manifest_bindings,
)


class FtepProfileRefTests(unittest.TestCase):
    def test_v1_001_stack_loads_three_profile_docs(self) -> None:
        root = Path(__file__).resolve().parents[2]
        stack = load_ftep_v1_001_profile_stack(repo_root=root)
        self.assertEqual(
            [row.profile_version_id for row in stack],
            ["FTEP_CORE_V1", "FUTURES_PROFILE_V1", "NEWS_CATALYST_PROFILE_V1"],
        )
        for row in stack:
            self.assertTrue(row.doc_path.is_file())
            self.assertEqual(len(row.doc_sha256), 64)
            self.assertIsNotNone(row.classification)

    def test_manifest_bindings_reference_docs_without_rule_duplication(self) -> None:
        root = Path(__file__).resolve().parents[2]
        stack = load_ftep_v1_001_profile_stack(repo_root=root)
        bindings = profile_stack_to_manifest_bindings(stack)
        self.assertEqual(bindings["ftep_core_version"], "FTEP_CORE_V1")
        self.assertEqual(bindings["asset_profile_version"], "FUTURES_PROFILE_V1")
        self.assertEqual(bindings["strategy_profile_version"], "NEWS_CATALYST_PROFILE_V1")
        self.assertEqual(len(bindings["profile_doc_bindings"]), 3)

    def test_core_profile_sha_is_stable_for_known_doc(self) -> None:
        root = Path(__file__).resolve().parents[2]
        ref = load_ftep_profile_ref("FTEP_CORE_V1", repo_root=root)
        again = load_ftep_profile_ref("FTEP_CORE_V1", repo_root=root)
        self.assertEqual(ref.doc_sha256, again.doc_sha256)


if __name__ == "__main__":
    unittest.main()
