"""XA-05 authority and protected-boundary tests."""

from __future__ import annotations

import ast
import importlib
import pkgutil
import unittest
from pathlib import Path

from market_platform_foundation.xa01.registry import get_registry as get_xa01_registry
from market_platform_foundation.xa02.registry import get_registry as get_xa02_registry
from market_platform_foundation.xa03.registry import get_registry as get_xa03_registry
from market_platform_foundation.xa05.operations import execute, reset_engine_for_tests

from tests.xa05.test_xa05_fixtures import build_engine, populate_repository

FORBIDDEN_IMPORT_PREFIXES = (
    "market_platform_foundation.execution",
    "market_platform_foundation.risk",
    "market_platform_foundation.paper",
    "market_platform_foundation.broker",
)


class Xa05AuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_engine_for_tests()

    def test_no_execution_module_imports_in_xa05(self) -> None:
        root = Path(__file__).resolve().parents[2] / "src" / "market_platform_foundation" / "xa05"
        offenders: list[str] = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                            offenders.append(f"{path.name}:{alias.name}")
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                        offenders.append(f"{path.name}:{node.module}")
        self.assertEqual(offenders, [])

    def test_operations_do_not_grant_authority(self) -> None:
        result = execute("XA05.OP.STATUS")
        self.assertFalse(result.verification["analytical_authority_granted"])
        self.assertFalse(result.verification["paid_infrastructure_required"])

    def test_state_construction_does_not_mutate_xa_registries(self) -> None:
        populate_repository()
        xa01_before = len(get_xa01_registry().list_ids())
        xa02_before = get_xa02_registry().status()
        xa03_before = get_xa03_registry().status()
        engine = build_engine()
        engine.construct_state(
            decision_time="2026-08-20T00:00:00Z",
            construction_time="2026-08-20T00:00:00Z",
        )
        self.assertEqual(len(get_xa01_registry().list_ids()), xa01_before)
        self.assertEqual(get_xa02_registry().status(), xa02_before)
        self.assertEqual(get_xa03_registry().status(), xa03_before)

    def test_xa05_package_importable_without_execution_dependencies(self) -> None:
        package = importlib.import_module("market_platform_foundation.xa05")
        self.assertTrue(hasattr(package, "CrossAssetStrategicState"))
        module_names = [
            module.name
            for module in pkgutil.walk_packages(package.__path__, package.__name__ + ".")
        ]
        self.assertTrue(any(name.endswith(".engine") for name in module_names))


if __name__ == "__main__":
    unittest.main()
