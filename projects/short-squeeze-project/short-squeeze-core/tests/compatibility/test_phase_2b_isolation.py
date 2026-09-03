import ast
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE_2A_COMMIT = "d776e30ee4af7cf7daee898ec0ccc8a007dd1a9e"
SRC = REPO_ROOT / "src" / "squeeze_core"


def _git_diff_exit_code(*paths: str) -> int:
    result = subprocess.run(
        ["git", "diff", "--exit-code", PHASE_2A_COMMIT, "--", *paths],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    return result.returncode


def test_phase_1_anchor_manifest_unchanged_since_phase_2a_completion():
    assert _git_diff_exit_code("tests/fixtures/compatibility/phase_1_anchor_manifest.json") == 0


def test_phase_2a_metric_metadata_unchanged_since_phase_2a_completion():
    assert _git_diff_exit_code("tests/fixtures/metrics/expected_phase_2a_metric_metadata.json") == 0


def test_phase_2a_cli_fixtures_unchanged_since_phase_2a_completion():
    assert _git_diff_exit_code(
        "tests/fixtures/metrics/cli_demo_bars.jsonl",
        "tests/fixtures/metrics/phase_2a_metric_cases.json",
    ) == 0


def test_phase_2a_metrics_source_files_unchanged_except_additive_edits():
    # These four files are allowed to change (additive enum members / diagnostic codes / registry
    # dispatch / package exports only -- verified by test_phase_1_release_candidate-style behavior
    # tests elsewhere, not by a byte diff here). Every other Phase 2A metrics source file must be
    # byte-identical to the Phase 2A completion commit.
    allowed_to_change = {
        "src/squeeze_core/metrics/models.py",
        "src/squeeze_core/metrics/diagnostics.py",
        "src/squeeze_core/metrics/registry.py",
        "src/squeeze_core/metrics/serialization.py",
        "src/squeeze_core/metrics/__init__.py",
    }
    phase_2a_only_files = {
        "src/squeeze_core/metrics/gaps.py",
        "src/squeeze_core/metrics/identifiers.py",
        "src/squeeze_core/metrics/ranges.py",
        "src/squeeze_core/metrics/returns.py",
        "src/squeeze_core/metrics/selection.py",
        "src/squeeze_core/metrics/volume_baselines.py",
    }
    for path in phase_2a_only_files:
        assert _git_diff_exit_code(path) == 0, f"{path} changed since Phase 2A completion"
    assert allowed_to_change  # documents the additive-only exception set for readability


def test_observation_schema_version_still_pinned():
    from squeeze_core.contracts import Observation

    assert Observation.model_fields["schema_version"].annotation.__args__ == ("1.0.0",)


def test_metric_result_still_defines_no_schema_version_field():
    from squeeze_core.metrics import MetricResult

    assert "schema_version" not in MetricResult.model_fields


def test_normalized_metric_result_and_baseline_statistics_define_no_schema_version_field():
    from squeeze_core.metrics import BaselineStatistics, NormalizedMetricResult

    assert "schema_version" not in NormalizedMetricResult.model_fields
    assert "schema_version" not in BaselineStatistics.model_fields


def test_no_phase_1_or_phase_2a_module_imports_normalized_phase_2b_modules():
    phase_2b_only_modules = {
        "normalized_models",
        "normalized_identifiers",
        "relative_volume",
        "volume_standardization",
        "return_baselines",
        "return_standardization",
        "statistics",
    }
    non_metrics_dirs = [
        SRC / "contracts",
        SRC / "evidence",
        SRC / "adapters",
        SRC / "replay",
        SRC / "serialization",
    ]
    phase_2a_only_files = {
        SRC / "metrics" / "gaps.py",
        SRC / "metrics" / "identifiers.py",
        SRC / "metrics" / "ranges.py",
        SRC / "metrics" / "returns.py",
        SRC / "metrics" / "selection.py",
        SRC / "metrics" / "volume_baselines.py",
    }
    for path in non_metrics_dirs:
        for py_file in (path.rglob("*.py") if path.is_dir() else [path]):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                module = None
                if isinstance(node, ast.ImportFrom) and node.module:
                    module = node.module
                if module is not None:
                    for phase_2b_module in phase_2b_only_modules:
                        assert f"squeeze_core.metrics.{phase_2b_module}" not in module, (
                            f"{py_file} imports Phase 2B-only module {phase_2b_module}"
                        )
    for py_file in phase_2a_only_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for phase_2b_module in phase_2b_only_modules:
                    assert f"squeeze_core.metrics.{phase_2b_module}" not in node.module, (
                        f"{py_file} imports Phase 2B-only module {phase_2b_module}"
                    )


def test_no_forbidden_runtime_dependencies_in_new_phase_2b_modules():
    forbidden_modules = {
        "socket", "http", "http.client", "urllib", "urllib.request", "requests",
        "sqlite3", "psycopg2", "pandas", "numpy", "scipy", "tkinter", "asyncio",
    }
    new_files = [
        SRC / "metrics" / "statistics.py",
        SRC / "metrics" / "normalized_models.py",
        SRC / "metrics" / "normalized_identifiers.py",
        SRC / "metrics" / "relative_volume.py",
        SRC / "metrics" / "volume_standardization.py",
        SRC / "metrics" / "return_baselines.py",
        SRC / "metrics" / "return_standardization.py",
    ]
    for path in new_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden_modules, f"{path}: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert module.split(".")[0] not in forbidden_modules, f"{path}: {module}"
