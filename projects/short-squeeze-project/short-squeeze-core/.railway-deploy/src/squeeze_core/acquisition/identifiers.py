import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid5


ACQUISITION_NAMESPACE = UUID("68ef52a8-c82d-5cc5-8ec1-f491041119bc")
_NON_IDENTITY_KEYS = {"absolute_path", "informational_created_at", "deterministic_id"}


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canonical(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
            if str(key) not in _NON_IDENTITY_KEYS
        }
    if isinstance(value, (tuple, list, set, frozenset)):
        items = [_canonical(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def deterministic_acquisition_id(identity: dict[str, Any]) -> str:
    encoded = json.dumps(
        _canonical(identity), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return str(uuid5(ACQUISITION_NAMESPACE, encoded))


__all__ = ["deterministic_acquisition_id"]
