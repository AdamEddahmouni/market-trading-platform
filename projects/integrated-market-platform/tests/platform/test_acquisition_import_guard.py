"""P2-2: admitted platform trees cannot import the nested stock_data collector."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

PLATFORM_SRC = Path(__file__).resolve().parents[2] / "src" / "market_platform_foundation"
RESEARCH_SRC = PLATFORM_SRC / "research"

FORBIDDEN_ROOTS = ("pipelines.stock_data", "stock_data")


def _forbidden_module(name: str) -> bool:
    lowered = name.lower().strip()
    if not lowered:
        return False
    for root in FORBIDDEN_ROOTS:
        if lowered == root or lowered.startswith(root + "."):
            return True
    return False


def _import_hits(root: Path) -> list[str]:
    hits: list[str] = []
    for path in root.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        relative = path.as_posix()
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names.append(module)
                if module.lower() == "pipelines":
                    names.extend(f"pipelines.{alias.name}" for alias in node.names)
            for name in names:
                if _forbidden_module(name):
                    hits.append(f"{relative}:{name}")
    return hits


class AcquisitionImportGuardTests(unittest.TestCase):
    def test_research_tree_does_not_import_stock_data(self) -> None:
        self.assertTrue(RESEARCH_SRC.is_dir())
        self.assertEqual(_import_hits(RESEARCH_SRC), [])

    def test_admitted_platform_package_does_not_import_stock_data(self) -> None:
        self.assertTrue(PLATFORM_SRC.is_dir())
        self.assertEqual(_import_hits(PLATFORM_SRC), [])


if __name__ == "__main__":
    unittest.main()
