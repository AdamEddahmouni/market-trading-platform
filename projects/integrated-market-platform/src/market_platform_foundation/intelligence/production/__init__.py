"""Path A PRODUCTION specialist ForecastV1 emitter + temporal calibrator."""

from .calibrator import (
    ProductionCalibrationResult,
    train_production_calibration,
)
from .emitter import (
    ProductionEmitResult,
    emit_production_forecast,
)
from .errors import (
    ProductionCalibrationError,
    ProductionEmitError,
    ProductionError,
    ProductionTrainingError,
)
from .identity import (
    PATH_A_FAMILY_KEY,
    PATH_A_HORIZON_NS,
    PATH_A_PRODUCTION_FEATURE_SCHEMA,
    PATH_A_TARGET_KIND,
    path_a_direction_target,
    path_a_horizon,
)
from .model import (
    ProductionSpecialistModel,
    ProductionTrainingExample,
    fit_production_specialist,
)

__all__ = [
    "PATH_A_FAMILY_KEY",
    "PATH_A_HORIZON_NS",
    "PATH_A_PRODUCTION_FEATURE_SCHEMA",
    "PATH_A_TARGET_KIND",
    "ProductionCalibrationError",
    "ProductionCalibrationResult",
    "ProductionEmitError",
    "ProductionEmitResult",
    "ProductionError",
    "ProductionSpecialistModel",
    "ProductionTrainingError",
    "ProductionTrainingExample",
    "emit_production_forecast",
    "fit_production_specialist",
    "path_a_direction_target",
    "path_a_horizon",
    "train_production_calibration",
]
