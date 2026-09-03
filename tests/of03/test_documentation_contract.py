from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class DocumentationContractTests(unittest.TestCase):
    def test_ops_pack_and_spec_exist(self) -> None:
        for rel in (
            "docs/operations/of-03/README.md",
            "docs/operations/of-03/RUNBOOK.md",
            "docs/operations/of-03/SOPS.md",
            "docs/operations/of-03/WORKFLOWS.md",
            "docs/operations/of-03/AGENT_OPERATING_RULES.md",
            "docs/superpowers/specs/2026-08-29-imp-of-03-governed-workflow-sop-capability-registry-implementation-spec.md",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_agent_rules_cover_required_prohibitions(self) -> None:
        text = (ROOT / "docs/operations/of-03/AGENT_OPERATING_RULES.md").read_text(encoding="utf-8")
        for needle in (
            "self-register",
            "implicit latest",
            "treat registration as authorization",
            "execution engine",
            "human-approval",
        ):
            self.assertIn(needle, text.lower())


if __name__ == "__main__":
    unittest.main()
