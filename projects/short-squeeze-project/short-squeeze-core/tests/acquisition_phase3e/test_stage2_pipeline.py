"""End-to-end Stage 2 pipeline smoke test (offline synthetic fixtures)."""

from __future__ import annotations

from pathlib import Path

from squeeze_core.acquisition.operation_readiness.evidence_inputs import FROZEN_COHORT
from squeeze_core.acquisition.stage2.pipeline import Stage2PipelineConfig, run_stage2_pipeline

ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_ROOT = ROOT / "tests" / "fixtures" / "acquisition" / "batch08" / "synthetic-batch05"


def test_stage2_pipeline_offline_smoke(tmp_path):
    stage2_root = tmp_path / "stage2"
    config = Stage2PipelineConfig(
        repo_root=ROOT,
        batch05_root=SYNTHETIC_ROOT,
        freeze_root=tmp_path / "freeze",
        stage2_root=stage2_root,
        offline=True,
        skip_freeze=False,
        force=True,
    )
    result = run_stage2_pipeline(config)
    assert result.summary_path is not None
    assert result.summary_path.is_file()
    assert len(result.passed_leakage) == len(FROZEN_COHORT)
    assert (stage2_root / "phase3b" / "research_batch.json").is_file()
    assert (stage2_root / "phase3c" / "analysis_collection.json").is_file()
    assert (stage2_root / "leakage-audit" / "leakage-audit.json").is_file()
