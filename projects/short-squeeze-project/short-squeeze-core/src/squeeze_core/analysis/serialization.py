import json
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel

from .models import ResearchAnalysisResult


_FIXED_INTERVAL_FIELDS = {"lower_bound", "upper_bound"}


def _format_decimal(value: Decimal, field_name: str | None) -> str:
    if field_name in _FIXED_INTERVAL_FIELDS:
        return format(value, ".12f")
    if value == 0:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _canonicalize(value: Any, field_name: str | None = None) -> Any:
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="python"), field_name)
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item, str(key))
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item, field_name) for item in value]
    if isinstance(value, datetime):
        normalized = value.astimezone(UTC)
        return normalized.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return _format_decimal(value, field_name)
    if isinstance(value, Enum):
        return value.value
    return value


def serialize_analysis_model(value: BaseModel) -> bytes:
    rendered = json.dumps(
        _canonicalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return rendered.encode("utf-8")


def deserialize_analysis_result(value: bytes | str) -> ResearchAnalysisResult:
    raw = value.decode("utf-8") if isinstance(value, bytes) else value
    return ResearchAnalysisResult.model_validate(json.loads(raw))


def serialize_analysis_collection(
    values: tuple[ResearchAnalysisResult, ...],
) -> bytes:
    ordered = tuple(sorted(values, key=lambda item: str(item.deterministic_id)))
    rendered = json.dumps(
        _canonicalize(ordered),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return rendered.encode("utf-8")


__all__ = [
    "deserialize_analysis_result",
    "serialize_analysis_collection",
    "serialize_analysis_model",
]
