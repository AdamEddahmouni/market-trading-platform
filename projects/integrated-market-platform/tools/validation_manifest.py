"""Typed, deterministic loader for the canonical validation manifest.

This module is intentionally stdlib-only and side-effect free: importing it
does not discover tests, import providers, inspect Git, or access the network.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SAFETY_CLASSES = frozenset(
    {
        "PARALLEL_SAFE",
        "SERIAL_REQUIRED",
        "LIVE_EXCLUSIVE",
        "RESOURCE_HEAVY",
        "GLOBAL_STATE_MUTATION",
    }
)
CLASSIFICATIONS = frozenset(
    {"offline", "live", "extended", "intentionally_absent", "intentionally_excluded"}
)
SELECTOR_PATTERN = re.compile(
    r"^(tests/[A-Za-z0-9_.\-/]+\.py)::([A-Za-z_][A-Za-z0-9_]*)::"
    r"([A-Za-z_][A-Za-z0-9_]*)$"
)


class ManifestValidationError(ValueError):
    """Raised when the canonical suite inventory is ambiguous or unsafe."""

    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True, slots=True)
class MandatoryInvariant:
    id: str
    selector: str
    order: int
    isolation: str


@dataclass(frozen=True, slots=True)
class ValidationSuite:
    id: str
    path: str
    classification: str
    tiers: tuple[str, ...]
    domains: tuple[str, ...]
    parallel_safety: str
    resource_weight: int
    source_globs: tuple[str, ...]
    test_globs: tuple[str, ...]
    neighbors: tuple[str, ...]
    live_provider: str | None = None
    deep_live: bool = False
    absence_reason: str | None = None
    superseded_by: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationManifest:
    schema_version: str
    domains: tuple[str, ...]
    full_invalidators: tuple[str, ...]
    mandatory_invariants: tuple[MandatoryInvariant, ...]
    suites: tuple[ValidationSuite, ...]

    def suite_by_id(self, suite_id: str) -> ValidationSuite:
        for suite in self.suites:
            if suite.id == suite_id:
                return suite
        raise KeyError(suite_id)


def _sequence(value: Any, *, field: str, errors: list[str]) -> tuple[Any, ...]:
    if not isinstance(value, list):
        errors.append(f"{field} must be an array")
        return ()
    return tuple(value)


def _text_sequence(value: Any, *, field: str, errors: list[str]) -> tuple[str, ...]:
    values = _sequence(value, field=field, errors=errors)
    if any(not isinstance(item, str) or not item for item in values):
        errors.append(f"{field} entries must be non-empty strings")
        return tuple(str(item) for item in values if isinstance(item, str) and item)
    return tuple(values)


def _valid_relative_glob(pattern: str) -> bool:
    if not pattern or "\\" in pattern:
        return False
    path = PurePosixPath(pattern)
    return not path.is_absolute() and ".." not in path.parts and path.parts[0] not in {"", "."}


def _parse_invariants(raw: Any, errors: list[str]) -> tuple[MandatoryInvariant, ...]:
    rows = _sequence(raw, field="mandatory_invariants", errors=errors)
    invariants: list[MandatoryInvariant] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"mandatory_invariants[{index}] must be an object")
            continue
        invariant_id = row.get("id")
        selector = row.get("selector")
        order = row.get("order")
        isolation = row.get("isolation", "shared")
        if not isinstance(invariant_id, str) or not invariant_id:
            errors.append(f"mandatory_invariants[{index}].id must be a non-empty string")
            continue
        if invariant_id in seen:
            errors.append(f"duplicate mandatory invariant id: {invariant_id}")
        seen.add(invariant_id)
        if not isinstance(selector, str) or SELECTOR_PATTERN.fullmatch(selector) is None:
            errors.append(f"invalid mandatory selector for {invariant_id}: {selector!r}")
            selector = str(selector or "")
        if not isinstance(order, int) or isinstance(order, bool) or order < 0:
            errors.append(f"invalid mandatory invariant order for {invariant_id}")
            order = 0
        if isolation not in {"shared", "isolated"}:
            errors.append(f"invalid mandatory invariant isolation for {invariant_id}")
            isolation = "shared"
        invariants.append(MandatoryInvariant(invariant_id, selector, order, str(isolation)))
    return tuple(sorted(invariants, key=lambda item: (item.order, item.id)))


def _parse_suites(raw: Any, domains: frozenset[str], errors: list[str]) -> tuple[ValidationSuite, ...]:
    rows = _sequence(raw, field="suites", errors=errors)
    suites: list[ValidationSuite] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"suites[{index}] must be an object")
            continue
        suite_id = row.get("id")
        path = row.get("path")
        classification = row.get("classification")
        if not isinstance(suite_id, str) or not suite_id:
            errors.append(f"suites[{index}].id must be a non-empty string")
            continue
        if suite_id in seen_ids:
            errors.append(f"duplicate suite id: {suite_id}")
        seen_ids.add(suite_id)
        if not isinstance(path, str) or not _valid_relative_glob(path):
            errors.append(f"invalid suite path for {suite_id}: {path!r}")
            path = str(path or "")
        if path in seen_paths:
            errors.append(f"duplicate suite path: {path}")
        seen_paths.add(path)
        if classification not in CLASSIFICATIONS:
            errors.append(f"invalid classification for {suite_id}: {classification!r}")
            classification = str(classification or "")
        tiers = _text_sequence(row.get("tiers", []), field=f"{suite_id}.tiers", errors=errors)
        suite_domains = _text_sequence(
            row.get("domains", []), field=f"{suite_id}.domains", errors=errors
        )
        for domain in suite_domains:
            if domain not in domains:
                errors.append(f"unknown domain for {suite_id}: {domain}")
        safety = row.get("parallel_safety")
        if safety not in SAFETY_CLASSES:
            errors.append(f"invalid parallel_safety for {suite_id}: {safety!r}")
            safety = str(safety or "")
        weight = row.get("resource_weight", 1)
        if not isinstance(weight, int) or isinstance(weight, bool) or weight < 1:
            errors.append(f"invalid resource_weight for {suite_id}: {weight!r}")
            weight = 1
        source_globs = _text_sequence(
            row.get("source_globs", []), field=f"{suite_id}.source_globs", errors=errors
        )
        test_globs = _text_sequence(
            row.get("test_globs", []), field=f"{suite_id}.test_globs", errors=errors
        )
        for pattern in source_globs:
            if not _valid_relative_glob(pattern):
                errors.append(f"invalid source glob for {suite_id}: {pattern}")
        for pattern in test_globs:
            if not _valid_relative_glob(pattern):
                errors.append(f"invalid test glob for {suite_id}: {pattern}")
        neighbors = _text_sequence(
            row.get("neighbors", []), field=f"{suite_id}.neighbors", errors=errors
        )
        absence_reason = row.get("absence_reason")
        if classification in {"intentionally_absent", "intentionally_excluded"}:
            if not isinstance(absence_reason, str) or not absence_reason.strip():
                errors.append(f"absence_reason required for {suite_id}")
        if classification == "live" and "full" in tiers:
            errors.append(f"live suite {suite_id} cannot be in offline full tier")
        live_provider = row.get("live_provider")
        if classification == "live" and (not isinstance(live_provider, str) or not live_provider):
            errors.append(f"live_provider required for live suite {suite_id}")
        superseded_by = _text_sequence(
            row.get("superseded_by", []), field=f"{suite_id}.superseded_by", errors=errors
        )
        suites.append(
            ValidationSuite(
                id=suite_id,
                path=path,
                classification=classification,
                tiers=tiers,
                domains=suite_domains,
                parallel_safety=safety,
                resource_weight=weight,
                source_globs=source_globs,
                test_globs=test_globs,
                neighbors=neighbors,
                live_provider=live_provider if isinstance(live_provider, str) else None,
                deep_live=bool(row.get("deep_live", False)),
                absence_reason=absence_reason if isinstance(absence_reason, str) else None,
                superseded_by=superseded_by,
            )
        )
    known_ids = {suite.id for suite in suites}
    for suite in suites:
        for neighbor in suite.neighbors:
            if neighbor not in known_ids:
                errors.append(f"unknown neighbor for {suite.id}: {neighbor}")
    return tuple(suites)


def _validate_inventory(
    suites: tuple[ValidationSuite, ...], repository_root: Path, errors: list[str]
) -> None:
    tests_root = repository_root / "tests"
    owned = {suite.path for suite in suites if suite.classification != "intentionally_absent"}
    if tests_root.is_dir():
        for directory in sorted(tests_root.iterdir(), key=lambda item: item.name):
            if not directory.is_dir() or directory.name == "fixtures":
                continue
            if not any(directory.glob("test_*.py")):
                continue
            relative = directory.relative_to(repository_root).as_posix()
            if relative not in owned:
                errors.append(f"unclassified test directory: {relative}")
    for suite in suites:
        target = repository_root / PurePosixPath(suite.path)
        if suite.classification == "intentionally_absent":
            if target.exists():
                errors.append(f"intentionally absent suite path exists: {suite.path}")
            continue
        if not target.is_dir():
            errors.append(f"configured suite path does not exist: {suite.path}")


def _validate_invariant_targets(
    invariants: tuple[MandatoryInvariant, ...], repository_root: Path, errors: list[str]
) -> None:
    """Statically verify selector files/classes/methods without importing tests."""

    parsed_files: dict[Path, ast.Module | None] = {}
    for invariant in invariants:
        match = SELECTOR_PATTERN.fullmatch(invariant.selector)
        if match is None:
            continue
        relative_path, class_name, method_name = match.groups()
        path = (repository_root / PurePosixPath(relative_path)).resolve()
        try:
            path.relative_to(repository_root)
        except ValueError:
            errors.append(f"mandatory selector path escapes repository: {invariant.selector}")
            continue
        if path not in parsed_files:
            try:
                parsed_files[path] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, UnicodeError, SyntaxError):
                parsed_files[path] = None
        module = parsed_files[path]
        found = False
        if module is not None:
            for node in module.body:
                if not isinstance(node, ast.ClassDef) or node.name != class_name:
                    continue
                found = any(
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child.name == method_name
                    for child in node.body
                )
                if found:
                    break
        if not found:
            errors.append(f"mandatory selector target not found: {invariant.selector}")


def load_manifest(path: Path, *, repository_root: Path | None = None) -> ValidationManifest:
    """Load and fully validate *path*, returning immutable typed records."""

    manifest_path = Path(path)
    root = Path(repository_root) if repository_root is not None else manifest_path.parents[1]
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestValidationError([f"cannot read validation manifest: {exc}"]) from exc
    if not isinstance(payload, dict):
        raise ManifestValidationError(["manifest root must be an object"])
    errors: list[str] = []
    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version:
        errors.append("schema_version must be a non-empty string")
        schema_version = ""
    domain_values = _text_sequence(payload.get("domains", []), field="domains", errors=errors)
    if len(set(domain_values)) != len(domain_values):
        errors.append("duplicate domain")
    domains = frozenset(domain_values)
    full_invalidators = _text_sequence(
        payload.get("full_invalidators", []), field="full_invalidators", errors=errors
    )
    for pattern in full_invalidators:
        if not _valid_relative_glob(pattern):
            errors.append(f"invalid full invalidator glob: {pattern}")
    invariants = _parse_invariants(payload.get("mandatory_invariants", []), errors)
    suites = _parse_suites(payload.get("suites", []), domains, errors)
    _validate_invariant_targets(invariants, root.resolve(), errors)
    _validate_inventory(suites, root.resolve(), errors)
    if errors:
        raise ManifestValidationError(errors)
    return ValidationManifest(
        schema_version=schema_version,
        domains=domain_values,
        full_invalidators=full_invalidators,
        mandatory_invariants=invariants,
        suites=suites,
    )


__all__ = [
    "CLASSIFICATIONS",
    "SAFETY_CLASSES",
    "ManifestValidationError",
    "MandatoryInvariant",
    "ValidationManifest",
    "ValidationSuite",
    "load_manifest",
]
