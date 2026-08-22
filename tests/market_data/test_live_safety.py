from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tools.moomoo.probe import FORBIDDEN_TRADE_NAMES


class MoomooObservationalSafetyTests(unittest.TestCase):
    def test_live_runtime_module_has_no_trade_context_import(self) -> None:
        paths = [ROOT / "src/market_platform_foundation/market_data/live_runtime.py"]
        paths.extend((ROOT / "tools" / "moomoo").glob("*.py"))
        for path in paths:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            imported = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name in FORBIDDEN_TRADE_NAMES:
                            imported.append(alias.name)
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_TRADE_NAMES:
                        imported.append(func.attr)
                    if isinstance(func, ast.Name) and func.id in FORBIDDEN_TRADE_NAMES:
                        imported.append(func.id)
            self.assertEqual(imported, [], msg=str(path))

    def test_observational_adapter_role_is_market_data_only(self) -> None:
        from market_platform_foundation.market_data.provider_lifecycle import ProviderLifecycle

        lifecycle = ProviderLifecycle()
        self.assertEqual(lifecycle.provider_role, "MARKET_DATA")


if __name__ == "__main__":
    unittest.main()
