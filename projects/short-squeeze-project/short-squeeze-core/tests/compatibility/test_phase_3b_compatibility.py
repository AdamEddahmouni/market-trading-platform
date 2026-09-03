import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PHASE_3A_COMPLETION = "b7c7394d5fe8ee16bd3bd1482ce218a203162104"


def _changed(*paths: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", PHASE_3A_COMPLETION, "--", *paths],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def test_phase_3b_runtime_is_additive() -> None:
    changed = _changed("src/squeeze_core")
    for path in changed:
        assert path.startswith((
            "src/squeeze_core/research/",
            "src/squeeze_core/analysis/",
            "src/squeeze_core/acquisition/",
        )) or path in (
            "src/squeeze_core/__main__.py",
            "src/squeeze_core/__init__.py",
            "src/squeeze_core/metrics/bar_acceleration.py",
        ), path


def test_all_prior_runtime_packages_are_byte_unchanged() -> None:
    prior_packages = (
        "contracts", "evidence", "adapters", "replay", "serialization", "metrics",
        "readiness", "validation", "evaluation",
    )
    changed = _changed(*(f"src/squeeze_core/{name}" for name in prior_packages))
    allowed_new = {"src/squeeze_core/metrics/bar_acceleration.py"}
    assert changed - allowed_new == set(), changed


def test_all_pre_phase_3b_fixture_families_are_byte_unchanged() -> None:
    changed = _changed("tests/fixtures")
    assert all(path.startswith((
        "tests/fixtures/research/",
        "tests/fixtures/analysis/",
        "tests/fixtures/acquisition/",
    )) for path in changed), changed


def test_observation_schema_remains_pinned_and_research_is_separate() -> None:
    from squeeze_core.contracts import Observation
    from squeeze_core.research import CandidateCaseRegistryEntry

    assert Observation.model_fields["schema_version"].annotation.__args__ == ("1.0.0",)
    assert CandidateCaseRegistryEntry.model_fields["schema_version"].default == "1.0.0"
    assert "research" not in Observation.model_fields
