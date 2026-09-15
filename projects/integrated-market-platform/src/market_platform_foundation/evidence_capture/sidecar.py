"""Versioned capture-context sidecar for receipt artifacts.

The sidecar sits beside an artifact (for example ``receipt.json`` +
``receipt.capture-context.json``). It records runtime provenance without
mutating the artifact receipt contract or upgrading evidence class.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from ..git_ref import read_git_head, read_remote_ref, repo_root

CAPTURE_CONTEXT_SCHEMA_VERSION = "1.0.0"
CAPTURE_CONTEXT_ARTIFACT_KIND = "evidence_capture_context_sidecar"
SIDECAR_SUFFIX = ".capture-context.json"

_SECRET_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
    "cookie",
    "authorization",
    "login_json_paths",
    "token_txt_paths",
)

_FIXTURE_MARKERS = frozenset(
    {
        "FIXTURE",
        "FIXTURE_SMOKE",
        "NON_EMPIRICAL_FIXTURE",
        "NOT_PROSPECTIVE_EVIDENCE",
        "SOFTWARE/FIXTURE/REPLAY",
        "REPLAY",
        "SMOKE",
    }
)

_PROSPECTIVE_MARKERS = frozenset(
    {
        "LIVE_PROSPECTIVE",
        "PROSPECTIVE",
        "PROSPECTIVE_OBSERVATIONAL",
        "PROSPECTIVE_BAR_OHLCV_1M",
        "PROSPECTIVE_FINVIZ_INGRESS",
    }
)


class CaptureContextError(ValueError):
    """Raised when capture-context create/verify fails closed."""


def default_sidecar_path_for_artifact(artifact_path: Path) -> Path:
    name = artifact_path.name
    if name.endswith(".json"):
        stem = name[: -len(".json")]
        return artifact_path.with_name(f"{stem}{SIDECAR_SUFFIX}")
    return artifact_path.with_name(f"{name}{SIDECAR_SUFFIX}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_evidence_token(value: Any) -> str:
    return str(value or "").strip().upper()


def _evidence_rank(evidence_class: str) -> int:
    normalized = _normalize_evidence_token(evidence_class)
    if not normalized:
        return 0
    if normalized in {"SOFTWARE", "UNCLASSIFIED"}:
        return 0
    if any(marker in normalized for marker in _FIXTURE_MARKERS):
        return 1
    if any(marker in normalized for marker in _PROSPECTIVE_MARKERS):
        return 2
    if normalized.startswith("LIVE") or "EMPIRICAL" in normalized:
        return 3
    return 1


def _artifact_fixture_signals(payload: Mapping[str, Any]) -> bool:
    for key in ("attention_data_kind", "watch_mode", "proof_mode", "test_mode"):
        token = _normalize_evidence_token(payload.get(key))
        if "FIXTURE" in token or token == "REPLAY":
            return True
    if payload.get("dry_run") is True:
        return True
    if payload.get("not_prospective_evidence") is True:
        return True
    return False


def infer_artifact_evidence_class(
    artifact_path: Path,
    *,
    payload: Mapping[str, Any] | None = None,
) -> str:
    data: Mapping[str, Any]
    if payload is not None:
        data = payload
    else:
        try:
            raw = json.loads(artifact_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CaptureContextError(f"ARTIFACT_NOT_READABLE:{artifact_path}") from exc
        if not isinstance(raw, dict):
            raise CaptureContextError("ARTIFACT_NOT_OBJECT")
        data = raw

    fixture = _artifact_fixture_signals(data)
    explicit = _normalize_evidence_token(data.get("evidence_class"))
    if fixture:
        if not explicit or explicit == "SOFTWARE" or _evidence_rank(explicit) > 1:
            return "NON_EMPIRICAL_FIXTURE"
        return explicit

    if explicit:
        return explicit
    return "SOFTWARE"


def _assert_no_secret_leak(value: Any, *, path: str = "") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in _SECRET_SUBSTRINGS):
                if isinstance(nested, (bool, int, float)) or nested in {None, "PRESENT", "ABSENT", "REDACTED"}:
                    continue
                if isinstance(nested, str) and nested in {"PRESENT", "ABSENT", "REDACTED", "VALID", "INVALID"}:
                    continue
                raise CaptureContextError(f"SECRET_LEAK:{path}.{key}")
            _assert_no_secret_leak(nested, path=f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _assert_no_secret_leak(nested, path=f"{path}[{index}]")


def _sanitize_gate_states(states: Mapping[str, Any] | None) -> dict[str, str]:
    if not states:
        return {}
    cleaned: dict[str, str] = {}
    for key, value in states.items():
        if isinstance(value, bool):
            cleaned[str(key)] = "ENABLED" if value else "DISABLED"
        elif value is None:
            cleaned[str(key)] = "UNSET"
        else:
            token = str(value).strip().upper()
            if any(part in token for part in ("=", "://", "BEGIN ")):
                raise CaptureContextError(f"GATE_STATE_RAW_VALUE:{key}")
            cleaned[str(key)] = token[:120]
    return cleaned


def _relative_artifact_path(artifact_path: Path, sidecar_path: Path) -> str:
    try:
        return artifact_path.resolve().relative_to(sidecar_path.parent.resolve()).as_posix()
    except ValueError:
        return artifact_path.name


def _resolve_repository_root(start: Path) -> Path:
    try:
        return repo_root(start=start)
    except FileNotFoundError:
        return start.resolve().parent


def create_capture_context_sidecar(
    *,
    artifact_path: Path,
    sidecar_path: Path | None = None,
    campaign: str,
    evidence_class: str | None = None,
    provider: str | None = None,
    command: str | None = None,
    working_directory: str | None = None,
    operator_run_id: str | None = None,
    captured_at_ns: int | None = None,
    temporary_gate_states: Mapping[str, Any] | None = None,
    repository_root: Path | None = None,
) -> dict[str, Any]:
    artifact = artifact_path.resolve()
    if not artifact.is_file():
        raise CaptureContextError(f"ARTIFACT_MISSING:{artifact}")

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CaptureContextError("ARTIFACT_NOT_OBJECT")

    inferred = infer_artifact_evidence_class(artifact, payload=payload)
    stated = _normalize_evidence_token(evidence_class) if evidence_class else inferred
    if _evidence_rank(stated) > _evidence_rank(inferred):
        raise CaptureContextError("EVIDENCE_CLASS_UPGRADE_DENIED")

    root = (repository_root or _resolve_repository_root(artifact)).resolve()
    target_sidecar = (sidecar_path or default_sidecar_path_for_artifact(artifact)).resolve()
    artifact_sha256 = _sha256_file(artifact)
    run_id = operator_run_id or f"ECC-{uuid.uuid4().hex[:12].upper()}"

    record: dict[str, Any] = {
        "schema_version": CAPTURE_CONTEXT_SCHEMA_VERSION,
        "artifact_kind": CAPTURE_CONTEXT_ARTIFACT_KIND,
        "capture_context_id": run_id,
        "artifact_path": _relative_artifact_path(artifact, target_sidecar),
        "artifact_sha256": artifact_sha256,
        "runtime_git_sha": read_git_head(start=root),
        "origin_main_sha": read_remote_ref("origin", "main", start=root),
        "captured_at_ns": captured_at_ns if captured_at_ns is not None else time.time_ns(),
        "operator_run_id": run_id,
        "command": command,
        "working_directory": working_directory,
        "campaign": campaign,
        "evidence_class": stated,
        "artifact_evidence_class": inferred,
        "provider": provider,
        "temporary_gate_states": _sanitize_gate_states(temporary_gate_states),
        "orders_placed": False,
        "empirical_lock_created": False,
    }
    _assert_no_secret_leak(record)
    target_sidecar.parent.mkdir(parents=True, exist_ok=True)
    target_sidecar.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def verify_capture_context_sidecar(
    *,
    sidecar_path: Path,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    sidecar = sidecar_path.resolve()
    if not sidecar.is_file():
        raise CaptureContextError(f"SIDECAR_MISSING:{sidecar}")

    try:
        record = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureContextError(f"SIDECAR_NOT_READABLE:{sidecar}") from exc
    if not isinstance(record, dict):
        raise CaptureContextError("SIDECAR_NOT_OBJECT")

    if record.get("schema_version") != CAPTURE_CONTEXT_SCHEMA_VERSION:
        raise CaptureContextError("SCHEMA_VERSION_MISMATCH")
    if record.get("artifact_kind") != CAPTURE_CONTEXT_ARTIFACT_KIND:
        raise CaptureContextError("ARTIFACT_KIND_MISMATCH")

    _assert_no_secret_leak(record)

    if record.get("orders_placed") is True:
        raise CaptureContextError("ORDERS_PLACED_FORBIDDEN")
    if record.get("empirical_lock_created") is True:
        raise CaptureContextError("EMPIRICAL_LOCK_FORBIDDEN")

    rel = str(record.get("artifact_path") or "")
    artifact = (artifact_path or (sidecar.parent / rel)).resolve()
    if not artifact.is_file():
        raise CaptureContextError(f"ARTIFACT_MISSING:{artifact}")

    current_hash = _sha256_file(artifact)
    if str(record.get("artifact_sha256") or "") != current_hash:
        raise CaptureContextError("ARTIFACT_SHA256_MISMATCH")

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CaptureContextError("ARTIFACT_NOT_OBJECT")

    inferred = infer_artifact_evidence_class(artifact, payload=payload)
    artifact_class = _normalize_evidence_token(record.get("artifact_evidence_class"))
    if artifact_class and artifact_class != inferred:
        raise CaptureContextError("ARTIFACT_EVIDENCE_CLASS_DRIFT")

    stated = _normalize_evidence_token(record.get("evidence_class"))
    if _evidence_rank(stated) > _evidence_rank(inferred):
        raise CaptureContextError("EVIDENCE_CLASS_UPGRADE_DENIED")

    return {
        "disposition": "VALID",
        "artifact_path": str(artifact),
        "artifact_sha256": current_hash,
        "artifact_evidence_class": inferred,
        "evidence_class": stated,
    }
