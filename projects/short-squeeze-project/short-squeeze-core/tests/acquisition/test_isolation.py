import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACQUISITION = ROOT / "src" / "squeeze_core" / "acquisition"
FORBIDDEN_IMPORT_ROOTS = {
    "aiohttp", "boto3", "django", "dotenv", "fastapi", "flask", "ftplib", "httpx",
    "numpy", "pandas", "requests", "scipy", "selenium", "sklearn", "sqlalchemy",
    "statsmodels", "tensorflow", "torch", "websocket",
}
FORBIDDEN_CALLS = {
    "getenv", "random", "randint", "randrange", "time", "today", "utcnow", "uuid1", "uuid4",
}


def _trees():
    for path in sorted(ACQUISITION.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_runtime_has_no_network_database_environment_ml_or_dataframe_access():
    violations = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS for name in names):
                violations.append((path.name, node.lineno, names))
            if isinstance(node, ast.Attribute) and node.attr == "environ":
                violations.append((path.name, node.lineno, "environ"))
    assert violations == []


def test_identity_has_no_random_or_wall_clock_calls():
    violations = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            name = function.id if isinstance(function, ast.Name) else (
                function.attr if isinstance(function, ast.Attribute) else ""
            )
            if name in FORBIDDEN_CALLS:
                violations.append((path.name, node.lineno, name))
    assert violations == []


def test_models_expose_no_score_rank_recommendation_alert_or_profit_fields():
    prohibited = {"score", "rank", "recommendation", "alert", "pnl", "p_and_l", "optimization"}
    violations = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id.lower() in prohibited:
                    violations.append((path.name, node.lineno, node.target.id))
    assert violations == []
