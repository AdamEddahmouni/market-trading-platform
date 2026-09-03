"""Frozen constants for the Phase 3E Stage 2 pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ..operation_readiness.evidence_inputs import FROZEN_BOUNDARY, FROZEN_COHORT
from ..phase3a_freeze.freeze import DISCOVERY_MANIFEST_ID

# Preregistered 13-symbol pilot cohort (Stage 2 plan); excludes KLRS/SG extensions.
PILOT_COHORT: tuple[tuple[str, str], ...] = FROZEN_COHORT[:13]

STAGE2_PLAN_ID = "phase-3e-stage2-forward-outcome-acquisition-plan"
STAGE2_PLAN_VERSION = "1.0.0"

OUTCOME_LABEL_POLICY_VERSION = "phase_3b_outcome_label_policy.v1"
DETECTION_POLICY_VERSION = "phase_3b_research_detection_policy.v1"
PHASE_3A_POLICY_VERSION = "phase_3a_transparent_candidate_policy.v1"
REGISTRY_VERSION = "phase_3e_stage2_case_registry.v1"
BATCH_VERSION = "phase_3e_stage2_batch.v1"

RETRIEVAL_COMPLETED_AT = datetime(2026, 7, 23, 20, 0, 1, tzinfo=UTC)

SYNTHETIC_BATCH05_ROOT = Path("tests/fixtures/acquisition/batch08/synthetic-batch05")
DEFAULT_BATCH05_ROOT = Path("intake/local-bars/ibkr-batch-05")
DEFAULT_FREEZE_SUBDIR = Path("phase3a/batch-08")
STAGE2_BUILD_ROOT = Path("build/acquisition/stage2")

PHASE3A_FREEZE_DIR = STAGE2_BUILD_ROOT / "phase3a-freeze"
OUTCOMES_DIR = STAGE2_BUILD_ROOT / "outcomes"
LEAKAGE_DIR = STAGE2_BUILD_ROOT / "leakage-audit"
PHASE3B_DIR = STAGE2_BUILD_ROOT / "phase3b"
PHASE3C_DIR = STAGE2_BUILD_ROOT / "phase3c"
PIPELINE_SUMMARY_PATH = STAGE2_BUILD_ROOT / "pipeline-summary.json"

__all__ = [
    "BATCH_VERSION",
    "DEFAULT_BATCH05_ROOT",
    "DEFAULT_FREEZE_SUBDIR",
    "DETECTION_POLICY_VERSION",
    "DISCOVERY_MANIFEST_ID",
    "FROZEN_BOUNDARY",
    "LEAKAGE_DIR",
    "OUTCOME_LABEL_POLICY_VERSION",
    "OUTCOMES_DIR",
    "PHASE3A_FREEZE_DIR",
    "PHASE3A_POLICY_VERSION",
    "PHASE3B_DIR",
    "PHASE3C_DIR",
    "PILOT_COHORT",
    "PIPELINE_SUMMARY_PATH",
    "REGISTRY_VERSION",
    "RETRIEVAL_COMPLETED_AT",
    "STAGE2_BUILD_ROOT",
    "STAGE2_PLAN_ID",
    "STAGE2_PLAN_VERSION",
    "SYNTHETIC_BATCH05_ROOT",
]
