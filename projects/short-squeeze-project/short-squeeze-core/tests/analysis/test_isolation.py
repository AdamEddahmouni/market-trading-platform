import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "src" / "squeeze_core" / "analysis"

FORBIDDEN_IMPORT_ROOTS = {
    "aiohttp", "boto3", "django", "dotenv", "fastapi", "flask", "ftplib",
    "httpx", "numpy", "pandas", "requests", "scipy", "selenium", "sklearn",
    "sqlalchemy", "statsmodels", "tensorflow", "torch", "websocket",
}
FORBIDDEN_CALLS = {
    "random", "randint", "randrange", "time", "today", "utcnow", "uuid1", "uuid4",
}


def _trees():
    for path in sorted(ANALYSIS.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_analysis_runtime_has_no_network_database_ml_or_dataframe_imports():
    violations = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                    violations.append((path.name, node.lineno, name))
    assert violations == []


def test_analysis_identity_has_no_random_or_wall_clock_calls():
    violations = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            name = (
                function.id if isinstance(function, ast.Name)
                else function.attr if isinstance(function, ast.Attribute)
                else ""
            )
            if name in FORBIDDEN_CALLS:
                violations.append((path.name, node.lineno, name))
    assert violations == []


def test_analysis_models_expose_no_score_rank_recommendation_or_pnl_fields():
    prohibited = {"score", "rank", "recommendation", "alert", "pnl", "p_and_l"}
    violations = []
    for path, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id.lower() in prohibited:
                    violations.append((path.name, node.lineno, node.target.id))
    assert violations == []
