import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid5


EVALUATION_NAMESPACE = UUID("6e8e556a-e02a-4933-9b43-4ec19c745a31")


def _default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"unsupported evaluation identity value: {type(value)!r}")


def deterministic_evaluation_id(identity: dict[str, Any]) -> str:
    rendered = json.dumps(identity, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, default=_default)
    return str(uuid5(EVALUATION_NAMESPACE, rendered))


def rule_result_identity(result: Any) -> dict[str, Any]:
    return {
        "result_type": "PHASE_3A_RULE_EVALUATION_RESULT",
        "rule_id": result.rule_id,
        "rule_version": result.rule_version,
        "category": result.category,
        "policy_version": result.policy_version,
        "symbol": result.symbol,
        "asset_class": result.asset_class,
        "as_of": result.as_of,
        "outcome": result.outcome,
        "operator": result.operator,
        "threshold_values": list(result.threshold_values),
        "threshold_unit": result.threshold_unit,
        "observed_value": result.observed_value,
        "observed_unit": result.observed_unit,
        "provider_scope": sorted(result.provider_scope),
        "input_observation_ids": sorted(result.input_observation_ids),
        "input_metric_ids": sorted(result.input_metric_ids),
        "readiness_snapshot_ids": sorted(result.readiness_snapshot_ids),
        "diagnostic_codes": sorted(item.code.value for item in result.diagnostics),
        "explanation_code": result.explanation_code,
    }


def candidate_evaluation_identity(result: Any) -> dict[str, Any]:
    return {
        "result_type": "PHASE_3A_CANDIDATE_EVALUATION_RESULT",
        "evaluation_version": result.evaluation_version,
        "policy_version": result.policy_version,
        "symbol": result.symbol,
        "asset_class": result.asset_class,
        "as_of": result.as_of,
        "enabled_rule_ids": sorted(result.enabled_rule_ids),
        "rule_result_ids": sorted(item.deterministic_id for item in result.rule_results),
        "input_observation_ids": sorted(result.input_observation_ids),
        "input_metric_ids": sorted(result.input_metric_ids),
        "readiness_snapshot_ids": sorted(result.readiness_snapshot_ids),
    }


__all__ = [
    "EVALUATION_NAMESPACE", "candidate_evaluation_identity",
    "deterministic_evaluation_id", "rule_result_identity",
]

