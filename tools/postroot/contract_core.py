from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from typing import Any


SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{9}Z$")
LOGICAL_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")

SCHEMA_CODES = {
    "SCHEMA-ADDITIONAL-PROPERTY-POLICY",
    "SCHEMA-ARRAY-DUPLICATE",
    "SCHEMA-ARRAY-ORDER",
    "SCHEMA-ENUM-INVALID",
    "SCHEMA-FORMAT-INVALID",
    "SCHEMA-MISSING-REQUIRED-FIELD",
    "SCHEMA-TYPE-INVALID",
    "SCHEMA-UNDECLARED-FIELD",
}


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class ValidationResult:
    status: str
    reason_codes: tuple[str, ...]


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("JSON-DUPLICATE-KEY")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise ContractError("JSON-PARSE-INVALID")


def strict_loads(raw: bytes) -> object:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ContractError("BYTE-UTF8-BOM")
    try:
        text = raw.decode("utf-8", errors="strict")
        return json.loads(
            text,
            object_pairs_hook=_pairs_no_duplicates,
            parse_constant=_reject_json_constant,
        )
    except UnicodeDecodeError as exc:
        raise ContractError("BYTE-UTF8-INVALID") from exc
    except json.JSONDecodeError as exc:
        raise ContractError("JSON-PARSE-INVALID") from exc


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def hash_without_fields(value: dict[str, object], omitted: set[str]) -> str:
    return sha256_bytes(
        canonical_bytes({key: item for key, item in value.items() if key not in omitted})
    )


def _matches_type(value: object, expected: object) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def _valid_timestamp(value: str) -> bool:
    if TIMESTAMP_RE.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value[:26] + "Z", "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return False
    return True


def _valid_format(value: str, format_name: object) -> bool:
    if format_name == "NONEMPTY":
        return bool(value)
    if format_name == "SHA256":
        return SHA256_RE.fullmatch(value) is not None
    if format_name == "TIMESTAMP":
        return _valid_timestamp(value)
    if format_name == "LOGICAL_ID":
        return LOGICAL_ID_RE.fullmatch(value) is not None
    return False


def _canonical_markers(values: list[object]) -> list[bytes]:
    return [canonical_bytes(value) for value in values]


def _validate_object(
    value: dict[str, object], rule: dict[str, object], reasons: set[str]
) -> None:
    policy = rule.get("additional_properties")
    if policy != "REJECT":
        reasons.add("SCHEMA-ADDITIONAL-PROPERTY-POLICY")

    field_rules = rule.get("field_rules", {})
    required_fields = rule.get("required_fields", [])
    if not isinstance(field_rules, dict) or not isinstance(required_fields, list):
        reasons.add("SCHEMA-TYPE-INVALID")
        return

    declared = set(field_rules)
    if any(not isinstance(field, str) for field in required_fields):
        reasons.add("SCHEMA-TYPE-INVALID")
    else:
        if any(field not in value for field in required_fields):
            reasons.add("SCHEMA-MISSING-REQUIRED-FIELD")

    if policy == "REJECT" and any(field not in declared for field in value):
        reasons.add("SCHEMA-UNDECLARED-FIELD")

    for field_name, field_rule in field_rules.items():
        if field_name in value:
            if not isinstance(field_rule, dict):
                reasons.add("SCHEMA-TYPE-INVALID")
                continue
            _validate_rule(value[field_name], field_rule, reasons)


def _validate_rule(value: object, rule: dict[str, object], reasons: set[str]) -> None:
    expected_type = rule.get("type")
    if not _matches_type(value, expected_type):
        reasons.add("SCHEMA-TYPE-INVALID")
        return

    enum_values = rule.get("enum")
    if enum_values is not None:
        if not isinstance(enum_values, list) or value not in enum_values:
            reasons.add("SCHEMA-ENUM-INVALID")

    format_name = rule.get("format")
    if format_name is not None:
        if not isinstance(value, str) or not _valid_format(value, format_name):
            reasons.add("SCHEMA-FORMAT-INVALID")

    if expected_type == "object":
        _validate_object(value, rule, reasons)  # type: ignore[arg-type]
        return

    if expected_type != "array":
        return

    values = value  # type: ignore[assignment]
    item_rule = rule.get("item_rule")
    if not isinstance(item_rule, dict):
        reasons.add("SCHEMA-TYPE-INVALID")
    else:
        for item in values:
            _validate_rule(item, item_rule, reasons)

    ordering = rule.get("ordering")
    if ordering == "LEXICOGRAPHIC_UNIQUE":
        markers = _canonical_markers(values)
        if len(set(markers)) != len(markers):
            reasons.add("SCHEMA-ARRAY-DUPLICATE")
        if markers != sorted(markers):
            reasons.add("SCHEMA-ARRAY-ORDER")
    elif ordering != "SEQUENCE":
        reasons.add("SCHEMA-ARRAY-ORDER")


def validate_contract(value: object, contract: dict[str, object]) -> ValidationResult:
    reasons: set[str] = set()
    if not isinstance(value, dict):
        reasons.add("SCHEMA-TYPE-INVALID")
    else:
        _validate_object(value, contract, reasons)
    reason_codes = tuple(sorted(reasons & SCHEMA_CODES))
    return ValidationResult("PASS" if not reason_codes else "FAIL", reason_codes)
