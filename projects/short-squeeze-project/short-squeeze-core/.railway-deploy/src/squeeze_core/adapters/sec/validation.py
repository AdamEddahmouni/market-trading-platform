from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from squeeze_core.adapters.diagnostics import DiagnosticCode


def structural_diagnostic_code(raw: Mapping[str, Any], error: ValidationError) -> DiagnosticCode:
    locations = {str(item["loc"][0]) for item in error.errors() if item.get("loc")}
    if "provider_schema" in locations:
        return DiagnosticCode.SEC_UNSUPPORTED_SCHEMA
    if "record_type" in locations:
        return DiagnosticCode.SEC_UNSUPPORTED_RECORD_TYPE
    if "fixture_origin" in locations:
        return DiagnosticCode.SEC_INVALID_FIXTURE_ORIGIN
    if "symbol" in locations:
        return DiagnosticCode.SEC_MISSING_SYMBOL
    return DiagnosticCode.SEC_UNSUPPORTED_RECORD_TYPE
