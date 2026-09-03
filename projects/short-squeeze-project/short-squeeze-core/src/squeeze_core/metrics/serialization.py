import json

from squeeze_core.serialization.canonical_json import canonical_hash, canonical_json_bytes

from .models import MetricResult
from .normalized_models import BaselineStatistics, NormalizedMetricResult
from .pressure_models import DaysToCoverComponents, PressureMetricResult


def serialize_metric_result(result: MetricResult) -> bytes:
    return canonical_json_bytes(result)


def deserialize_metric_result(serialized: bytes | str) -> MetricResult:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return MetricResult.model_validate(json.loads(raw))


def metric_result_hash(result: MetricResult) -> str:
    return canonical_hash(result)


def serialize_normalized_metric_result(result: NormalizedMetricResult) -> bytes:
    return canonical_json_bytes(result)


def deserialize_normalized_metric_result(serialized: bytes | str) -> NormalizedMetricResult:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return NormalizedMetricResult.model_validate(json.loads(raw))


def normalized_metric_result_hash(result: NormalizedMetricResult) -> str:
    return canonical_hash(result)


def serialize_baseline_statistics(result: BaselineStatistics) -> bytes:
    return canonical_json_bytes(result)


def deserialize_baseline_statistics(serialized: bytes | str) -> BaselineStatistics:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return BaselineStatistics.model_validate(json.loads(raw))


def baseline_statistics_hash(result: BaselineStatistics) -> str:
    return canonical_hash(result)


def serialize_pressure_metric_result(result: PressureMetricResult) -> bytes:
    return canonical_json_bytes(result)


def deserialize_pressure_metric_result(serialized: bytes | str) -> PressureMetricResult:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return PressureMetricResult.model_validate(json.loads(raw))


def pressure_metric_result_hash(result: PressureMetricResult) -> str:
    return canonical_hash(result)


def serialize_days_to_cover_components(result: DaysToCoverComponents) -> bytes:
    return canonical_json_bytes(result)


def deserialize_days_to_cover_components(serialized: bytes | str) -> DaysToCoverComponents:
    raw = serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
    return DaysToCoverComponents.model_validate(json.loads(raw))


def days_to_cover_components_hash(result: DaysToCoverComponents) -> str:
    return canonical_hash(result)
