import csv
import io
import json
from decimal import Decimal

from pydantic import BaseModel

from squeeze_core.serialization import canonical_json_bytes

from .models import BatchEvaluationResult, ResearchDataset


def serialize_research_model(value: BaseModel) -> bytes:
    return canonical_json_bytes(value)


def serialize_research_json(value: ResearchDataset) -> bytes:
    return canonical_json_bytes(value)


def serialize_research_jsonl(value: ResearchDataset) -> bytes:
    return b"".join(canonical_json_bytes(row) + b"\n" for row in value.rows)


_CORE_COLUMNS = (
    "dataset_version", "case_id", "symbol", "asset_class", "case_type", "case_status",
    "evaluation_as_of", "phase_3a_policy_version", "research_detection_policy_version",
    "outcome_policy_version", "original_platform_status", "research_detection_status",
    "outcome_label", "research_classification", "phase_3a_evaluation_id",
    "outcome_observation_id", "outcome_reference_policy", "outcome_horizon",
    "maximum_observed_move_percent", "maximum_adverse_move_percent",
    "fixture_classification", "source_ids", "missing_domains", "conflicted_rules",
    "insufficient_rules", "limitations", "row_id",
)


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "value"):
        value = value.value
    if isinstance(value, (tuple, list, dict)):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    rendered = str(value)
    return "'" + rendered if rendered.startswith(("=", "+", "-", "@")) else rendered


def serialize_research_csv(value: ResearchDataset) -> bytes:
    rule_ids = () if not value.rows else tuple(value.rows[0].rule_outcomes)
    columns = _CORE_COLUMNS + tuple(f"{rule_id}_outcome" for rule_id in rule_ids)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(columns)
    for row in value.rows:
        document = row.model_dump(mode="python")
        cells = [_cell(document[column]) for column in _CORE_COLUMNS]
        cells.extend(_cell(row.rule_outcomes[rule_id]) for rule_id in rule_ids)
        writer.writerow(cells)
    return stream.getvalue().encode("utf-8")


def deserialize_batch_result(value: bytes | str) -> BatchEvaluationResult:
    return BatchEvaluationResult.model_validate_json(value)


def deserialize_research_dataset(value: bytes | str) -> ResearchDataset:
    return ResearchDataset.model_validate_json(value)


__all__ = [
    "deserialize_batch_result", "deserialize_research_dataset", "serialize_research_csv",
    "serialize_research_json", "serialize_research_jsonl", "serialize_research_model",
]
