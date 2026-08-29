"""Documentation contract for the OF-02 operations pack."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from market_platform_foundation.of02.operations import CAPABILITY_IDS

REPO_ROOT = Path(__file__).resolve().parents[2]
OPS_DIR = REPO_ROOT / "docs" / "operations" / "of-02"


class TestOf02DocumentationContract(unittest.TestCase):
    def test_sop_ids(self) -> None:
        sops = (OPS_DIR / "SOPS.md").read_text(encoding="utf-8")
        found = re.findall(r"SOP-OF02-(\d{3})", sops)
        self.assertEqual(sorted({int(n) for n in found}), list(range(1, 9)))

    def test_capabilities_exist(self) -> None:
        text = "\n".join(path.read_text(encoding="utf-8") for path in OPS_DIR.glob("*.md"))
        referenced = set(re.findall(r"OF02\.OP\.[A-Z0-9_]+", text))
        self.assertTrue(referenced <= CAPABILITY_IDS, referenced - CAPABILITY_IDS)

    def test_links_resolve(self) -> None:
        for path in OPS_DIR.glob("*.md"):
            for match in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if match.startswith("http") or match.startswith("#"):
                    continue
                link_path = match.split("#", 1)[0]
                if not link_path:
                    continue
                target = (path.parent / link_path).resolve()
                self.assertTrue(target.exists(), f"broken link {match} in {path.name}")
