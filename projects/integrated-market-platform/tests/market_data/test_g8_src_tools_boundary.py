"""G8 structural regression: no src → tools/ibkr implementation dependency."""

from __future__ import annotations

import ast
import sys
import unittest
from inspect import signature
from pathlib import Path
from typing import get_type_hints

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "market_platform_foundation"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.providers.ibkr_observational.adapter import (  # noqa: E402
    IbkrObservationalAdapter,
    IbkrTransport,
)

from ibkr_observational_support import FakeTransport  # noqa: E402

_IMPORT_CALLS = {"import_module", "__import__"}
_PATH_LOAD_CALLS = {"spec_from_file_location", "module_from_spec"}
_EXEC_CALLS = {"exec", "eval"}
_EXECUTION_METHODS = (
    "placeOrder",
    "cancelOrder",
    "modifyOrder",
    "exerciseOptions",
    "reqFundTransfer",
    "reqPositions",
    "reqAccountUpdates",
    "reqAccountSummary",
)


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_tools_ibkr_module(name: str | None) -> bool:
    if not name:
        return False
    return name == "tools.ibkr" or name.startswith("tools.ibkr.")


def _is_tools_ibkr_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return "tools/ibkr" in normalized or "tools.ibkr" in normalized


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _scan_file(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_tools_ibkr_module(alias.name):
                    violations.append(f"{path}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if _is_tools_ibkr_module(node.module):
                violations.append(f"{path}:{node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Call):
            name = _call_name(node)
            args = [_const_str(arg) for arg in node.args]
            if name in _IMPORT_CALLS:
                for arg in args:
                    if arg and _is_tools_ibkr_module(arg):
                        violations.append(f"{path}:{node.lineno}: {name}({arg!r})")
            elif name in _PATH_LOAD_CALLS:
                for arg in args:
                    if arg and _is_tools_ibkr_path(arg):
                        violations.append(f"{path}:{node.lineno}: {name}({arg!r})")
            elif name in _EXEC_CALLS:
                for arg in args:
                    if arg and _is_tools_ibkr_path(arg):
                        violations.append(f"{path}:{node.lineno}: {name}({arg!r})")
    return violations


class G8SrcToolsBoundaryTests(unittest.TestCase):
    def test_canonical_src_has_no_tools_ibkr_implementation_dependency(self) -> None:
        violations: list[str] = []
        for path in sorted(SRC.rglob("*.py")):
            violations.extend(_scan_file(path))
        self.assertEqual(violations, [], "\n".join(violations))

    def test_adapter_receives_transport_only_through_protocol(self) -> None:
        hints = get_type_hints(IbkrObservationalAdapter.__init__)
        self.assertIs(hints["transport"], IbkrTransport)
        transport_param = signature(IbkrObservationalAdapter.__init__).parameters["transport"]
        self.assertEqual(transport_param.kind, transport_param.KEYWORD_ONLY)

    def test_no_execution_methods_on_canonical_adapter(self) -> None:
        for method in _EXECUTION_METHODS:
            self.assertFalse(hasattr(IbkrObservationalAdapter, method), method)

    def test_no_execution_methods_on_injected_fake_transport(self) -> None:
        transport = FakeTransport()
        for method in _EXECUTION_METHODS:
            self.assertFalse(hasattr(transport, method), method)


if __name__ == "__main__":
    unittest.main()
