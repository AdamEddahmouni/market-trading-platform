"""Unit tests must not leak tempfile.mkdtemp() directories."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"


def _leaky_tempfile_calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    leaks: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.value.id == "tempfile":
                name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        if name == "mkdtemp":
            leaks.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:tempfile.mkdtemp")
        if name == "NamedTemporaryFile":
            for keyword in node.keywords:
                if keyword.arg == "delete" and isinstance(keyword.value, ast.Constant) and keyword.value.value is False:
                    leaks.append(
                        f"{path.relative_to(ROOT).as_posix()}:{node.lineno}:NamedTemporaryFile(delete=False)"
                    )
    return leaks


class UnitTestTempfileHermeticityTests(unittest.TestCase):
    def test_tests_tree_has_no_leaky_tempfile_constructors(self) -> None:
        leaks: list[str] = []
        for path in TESTS.rglob("*.py"):
            if path.name == Path(__file__).name:
                continue
            leaks.extend(_leaky_tempfile_calls(path))
        self.assertEqual(leaks, [])


if __name__ == "__main__":
    unittest.main()
