"""Strategy interpretation: forecast + evidence → signal or abstention."""

from __future__ import annotations

from typing import Any

from ..features.institutional import query_all_institutional
from .abstention import ABSTAIN_CONFLICTING_EVIDENCE, evaluate_abstention
from .preregistration import verify_preregistration


def _forecast_direction(forecast: dict[str, Any]) -> str | None:
    score = forecast.get("score")
    if score is None:
        return None
    try:
        value = float(str(score))
    except ValueError:
        return None
    if value > 0:
        return "long"
    if value < 0:
        return "short"
    return "flat"


def interpret_strategy(
    *,
    strategy_spec: dict[str, Any],
    preregistration: dict[str, Any] | None,
    forecast: dict[str, Any],
    forecast_status: str,
    prediction_cutoff: int,
    observation_time: int,
    force_signal: bool = False,
) -> dict[str, Any]:
    prereg_status = "FAIL"
    prereg_reasons: list[str] = ["ABSTAIN_NO_PREREGISTRATION"]
    if preregistration is not None:
        prereg_status, prereg_reasons = verify_preregistration(preregistration, strategy_spec)

    institutional = query_all_institutional(prediction_cutoff=prediction_cutoff)
    should_abstain, abstain_reasons = evaluate_abstention(
        prereg_status=prereg_status,
        forecast_status=forecast_status,
        alignment_type=str(strategy_spec["alignment_type"]),
        institutional_rows=institutional,
        prediction_cutoff=prediction_cutoff,
        observation_time=observation_time,
    )

    if should_abstain:
        reasons = list(abstain_reasons)
        if force_signal and ABSTAIN_CONFLICTING_EVIDENCE not in reasons:
            reasons.append(ABSTAIN_CONFLICTING_EVIDENCE)
        return {
            "abstention_reason_codes": reasons,
            "alignment_type": strategy_spec["alignment_type"],
            "direction": None,
            "outcome": "abstention",
            "prediction_cutoff": prediction_cutoff,
            "strategy_identity_hash": strategy_spec["strategy_identity_hash"],
        }

    if force_signal:
        return {
            "abstention_reason_codes": [ABSTAIN_CONFLICTING_EVIDENCE],
            "alignment_type": strategy_spec["alignment_type"],
            "direction": None,
            "outcome": "abstention",
            "prediction_cutoff": prediction_cutoff,
            "strategy_identity_hash": strategy_spec["strategy_identity_hash"],
        }

    direction = _forecast_direction(forecast)
    alignment = str(strategy_spec["alignment_type"])
    if alignment == "WHALE_CONTRARIAN" and direction in ("long", "short"):
        direction = "short" if direction == "long" else "long"

    return {
        "abstention_reason_codes": [],
        "alignment_type": alignment,
        "direction": direction,
        "outcome": "signal",
        "prediction_cutoff": prediction_cutoff,
        "strategy_identity_hash": strategy_spec["strategy_identity_hash"],
    }
