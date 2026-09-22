"""Item 9 calibration execute gate (fail-closed; never fits this sprint).

Checks an explicit authorization artifact BEFORE reading the real corpus for
any result write. Missing authorization returns CALIBRATION_EXECUTION_REFUSED.
This module does not create authorization artifacts and does not invoke
execution against the frozen collector receipt directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .item9_calibration_protocol import (
    CALIBRATION_STATE,
    ITEM9_STATUS_NOT_CALIBRATED,
    PROTOCOL_VERSION,
    protocol_freeze_record,
)
from .item9_validation_readiness_contract import (
    AUTHORIZATION_ABSENT,
    AUTHORIZATION_ARTIFACT_SCHEMA_ID,
    AUTHORIZATION_INVALID,
    AUTHORIZATION_PRESENT,
    BOUND_PROTOCOL_VERSION,
    CALIBRATED_DEFAULT,
    CALIBRATION_ARTIFACT_SCHEMA_ID,
    CALIBRATION_EXECUTION_REFUSED,
    FITTING_ALLOWED_DEFAULT,
    ITEM9_CALIBRATION_RUN_FORBIDDEN,
    METHODOLOGY_FREEZE_SCHEMA_ID,
    REASON_TOCTOU_FINGERPRINT_MISMATCH,
    RULE_AUTH_REQUIRED_FOR_EXECUTE,
    RULE_PROTOCOL_SEARCH_COMPLEXITY_0,
    RULE_TOCTOU_FINGERPRINT,
    SEARCH_COMPLEXITY_MAX,
    contract_freeze_record,
)

EXECUTE_ARTIFACT_KIND = "item9_calibration_execute_v1"
METHODOLOGY_MANIFEST_REL = Path("manifests/paper/item9_calibration_methodology_freeze_v1.json")
TOCTOU_FINGERPRINT_KEYS: tuple[str, ...] = (
    "corpus_fingerprint",
    "evaluation_fingerprint",
    "protocol_fingerprint",
)


def bind_preflight_toctou(
    preflight: Mapping[str, Any],
    *,
    code_sha: str | None = None,
) -> dict[str, Any]:
    """Capture fingerprints at preflight so execute can detect later mutation."""

    return {
        "corpus_fingerprint": preflight.get("corpus_fingerprint"),
        "evaluation_fingerprint": preflight.get("evaluation_fingerprint"),
        "protocol_fingerprint": preflight.get("protocol_fingerprint"),
        "code_sha": code_sha,
        "bound": True,
        "governing_rule_id": RULE_TOCTOU_FINGERPRINT,
    }


def compare_toctou_bindings(
    bound: Mapping[str, Any] | None,
    current: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Fail closed when bound preflight fingerprints disagree with current."""

    if not bound or not current:
        return {
            "ok": False,
            "mismatched": ["binding_absent"],
            "reason": REASON_TOCTOU_FINGERPRINT_MISMATCH,
            "governing_rule_id": RULE_TOCTOU_FINGERPRINT,
        }
    mismatched: list[str] = []
    for key in TOCTOU_FINGERPRINT_KEYS:
        left = bound.get(key)
        right = current.get(key)
        if not left or not right or str(left) != str(right):
            mismatched.append(key)
    if bound.get("code_sha") is not None and current.get("code_sha") is not None:
        if str(bound.get("code_sha")) != str(current.get("code_sha")):
            mismatched.append("code_sha")
    return {
        "ok": not mismatched,
        "mismatched": mismatched,
        "reason": REASON_TOCTOU_FINGERPRINT_MISMATCH if mismatched else None,
        "governing_rule_id": RULE_TOCTOU_FINGERPRINT,
    }


def load_methodology_freeze(*, imp_root: Path) -> dict[str, Any]:
    path = imp_root / METHODOLOGY_MANIFEST_REL
    if not path.is_file():
        return {
            "loaded": False,
            "schema_id": METHODOLOGY_FREEZE_SCHEMA_ID,
            "path": str(path),
            "search_complexity_max": SEARCH_COMPLEXITY_MAX,
            "fitting_allowed": FITTING_ALLOWED_DEFAULT,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {
            "loaded": False,
            "schema_id": METHODOLOGY_FREEZE_SCHEMA_ID,
            "path": str(path),
            "invalid": True,
        }
    return {"loaded": True, "path": str(path.resolve()), **payload}


def inspect_authorization_artifact(path: Path | None) -> dict[str, Any]:
    """Read-only authorization inspection. Does not create artifacts."""

    if path is None or not path.is_file():
        return {
            "authorization_state": AUTHORIZATION_ABSENT,
            "path": str(path) if path is not None else None,
            "schema_id": AUTHORIZATION_ARTIFACT_SCHEMA_ID,
            "valid": False,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {
            "authorization_state": AUTHORIZATION_INVALID,
            "path": str(path),
            "schema_id": AUTHORIZATION_ARTIFACT_SCHEMA_ID,
            "valid": False,
            "reason": "UNREADABLE_OR_INVALID_JSON",
        }
    if not isinstance(payload, dict):
        return {
            "authorization_state": AUTHORIZATION_INVALID,
            "path": str(path),
            "valid": False,
            "reason": "NOT_AN_OBJECT",
        }
    schema = str(payload.get("schema_id") or payload.get("schema_version") or "")
    grant = str(payload.get("grant") or payload.get("authorization_grant") or "").upper()
    if schema and AUTHORIZATION_ARTIFACT_SCHEMA_ID.split("/")[0] not in schema:
        return {
            "authorization_state": AUTHORIZATION_INVALID,
            "path": str(path),
            "valid": False,
            "reason": "SCHEMA_MISMATCH",
            "observed_schema": schema,
        }
    if grant not in {"ITEM9_CALIBRATION_RUN_AUTHORIZED", "AUTHORIZED"}:
        return {
            "authorization_state": AUTHORIZATION_INVALID,
            "path": str(path),
            "valid": False,
            "reason": "GRANT_MISSING_OR_DENIED",
            "grant": grant or None,
        }
    if payload.get("fitting_allowed") is True:
        return {
            "authorization_state": AUTHORIZATION_INVALID,
            "path": str(path),
            "valid": False,
            "reason": "FITTING_ALLOWED_TRUE_FORBIDDEN_UNDER_PROTOCOL_1_0_0",
        }
    return {
        "authorization_state": AUTHORIZATION_PRESENT,
        "path": str(path.resolve()),
        "valid": True,
        "schema_id": schema or AUTHORIZATION_ARTIFACT_SCHEMA_ID,
        "grant": grant,
        "payload_keys": sorted(payload.keys()),
    }


def calibration_artifact_schema_template() -> dict[str, Any]:
    """Would-be immutable artifact slots. Cannot set CALIBRATED."""

    return {
        "schema_id": CALIBRATION_ARTIFACT_SCHEMA_ID,
        "bound_protocol_version": BOUND_PROTOCOL_VERSION,
        "slots": {
            "corpus_fingerprint": None,
            "protocol_fingerprint": None,
            "code_sha": None,
            "config": None,
            "seed": None,
            "inputs": None,
            "exclusions": None,
            "warnings": None,
            "fixed_parameters": None,
            "metrics": None,
            "time": None,
            "environment": None,
        },
        "calibrated": CALIBRATED_DEFAULT,
        "fitting_allowed": FITTING_ALLOWED_DEFAULT,
        "item9_status": ITEM9_STATUS_NOT_CALIBRATED,
        "cannot_set_calibrated": True,
        "search_complexity_max": SEARCH_COMPLEXITY_MAX,
    }


def refuse_calibration_execution_before_corpus_read(
    *,
    authorization_path: Path | None = None,
    receipt_dir: Path | None = None,
    imp_root: Path | None = None,
    bound_toctou: Mapping[str, Any] | None = None,
    current_toctou: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed BEFORE reading corpus rows for any result write.

    When authorization is absent/invalid, return CALIBRATION_EXECUTION_REFUSED
    without opening receipt_dir for calibration result generation.
    """

    auth = inspect_authorization_artifact(authorization_path)
    corpus_read_attempted = False
    receipt_listing_attempted = False
    toctou = None
    if bound_toctou is not None or current_toctou is not None:
        toctou = compare_toctou_bindings(bound_toctou, current_toctou)

    if auth["authorization_state"] != AUTHORIZATION_PRESENT or not auth.get("valid"):
        return {
            "artifact_kind": EXECUTE_ARTIFACT_KIND,
            "verdict": CALIBRATION_EXECUTION_REFUSED,
            "reason": "AUTHORIZATION_REQUIRED_BEFORE_CORPUS_READ",
            "governing_rule_id": RULE_AUTH_REQUIRED_FOR_EXECUTE,
            "authorization": auth,
            "authorization_state": auth["authorization_state"],
            "corpus_read_attempted": corpus_read_attempted,
            "receipt_listing_attempted": receipt_listing_attempted,
            "receipt_dir": str(receipt_dir) if receipt_dir is not None else None,
            "receipt_dir_opened": False,
            "calibrated": CALIBRATED_DEFAULT,
            "fitting_allowed": FITTING_ALLOWED_DEFAULT,
            "item9_calibration_run": ITEM9_CALIBRATION_RUN_FORBIDDEN,
            "item9_status": ITEM9_STATUS_NOT_CALIBRATED,
            "calibration_state": CALIBRATION_STATE,
            "protocol_version": PROTOCOL_VERSION,
            "bound_protocol_version": BOUND_PROTOCOL_VERSION,
            "search_complexity_max": SEARCH_COMPLEXITY_MAX,
            "search_complexity_rule": RULE_PROTOCOL_SEARCH_COMPLEXITY_0,
            "toctou": toctou,
            "would_be_artifact": calibration_artifact_schema_template(),
            "contract_freeze": contract_freeze_record(),
            "protocol_freeze": protocol_freeze_record(),
            "methodology": (
                load_methodology_freeze(imp_root=imp_root)
                if imp_root is not None
                else {"loaded": False}
            ),
        }

    if toctou is not None and not toctou.get("ok"):
        return {
            "artifact_kind": EXECUTE_ARTIFACT_KIND,
            "verdict": CALIBRATION_EXECUTION_REFUSED,
            "reason": REASON_TOCTOU_FINGERPRINT_MISMATCH,
            "governing_rule_id": RULE_TOCTOU_FINGERPRINT,
            "authorization": auth,
            "authorization_state": AUTHORIZATION_PRESENT,
            "corpus_read_attempted": False,
            "receipt_listing_attempted": False,
            "receipt_dir": str(receipt_dir) if receipt_dir is not None else None,
            "receipt_dir_opened": False,
            "calibrated": CALIBRATED_DEFAULT,
            "fitting_allowed": FITTING_ALLOWED_DEFAULT,
            "item9_calibration_run": ITEM9_CALIBRATION_RUN_FORBIDDEN,
            "item9_status": ITEM9_STATUS_NOT_CALIBRATED,
            "calibration_state": CALIBRATION_STATE,
            "protocol_version": PROTOCOL_VERSION,
            "bound_protocol_version": BOUND_PROTOCOL_VERSION,
            "search_complexity_max": SEARCH_COMPLEXITY_MAX,
            "toctou": toctou,
            "would_be_artifact": calibration_artifact_schema_template(),
        }

    # Authorization present: still refuse in this sprint path unless explicitly
    # extended later. Do not read the real corpus here.
    return {
        "artifact_kind": EXECUTE_ARTIFACT_KIND,
        "verdict": CALIBRATION_EXECUTION_REFUSED,
        "reason": "EXECUTION_NOT_INVOKED_THIS_SPRINT",
        "governing_rule_id": RULE_AUTH_REQUIRED_FOR_EXECUTE,
        "authorization": auth,
        "authorization_state": AUTHORIZATION_PRESENT,
        "corpus_read_attempted": False,
        "receipt_listing_attempted": False,
        "receipt_dir": str(receipt_dir) if receipt_dir is not None else None,
        "receipt_dir_opened": False,
        "calibrated": CALIBRATED_DEFAULT,
        "fitting_allowed": FITTING_ALLOWED_DEFAULT,
        "item9_calibration_run": ITEM9_CALIBRATION_RUN_FORBIDDEN,
        "item9_status": ITEM9_STATUS_NOT_CALIBRATED,
        "calibration_state": CALIBRATION_STATE,
        "protocol_version": PROTOCOL_VERSION,
        "bound_protocol_version": BOUND_PROTOCOL_VERSION,
        "search_complexity_max": SEARCH_COMPLEXITY_MAX,
        "toctou": toctou,
        "would_be_artifact": calibration_artifact_schema_template(),
        "note": (
            "Authorization may be PRESENT in tests; this sprint still does not "
            "invoke calibration against the frozen collector corpus."
        ),
    }


def assert_corpus_unread_on_refusal(result: Mapping[str, Any]) -> None:
    if result.get("verdict") == CALIBRATION_EXECUTION_REFUSED:
        if result.get("corpus_read_attempted") or result.get("receipt_dir_opened"):
            raise AssertionError("REFUSAL_MUST_PRECEDE_CORPUS_READ")


__all__ = [
    "EXECUTE_ARTIFACT_KIND",
    "METHODOLOGY_MANIFEST_REL",
    "assert_corpus_unread_on_refusal",
    "bind_preflight_toctou",
    "calibration_artifact_schema_template",
    "compare_toctou_bindings",
    "inspect_authorization_artifact",
    "load_methodology_freeze",
    "refuse_calibration_execution_before_corpus_read",
]
