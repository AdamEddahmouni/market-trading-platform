"""Order Flow OF12 baseline gate rules."""

from __future__ import annotations

from typing import Any

GATE_MILESTONE_OF12_S1 = "OF12-S1"
GATE_MILESTONE_OF_Q9 = "OF-Q9"


def _brier_score(probabilities: list[float], realized_up: list[bool]) -> float | None:
    if not probabilities or len(probabilities) != len(realized_up):
        return None
    scores = [
        (prob - (1.0 if label else 0.0)) ** 2
        for prob, label in zip(probabilities, realized_up)
    ]
    return sum(scores) / len(scores)


def _directional_accuracy(probabilities: list[float], realized_up: list[bool]) -> float | None:
    if not probabilities or len(probabilities) != len(realized_up):
        return None
    correct = 0
    for prob, label in zip(probabilities, realized_up):
        predicted_up = prob >= 0.5
        if predicted_up == label:
            correct += 1
    return correct / len(probabilities)


def evaluate_of12_s1_gate(
    m1_probabilities: list[float],
    m8_probabilities: list[float],
    realized_up: list[bool],
) -> dict[str, Any]:
    """M8 must beat M1 on Brier or directional accuracy (fixture scope)."""
    if not m1_probabilities or not m8_probabilities or not realized_up:
        return {
            "available": False,
            "gate_milestone": GATE_MILESTONE_OF12_S1,
            "gate_status": "INSUFFICIENT_SAMPLE",
            "reason": "EMPTY_PREDICTIONS",
        }
    if len(m1_probabilities) != len(realized_up) or len(m8_probabilities) != len(realized_up):
        return {
            "available": False,
            "gate_milestone": GATE_MILESTONE_OF12_S1,
            "gate_status": "INSUFFICIENT_SAMPLE",
            "reason": "LENGTH_MISMATCH",
        }

    m1_brier = _brier_score(m1_probabilities, realized_up)
    m8_brier = _brier_score(m8_probabilities, realized_up)
    m1_acc = _directional_accuracy(m1_probabilities, realized_up)
    m8_acc = _directional_accuracy(m8_probabilities, realized_up)

    gate_status = "INSUFFICIENT_SAMPLE"
    if m1_brier is not None and m8_brier is not None and m1_acc is not None and m8_acc is not None:
        brier_win = m8_brier <= m1_brier
        acc_win = m8_acc >= m1_acc
        gate_status = "PASS" if (brier_win or acc_win) and not (m8_brier > m1_brier and m8_acc < m1_acc) else "FAIL"
        if m8_brier < m1_brier or m8_acc > m1_acc:
            gate_status = "PASS"

    return {
        "available": True,
        "gate_milestone": GATE_MILESTONE_OF12_S1,
        "gate_status": gate_status,
        "m1_brier": round(m1_brier, 6) if m1_brier is not None else None,
        "m8_brier": round(m8_brier, 6) if m8_brier is not None else None,
        "m1_directional_accuracy": round(m1_acc, 6) if m1_acc is not None else None,
        "m8_directional_accuracy": round(m8_acc, 6) if m8_acc is not None else None,
        "sample_size": len(realized_up),
        "research_only": True,
    }


def evaluate_of_q9_gate(
    l2_passive_fill: float | None,
    mbo_passive_fill: float | None,
    *,
    l2_queue_model: str | None = None,
    mbo_queue_model: str | None = None,
) -> dict[str, Any]:
    """MBO queue model must upgrade passive fill estimate vs L2-only path."""
    if l2_passive_fill is None or mbo_passive_fill is None:
        return {
            "available": False,
            "gate_milestone": GATE_MILESTONE_OF_Q9,
            "gate_status": "INSUFFICIENT_SAMPLE",
            "reason": "MISSING_FILL_ESTIMATES",
        }

    queue_upgraded = (
        l2_queue_model == "none"
        and mbo_queue_model is not None
        and mbo_queue_model != "none"
    )
    fill_differs = abs(mbo_passive_fill - l2_passive_fill) >= 1e-6
    gate_status = "PASS" if queue_upgraded and fill_differs else "FAIL"

    return {
        "available": True,
        "gate_milestone": GATE_MILESTONE_OF_Q9,
        "gate_status": gate_status,
        "l2_passive_fill_probability": round(l2_passive_fill, 6),
        "mbo_passive_fill_probability": round(mbo_passive_fill, 6),
        "l2_queue_model_version": l2_queue_model,
        "mbo_queue_model_version": mbo_queue_model,
        "research_only": True,
    }


__all__ = [
    "GATE_MILESTONE_OF12_S1",
    "GATE_MILESTONE_OF_Q9",
    "evaluate_of12_s1_gate",
    "evaluate_of_q9_gate",
]
