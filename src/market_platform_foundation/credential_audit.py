"""Value-blind credential-path classification and redacted scanning."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable

_PRIVATE_PATH = re.compile(
    r"(?i)(^|/)(\.env(?:\..*)?$|[^/]*(?:credential|secret|password|private[_-]?key|api[_-]?key|auth[_-]?token|access[_-]?token)[^/]*$)"
)
_PLACEHOLDERS = {"CHANGEME", "EXAMPLE", "PLACEHOLDER", "NOT_A_SECRET"}
_AUDIT_SOURCE_EXCEPTIONS = {
    "src/market_platform_foundation/credential_audit.py",
    "tests/phase0/test_credential_audit.py",
}


def classify_path(path: str, tracked: bool) -> dict[str, object]:
    normalized = path.replace("\\", "/")
    sanitized_evidence = re.fullmatch(
        r"evidence/phase0/[0-9A-F]{64}/credential-audit\.json", normalized
    )
    if normalized in _AUDIT_SOURCE_EXCEPTIONS or sanitized_evidence:
        return {"classification": "CONTENT_SCAN_ELIGIBLE", "content_read": False}
    if _PRIVATE_PATH.search(normalized):
        return {
            "classification": (
                "PROHIBITED_TRACKED_MATERIAL" if tracked else "PRIVATE_LOCAL_MATERIAL"
            ),
            "content_read": False,
        }
    return {"classification": "CONTENT_SCAN_ELIGIBLE", "content_read": False}


def _opaque_path_id() -> str:
    return "PATH-" + uuid.uuid4().hex[:12].upper()


def redact_match(
    rule_id: str,
    opaque_path_id: str,
    _matched_value: str,
    revision_id: str = "WORKTREE",
    line_number: int | None = None,
) -> dict[str, str]:
    location = "LINE-REDACTED" if line_number is None else f"LINE-{line_number}"
    return {
        "opaque_path_id": opaque_path_id,
        "revision_id": revision_id,
        "rule_id": rule_id,
        "sanitized_location": location,
    }


def validate_public_example(value: str) -> bool:
    return value in _PLACEHOLDERS


def audit_path_inventory(paths: Iterable[str], tracked: bool) -> dict[str, object]:
    prohibited: list[dict[str, str]] = []
    eligible_count = 0
    for path in paths:
        classification = classify_path(path, tracked)
        if classification["classification"] == "PROHIBITED_TRACKED_MATERIAL":
            prohibited.append(
                {
                    "classification": "PROHIBITED_TRACKED_MATERIAL",
                    "opaque_path_id": _opaque_path_id(),
                }
            )
        elif classification["classification"] == "CONTENT_SCAN_ELIGIBLE":
            eligible_count += 1
    return {
        "content_eligible_count": eligible_count,
        "private_content_read": False,
        "prohibited_count": len(prohibited),
        "prohibited_paths": prohibited,
    }


def scan_redacted_bytes(
    data: bytes,
    opaque_path_id: str,
    revision_id: str,
    rules: dict[str, str],
) -> list[dict[str, str]]:
    text = data.decode("utf-8", errors="replace")
    findings: list[dict[str, str]] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for rule_id, pattern in sorted(rules.items()):
            if re.search(pattern, line):
                findings.append(
                    redact_match(rule_id, opaque_path_id, "", revision_id, line_number)
                )
    return findings
