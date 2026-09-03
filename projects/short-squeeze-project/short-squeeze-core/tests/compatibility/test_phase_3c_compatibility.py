import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PHASE_3B_COMPLETION = "e0708f51212ab11fd5767fc55b41b58f4614b44b"
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
)


def _changed(*paths: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", PHASE_3B_COMPLETION, "--", *paths],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return set(result.stdout.splitlines())


def test_phase_3c_runtime_is_additive():
    changed = _changed("src/squeeze_core")
    allowed = {
        "src/squeeze_core/__main__.py",
        "src/squeeze_core/__init__.py",
        "src/squeeze_core/metrics/bar_acceleration.py",
    }
    assert all(
        path.startswith("src/squeeze_core/analysis/")
        or path.startswith("src/squeeze_core/acquisition/")
        or path in allowed
        for path in changed
    ), changed


def test_prior_fixture_families_and_all_nine_manifests_are_unchanged():
    changed = _changed("tests/fixtures")
    assert all(path.startswith((
        "tests/fixtures/analysis/", "tests/fixtures/acquisition/",
    )) for path in changed), changed
    assert _changed(*PRIOR_MANIFESTS) == set()


def test_phase_3c_contracts_are_separate_and_schema_remains_1_0_0():
    from squeeze_core.analysis import ResearchAnalysisRequest
    from squeeze_core.contracts import Observation
    from squeeze_core.research import CandidateCaseRegistryEntry

    assert Observation.model_fields["schema_version"].annotation.__args__ == ("1.0.0",)
    assert CandidateCaseRegistryEntry.model_fields["schema_version"].default == "1.0.0"
    assert ResearchAnalysisRequest.model_fields["schema_version"].default == "1.0.0"
    assert "analysis" not in Observation.model_fields
    assert "analysis" not in CandidateCaseRegistryEntry.model_fields
