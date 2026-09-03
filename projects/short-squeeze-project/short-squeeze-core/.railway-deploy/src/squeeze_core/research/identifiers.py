import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid5


RESEARCH_NAMESPACE = UUID("7e4598d1-8c1d-4d15-92c5-9d7ec6a43bc3")


def _identity_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"unsupported identity value: {type(value)!r}")


def deterministic_research_id(identity: dict[str, Any]) -> str:
    encoded = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_identity_default,
    )
    return str(uuid5(RESEARCH_NAMESPACE, encoded))


__all__ = ["deterministic_research_id"]
