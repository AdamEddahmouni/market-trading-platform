import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid5


ANALYSIS_NAMESPACE = UUID("30f77e74-c484-4f73-a651-20f698543c55")


def _identity_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"unsupported analysis identity value: {type(value)!r}")


def deterministic_analysis_id(identity: dict[str, Any]) -> str:
    encoded = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_identity_default,
    )
    return str(uuid5(ANALYSIS_NAMESPACE, encoded))


__all__ = ["deterministic_analysis_id"]
