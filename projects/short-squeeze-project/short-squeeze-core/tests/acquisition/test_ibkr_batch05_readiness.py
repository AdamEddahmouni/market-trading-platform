"""Batch 07 readiness against the committed IBKR Batch 05 intake root."""

from __future__ import annotations

from pathlib import Path

import pytest

from squeeze_core.acquisition.operation_readiness import FROZEN_COHORT, build_report
from squeeze_core.acquisition.operation_readiness.evidence_inputs import load_detection_context_evidence

REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH05_ROOT = REPO_ROOT / "intake" / "local-bars" / "ibkr-batch-05"


@pytest.mark.skipif(not BATCH05_ROOT.is_dir(), reason="private batch-05 intake not present")
def test_ibkr_batch05_readiness_has_full_frozen_cohort():
    report = build_report(BATCH05_ROOT)
    assert len(report.cases) == len(FROZEN_COHORT)
    assert [case.symbol for case in report.cases] == [symbol for symbol, _ in FROZEN_COHORT]
    assert [case.case_id for case in report.cases] == [case_id for _, case_id in FROZEN_COHORT]
    assert report.cases[-1].symbol == "BIYA"


@pytest.mark.skipif(not BATCH05_ROOT.is_dir(), reason="private batch-05 intake not present")
def test_ibkr_batch05_readiness_all_cohort_includes_batch3f05():
    report = build_report(BATCH05_ROOT, cohort_track="all")
    assert len(report.cases) == len(FROZEN_COHORT) + 5
    batch3f05_symbols = {"AACB", "AACG", "AACI", "AACP", "AADX"}
    assert batch3f05_symbols <= {case.symbol for case in report.cases}


@pytest.mark.skipif(not BATCH05_ROOT.is_dir(), reason="private batch-05 intake not present")
def test_ibkr_batch05_detection_context_covers_all_symbols():
    evidence = load_detection_context_evidence(BATCH05_ROOT)
    frozen_symbols = {symbol for symbol, _ in FROZEN_COHORT}
    assert frozen_symbols <= set(evidence)
    assert "BIYA" in evidence
    assert "AACB" in evidence
