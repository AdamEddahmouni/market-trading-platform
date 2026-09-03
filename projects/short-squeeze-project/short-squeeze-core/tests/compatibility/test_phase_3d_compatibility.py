import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PHASE_3C_COMPLETION = "14d35abfc9aacc6f2f4adaa3ad264950ec556d17"
PRIOR_MANIFESTS = (
    "tests/fixtures/compatibility/phase_1_anchor_manifest.json",
    "tests/fixtures/metrics/expected_phase_2a_metric_metadata.json",
    "tests/fixtures/metrics/expected_phase_2b_metric_metadata.json",
    "tests/fixtures/metrics/expected_phase_2c_metric_metadata.json",
    "tests/fixtures/readiness/expected_phase_2d_readiness_metadata.json",
    "tests/fixtures/validation/expected_phase_2v_validation_metadata.json",
    "tests/fixtures/validation/outcome_amendment/expected_phase_2v_outcome_metadata.json",
    "tests/fixtures/evaluation/expected_phase_3a_evaluation_metadata.json",
    "tests/fixtures/research/expected_phase_3b_research_metadata.json",
    "tests/fixtures/analysis/expected_phase_3c_analysis_metadata.json",
)


def _changed(*paths: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", PHASE_3C_COMPLETION, "--", *paths],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return set(result.stdout.splitlines())


def test_phase3d_runtime_is_additive():
    changed = _changed("src/squeeze_core")
    allowed = {
        "src/squeeze_core/__main__.py",
        "src/squeeze_core/__init__.py",
        "src/squeeze_core/metrics/bar_acceleration.py",
    }
    assert all(
        path.startswith("src/squeeze_core/acquisition/")
        or path in allowed
        for path in changed
    ), changed


def test_all_prior_fixture_families_and_manifests_are_unchanged():
    changed = _changed("tests/fixtures")
    assert all(path.startswith("tests/fixtures/acquisition/") for path in changed), changed
    assert _changed(*PRIOR_MANIFESTS) == set()


def test_phase3d_contracts_are_separate_and_schema_remains_1_0_0():
    from squeeze_core.acquisition.models import AcquisitionPlan
    from squeeze_core.analysis.models import ResearchAnalysisRequest
    from squeeze_core.contracts import Observation
    from squeeze_core.research.models import CandidateCaseRegistryEntry

    assert Observation.model_fields["schema_version"].annotation.__args__ == ("1.0.0",)
    assert CandidateCaseRegistryEntry.model_fields["schema_version"].default == "1.0.0"
    assert ResearchAnalysisRequest.model_fields["schema_version"].default == "1.0.0"
    assert AcquisitionPlan.model_fields["schema_version"].default == "1.0.0"
    assert "acquisition" not in Observation.model_fields
    assert "acquisition" not in CandidateCaseRegistryEntry.model_fields
