import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "squeeze_core" / "research"

BANNED_IMPORT_ROOTS = {
    "requests", "httpx", "urllib", "socket", "ftplib", "websocket", "websockets",
    "dotenv", "sqlalchemy", "sqlite3", "psycopg", "pymongo", "flask", "django",
    "fastapi", "tkinter", "pandas", "numpy", "scipy", "sklearn", "tensorflow",
    "torch", "talib", "random", "secrets",
}
BANNED_CALLS = {"uuid4", "random", "randint", "time", "now", "utcnow", "today"}
BANNED_FIELD_FRAGMENTS = {
    "score", "weight", "rank", "recommend", "alert", "pnl", "profit", "loss",
    "trade_entry", "trade_exit", "position", "portfolio",
}


def _trees():
    for path in PACKAGE.rglob("*.py"):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_research_runtime_is_offline_deterministic_and_dependency_isolated() -> None:
    for path, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
                assert not roots & BANNED_IMPORT_ROOTS, path
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in BANNED_IMPORT_ROOTS, path
            elif isinstance(node, ast.Call):
                name = (
                    node.func.id if isinstance(node.func, ast.Name)
                    else node.func.attr if isinstance(node.func, ast.Attribute)
                    else ""
                )
                assert name not in BANNED_CALLS, f"{path}: prohibited call {name}"


def test_research_contracts_have_no_decision_or_trading_fields() -> None:
    from squeeze_core.research import models

    offenders: list[str] = []
    for exported_name in models.__all__:
        model = getattr(models, exported_name)
        for field_name in getattr(model, "model_fields", {}):
            lowered = field_name.lower()
            if any(fragment in lowered for fragment in BANNED_FIELD_FRAGMENTS):
                offenders.append(f"{exported_name}.{field_name}")
    assert offenders == []


def test_prior_phase_runtime_never_imports_research() -> None:
    prior_packages = (
        "contracts", "evidence", "adapters", "replay", "serialization", "metrics",
        "readiness", "validation", "evaluation",
    )
    for package_name in prior_packages:
        for path in (ROOT / "src" / "squeeze_core" / package_name).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert "squeeze_core.research" not in node.module, path
                elif isinstance(node, ast.Import):
                    assert all("squeeze_core.research" not in alias.name for alias in node.names), path
