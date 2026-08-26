"""Validate the post-BUILD35 whole-repository closure classification."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


CLASSIFICATIONS = frozenset(
    {
        "CANONICAL",
        "WRAPPED",
        "RETAINED_SUPPORTING",
        "SUPERSEDED",
        "DUPLICATE",
        "DEAD",
        "UNINTEGRATED",
    }
)

DISPOSITIONS = {
    "CANONICAL": frozenset({"KEEP"}),
    "WRAPPED": frozenset({"KEEP_WRAPPER"}),
    "RETAINED_SUPPORTING": frozenset({"KEEP"}),
    "SUPERSEDED": frozenset({"PRESERVE_HISTORY"}),
    "DUPLICATE": frozenset({"CONSOLIDATE"}),
    "DEAD": frozenset({"REMOVE", "QUARANTINE"}),
    "UNINTEGRATED": frozenset({"INTEGRATE", "DEFER", "RETIRE"}),
}

TARGETED_CLASSIFICATIONS = frozenset({"WRAPPED", "SUPERSEDED", "DUPLICATE"})
COVERAGE_KINDS = frozenset({"CHILD_DIRECTORIES", "PYTHON_FILES"})


class ClosureAuditError(ValueError):
    """Raised when closure classification is incomplete or contradictory."""

    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True, slots=True)
class ClosureEntry:
    id: str
    classification: str
    scope: tuple[str, ...]
    responsibility: str
    evidence: tuple[str, ...]
    disposition: str
    canonical_target: str | None = None


@dataclass(frozen=True, slots=True)
class ClosureAudit:
    schema_version: str
    campaign: str
    predecessor: str
    classification_time_changes: str
    entries: tuple[ClosureEntry, ...]
    discovered_paths: frozenset[str]
    covered_paths: frozenset[str]


def _relative_path(value: Any, *, field: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        errors.append(f"{field} must be a normalized repository-relative path")
        return ""
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        errors.append(f"{field} must be a normalized repository-relative path")
        return ""
    return value


def _text_list(value: Any, *, field: str, errors: list[str]) -> tuple[str, ...]:
    if not isinstance(value, list):
        errors.append(f"{field} must be an array")
        return ()
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}[{index}] must be a non-empty string")
            continue
        result.append(item)
    return tuple(result)


def _discover_paths(
    raw_rules: Any,
    repository_root: Path,
    errors: list[str],
) -> set[str]:
    if not isinstance(raw_rules, list) or not raw_rules:
        errors.append("coverage_rules must be a non-empty array")
        return set()
    discovered: set[str] = set()
    for index, rule in enumerate(raw_rules):
        if not isinstance(rule, dict):
            errors.append(f"coverage_rules[{index}] must be an object")
            continue
        root = _relative_path(
            rule.get("root"), field=f"coverage_rules[{index}].root", errors=errors
        )
        include = rule.get("include")
        if include not in COVERAGE_KINDS:
            errors.append(f"invalid coverage include at index {index}: {include!r}")
            continue
        excluded = set(
            _text_list(
                rule.get("exclude", []),
                field=f"coverage_rules[{index}].exclude",
                errors=errors,
            )
        )
        if not root:
            continue
        target = repository_root / PurePosixPath(root)
        if not target.is_dir():
            errors.append(f"coverage root does not exist: {root}")
            continue
        children = sorted(target.iterdir(), key=lambda item: item.name)
        if include == "CHILD_DIRECTORIES":
            selected = [item for item in children if item.is_dir() and item.name not in excluded]
        else:
            selected = [
                item
                for item in children
                if item.is_file() and item.suffix == ".py" and item.name not in excluded
            ]
        discovered.update(item.relative_to(repository_root).as_posix() for item in selected)
    return discovered


def _parse_entries(raw_entries: Any, repository_root: Path, errors: list[str]) -> tuple[ClosureEntry, ...]:
    if not isinstance(raw_entries, list) or not raw_entries:
        errors.append("entries must be a non-empty array")
        return ()
    entries: list[ClosureEntry] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(raw_entries):
        if not isinstance(row, dict):
            errors.append(f"entries[{index}] must be an object")
            continue
        entry_id = row.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            errors.append(f"entries[{index}].id must be a non-empty string")
            continue
        if entry_id in seen_ids:
            errors.append(f"duplicate entry id: {entry_id}")
        seen_ids.add(entry_id)
        classification = row.get("classification")
        if classification not in CLASSIFICATIONS:
            errors.append(f"invalid classification for {entry_id}: {classification!r}")
            classification = str(classification or "")
        raw_scope = row.get("scope")
        if not isinstance(raw_scope, list) or not raw_scope:
            errors.append(f"scope must be a non-empty array for {entry_id}")
            raw_scope = []
        scope: list[str] = []
        for scope_index, item in enumerate(raw_scope):
            relative = _relative_path(
                item,
                field=f"{entry_id}.scope[{scope_index}]",
                errors=errors,
            )
            if not relative:
                continue
            if not (repository_root / PurePosixPath(relative)).exists():
                errors.append(f"scope path does not exist for {entry_id}: {relative}")
            scope.append(relative)
        responsibility = row.get("responsibility")
        if not isinstance(responsibility, str) or not responsibility.strip():
            errors.append(f"responsibility required for {entry_id}")
            responsibility = ""
        evidence = _text_list(row.get("evidence"), field=f"{entry_id}.evidence", errors=errors)
        if not evidence:
            errors.append(f"evidence required for {entry_id}")
        disposition = row.get("disposition")
        allowed_dispositions = DISPOSITIONS.get(classification, frozenset())
        if disposition not in allowed_dispositions:
            errors.append(
                f"invalid disposition for {entry_id}: {disposition!r} under {classification}"
            )
            disposition = str(disposition or "")
        canonical_target = row.get("canonical_target")
        if canonical_target is not None and (
            not isinstance(canonical_target, str) or not canonical_target
        ):
            errors.append(f"canonical_target must be a non-empty entry id for {entry_id}")
            canonical_target = None
        if classification in TARGETED_CLASSIFICATIONS and canonical_target is None:
            errors.append(f"canonical_target required for {entry_id}")
        entries.append(
            ClosureEntry(
                id=entry_id,
                classification=classification,
                scope=tuple(scope),
                responsibility=responsibility,
                evidence=evidence,
                disposition=disposition,
                canonical_target=canonical_target,
            )
        )
    return tuple(entries)


def load_closure_audit(path: Path, *, repository_root: Path) -> ClosureAudit:
    """Load and validate one closure classification artifact."""

    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ClosureAuditError([f"unable to read closure audit: {exc}"]) from exc
    if not isinstance(payload, dict):
        raise ClosureAuditError(["closure audit root must be an object"])

    schema_version = payload.get("schema_version")
    campaign = payload.get("campaign")
    predecessor = payload.get("predecessor")
    classification_time_changes = payload.get("classification_time_changes")
    if schema_version != "1.0":
        errors.append(f"unsupported schema_version: {schema_version!r}")
    if campaign != "POST-BUILD35-REPOSITORY-CLOSURE-001":
        errors.append(f"invalid campaign: {campaign!r}")
    if predecessor != "BUILD35":
        errors.append(f"invalid predecessor: {predecessor!r}")
    if classification_time_changes != "NONE":
        errors.append("classification_time_changes must be NONE")

    discovered = _discover_paths(payload.get("coverage_rules"), repository_root, errors)
    required_paths = _text_list(
        payload.get("required_paths"), field="required_paths", errors=errors
    )
    for index, value in enumerate(required_paths):
        relative = _relative_path(value, field=f"required_paths[{index}]", errors=errors)
        if not relative:
            continue
        if not (repository_root / PurePosixPath(relative)).exists():
            errors.append(f"required path does not exist: {relative}")
        discovered.add(relative)

    entries = _parse_entries(payload.get("entries"), repository_root, errors)
    entries_by_id = {entry.id: entry for entry in entries}
    owners: dict[str, list[str]] = {}
    for entry in entries:
        for relative in entry.scope:
            owners.setdefault(relative, []).append(entry.id)
        if entry.classification in TARGETED_CLASSIFICATIONS and entry.canonical_target is not None:
            target = entries_by_id.get(entry.canonical_target)
            if target is None:
                errors.append(
                    f"unknown canonical_target for {entry.id}: {entry.canonical_target}"
                )
            elif target.classification != "CANONICAL":
                errors.append(
                    f"canonical_target for {entry.id} is not CANONICAL: {entry.canonical_target}"
                )
            elif target.id == entry.id:
                errors.append(f"entry cannot target itself: {entry.id}")

    for relative in sorted(discovered):
        path_owners = owners.get(relative, [])
        if not path_owners:
            errors.append(f"unclassified path: {relative}")
        elif len(path_owners) > 1:
            errors.append(f"multiply classified path: {relative} ({', '.join(path_owners)})")

    if errors:
        raise ClosureAuditError(errors)
    return ClosureAudit(
        schema_version=str(schema_version),
        campaign=str(campaign),
        predecessor=str(predecessor),
        classification_time_changes=str(classification_time_changes),
        entries=entries,
        discovered_paths=frozenset(discovered),
        covered_paths=frozenset(owners),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        audit = load_closure_audit(
            args.audit.resolve(), repository_root=args.repository_root.resolve()
        )
    except ClosureAuditError as exc:
        print(
            json.dumps(
                {"errors": list(exc.errors), "status": "FAIL"},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    counts = {classification: 0 for classification in sorted(CLASSIFICATIONS)}
    for entry in audit.entries:
        counts[entry.classification] += 1
    print(
        json.dumps(
            {
                "campaign": audit.campaign,
                "classification_counts": counts,
                "classified_paths": len(audit.covered_paths),
                "discovered_paths": len(audit.discovered_paths),
                "status": "PASS",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
