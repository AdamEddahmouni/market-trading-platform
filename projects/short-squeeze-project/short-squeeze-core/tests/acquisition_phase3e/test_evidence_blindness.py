"""Outcome-blind evidence bundle checks for Phase 3E Stage 1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BUNDLES_DIR = ROOT / "build" / "acquisition" / "evidence-bundles"
SYNTHETIC_BATCH05 = ROOT / "tests" / "fixtures" / "acquisition" / "batch08" / "synthetic-batch05"

OUTCOME_TOKENS = (
    "maximum_observed_move",
    "maximum_return",
    "later_return",
    "outcome_label",
    "percentage_return",
)


@pytest.fixture(scope="module")
def evidence_bundles_built() -> Path:
    if not BUNDLES_DIR.is_dir() or not any(BUNDLES_DIR.glob("*/bundle.json")):
        pytest.skip("evidence bundles not built; run build_evidence_bundles.py")
    return BUNDLES_DIR


def test_evidence_bundles_exclude_outcome_fields(evidence_bundles_built: Path):
    for bundle_path in sorted(evidence_bundles_built.glob("*/bundle.json")):
        payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        serialized = json.dumps(payload).lower()
        for token in OUTCOME_TOKENS:
            assert token not in serialized, (
                f"{bundle_path.parent.name} contains outcome token {token!r}"
            )


def test_evidence_bundles_market_bars_only_from_detection_context(evidence_bundles_built: Path):
    for bundle_path in sorted(evidence_bundles_built.glob("*/bundle.json")):
        symbol = bundle_path.parent.name
        detection = SYNTHETIC_BATCH05 / "raw" / f"{symbol}-detection-context.csv"
        forward = SYNTHETIC_BATCH05 / "raw" / f"{symbol}-frozen-forward-24h.csv"
        assert detection.is_file(), f"missing detection fixture for {symbol}"
        assert forward.is_file(), f"missing forward fixture for {symbol}"
        payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        assert payload.get("bundle_id"), f"{bundle_path} missing bundle_id"
