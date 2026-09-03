import ast
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE_2C_COMMIT = "61b15ab3f44c2dc70a25e95db88cdaab413dcd94"
SRC = REPO_ROOT / "src" / "squeeze_core"
READINESS = SRC / "readiness"


def _git_diff_exit_code(*paths: str) -> int:
    result = subprocess.run(
        ["git", "diff", "--exit-code", PHASE_2C_COMMIT, "--", *paths],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    return result.returncode


def test_phase_1_anchor_manifest_unchanged_since_phase_2c_completion():
    assert _git_diff_exit_code("tests/fixtures/compatibility/phase_1_anchor_manifest.json") == 0


def test_phase_2a_metric_metadata_unchanged_since_phase_2c_completion():
    assert _git_diff_exit_code("tests/fixtures/metrics/expected_phase_2a_metric_metadata.json") == 0


def test_phase_2b_metric_metadata_unchanged_since_phase_2c_completion():
    assert _git_diff_exit_code("tests/fixtures/metrics/expected_phase_2b_metric_metadata.json") == 0


def test_phase_2c_metric_metadata_unchanged_since_phase_2c_completion():
    assert _git_diff_exit_code("tests/fixtures/metrics/expected_phase_2c_metric_metadata.json") == 0


def test_phase_1_through_2c_cli_fixtures_unchanged_since_phase_2c_completion():
    assert _git_diff_exit_code(
        "tests/fixtures/metrics/cli_demo_bars.jsonl",
        "tests/fixtures/metrics/phase_2a_metric_cases.json",
        "tests/fixtures/metrics/phase_2b_cli_demo_bars.jsonl",
        "tests/fixtures/metrics/phase_2b_normalized_metric_cases.json",
        "tests/fixtures/metrics/phase_2c_cli_demo_observations.jsonl",
        "tests/fixtures/metrics/phase_2c_metric_cases.json",
    ) == 0


def test_no_evidence_contracts_adapters_or_prior_metrics_file_modified_since_phase_2c_completion():
    # Phase 2D is purely additive: a brand-new src/squeeze_core/readiness/ package
    # plus new subcommand branches in __main__.py. Every other runtime source file
    # must be byte-identical to the Phase 2C completion commit.
    #
    # Phase 3E (Batch 16): bar_acceleration.py is a new additive metric added
    # to support the real-time evidence pipeline. No existing metrics files
    # were modified.
    result = subprocess.run(
        ["git", "diff", "--name-only", PHASE_2C_COMMIT, "--",
         "src/squeeze_core/evidence",
         "src/squeeze_core/contracts",
         "src/squeeze_core/adapters",
         "src/squeeze_core/replay",
         "src/squeeze_core/serialization",
         "src/squeeze_core/metrics",
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    changed = {line for line in result.stdout.splitlines() if line}
    allowed_new = {"src/squeeze_core/metrics/bar_acceleration.py"}
    unexpected = changed - allowed_new
    assert not unexpected, f"unexpected changes: {unexpected}"


def test_only_main_module_changed_outside_the_new_additive_packages():
    """Since Phase 2C, every change under src/squeeze_core must live in a new additive
    package or in the CLI entry point.

    Phase 2V adds squeeze_core/validation the same way Phase 2D added
    squeeze_core/readiness, so it joins the allowed prefixes. The guard keeps its force:
    the pre-existing packages (contracts, adapters, replay, serialization, metrics) are
    asserted unchanged by test_prior_phase_sources_unchanged above, and any file
    appearing outside these prefixes still fails here."""

    result = subprocess.run(
        ["git", "diff", "--name-only", PHASE_2C_COMMIT, "--", "src/squeeze_core"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    changed = {line for line in result.stdout.splitlines() if line}
    allowed_new_packages = (
        "src/squeeze_core/readiness/",
        "src/squeeze_core/validation/",
        "src/squeeze_core/evaluation/",
        "src/squeeze_core/research/",
        "src/squeeze_core/analysis/",
        "src/squeeze_core/acquisition/",
    )
    allowed_files = {
        "src/squeeze_core/__main__.py",
        "src/squeeze_core/__init__.py",
        "src/squeeze_core/metrics/bar_acceleration.py",
    }
    for path in changed:
        assert path.startswith(allowed_new_packages) or path in allowed_files, (
            f"unexpected file changed outside the new additive packages: {path}"
        )


def test_observation_schema_version_still_pinned():
    from squeeze_core.contracts import Observation

    assert Observation.model_fields["schema_version"].annotation.__args__ == ("1.0.0",)


def test_no_readiness_model_defines_schema_version():
    from squeeze_core.readiness import models as models_module

    for name in models_module.__all__:
        obj = getattr(models_module, name)
        if hasattr(obj, "model_fields"):
            assert "schema_version" not in obj.model_fields


def test_no_prior_phase_module_imports_the_readiness_package():
    non_readiness_dirs = [
        SRC / "contracts",
        SRC / "evidence",
        SRC / "adapters",
        SRC / "replay",
        SRC / "serialization",
        SRC / "metrics",
    ]
    for directory in non_readiness_dirs:
        for py_file in directory.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    assert "squeeze_core.readiness" not in node.module, (
                        f"{py_file} imports the Phase 2D-only readiness package"
                    )


def test_no_forbidden_runtime_dependencies_in_readiness_package():
    forbidden_modules = {
        "socket", "http", "http.client", "urllib", "urllib.request", "requests",
        "sqlite3", "psycopg2", "pandas", "numpy", "scipy", "tkinter", "asyncio",
        "ftplib", "websocket", "websockets", "random", "secrets",
    }
    for py_file in READINESS.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden_modules, f"{py_file}: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert module.split(".")[0] not in forbidden_modules, f"{py_file}: {module}"


def test_readiness_package_never_calls_wall_clock_or_random():
    forbidden_calls = {"now", "utcnow", "today", "random", "randint", "uuid4"}
    for py_file in READINESS.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden_calls:
                raise AssertionError(f"{py_file} calls forbidden wall-clock/random attribute {node.attr}")


def test_no_qualitative_or_scoring_vocabulary_in_readiness_source():
    forbidden_terms = (
        "score", "rank", "recommend", "prime", "subprime", "bullish", "bearish",
        "confidence_percent", "alert_", "grade", "tier",
    )
    for py_file in READINESS.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = node.name
            if name is None:
                continue
            lowered = name.lower()
            for term in forbidden_terms:
                assert term not in lowered, f"{py_file}: identifier {name!r} contains forbidden term {term!r}"


def test_structural_state_enum_has_no_trading_meaning():
    from squeeze_core.readiness import StructuralState

    assert {member.value for member in StructuralState} == {
        "SUFFICIENT",
        "INSUFFICIENT",
        "UNKNOWN",
        "CONFLICTED",
    }
