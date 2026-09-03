"""Futures F11 research harness package."""

from .baseline_harness import (
    DEFAULT_CL_F11_BASELINE_FIXTURE,
    DEFAULT_CL_F11_COT_UPGRADE_FIXTURE,
    DEFAULT_ES_F11_BASELINE_FIXTURE,
    DEFAULT_ES_F11_COT_UPGRADE_FIXTURE,
    load_cl_f11_baseline_dataset,
    load_cl_f11_cot_upgrade_dataset,
    load_es_f11_baseline_dataset,
    load_es_f11_cot_upgrade_dataset,
    run_f11_baseline_gate_validation,
    run_f11_baseline_walk_forward_harness,
    run_f11_cot_upgrade_harness,
    run_f11_energy_baseline_gate_validation,
)
from .gates import GATE_MILESTONE_F11_S1, GATE_MILESTONE_FQ8, evaluate_f11_s1_gate, evaluate_fq8_gate

__all__ = [
    "DEFAULT_CL_F11_BASELINE_FIXTURE",
    "DEFAULT_CL_F11_COT_UPGRADE_FIXTURE",
    "DEFAULT_ES_F11_BASELINE_FIXTURE",
    "DEFAULT_ES_F11_COT_UPGRADE_FIXTURE",
    "GATE_MILESTONE_F11_S1",
    "GATE_MILESTONE_FQ8",
    "evaluate_f11_s1_gate",
    "evaluate_fq8_gate",
    "load_cl_f11_baseline_dataset",
    "load_cl_f11_cot_upgrade_dataset",
    "load_es_f11_baseline_dataset",
    "load_es_f11_cot_upgrade_dataset",
    "run_f11_baseline_gate_validation",
    "run_f11_baseline_walk_forward_harness",
    "run_f11_cot_upgrade_harness",
    "run_f11_energy_baseline_gate_validation",
]
