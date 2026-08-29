"""Non-executing binding verification. Never imports or invokes bound callables."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .contracts import Binding, CapabilityDefinition
from .enums import BindingKind, FindingSeverity
from .errors import OF03Error, OF03ErrorCode

ALLOWED_MODULE_PREFIX = "market_platform_foundation."
ALLOWED_SCRIPTS = frozenset({"tools/validate.py"})


def verify_binding(capability: CapabilityDefinition, *, repository_root: Path) -> dict[str, Any]:
    binding = capability.binding
    result: dict[str, Any] = {
        "capability_id": capability.capability_id,
        "definition_version": capability.definition_version,
        "binding_kind": binding.binding_kind.value,
        "ok": False,
        "invoked": False,
        "findings": [],
    }
    try:
        if binding.binding_kind is BindingKind.UNBOUND:
            result["ok"] = True
            result["state"] = "UNBOUND"
            return result
        if binding.binding_kind is BindingKind.DOCUMENTED_MANUAL_OPERATION:
            path = binding.document_path
            if not path:
                result["findings"].append(_finding("missing document_path"))
                return result
            if _unsafe_path(path):
                result["findings"].append(_finding("path traversal in document_path"))
                return result
            if not (repository_root / path).is_file():
                result["findings"].append(_finding("document missing", {"path": path}))
                return result
            result["ok"] = True
            result["state"] = "BOUND"
            return result
        if binding.binding_kind is BindingKind.PYTHON_API:
            _verify_python(binding, result, repository_root)
            if result["ok"] and binding.cli_module:
                cli_probe: dict[str, Any] = {"findings": [], "ok": False, "invoked": False}
                _verify_cli(binding, cli_probe, repository_root)
                if not cli_probe["ok"]:
                    result["ok"] = False
                    result["findings"].extend(cli_probe["findings"])
                    result.pop("state", None)
            return result
        if binding.binding_kind is BindingKind.CLI_CAPABILITY:
            _verify_cli(binding, result, repository_root)
            return result
        result["findings"].append(_finding("unknown binding kind", {"kind": binding.binding_kind.value}))
        return result
    except OF03Error as exc:
        result["findings"].append(_finding(exc.message, dict(exc.details)))
        return result


def _verify_python(binding: Binding, result: dict[str, Any], repository_root: Path) -> None:
    module_name = _safe_module(binding.module)
    if not binding.qualname:
        result["findings"].append(_finding("missing qualname"))
        return
    path = _module_source_path(repository_root, module_name)
    if path is None:
        result["findings"].append(_finding("module source missing", {"module": module_name}))
        return
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if not _qualname_in_ast(tree, binding.qualname):
        result["findings"].append(_finding("missing callable", {"qualname": binding.qualname}))
        return
    result["ok"] = True
    result["state"] = "BOUND"


def _verify_cli(binding: Binding, result: dict[str, Any], repository_root: Path) -> None:
    if binding.cli_script:
        script = binding.cli_script.replace("\\", "/")
        if _unsafe_path(script) or script not in ALLOWED_SCRIPTS:
            result["findings"].append(_finding("cli_script not allowlisted", {"cli_script": script}))
            return
        if not (repository_root / script).is_file():
            result["findings"].append(_finding("cli_script missing", {"cli_script": script}))
            return
        result["ok"] = True
        result["state"] = "BOUND"
        return
    module_name = _safe_module(binding.cli_module)
    if not binding.cli_subcommand or not binding.cli_parser_attr:
        result["findings"].append(_finding("CLI binding requires subcommand and parser attr"))
        return
    path = _module_source_path(repository_root, module_name)
    if path is None:
        result["findings"].append(_finding("cli module source missing", {"module": module_name}))
        return
    tree = ast.parse(path.read_text(encoding="utf-8"))
    if not _qualname_in_ast(tree, binding.cli_parser_attr):
        result["findings"].append(_finding("cli parser factory missing"))
        return
    if not _cli_subcommand_in_ast(tree, binding.cli_subcommand):
        result["findings"].append(_finding("CLI subcommand missing", {"subcommand": binding.cli_subcommand}))
        return
    result["ok"] = True
    result["state"] = "BOUND"


def _module_source_path(repository_root: Path, module_name: str) -> Path | None:
    rel = Path("src").joinpath(*module_name.split("."))
    py_file = repository_root / f"{rel}.py"
    init_file = repository_root / rel / "__init__.py"
    if py_file.is_file():
        return py_file
    if init_file.is_file():
        return init_file
    return None


def _qualname_in_ast(tree: ast.AST, qualname: str) -> bool:
    parts = qualname.split(".")
    if len(parts) == 1:
        return any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign))
            and _name_matches(node, parts[0])
            for node in ast.iter_child_nodes(tree)
        ) or any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == parts[0]
            for node in ast.walk(tree)
        )
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == parts[0]:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == parts[1]:
                    return True
    return False


def _name_matches(node: ast.AST, name: str) -> bool:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name
    if isinstance(node, ast.Assign):
        return any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
    return False


def _cli_subcommand_in_ast(tree: ast.AST, subcommand: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        attr = func.attr if isinstance(func, ast.Attribute) else None
        if attr != "add_parser":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == subcommand:
            return True
    return False


def _safe_module(name: str | None) -> str:
    if not name:
        raise OF03Error(OF03ErrorCode.UNSAFE_BINDING, "missing module", {})
    if any(token in name for token in ("/", "\\", "..")):
        raise OF03Error(OF03ErrorCode.UNSAFE_BINDING, "path traversal in module", {"module": name})
    if not name.startswith(ALLOWED_MODULE_PREFIX):
        raise OF03Error(OF03ErrorCode.UNSAFE_BINDING, "module outside approved package root", {"module": name})
    remainder = name[len(ALLOWED_MODULE_PREFIX) :]
    if not remainder or remainder.startswith("."):
        raise OF03Error(OF03ErrorCode.UNSAFE_BINDING, "module outside approved package root", {"module": name})
    return name


def _unsafe_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith("/") or ".." in Path(normalized).parts or normalized.startswith("..")


def _finding(message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {"severity": FindingSeverity.ERROR.value, "message": message}
    if extra:
        payload.update(extra)
    return payload
