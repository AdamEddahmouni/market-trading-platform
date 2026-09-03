import json
from pathlib import Path

from pydantic import TypeAdapter

from squeeze_core.contracts import Observation

from .models import EvaluationMetric, EvaluationReadiness


_METRIC_ADAPTER = TypeAdapter(EvaluationMetric)
_READINESS_ADAPTER = TypeAdapter(EvaluationReadiness)


def load_evaluation_evidence(path: str | Path):
    observations = []
    metrics = []
    readiness = []
    defaults = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"evidence line {line_number} must be an object")
        record_type = record.get("record_type")
        data = record.get("data")
        if record_type == "observation":
            observations.append(Observation.model_validate(data))
        elif record_type == "metric":
            metrics.append(_METRIC_ADAPTER.validate_python(data))
        elif record_type == "readiness":
            readiness.append(_READINESS_ADAPTER.validate_python(data))
        elif record_type == "default_substitution":
            field = record.get("field")
            if not isinstance(field, str) or not field:
                raise ValueError(f"evidence line {line_number} has invalid default substitution")
            defaults.append(field)
        else:
            raise ValueError(f"evidence line {line_number} has unknown record_type: {record_type}")
    return tuple(observations), tuple(metrics), tuple(readiness), tuple(defaults)


__all__ = ["load_evaluation_evidence"]

