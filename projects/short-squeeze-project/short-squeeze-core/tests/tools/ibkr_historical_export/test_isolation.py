"""Isolation and safety-boundary invariants between the tool and the runtime."""

from __future__ import annotations

from pathlib import Path

from tools.ibkr_historical_export.guard import package_dir

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RUNTIME = _REPO_ROOT / "src" / "squeeze_core"


def _runtime_sources():
    return [p for p in _RUNTIME.rglob("*.py") if "__pycache__" not in p.parts]


def _tool_sources():
    return [p for p in package_dir().rglob("*.py") if "__pycache__" not in p.parts]


def test_runtime_never_imports_the_tool_or_ibapi():
    for source in _runtime_sources():
        text = source.read_text(encoding="utf-8")
        assert "ibkr_historical_export" not in text, source
        assert "import ibapi" not in text, source
        assert "from ibapi" not in text, source
        assert "import tools" not in text, source


def test_tool_never_references_case_association_class():
    for source in _tool_sources():
        text = source.read_text(encoding="utf-8")
        assert "CaseAssociationMapping" not in text, source


def test_tool_only_imports_allowed_runtime_modules():
    # The only squeeze_core imports permitted are the intake models/semantics and the
    # offline preflight -- never publication, analysis, or outcome modules.
    forbidden_runtime = (
        "squeeze_core.acquisition.publication",
        "squeeze_core.analysis",
        "squeeze_core.evaluation",
        "squeeze_core.research",
        "outcome",
    )
    for source in _tool_sources():
        text = source.read_text(encoding="utf-8")
        for module in forbidden_runtime:
            assert f"import {module}" not in text, (source, module)
            assert f"from {module}" not in text, (source, module)


def test_tool_imports_ibapi_only_in_session_layer():
    import re
    pattern = re.compile(r"^\s*(?:from\s+ibapi|import\s+ibapi)", re.MULTILINE)
    for source in _tool_sources():
        text = source.read_text(encoding="utf-8")
        has_import = bool(pattern.search(text))
        if source.name == "session.py":
            assert has_import, "session.py should import ibapi"
        else:
            assert not has_import, f"{source.name} must not import ibapi"


def test_only_intended_python_modules_present():
    names = {p.name for p in _tool_sources()}
    expected = {
        "__init__.py", "__main__.py", "cli.py", "cohort.py", "collector.py",
        "errors.py", "guard.py", "models.py", "paths.py", "policy.py",
        "preflight_bundle.py", "resolution.py", "semantics_overlay.py",
        "serialization.py", "session.py", "statuses.py",
    }
    assert names == expected
