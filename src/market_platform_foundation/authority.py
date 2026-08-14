"""Fail-closed resolution of the repository's canonical specification authority."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from .canonical import load_json_strict, sha256_bytes


def _result(status: str, reasons: list[str], **values: object) -> dict[str, object]:
    return {"reason_codes": sorted(set(reasons)), "status": status, **values}


def _repository_path(root: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        return None
    candidate = (root / Path(*relative.parts)).resolve()
    if not candidate.is_relative_to(root):
        return None
    return candidate


def _verify_bound_file(
    root: Path,
    row: dict[str, object],
    missing: str,
    mismatch: str,
) -> tuple[str | None, str | None]:
    path = _repository_path(root, row.get("path"))
    if path is None:
        return "AUTHORITY_PATH_INVALID", None
    if not path.is_file():
        return missing, None
    try:
        actual = sha256_bytes(path.read_bytes())
    except OSError:
        return "AUTHORITY_FILE_UNREADABLE", None
    if actual != str(row.get("sha256", "")):
        return mismatch, actual
    return None, actual


def _status_for_reason(reason: str) -> str:
    if reason.endswith("MISSING") or reason.endswith("UNREADABLE"):
        return "BLOCKED"
    return "FAIL"


def _has_nonempty_strings(row: dict[str, object], fields: tuple[str, ...]) -> bool:
    return all(isinstance(row.get(field), str) and bool(row[field]) for field in fields)


def resolve_canonical_authority(repository_root: Path) -> dict[str, object]:
    root = repository_root.resolve()
    manifest_path = root / "manifests" / "phase0" / "canonical-authority.json"
    if not manifest_path.is_file():
        return _result(
            "BLOCKED",
            ["AUTHORITY_MANIFEST_MISSING"],
            one_canonical_specification=False,
        )
    try:
        manifest = load_json_strict(manifest_path)
    except (OSError, UnicodeError, ValueError):
        return _result(
            "FAIL",
            ["AUTHORITY_MANIFEST_INVALID"],
            one_canonical_specification=False,
        )
    if not isinstance(manifest, dict) or manifest.get("status") != "EFFECTIVE":
        return _result(
            "BLOCKED",
            ["AUTHORITY_MANIFEST_NOT_EFFECTIVE"],
            one_canonical_specification=False,
        )
    active = manifest.get("active_specification")
    phase0 = manifest.get("phase0_authority")
    incorporated = manifest.get("incorporated_specifications")
    if (
        not isinstance(active, dict)
        or not isinstance(phase0, dict)
        or not isinstance(incorporated, list)
        or not _has_nonempty_strings(
            active,
            (
                "approval_logical_id",
                "approval_path",
                "approval_sha256",
                "logical_id",
                "path",
                "sha256",
            ),
        )
        or not _has_nonempty_strings(phase0, ("logical_id", "path", "sha256"))
    ):
        return _result(
            "FAIL",
            ["AUTHORITY_MANIFEST_SHAPE_INVALID"],
            one_canonical_specification=False,
        )
    reason, _actual = _verify_bound_file(
        root,
        active,
        "ACTIVE_SPECIFICATION_MISSING",
        "ACTIVE_SPECIFICATION_HASH_MISMATCH",
    )
    if reason:
        return _result(
            _status_for_reason(reason),
            [reason],
            one_canonical_specification=False,
        )
    approval_path = _repository_path(root, active.get("approval_path"))
    if approval_path is None:
        return _result(
            "FAIL", ["AUTHORITY_PATH_INVALID"], one_canonical_specification=False
        )
    if not approval_path.is_file():
        return _result(
            "BLOCKED", ["APPROVAL_RECORD_MISSING"], one_canonical_specification=False
        )
    try:
        approval_bytes = approval_path.read_bytes()
    except OSError:
        return _result(
            "BLOCKED",
            ["APPROVAL_RECORD_UNREADABLE"],
            one_canonical_specification=False,
        )
    approval_sha256 = sha256_bytes(approval_bytes)
    if approval_sha256 != str(active.get("approval_sha256", "")):
        return _result(
            "FAIL",
            ["APPROVAL_RECORD_HASH_MISMATCH"],
            one_canonical_specification=False,
        )
    try:
        approval = load_json_strict(approval_path)
    except (OSError, UnicodeError, ValueError):
        return _result(
            "FAIL", ["APPROVAL_RECORD_INVALID"], one_canonical_specification=False
        )
    if not isinstance(approval, dict) or any(
        (
            approval.get("status") != "APPROVED",
            approval.get("logical_id") != active.get("approval_logical_id"),
            approval.get("specification_logical_id") != active.get("logical_id"),
            approval.get("specification_sha256") != active.get("sha256"),
        )
    ):
        return _result(
            "FAIL", ["APPROVAL_BINDING_MISMATCH"], one_canonical_specification=False
        )
    incorporated_bindings: dict[str, tuple[str, str]] = {}
    for row in [phase0, *incorporated]:
        if not isinstance(row, dict) or not _has_nonempty_strings(
            row, ("logical_id", "path", "sha256")
        ):
            return _result(
                "FAIL",
                ["INCORPORATED_BINDING_INVALID"],
                one_canonical_specification=False,
            )
        reason, _actual = _verify_bound_file(
            root,
            row,
            "INCORPORATED_SPECIFICATION_MISSING",
            "INCORPORATED_SPECIFICATION_HASH_MISMATCH",
        )
        if reason:
            return _result(
                _status_for_reason(reason),
                [reason],
                one_canonical_specification=False,
            )
        if row is not phase0:
            logical_id = str(row["logical_id"])
            if logical_id in incorporated_bindings:
                return _result(
                    "FAIL",
                    ["INCORPORATED_BINDING_INVALID"],
                    one_canonical_specification=False,
                )
            incorporated_bindings[logical_id] = (str(row["path"]), str(row["sha256"]))
    phase0_logical_id = str(phase0["logical_id"])
    if phase0_logical_id not in incorporated_bindings:
        return _result(
            "FAIL",
            ["INCORPORATED_BINDING_INVALID"],
            one_canonical_specification=False,
        )
    if incorporated_bindings[phase0_logical_id] != (
        str(phase0["path"]),
        str(phase0["sha256"]),
    ):
        return _result(
            "FAIL",
            ["PHASE0_AUTHORITY_BINDING_MISMATCH"],
            one_canonical_specification=False,
        )
    return _result(
        "PASS",
        [],
        active_logical_id=str(active["logical_id"]),
        active_path=str(active["path"]),
        active_sha256=str(active["sha256"]),
        approval_logical_id=str(active["approval_logical_id"]),
        approval_sha256=approval_sha256,
        authority_manifest_sha256=sha256_bytes(manifest_path.read_bytes()),
        incorporated_specification_count=len(incorporated),
        one_canonical_specification=True,
        phase0_status=str(manifest.get("phase0_status", "BLOCKED")),
    )
