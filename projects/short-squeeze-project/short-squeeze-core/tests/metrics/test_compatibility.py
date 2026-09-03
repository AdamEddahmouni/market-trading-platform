import ast
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "compatibility" / "phase_1_anchor_manifest.json"
SRC = REPO_ROOT / "src" / "squeeze_core"


def test_phase_1_anchor_manifest_is_untouched_and_well_formed():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["observation_schema_version"] == "1.0.0"
    for phase in ("phase_1g", "phase_1h", "phase_1i"):
        assert phase in manifest
        assert manifest[phase], f"{phase} anchors must not be empty"


def test_observation_schema_version_is_unchanged():
    from squeeze_core.contracts import Observation

    assert Observation.model_fields["schema_version"].annotation.__args__ == ("1.0.0",)


def test_metric_result_defines_no_competing_schema_version_field():
    from squeeze_core.metrics import MetricResult

    assert "schema_version" not in MetricResult.model_fields


def test_no_phase_1_module_imports_the_new_metrics_package():
    # metrics/ depends on evidence/contracts/serialization -- never the other way around.
    non_metrics_dirs = [
        SRC / "contracts",
        SRC / "evidence",
        SRC / "adapters",
        SRC / "replay",
        SRC / "serialization",
    ]
    for directory in non_metrics_dirs:
        for path in directory.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and "squeeze_core.metrics" in node.module:
                    raise AssertionError(f"{path} imports squeeze_core.metrics")
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("squeeze_core.metrics"):
                            raise AssertionError(f"{path} imports squeeze_core.metrics")
