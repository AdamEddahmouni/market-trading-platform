"""Options lane — IV, Greeks, surface (O2), Q inference (O3), P vs Q (O4)."""

from .edge import (
    EDGE_VERSION,
    apply_executable_edge,
    compare_physical_vs_risk_neutral,
    estimate_execution_friction,
)
from .flow import (
    FLOW_VERSION,
    abnormal_flow_vs_baseline,
    aggregate_signed_flow,
    build_flow_snapshot,
    classify_signed_flow,
)
from .greeks import bsm_greeks, GREEKS_VERSION
from .iv import bsm_price, dual_track_iv, implied_volatility, IV_SOLVER_VERSION
from .risk_neutral import MODEL_VERSION as RISK_NEUTRAL_MODEL_VERSION, infer_risk_neutral_distribution
from .surface import build_surface_point, build_volatility_surface
from .surface_qa import evaluate_surface_qa
from .vrp import VRP_VERSION, estimate_vrp, vrp_research_snapshot

__all__ = [
    "EDGE_VERSION",
    "FLOW_VERSION",
    "GREEKS_VERSION",
    "IV_SOLVER_VERSION",
    "RISK_NEUTRAL_MODEL_VERSION",
    "VRP_VERSION",
    "abnormal_flow_vs_baseline",
    "aggregate_signed_flow",
    "apply_executable_edge",
    "bsm_greeks",
    "bsm_price",
    "build_flow_snapshot",
    "build_surface_point",
    "build_volatility_surface",
    "compare_physical_vs_risk_neutral",
    "classify_signed_flow",
    "dual_track_iv",
    "estimate_execution_friction",
    "estimate_vrp",
    "evaluate_surface_qa",
    "implied_volatility",
    "infer_risk_neutral_distribution",
    "vrp_research_snapshot",
]
