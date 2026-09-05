"""BIYA yahoo import registers Batch 05 manifests for Phase 3A freeze."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from squeeze_core.acquisition.operation_readiness.evidence_inputs import (
    DETECTION_CONTEXT_REQUEST,
    FORWARD_REQUEST,
    load_detection_context_evidence,
    forward_artifact_identity,
)
from scripts.acquisition.import_biya_yahoo_bars_to_ibkr_intake import (
    import_biya_yahoo_bars,
    SYMBOL,
)


@pytest.fixture
def batch05_tmp(tmp_path: Path) -> Path:
    root = tmp_path / "ibkr-batch-05"
    for sub in ("raw", "requests", "provenance"):
        (root / sub).mkdir(parents=True)
    (root / "provenance" / "artifact-manifest.json").write_text("[]", encoding="utf-8")
    (root / "requests" / "request-manifest.json").write_text("[]", encoding="utf-8")
    (root / "provenance" / "sha256-manifest.json").write_text("{}", encoding="utf-8")
    return root


def test_import_registers_biya_in_batch05_manifests(batch05_tmp: Path) -> None:
    counts = import_biya_yahoo_bars(batch05_tmp)
    assert counts["detection_context_bars"] > 0
    assert counts["frozen_forward_bars"] == 0
    assert counts["forward_outcome_bars"] > 0

    coverage = load_detection_context_evidence(batch05_tmp)
    forward = forward_artifact_identity(batch05_tmp)
    assert SYMBOL in coverage
    assert SYMBOL in forward

    artifacts = json.loads(
        (batch05_tmp / "provenance" / "artifact-manifest.json").read_text(encoding="utf-8")
    )
    biya_artifacts = [row for row in artifacts if row["symbol"] == SYMBOL]
    assert len(biya_artifacts) == 2
    request_names = {row["request_name"] for row in biya_artifacts}
    assert request_names == {DETECTION_CONTEXT_REQUEST, FORWARD_REQUEST}

    requests = json.loads(
        (batch05_tmp / "requests" / "request-manifest.json").read_text(encoding="utf-8")
    )
    biya_requests = [row for row in requests if row["symbol"] == SYMBOL]
    assert len(biya_requests) == 2

    raw = batch05_tmp / "raw"
    assert (raw / f"{SYMBOL}-detection-context.csv").exists()
    assert (raw / f"{SYMBOL}-detection-context.jsonl").exists()
    assert (raw / f"{SYMBOL}-frozen-forward-24h.csv").exists()
    assert (raw / f"{SYMBOL}-forward-outcome.csv").exists()
