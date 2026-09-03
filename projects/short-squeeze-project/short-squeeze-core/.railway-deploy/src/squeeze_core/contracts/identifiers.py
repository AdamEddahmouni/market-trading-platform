import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid5


OBSERVATION_NAMESPACE = UUID("c920de75-dd5e-56ac-bf36-5434ab2e2555")


def _identity_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"unsupported identity value: {type(value)!r}")


def deterministic_observation_id(identity: dict[str, Any]) -> str:
    encoded = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_identity_default,
    )
    return str(uuid5(OBSERVATION_NAMESPACE, encoded))
