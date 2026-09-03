from __future__ import annotations

from .evidence import EvidenceInput
from .models import MethodologyResult

PEER_ID = "peer_reference_methodology"
PEER_LABEL = "PEER REFERENCE METHODOLOGY — NOT OUR MODEL"
PRESSURE_WEIGHTS = {
    "estimated_si_pct": 45,
    "days_to_cover": 20,
    "cost_to_borrow": 15,
    "shortability": 10,
    "short_volume_pct": 10,
}
IGNITION_WEIGHTS = {
    "relative_volume": 40,
    "positive_current_percentage_change": 40,
    "ttm_squeeze": 20,
}
MISSING_DEFINITIONS = (
    "normalization_functions",
    "estimated_si_formula",
    "float_multiplier_mapping",
    "ttm_squeeze_implementation",
    "subprime_boundaries",
    "missing_data_behavior",
    "caps_and_floors",
)


def describe_peer(inputs: dict[str, EvidenceInput], *, as_of: str | None = None) -> MethodologyResult:
    available = tuple(key for key in (*PRESSURE_WEIGHTS, *IGNITION_WEIGHTS) if key in inputs)
    return MethodologyResult(
        methodology_id=PEER_ID,
        methodology_version="reference-email.v1",
        methodology_label=PEER_LABEL,
        classification="REFERENCE_DEFINITION_INCOMPLETE",
        evaluable=False,
        pressure=None,
        ignition=None,
        evidence_coverage={
            "category": "REFERENCE_DEFINITION_INCOMPLETE",
            "available_reference_inputs": len(available),
            "required_reference_inputs": len(PRESSURE_WEIGHTS) + len(IGNITION_WEIGHTS),
        },
        known_inputs=available,
        missing_inputs=tuple(key for key in (*PRESSURE_WEIGHTS, *IGNITION_WEIGHTS) if key not in inputs),
        supporting_evidence=tuple(inputs[key].as_dict() for key in available),
        blocking_reasons=tuple(
            f"Peer reference does not specify {name.replace('_', ' ')}"
            for name in MISSING_DEFINITIONS
        ),
        as_of=as_of,
        metadata={
            "pressure_weights": PRESSURE_WEIGHTS,
            "float_multiplier_range": {"minimum": 0.85, "maximum": 1.15},
            "ignition_weights": IGNITION_WEIGHTS,
            "prime_thresholds": {"pressure_gte": 55, "ignition_gte": 50},
            "missing_definitions": list(MISSING_DEFINITIONS),
            "source_role": "DOCUMENTED_COMPARISON_ONLY",
        },
    )
