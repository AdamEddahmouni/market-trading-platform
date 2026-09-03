"""Campaign progress summaries for EVIDENCE-01A."""

from __future__ import annotations

from typing import Any

from ..evidence01.policy import build_forward_evidence_qualification_policy
from ..evidence01.types import ForwardEvidenceQualificationPolicyV1, SettlementRateState
from .types import ForwardObservationCampaignState


def _ns_to_days(ns: int) -> float:
    return ns / (24 * 60 * 60 * 1_000_000_000)


def _ns_to_hours_minutes(ns: int) -> str:
    total_minutes = ns // (60 * 1_000_000_000)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}h {minutes}m"


def build_progress_summary(
    *,
    policy: ForwardEvidenceQualificationPolicyV1,
    observation_summary: Any,
    campaign_state: ForwardObservationCampaignState,
    qualifying_session_count: int,
) -> dict[str, Any]:
    settlement_rate_display: str
    if observation_summary.settlement_rate_state == SettlementRateState.NOT_EVALUABLE:
        settlement_rate_display = "NOT_EVALUABLE"
    else:
        rate = observation_summary.settlement_rate or 0.0
        settlement_rate_display = f"{rate * 100:.1f}%"

    return {
        "campaign_state": campaign_state.value,
        "calendar_span_days": {
            "actual": round(_ns_to_days(observation_summary.elapsed_qualifying_duration_ns), 2),
            "required": round(_ns_to_days(policy.minimum_duration_ns), 2),
        },
        "trading_days": {
            "actual": observation_summary.distinct_trading_days,
            "required": policy.minimum_distinct_trading_days,
        },
        "sessions": {
            "actual": qualifying_session_count,
            "required": policy.minimum_distinct_sessions,
        },
        "eligible_predictions": {
            "actual": observation_summary.eligible_predictions,
            "required": policy.minimum_eligible_predictions,
        },
        "settled_predictions": {
            "actual": observation_summary.settled_predictions,
            "required": policy.minimum_settled_predictions,
        },
        "settlement_rate": {
            "actual": settlement_rate_display,
            "required": f">={int(policy.minimum_settlement_rate * 100)}%",
            "state": observation_summary.settlement_rate_state.value,
        },
        "up_support": {
            "actual": observation_summary.up_support,
            "required": policy.minimum_class_support,
        },
        "down_support": {
            "actual": observation_summary.down_support,
            "required": policy.minimum_class_support,
        },
        "maximum_gap": {
            "actual": _ns_to_hours_minutes(observation_summary.maximum_observation_gap_ns),
            "required_max": _ns_to_hours_minutes(policy.maximum_admissible_gap_ns),
        },
        "raw_observations": observation_summary.raw_observations,
        "excluded_observations": observation_summary.excluded_observations,
        "exclusions_by_reason": dict(observation_summary.exclusions_by_reason),
    }


def format_progress_text(progress: dict[str, Any], *, disposition: str, remaining: tuple[str, ...]) -> str:
    lines = [
        "EVIDENCE-01A CAMPAIGN PROGRESS",
        "",
        f"Calendar span:          {progress['calendar_span_days']['actual']} / {progress['calendar_span_days']['required']} days",
        f"Trading days:           {progress['trading_days']['actual']} / {progress['trading_days']['required']}",
        f"Sessions:               {progress['sessions']['actual']} / {progress['sessions']['required']}",
        f"Eligible predictions:  {progress['eligible_predictions']['actual']} / {progress['eligible_predictions']['required']}",
        f"Settled predictions:   {progress['settled_predictions']['actual']} / {progress['settled_predictions']['required']}",
        f"Settlement rate:       {progress['settlement_rate']['actual']} / {progress['settlement_rate']['required']}",
        f"UP support:             {progress['up_support']['actual']} / {progress['up_support']['required']}",
        f"DOWN support:           {progress['down_support']['actual']} / {progress['down_support']['required']}",
        f"Max decision gap:       {progress['maximum_gap']['actual']} / {progress['maximum_gap']['required_max']} max",
        "",
        "Disposition:",
        disposition,
    ]
    if remaining:
        lines.extend(["", "Remaining requirements:"])
        lines.extend(f"- {item}" for item in remaining)
    return "\n".join(lines)


def default_policy() -> ForwardEvidenceQualificationPolicyV1:
    return build_forward_evidence_qualification_policy()
