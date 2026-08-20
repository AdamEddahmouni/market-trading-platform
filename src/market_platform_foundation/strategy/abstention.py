"""Abstention rules for strategy interpretation."""

from __future__ import annotations

from typing import Any

ABSTAIN_NO_PREREG = "ABSTAIN_NO_PREREGISTRATION"
ABSTAIN_INSTITUTIONAL_UNAVAILABLE = "ABSTAIN_INSTITUTIONAL_UNAVAILABLE"
ABSTAIN_FORECAST_INVALID = "ABSTAIN_FORECAST_INVALID"
ABSTAIN_FUTURE_INPUT = "ABSTAIN_FUTURE_INPUT"
ABSTAIN_CONFLICTING_EVIDENCE = "ABSTAIN_CONFLICTING_EVIDENCE"
ABSTAIN_COPYABILITY_UNAVAILABLE = "ABSTAIN_COPYABILITY_UNAVAILABLE"


def institutional_available(evidence_rows: list[dict[str, Any]]) -> bool:
    return any(row.get("status") != "unavailable" for row in evidence_rows)


def evaluate_abstention(
    *,
    prereg_status: str,
    forecast_status: str,
    alignment_type: str,
    institutional_rows: list[dict[str, Any]],
    prediction_cutoff: int,
    observation_time: int,
    copyability_gate_ok: bool | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if prereg_status != "PASS":
        reasons.append(ABSTAIN_NO_PREREG)
    if forecast_status != "PASS":
        reasons.append(ABSTAIN_FORECAST_INVALID)
    if observation_time > prediction_cutoff:
        reasons.append(ABSTAIN_FUTURE_INPUT)
    if alignment_type in ("WHALE_ALIGNED", "WHALE_CONTRARIAN"):
        if not institutional_available(institutional_rows):
            reasons.append(ABSTAIN_INSTITUTIONAL_UNAVAILABLE)
        if alignment_type == "WHALE_ALIGNED" and copyability_gate_ok is False:
            reasons.append(ABSTAIN_COPYABILITY_UNAVAILABLE)
    return bool(reasons), reasons
