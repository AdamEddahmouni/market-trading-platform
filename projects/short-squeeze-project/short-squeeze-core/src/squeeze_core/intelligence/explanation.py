"""Build a causal explanation graph from squeeze intelligence output."""

from __future__ import annotations

from typing import Any

from .contracts import SqueezeIntelligenceResult, SqueezeState


def build_explanation_graph(result: SqueezeIntelligenceResult) -> dict[str, Any]:
    """Return a nested explanation graph suitable for UI progressive disclosure."""
    root: dict[str, Any] = {
        "headline": f"State: {result.state.value}",
        "confidence": result.overall_confidence,
        "summary": result.explanation.summary,
        "children": [],
    }

    dimensions = [
        ("Structural vulnerability", result.vulnerability),
        ("Securities-lending constraint", result.constraint_pressure),
        ("Short stress", result.short_stress),
        ("Ignition strength", result.ignition_strength),
        ("Reflexivity", result.reflexivity_strength),
        ("Remaining fuel", result.remaining_fuel),
        ("Exhaustion risk", result.exhaustion_risk),
    ]
    for label, value in dimensions:
        if value is not None:
            root["children"].append(
                {
                    "label": label,
                    "value": value,
                    "kind": "dimension",
                }
            )

    if result.supporting_evidence:
        root["children"].append(
            {
                "label": "Supporting evidence",
                "kind": "evidence_group",
                "items": [
                    {
                        "code": item.code,
                        "label": item.label,
                        "detail": item.detail,
                        "strength": item.strength,
                    }
                    for item in result.supporting_evidence
                ],
            }
        )

    if result.contradicting_evidence:
        root["children"].append(
            {
                "label": "Contradicting evidence / gaps",
                "kind": "evidence_group",
                "items": [
                    {
                        "code": item.code,
                        "label": item.label,
                        "detail": item.detail,
                        "strength": item.strength,
                    }
                    for item in result.contradicting_evidence
                ],
            }
        )

    if result.missing_capabilities:
        root["children"].append(
            {
                "label": "Missing capabilities",
                "kind": "capability_gap",
                "items": list(result.missing_capabilities),
            }
        )

    if result.horizon_probabilities:
        root["children"].append(
            {
                "label": "Horizon probabilities",
                "kind": "horizons",
                "note": "Calibrated probabilities require validated labels and walk-forward models.",
                "items": [
                    {
                        "horizon_days": hp.horizon_days,
                        "value": hp.value,
                        "status": hp.status,
                        "note": hp.note,
                    }
                    for hp in result.horizon_probabilities
                ],
            }
        )

    if result.state is SqueezeState.UNEVALUABLE:
        root["children"].append(
            {
                "label": "Evaluation blocked",
                "kind": "blocked",
                "quality_flags": list(result.quality_flags),
            }
        )

    return root
