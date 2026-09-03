from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError


def structural_diagnostic_code(raw: Mapping[str, Any], error: ValidationError) -> str:
    locations = {str(item["loc"][0]) for item in error.errors() if item.get("loc")}
    if "provider_schema" in locations:
        return "BAR_UNSUPPORTED_SCHEMA"
    if "record_type" in locations:
        return "BAR_UNSUPPORTED_RECORD_TYPE"
    if "fixture_origin" in locations:
        return "BAR_INVALID_FIXTURE_ORIGIN"
    if "symbol" in locations or "ticker" in locations:
        return "BAR_MISSING_SYMBOL"
    if "interval" in locations:
        return "BAR_UNSUPPORTED_INTERVAL"
    return "BAR_UNSUPPORTED_RECORD_TYPE"

