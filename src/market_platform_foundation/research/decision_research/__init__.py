"""Governed decision-combination research."""

from .cards import ExperimentCard
from .experiments import SHORT_SQUEEZE_EXPERIMENTS
from .harness import build_folds, order_examples, run_harness, verify_harness_folds
from .models import ResearchResultStatus
from .pit_gate import reject_historical_finviz_screen_without_capture, validate_temporal_example
from .registry import ExperimentCardRegistry, verify_experiment_card_registration
from .runner import run_short_squeeze_family
from .synthesis import DecisionCandidate, build_decision_candidate

__all__ = [
    "ExperimentCard",
    "ExperimentCardRegistry",
    "ResearchResultStatus",
    "DecisionCandidate",
    "SHORT_SQUEEZE_EXPERIMENTS",
    "build_decision_candidate",
    "build_folds",
    "order_examples",
    "reject_historical_finviz_screen_without_capture",
    "run_harness",
    "run_short_squeeze_family",
    "validate_temporal_example",
    "verify_experiment_card_registration",
    "verify_harness_folds",
]
