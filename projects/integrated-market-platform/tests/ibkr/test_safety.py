from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "ibkr"
# G11.1 bounded live verification harness (read-only; no execution surface).
G111_LIVE_CANARY = frozenset({"canary.py"})


class IbkrStructuralSafetyTests(unittest.TestCase):
    def test_tooling_imports_only_stdlib_and_local_ibkr_modules(self) -> None:
        prohibited = {"ibapi", "ib_insync", "requests", "aiohttp", "websocket", "socket"}
        for path in sorted(TOOLS.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".", 1)[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    roots = {node.module.split(".", 1)[0]}
                else:
                    continue
                if path.name in {"tws_client.py", "observational_transport.py"}:
                    roots.discard("ib_insync")
                if path.name == "runtime_bootstrap.py":
                    roots.discard("market_platform_foundation")
                if path.name in G111_LIVE_CANARY:
                    roots.discard("socket")
                    roots.discard("ib_insync")
                self.assertTrue(roots.isdisjoint(prohibited), f"{path}: {roots & prohibited}")
                for root in roots:
                    if path.name in G111_LIVE_CANARY and root == "market_platform_foundation":
                        continue
                    self.assertTrue(
                        root in sys.stdlib_module_names or root == "tools",
                        f"non-stdlib import {root!r} in {path}",
                    )

    def test_optional_tws_module_has_no_mutation_surface(self) -> None:
        source = (TOOLS / "tws_client.py").read_text(encoding="utf-8")
        for marker in ("placeOrder", "modifyOrder", "cancelOrder", "reqFundTransfer"):
            self.assertNotIn(marker, source)

    def test_allowlist_contains_no_order_execution_or_fund_routes(self) -> None:
        source = (TOOLS / "client.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        route_literals = {
            node.value.lower()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.startswith("/")
        }
        for marker in ("order", "trade", "execution", "fund", "withdraw", "deposit"):
            self.assertFalse(
                any(marker in route for route in route_literals),
                f"forbidden route marker {marker!r}: {sorted(route_literals)}",
            )

    def test_tooling_does_not_import_foundation_runtime(self) -> None:
        for path in sorted(TOOLS.rglob("*.py")):
            if path.name in {"runtime_bootstrap.py"} | G111_LIVE_CANARY:
                continue
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("market_platform_foundation", source, str(path))

    def test_runtime_bootstrap_may_import_canonical_src_contracts(self) -> None:
        source = (TOOLS / "runtime_bootstrap.py").read_text(encoding="utf-8")
        self.assertIn("market_platform_foundation", source)
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        self.assertTrue(
            any(name.startswith("market_platform_foundation") for name in imported),
            imported,
        )

    def test_documented_probe_script_help_is_offline_and_executable(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(TOOLS / "probe.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("read-only IBKR Gateway capabilities", completed.stdout)


if __name__ == "__main__":
    unittest.main()
