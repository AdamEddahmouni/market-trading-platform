"""Phase 3D evidence calibration pipeline and the Phase 4 walk-forward scaffold + item 1.3 fit-report skeleton."""

from .experiments import CalibrationExperimentError, load_experiment, load_source_dataset
from .fit_report import (
    FeasibilityGateId,
    FeasibilityGateResult,
    FitReportSkeleton,
    HorizonSlotStatus,
    OutcomeCounts,
    Phase4Verdict,
    build_fit_report_skeleton,
    render_fit_report_markdown,
)
from .models import CalibrationExperiment, CalibrationReport
from .report import render_markdown, write_report
from .runner import run_calibration_experiment, run_calibration_from_path
from .walkforward import (
    BoundaryObservation,
    RegimeSlice,
    WalkForwardDiagnostics,
    WalkForwardInputError,
    WalkForwardPlan,
    boundary_observations_from_bytes,
    plan_walk_forward_folds,
    regime_slice_for_boundary,
    walk_forward_diagnostics,
)

__all__ = [
    "BoundaryObservation",
    "CalibrationExperiment",
    "CalibrationExperimentError",
    "CalibrationReport",
    "FeasibilityGateId",
    "FeasibilityGateResult",
    "FitReportSkeleton",
    "HorizonSlotStatus",
    "OutcomeCounts",
    "Phase4Verdict",
    "RegimeSlice",
    "WalkForwardDiagnostics",
    "WalkForwardInputError",
    "WalkForwardPlan",
    "boundary_observations_from_bytes",
    "build_fit_report_skeleton",
    "load_experiment",
    "load_source_dataset",
    "plan_walk_forward_folds",
    "regime_slice_for_boundary",
    "render_fit_report_markdown",
    "render_markdown",
    "run_calibration_experiment",
    "run_calibration_from_path",
    "walk_forward_diagnostics",
    "write_report",
]
