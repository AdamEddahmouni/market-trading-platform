import ast
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE_2B_COMMIT = "b2a75e3e7e18d500aa655d2260cae38bea93fb52"
SRC = REPO_ROOT / "src" / "squeeze_core"


def _git_diff_exit_code(*paths: str) -> int:
    result = subprocess.run(
        ["git", "diff", "--exit-code", PHASE_2B_COMMIT, "--", *paths],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    return result.returncode


def test_phase_1_anchor_manifest_unchanged_since_phase_2b_completion():
    assert _git_diff_exit_code("tests/fixtures/compatibility/phase_1_anchor_manifest.json") == 0


def test_phase_2a_metric_metadata_unchanged_since_phase_2b_completion():
    assert _git_diff_exit_code("tests/fixtures/metrics/expected_phase_2a_metric_metadata.json") == 0


def test_phase_2b_metric_metadata_unchanged_since_phase_2b_completion():
    assert _git_diff_exit_code("tests/fixtures/metrics/expected_phase_2b_metric_metadata.json") == 0


def test_phase_2a_and_2b_cli_fixtures_unchanged_since_phase_2b_completion():
    assert _git_diff_exit_code(
        "tests/fixtures/metrics/cli_demo_bars.jsonl",
        "tests/fixtures/metrics/phase_2a_metric_cases.json",
        "tests/fixtures/metrics/phase_2b_cli_demo_bars.jsonl",
        "tests/fixtures/metrics/phase_2b_normalized_metric_cases.json",
    ) == 0


def test_phase_2a_and_2b_only_metrics_source_files_unchanged_except_additive_edits():
    # These five files are allowed to change (additive enum members / diagnostic codes /
    # registry dispatch / new-model serialization helpers / package exports only). Every
    # Phase-2A-or-2B-only metrics source file must be byte-identical to the Phase 2B
    # completion commit.
    allowed_to_change = {
        "src/squeeze_core/metrics/models.py",
        "src/squeeze_core/metrics/diagnostics.py",
        "src/squeeze_core/metrics/registry.py",
        "src/squeeze_core/metrics/serialization.py",
        "src/squeeze_core/metrics/__init__.py",
    }
    phase_2a_or_2b_only_files = {
        "src/squeeze_core/metrics/gaps.py",
        "src/squeeze_core/metrics/identifiers.py",
        "src/squeeze_core/metrics/ranges.py",
        "src/squeeze_core/metrics/returns.py",
        "src/squeeze_core/metrics/selection.py",
        "src/squeeze_core/metrics/volume_baselines.py",
        "src/squeeze_core/metrics/statistics.py",
        "src/squeeze_core/metrics/normalized_models.py",
        "src/squeeze_core/metrics/normalized_identifiers.py",
        "src/squeeze_core/metrics/relative_volume.py",
        "src/squeeze_core/metrics/volume_standardization.py",
        "src/squeeze_core/metrics/return_baselines.py",
        "src/squeeze_core/metrics/return_standardization.py",
    }
    for path in phase_2a_or_2b_only_files:
        assert _git_diff_exit_code(path) == 0, f"{path} changed since Phase 2B completion"
    assert allowed_to_change  # documents the additive-only exception set for readability


def test_no_finra_ibkr_adapter_or_evidence_file_modified_since_phase_2b_completion():
    assert _git_diff_exit_code(
        "src/squeeze_core/adapters/finra",
        "src/squeeze_core/adapters/ibkr",
        "src/squeeze_core/evidence",
        "src/squeeze_core/contracts",
    ) == 0


def test_observation_schema_version_still_pinned():
    from squeeze_core.contracts import Observation

    assert Observation.model_fields["schema_version"].annotation.__args__ == ("1.0.0",)


def test_metric_result_and_normalized_result_still_define_no_schema_version_field():
    from squeeze_core.metrics import BaselineStatistics, MetricResult, NormalizedMetricResult

    assert "schema_version" not in MetricResult.model_fields
    assert "schema_version" not in NormalizedMetricResult.model_fields
    assert "schema_version" not in BaselineStatistics.model_fields


def test_pressure_metric_result_and_days_to_cover_components_define_no_schema_version_field():
    from squeeze_core.metrics import DaysToCoverComponents, PressureMetricResult

    assert "schema_version" not in PressureMetricResult.model_fields
    assert "schema_version" not in DaysToCoverComponents.model_fields


def test_no_phase_1_or_prior_phase_module_imports_phase_2c_only_modules():
    phase_2c_only_modules = {
        "source_age",
        "pressure_models",
        "pressure_identifiers",
        "pressure_selection",
        "short_interest_changes",
        "days_to_cover",
        "borrow_fee_changes",
        "borrow_availability_changes",
    }
    non_metrics_dirs = [
        SRC / "contracts",
        SRC / "evidence",
        SRC / "adapters",
        SRC / "replay",
        SRC / "serialization",
    ]
    prior_phase_only_files = {
        SRC / "metrics" / "gaps.py",
        SRC / "metrics" / "identifiers.py",
        SRC / "metrics" / "ranges.py",
        SRC / "metrics" / "returns.py",
        SRC / "metrics" / "selection.py",
        SRC / "metrics" / "volume_baselines.py",
        SRC / "metrics" / "normalized_models.py",
        SRC / "metrics" / "normalized_identifiers.py",
        SRC / "metrics" / "relative_volume.py",
        SRC / "metrics" / "volume_standardization.py",
        SRC / "metrics" / "return_baselines.py",
        SRC / "metrics" / "return_standardization.py",
    }
    for path in non_metrics_dirs:
        for py_file in (path.rglob("*.py") if path.is_dir() else [path]):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for phase_2c_module in phase_2c_only_modules:
                        assert f"squeeze_core.metrics.{phase_2c_module}" not in node.module, (
                            f"{py_file} imports Phase 2C-only module {phase_2c_module}"
                        )
    for py_file in prior_phase_only_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for phase_2c_module in phase_2c_only_modules:
                    assert f"squeeze_core.metrics.{phase_2c_module}" not in node.module, (
                        f"{py_file} imports Phase 2C-only module {phase_2c_module}"
                    )


def test_no_forbidden_runtime_dependencies_in_new_phase_2c_modules():
    forbidden_modules = {
        "socket", "http", "http.client", "urllib", "urllib.request", "requests",
        "sqlite3", "psycopg2", "pandas", "numpy", "scipy", "tkinter", "asyncio",
    }
    new_files = [
        SRC / "metrics" / "source_age.py",
        SRC / "metrics" / "pressure_models.py",
        SRC / "metrics" / "pressure_identifiers.py",
        SRC / "metrics" / "pressure_selection.py",
        SRC / "metrics" / "short_interest_changes.py",
        SRC / "metrics" / "days_to_cover.py",
        SRC / "metrics" / "borrow_fee_changes.py",
        SRC / "metrics" / "borrow_availability_changes.py",
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
