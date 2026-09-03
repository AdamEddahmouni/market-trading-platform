"""Documentation contract conformance for OF-01 operations pack."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from market_platform_foundation.of01.operations import CAPABILITY_IDS

REPO_ROOT = Path(__file__).resolve().parents[2]
OPS_DIR = REPO_ROOT / "docs" / "operations" / "of-01"


class TestDocumentationContract(unittest.TestCase):
    def test_sop_ids_unique_and_complete(self) -> None:
        sops = (OPS_DIR / "SOPS.md").read_text(encoding="utf-8")
        found = re.findall(r"SOP-OF01-(\d{3})", sops)
        numbers = sorted({int(n) for n in found})
        self.assertEqual(numbers, list(range(1, 19)))

    def test_workflow_ids_unique_and_complete(self) -> None:
        workflows = (OPS_DIR / "WORKFLOWS.md").read_text(encoding="utf-8")
        found = re.findall(r"WF-OF01-(\d{3})", workflows)
        numbers = sorted({int(n) for n in found})
        self.assertEqual(numbers, list(range(1, 19)))

    def test_documented_capabilities_exist_in_registry(self) -> None:
        readme = (OPS_DIR / "README.md").read_text(encoding="utf-8")
        referenced = set(re.findall(r"OF01\.OP\.[A-Z0-9_]+", readme))
        sops = (OPS_DIR / "SOPS.md").read_text(encoding="utf-8")
        referenced.update(re.findall(r"OF01\.OP\.[A-Z0-9_]+", sops))
        missing = referenced - CAPABILITY_IDS
        self.assertEqual(missing, set(), f"capabilities missing from registry: {missing}")

    def test_internal_links_resolve(self) -> None:
        for path in OPS_DIR.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            for match in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if match.startswith("http") or match.startswith("#"):
                    continue
                link_path = match.split("#", 1)[0]
                if not link_path:
                    continue
                target = (path.parent / link_path).resolve()
                self.assertTrue(target.exists(), f"broken link {match} in {path.name}")


if __name__ == "__main__":
    unittest.main()
