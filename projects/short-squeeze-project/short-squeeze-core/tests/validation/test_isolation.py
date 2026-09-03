"""Runtime isolation for squeeze_core.validation.

Mirrors the isolation guarantees the earlier phases assert: the deterministic core
reaches no network, no database, no GUI, no ML stack, and no wall clock in any identity
path, and it contains no scoring, ranking, recommendation, alerting, or order logic.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "squeeze_core" / "validation"
MODULES = sorted(PACKAGE.glob("*.py"))

FORBIDDEN_IMPORTS = {
    "requests",
    "httpx",
    "urllib",
    "urllib3",
    "http",
    "socket",
    "aiohttp",
    "websockets",
    "sqlite3",
    "pymongo",
    "psycopg2",
    "sqlalchemy",
    "redis",
    "tkinter",
    "PyQt5",
    "flask",
    "fastapi",
    "django",
    "pandas",
    "numpy",
    "scipy",
    "sklearn",
    "torch",
    "transformers",
    "yfinance",
    "ib_insync",
    "random",
    "secrets",
}

# Identifiers naming a trading action or a simulated position. Forbidden everywhere:
# no module in this phase may act on, or pretend to act on, a market.
FORBIDDEN_IDENTIFIER_SUBSTRINGS = (
    "buy_signal",
    "sell_signal",
    "place_order",
    "entry_price",
    "exit_price",
    "stop_loss",
    "take_profit",
    "portfolio",
    "backtest",
    "paper_trade",
)

# Candidate-quality vocabulary from the original platform. Phase 2V must never *emit*
# these labels, but original_rules.py exists precisely to *describe* the original
# Prime/Subprime rule as frozen historical evidence, so it is exempt. Every other
# module naming them would mean the label had leaked into live logic.
FORBIDDEN_LABEL_SUBSTRINGS = ("prime", "subprime", "bullish", "bearish")
DESCRIBES_ORIGINAL_PLATFORM = {"original_rules.py"}


def _module_trees():
    for path in MODULES:
        yield path, ast.parse(path.read_text(encoding="utf-8"))


def test_the_package_has_modules_to_check():
    assert MODULES, "no validation modules were discovered"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_forbidden_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [(node.module or "").split(".")[0]]
        else:
            continue
        for name in names:
            assert name not in FORBIDDEN_IMPORTS, f"{path.name} imports {name}"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_wall_clock_reads(path):
    """datetime.now / utcnow / time.time would make an identity depend on when it ran."""

    source = path.read_text(encoding="utf-8")
    for forbidden in ("datetime.now(", "datetime.utcnow(", "time.time(", "date.today("):
        assert forbidden not in source, f"{path.name} reads the wall clock: {forbidden}"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_random_identifiers(path):
    source = path.read_text(encoding="utf-8")
    for forbidden in ("uuid4(", "uuid1(", "random.", "secrets."):
        assert forbidden not in source, f"{path.name} uses a nondeterministic id: {forbidden}"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_trading_or_candidate_quality_identifiers(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    defined: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.append(node.name.lower())
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.append(node.id.lower())
    for name in defined:
        for forbidden in FORBIDDEN_IDENTIFIER_SUBSTRINGS:
            assert forbidden not in name, f"{path.name} defines {name!r}"

    if path.name in DESCRIBES_ORIGINAL_PLATFORM:
        return
    for name in defined:
        for forbidden in FORBIDDEN_LABEL_SUBSTRINGS:
            assert forbidden not in name, (
                f"{path.name} defines {name!r}; candidate-quality labels belong only to "
                "the frozen original-platform description"
            )


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.name)
def test_no_file_writes_from_the_deterministic_core(path):
    """Writing belongs to the CLI, not to the package that computes identities."""

    source = path.read_text(encoding="utf-8")
    for forbidden in ("open(", ".write_text(", ".write_bytes(", "shutil."):
        assert forbidden not in source, f"{path.name} performs I/O: {forbidden}"


def test_public_surface_exposes_no_scoring_helper():
    import squeeze_core.validation as validation

    for name in validation.__all__:
        lowered = name.lower()
        for forbidden in ("score", "rank", "recommend", "alert", "signal", "prime"):
            assert forbidden not in lowered, f"validation exports {name}"
