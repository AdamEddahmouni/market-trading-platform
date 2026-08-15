from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath

from .contract_core import SHA256_RE, canonical_bytes, hash_without_fields, sha256_bytes


POSTROOT_INDEX_IDS = {
    "phase0.ai_review_coverage",
    "phase0.ai_review_runs",
    "phase0.approval_records",
    "phase0.candidate_evidence_root",
    "phase0.postroot_acceptance_contract_suite",
    "phase0.postroot_acceptance_contract_suite.approval",
}


def record_identity(record: dict[str, object], identity_field: str) -> str:
    return hash_without_fields(record, {identity_field})


def expected_index_logical_ids(candidate_ids: list[str]) -> tuple[str, ...]:
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("INDEX-DUPLICATE-LOGICAL-ID")
    return tuple(sorted(set(candidate_ids) | POSTROOT_INDEX_IDS))


def _is_normalized_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    if value.startswith("/") or PureWindowsPath(value).drive:
        return False
    if any(part in {"", ".", ".."} for part in value.split("/")):
        return False
    return PurePosixPath(value).as_posix() == value


def _normalized_index_rows(index: dict[str, object]) -> list[dict[str, object]]:
    rows = index.get("index_members")
    if not isinstance(rows, list):
        raise ValueError("INDEX-MEMBERS-INVALID")

    logical_ids: list[str] = []
    paths: list[str] = []
    normalized: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("INDEX-MISSING-MEMBER")
        logical_id = row.get("logical_id")
        if not isinstance(logical_id, str) or not logical_id:
            raise ValueError("ID-LOGICAL-ID-INVALID")
        if logical_id == "phase0.acceptance_index":
            raise ValueError("INDEX-SELF-MEMBERSHIP")
        if logical_id == "phase0.final_acceptance_result":
            raise ValueError("INDEX-FINAL-RESULT-MEMBERSHIP")

        path = row.get("repository_relative_path")
        if not _is_normalized_relative_path(path):
            raise ValueError("INDEX-NONNORMALIZED-PATH")
        digest = row.get("member_sha256")
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise ValueError("INDEX-MEMBER-HASH-MISMATCH")

        logical_ids.append(logical_id)
        paths.append(path)
        normalized.append(row)

    if len(set(logical_ids)) != len(logical_ids):
        raise ValueError("INDEX-DUPLICATE-LOGICAL-ID")
    if len(set(paths)) != len(paths):
        raise ValueError("INDEX-DUPLICATE-PATH")
    return sorted(
        normalized,
        key=lambda row: (
            str(row["logical_id"]),
            str(row["repository_relative_path"]),
        ),
    )


def compute_index_hashes(index: dict[str, object]) -> tuple[str, str]:
    provisional = {
        key: value
        for key, value in index.items()
        if key not in {"index_sha256", "root_hash"}
    }
    ordered_rows = _normalized_index_rows(provisional)
    provisional["index_members"] = ordered_rows
    index_sha256 = sha256_bytes(canonical_bytes(provisional))
    ordered_pairs = sorted(
        [
            [str(row["logical_id"]), str(row["member_sha256"])]
            for row in ordered_rows
        ],
        key=lambda pair: (pair[0], pair[1]),
    )
    root_input = {
        "index_sha256": index_sha256,
        "ordered_member_pairs": ordered_pairs,
    }
    return index_sha256, sha256_bytes(canonical_bytes(root_input))


def verify_index_hashes(index: dict[str, object]) -> tuple[str, ...]:
    expected_index, expected_root = compute_index_hashes(index)
    reasons = []
    if index.get("index_sha256") != expected_index:
        reasons.append("INDEX-SHA256-MISMATCH")
    if index.get("root_hash") != expected_root:
        reasons.append("INDEX-ROOT-HASH-MISMATCH")
    return tuple(sorted(reasons))


def derive_final_outcome(
    assertion_aggregate_status: str,
    observed_invalid_statuses: list[str],
    required_evidence_absent: bool,
) -> str:
    if (
        assertion_aggregate_status == "FAIL"
        or "FAIL" in observed_invalid_statuses
        or "INVALID" in observed_invalid_statuses
    ):
        return "FAIL"
    if (
        assertion_aggregate_status == "BLOCKED"
        or "BLOCKED" in observed_invalid_statuses
        or required_evidence_absent
    ):
        return "BLOCKED"
    return "PASS" if assertion_aggregate_status == "PASS" else "BLOCKED"
