"""Centralized Phase 1 deterministic-anchor compatibility runner.

This module is the single place that verifies every retained Phase 1 anchor. It does not
rewrite anchors: it cross-checks the machine-readable manifest against the committed
per-phase expected metadata files, then regenerates the Phase 1G/1H/1I artifacts twice and
proves the regenerated hashes are byte-identical across runs and equal to both the committed
metadata and the manifest. It also proves the standalone and provider fixture files still hash
to their recorded values, so any silent fixture drift is caught here as well.
"""

import hashlib
import json
from pathlib import Path

import pytest

from phase_1g_fixture_builders import build_phase_1g_artifacts
from phase_1h_fixture_builders import build_phase_1h_artifacts
from phase_1i_fixture_builders import build_phase_1i_artifacts

ROOT = Path(__file__).parents[1] / "fixtures"
MANIFEST_PATH = ROOT / "compatibility" / "phase_1_anchor_manifest.json"


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _committed(phase: str) -> dict:
    return json.loads(
        (ROOT / "evidence" / f"expected_phase_{phase}_bundle_metadata.json").read_text(
            encoding="utf-8"
        )
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_matches_committed_phase_metadata() -> None:
    """Every manifest anchor must equal the value recorded in the committed metadata file."""
    manifest = _manifest()
    for phase in ("1g", "1h", "1i"):
        committed = _committed(phase)
        for key, value in manifest[f"phase_{phase}"].items():
            assert committed[key] == value, f"phase {phase} anchor drift: {key}"


def test_manifest_cross_phase_embeddings_match() -> None:
    manifest = _manifest()
    committed_1h = _committed("1h")
    committed_1i = _committed("1i")
    for key, value in manifest["cross_phase_embeddings"]["phase_1h_embeds_phase_1g"].items():
        assert committed_1h[key] == value
    for key, value in manifest["cross_phase_embeddings"]["phase_1i_embeds_phase_1h"].items():
        assert committed_1i[key] == value


def test_manifest_provider_fixture_content_hashes_match_committed() -> None:
    manifest = _manifest()
    committed_1h = _committed("1h")
    committed_1i = _committed("1i")
    for key, value in manifest["provider_fixture_content_sha256"]["phase_1h"].items():
        assert committed_1h[key] == value
    for key, value in manifest["provider_fixture_content_sha256"]["phase_1i"].items():
        assert committed_1i[key] == value


@pytest.mark.parametrize(
    "phase,builder",
    [
        ("1g", build_phase_1g_artifacts),
        ("1h", build_phase_1h_artifacts),
        ("1i", build_phase_1i_artifacts),
    ],
)
def test_regenerated_artifacts_are_deterministic_and_match_manifest(phase, builder) -> None:
    """Regenerate twice: prove byte identity, equality to committed metadata, and to manifest."""
    first = builder()
    second = builder()
    assert first["metadata"] == second["metadata"], f"phase {phase} regeneration is nondeterministic"
    committed = _committed(phase)
    assert first["metadata"] == committed, f"phase {phase} regeneration diverged from committed metadata"
    manifest_anchors = _manifest()[f"phase_{phase}"]
    for key, value in manifest_anchors.items():
        assert first["metadata"][key] == value, f"phase {phase} regenerated anchor mismatch: {key}"


def test_standalone_fixture_hashes_match_manifest() -> None:
    manifest = _manifest()
    for name, expected_hash in manifest["standalone_fixture_sha256"].items():
        assert _sha256(ROOT / name) == expected_hash, f"standalone fixture drift: {name}"


def test_manifest_declares_observation_schema_version_1_0_0() -> None:
    manifest = _manifest()
    assert manifest["observation_schema_version"] == "1.0.0"
    for phase in ("1g", "1h", "1i"):
        assert _committed(phase)["schema_version"] == "1.0.0"


def test_manifest_covers_every_handoff_anchor_family() -> None:
    """Guard against an anchor family silently disappearing from the manifest."""
    manifest = _manifest()
    assert set(manifest["phase_1g"]) == {
        "mixed_jsonl_sha256",
        "strict_replay_sha256",
        "final_bundle_sha256",
        "serialized_final_bundle_sha256",
    }
    assert {
        "partial_bar_observation_sha256",
        "completed_bar_observation_sha256",
        "corrected_bar_observation_sha256",
        "cancelled_bar_observation_sha256",
        "mixed_jsonl_sha256",
        "strict_replay_sha256",
        "final_bar_series_sha256",
        "final_bundle_sha256",
        "serialized_final_bundle_sha256",
    } == set(manifest["phase_1h"])
    assert {
        "original_trade_observation_sha256",
        "corrected_trade_observation_sha256",
        "cancelled_trade_observation_sha256",
        "original_quote_observation_sha256",
        "corrected_quote_observation_sha256",
        "cancelled_quote_observation_sha256",
        "mixed_jsonl_sha256",
        "strict_replay_sha256",
        "trade_quote_series_sha256",
        "final_bundle_sha256",
        "serialized_final_bundle_sha256",
    } == set(manifest["phase_1i"])
