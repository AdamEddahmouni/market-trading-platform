import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "squeeze_core" / "evaluation"
BANNED_IMPORT_ROOTS = {
    "requests", "httpx", "urllib", "ftplib", "websocket", "dotenv",
    "sqlalchemy", "sqlite3", "psycopg", "pymongo", "flask", "django", "fastapi",
    "pandas", "numpy", "scipy", "sklearn", "tensorflow", "torch", "talib",
}
BANNED_CALLS = {"uuid4", "random", "randint", "time", "now", "utcnow"}


def test_evaluation_runtime_is_offline_deterministic_and_dependency_isolated():
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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

