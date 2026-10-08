"""AST-based import, dynamic-load, and prohibited-route analysis."""

from __future__ import annotations

import ast
import sys
from collections import deque
from pathlib import Path

from .policy import FIXED_COMMANDS

# The ``alpaca`` SDK package remains prohibited. A stdlib urllib adapter
# whose import root is not ``alpaca`` (for example ``alpaca_paper_http``)
# is allowed and must never ``import alpaca``. Live Alpaca stays unauthorized.
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


def _read_only_local_memory_bridge(relative: str, tree: ast.AST) -> bool:
    """Audit the authorized Windows memory-only bridge; ctypes stays prohibited elsewhere."""
    if relative != "intelligence/inference/local_resources.py":
        return False
    allowed = {
        "ctypes.Structure", "ctypes.c_ulonglong", "ctypes.c_size_t", "ctypes.c_void_p",
        "ctypes.sizeof", "ctypes.byref", "ctypes.windll", "ctypes.windll.kernel32",
        "ctypes.windll.kernel32.GlobalMemoryStatusEx", "ctypes.windll.psapi",
        "ctypes.windll.psapi.GetProcessMemoryInfo", "wintypes.DWORD", "wintypes.HANDLE",
    }
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    namespaces = {"ctypes.windll", "ctypes.windll.kernel32", "ctypes.windll.psapi"}
    for node in ast.walk(tree):
        parent = parents.get(node)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in {"ctypes", "wintypes"} and not (isinstance(parent, ast.Attribute) and parent.value is node):
                return False
            if node.id == "query" and not (
                isinstance(parent, ast.Call) and parent.func is node
                or isinstance(parent, ast.Attribute) and parent.value is node and parent.attr == "argtypes"
            ):
                return False
        if isinstance(node, ast.Import):
            if any(a.name.startswith("ctypes") and (a.name != "ctypes" or a.asname) for a in node.names):
                return False
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("ctypes"):
            if node.module != "ctypes" or any(a.name != "wintypes" or a.asname for a in node.names):
                return False
        elif isinstance(node, ast.Attribute):
            # Apply the same static member-name audit to data attributes and calls.
            name = _call_name(ast.Call(func=node, args=[], keywords=[]))
            if name.split(".", 1)[0] in {"ctypes", "wintypes"} and name not in allowed:
                return False
            if name in namespaces and not (isinstance(parent, ast.Attribute) and parent.value is node):
                return False
            if name in {"ctypes.windll.kernel32.GlobalMemoryStatusEx", "ctypes.windll.psapi.GetProcessMemoryInfo"}:
                called = isinstance(parent, ast.Call) and parent.func is node
                alias = (
                    name == "ctypes.windll.psapi.GetProcessMemoryInfo" and isinstance(parent, ast.Assign)
                    and parent.value is node and len(parent.targets) == 1
                    and isinstance(parent.targets[0], ast.Name) and parent.targets[0].id == "query"
                )
                if not (called or alias):
                    return False
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            if node.value.id in {"ctypes", "wintypes"}:
                return False
    return True


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
                if root_name in _PROHIBITED_MODULE_ROOTS and not (
                    root_name == "ctypes" and _read_only_local_memory_bridge(relative, tree)
                ):
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
