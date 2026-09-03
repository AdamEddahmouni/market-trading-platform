"""AST-based import, dynamic-load, and prohibited-route analysis."""

from __future__ import annotations

import ast
import sys
from collections import deque
from pathlib import Path

from .policy import FIXED_COMMANDS

_PROHIBITED_MODULE_ROOTS = {
    "alpaca",
    "binance",
    "ccxt",
    "ctypes",
    "ib_insync",
    "interactive_brokers",
    "moomoo",
    "futu",
    "requests",
    "websocket",
}
_PROHIBITED_CALLS = {
    "eval": "EVAL_EXEC",
    "exec": "EVAL_EXEC",
    "os.system": "PROCESS_SPAWN",
    "pickle.load": "UNSAFE_DESERIALIZATION",
    "pickle.loads": "UNSAFE_DESERIALIZATION",
    "marshal.load": "UNSAFE_DESERIALIZATION",
    "marshal.loads": "UNSAFE_DESERIALIZATION",
    "subprocess.Popen": "PROCESS_SPAWN",
    "subprocess.run": "PROCESS_SPAWN",
}
_ROUTE_CATEGORIES = (
    "broker_account_access",
    "broker_operations",
    "live_market_data",
    "live_submission",
    "process_escape",
)


def _module_name(root: Path, path: Path) -> tuple[str, bool]:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    is_package = bool(parts and parts[-1] == "__init__")
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


def _call_name(node: ast.Call) -> str:
    value: ast.AST = node.func
    parts: list[str] = []
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def analyze_tree(root: Path) -> dict[str, object]:
    root = root.resolve()
    paths = sorted(root.rglob("*.py"), key=lambda item: item.relative_to(root).as_posix())
    module_rows = [_module_name(root, path) for path in paths]
    modules = {name for name, _is_package in module_rows if name}
    module_by_path = {path: row for path, row in zip(paths, module_rows)}
    imports: list[dict[str, str]] = []
    prohibited: list[dict[str, str]] = []
    dynamic: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    syntax_errors: list[dict[str, object]] = []
    graph: dict[str, set[str]] = {name: set() for name in modules}

    for path in paths:
        relative = path.relative_to(root).as_posix()
        module, is_package = module_by_path[path]
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except SyntaxError as error:
            syntax_errors.append({"line": error.lineno or 0, "path": relative})
            continue
        for node in ast.walk(tree):
            targets: list[tuple[str, int]] = []
            if isinstance(node, ast.Import):
                targets = [(alias.name, 0) for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                targets = [(node.module or "", node.level)]
            for target, level in targets:
                resolved = target
                if level:
                    package_parts = module.split(".") if is_package else module.split(".")[:-1]
                    trim = level - 1
                    if trim > len(package_parts):
                        unresolved.append({"path": relative, "target": target})
                        continue
                    prefix = package_parts[: len(package_parts) - trim]
                    resolved = ".".join(prefix + ([target] if target else []))
                    if resolved not in modules and not any(name.startswith(resolved + ".") for name in modules):
                        unresolved.append({"path": relative, "target": resolved})
                    elif module:
                        graph.setdefault(module, set()).add(resolved)
                imports.append({"path": relative, "target": resolved or target})
                root_name = (resolved or target).split(".", 1)[0]
                if root_name in _PROHIBITED_MODULE_ROOTS:
                    prohibited.append({"path": relative, "target": resolved or target})
            if not isinstance(node, ast.Call):
                continue
            call = _call_name(node)
            if call in {"__import__", "importlib.import_module"}:
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    target = node.args[0].value
                    imports.append({"path": relative, "target": target})
                    root_name = target.split(".", 1)[0]
                    if root_name in _PROHIBITED_MODULE_ROOTS:
                        prohibited.append({"path": relative, "target": target})
                    elif module and (
                        target in modules
                        or any(name.startswith(target + ".") for name in modules)
                    ):
                        graph.setdefault(module, set()).add(target)
                    continue
                dynamic.append({"path": relative, "reason": "NONCONSTANT_DYNAMIC_IMPORT"})
            elif call.endswith(".entry_points"):
                dynamic.append({"path": relative, "reason": "ENTRY_POINT_DISCOVERY_PROHIBITED"})
            elif call in _PROHIBITED_CALLS and not (
                relative == "offline_guard.py" and call == "os.system"
            ):
                prohibited.append({"path": relative, "target": call})

    prohibited.sort(key=lambda row: (row["path"], row["target"]))
    dynamic.sort(key=lambda row: (row["path"], row["reason"]))
    unresolved.sort(key=lambda row: (row["path"], row["target"]))
    routes: dict[str, list[list[str]]] = {key: [] for key in _ROUTE_CATEGORIES}
    if prohibited or dynamic:
        for command in FIXED_COMMANDS:
            for finding in prohibited:
                routes["broker_operations"].append(
                    [f"cli:{command}", f"file:{finding['path']}", f"target:{finding['target']}"]
                )
    return {
        "dynamic_load_findings": dynamic,
        "entry_points": list(FIXED_COMMANDS),
        "file_count": len(paths),
        "import_edges": sorted(imports, key=lambda row: (row["path"], row["target"])),
        "prohibited_edges": prohibited,
        "prohibited_routes": routes,
        "syntax_errors": syntax_errors,
        "unresolved_internal_imports": unresolved,
    }
