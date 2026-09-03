"""SS P3 squeeze baseline models and calibration harness."""

from .calibration import brier_score, calibration_report, precision_at_k, pr_auc_approx
from .harness import load_mechanism_dataset, run_squeeze_walk_forward_harness
from .logistic_hazard import predict_squeeze_probability
from .magnitude import predict_squeeze_magnitude
from .pain_distribution import estimate_short_pain_distribution, pain_distribution_result
from .rare_event_ensemble import predict_squeeze_ensemble

__all__ = [
    "brier_score",
    "calibration_report",
    "estimate_short_pain_distribution",
    "load_mechanism_dataset",
    "pain_distribution_result",
    "predict_squeeze_ensemble",
    "predict_squeeze_magnitude",
    "predict_squeeze_probability",
    "precision_at_k",
    "pr_auc_approx",
    "run_squeeze_walk_forward_harness",
]
