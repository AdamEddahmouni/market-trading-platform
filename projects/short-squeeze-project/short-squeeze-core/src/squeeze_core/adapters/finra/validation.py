from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from squeeze_core.adapters.diagnostics import DiagnosticCode


def structural_diagnostic_code(
    raw: Mapping[str, Any], error: ValidationError
) -> DiagnosticCode:
    record_type = raw.get("record_type")
    if record_type in {"DAILY_SHORT_VOLUME", "SHORT_SALE_VOLUME"}:
        return DiagnosticCode.FINRA_DAILY_SHORT_VOLUME_NOT_SUPPORTED
    details = error.errors()
    if any(item["type"] == "extra_forbidden" for item in details):
        return DiagnosticCode.FINRA_UNSUPPORTED_RECORD_TYPE
    locations = {str(item["loc"][0]) for item in details if item.get("loc")}
    if "provider_schema" in locations:
        return DiagnosticCode.FINRA_UNSUPPORTED_SCHEMA
    if "record_type" in locations:
        return DiagnosticCode.FINRA_UNSUPPORTED_RECORD_TYPE
    if "fixture_origin" in locations:
        return DiagnosticCode.FINRA_INVALID_FIXTURE_ORIGIN
    if "symbol" in locations:
        return DiagnosticCode.FINRA_MISSING_SYMBOL
    return DiagnosticCode.INVALID_NUMERIC_VALUE
