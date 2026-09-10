"""Typed, deterministic loader for the canonical validation manifest.

This module is intentionally stdlib-only and side-effect free: importing it
does not discover tests, import providers, inspect Git, or access the network.
"""

from __future__ import annotations

import ast
import fnmatch
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
# Canonical shared/common modules. Each entry either has an explicit
# ``shared_module_dependents`` mapping in the manifest (bounded dependent
# selection) or intentionally escalates to the core checkpoint.
SHARED_MODULE_PATHS = frozenset(
    {
        "src/market_platform_foundation/numeric.py",
        "src/market_platform_foundation/clock.py",
        "src/market_platform_foundation/errors.py",
        "src/market_platform_foundation/assertions.py",
        "src/market_platform_foundation/authority.py",
        "src/market_platform_foundation/evidence.py",
        "src/market_platform_foundation/market_sessions.py",
    }
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
    dependents: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SharedModuleDependency:
    path: str
    dependent_suites: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class EvidenceOnlyPattern:
    id: str
    category: str
    patterns: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class GovernanceOnlyPattern:
    id: str
    patterns: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class SubsystemPartition:
    id: str
    owner_suite: str
    source_globs: tuple[str, ...]
    dependent_suites: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class ValidationManifest:
    schema_version: str
    domains: tuple[str, ...]
    core_checkpoint_invalidators: tuple[str, ...]
    mandatory_invariants: tuple[MandatoryInvariant, ...]
    suites: tuple[ValidationSuite, ...]
    shared_module_dependents: tuple[SharedModuleDependency, ...] = ()
    evidence_only_patterns: tuple[EvidenceOnlyPattern, ...] = ()
    governance_only_patterns: tuple[GovernanceOnlyPattern, ...] = ()
    subsystem_partitions: tuple[SubsystemPartition, ...] = ()

    def suite_by_id(self, suite_id: str) -> ValidationSuite:
        for suite in self.suites:
            if suite.id == suite_id:
                return suite
        raise KeyError(suite_id)

    def match_evidence_only(self, path: str) -> EvidenceOnlyPattern | None:
        for entry in self.evidence_only_patterns:
            if any(_glob_match(path, pattern) for pattern in entry.patterns):
                return entry
        return None

    def match_governance_only(self, path: str) -> GovernanceOnlyPattern | None:
        for entry in self.governance_only_patterns:
            if any(_glob_match(path, pattern) for pattern in entry.patterns):
                return entry
        return None

    def match_subsystem_partition(self, path: str) -> SubsystemPartition | None:
        for partition in self.subsystem_partitions:
            if any(_glob_match(path, pattern) for pattern in partition.source_globs):
                return partition
        return None


def _glob_match(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern)


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
        dependents = _text_sequence(
            row.get("dependents", []), field=f"{suite_id}.dependents", errors=errors
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
                dependents=dependents,
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
        for dependent in suite.dependents:
            if dependent not in known_ids:
                errors.append(f"unknown dependent for {suite.id}: {dependent}")
    return tuple(suites)


def _parse_evidence_only_patterns(raw: Any, errors: list[str]) -> tuple[EvidenceOnlyPattern, ...]:
    rows = _sequence(raw, field="evidence_only_patterns", errors=errors)
    patterns: list[EvidenceOnlyPattern] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"evidence_only_patterns[{index}] must be an object")
            continue
        pattern_id = row.get("id")
        category = row.get("category")
        glob_values = _text_sequence(
            row.get("patterns", []),
            field=f"evidence_only_patterns[{index}].patterns",
            errors=errors,
        )
        reason = row.get("reason")
        if not isinstance(pattern_id, str) or not pattern_id:
            errors.append(f"evidence_only_patterns[{index}].id must be a non-empty string")
            pattern_id = ""
        if pattern_id in seen:
            errors.append(f"duplicate evidence_only_patterns id: {pattern_id}")
        seen.add(pattern_id)
        if not isinstance(category, str) or not category:
            errors.append(f"evidence_only_patterns[{index}].category is required")
            category = ""
        for pattern in glob_values:
            if not _valid_relative_glob(pattern):
                errors.append(f"invalid evidence_only pattern for {pattern_id}: {pattern}")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"evidence_only_patterns[{index}].reason is required")
            reason = ""
        patterns.append(
            EvidenceOnlyPattern(str(pattern_id), str(category), glob_values, str(reason))
        )
    return tuple(patterns)


def _parse_governance_only_patterns(raw: Any, errors: list[str]) -> tuple[GovernanceOnlyPattern, ...]:
    rows = _sequence(raw, field="governance_only_patterns", errors=errors)
    patterns: list[GovernanceOnlyPattern] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"governance_only_patterns[{index}] must be an object")
            continue
        pattern_id = row.get("id")
        glob_values = _text_sequence(
            row.get("patterns", []),
            field=f"governance_only_patterns[{index}].patterns",
            errors=errors,
        )
        reason = row.get("reason")
        if not isinstance(pattern_id, str) or not pattern_id:
            errors.append(f"governance_only_patterns[{index}].id must be a non-empty string")
            pattern_id = ""
        if pattern_id in seen:
            errors.append(f"duplicate governance_only_patterns id: {pattern_id}")
        seen.add(pattern_id)
        for pattern in glob_values:
            if not _valid_relative_glob(pattern):
                errors.append(f"invalid governance_only pattern for {pattern_id}: {pattern}")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"governance_only_patterns[{index}].reason is required")
            reason = ""
        patterns.append(GovernanceOnlyPattern(str(pattern_id), glob_values, str(reason)))
    return tuple(patterns)


def _parse_subsystem_partitions(
    raw: Any,
    suites: tuple[ValidationSuite, ...],
    errors: list[str],
) -> tuple[SubsystemPartition, ...]:
    rows = _sequence(raw, field="subsystem_partitions", errors=errors)
    known_ids = {suite.id for suite in suites}
    partitions: list[SubsystemPartition] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"subsystem_partitions[{index}] must be an object")
            continue
        partition_id = row.get("id")
        owner_suite = row.get("owner_suite")
        glob_values = _text_sequence(
            row.get("source_globs", []),
            field=f"subsystem_partitions[{index}].source_globs",
            errors=errors,
        )
        dependent_suites = _text_sequence(
            row.get("dependent_suites", []),
            field=f"subsystem_partitions[{index}].dependent_suites",
            errors=errors,
        )
        reason = row.get("reason")
        if not isinstance(partition_id, str) or not partition_id:
            errors.append(f"subsystem_partitions[{index}].id must be a non-empty string")
            partition_id = ""
        if partition_id in seen:
            errors.append(f"duplicate subsystem_partitions id: {partition_id}")
        seen.add(partition_id)
        if not isinstance(owner_suite, str) or owner_suite not in known_ids:
            errors.append(f"subsystem_partitions[{index}].owner_suite is invalid: {owner_suite!r}")
            owner_suite = str(owner_suite or "")
        for pattern in glob_values:
            if not _valid_relative_glob(pattern):
                errors.append(f"invalid subsystem partition glob for {partition_id}: {pattern}")
        for suite_id in dependent_suites:
            if suite_id not in known_ids:
                errors.append(f"unknown dependent suite for partition {partition_id}: {suite_id}")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"subsystem_partitions[{index}].reason is required")
            reason = ""
        if not glob_values:
            errors.append(f"subsystem_partitions[{index}] must declare source_globs")
        partitions.append(
            SubsystemPartition(
                str(partition_id),
                str(owner_suite),
                glob_values,
                dependent_suites,
                str(reason),
            )
        )
    return tuple(partitions)


def _parse_shared_module_dependents(
    payload: Any,
    suites: tuple[ValidationSuite, ...],
    errors: list[str],
) -> tuple[SharedModuleDependency, ...]:
    rows = _sequence(
        payload.get("shared_module_dependents", []),
        field="shared_module_dependents",
        errors=errors,
    )
    known_ids = {suite.id for suite in suites}
    known_shared = set(SHARED_MODULE_PATHS)
    dependents: list[SharedModuleDependency] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"shared_module_dependents[{index}] must be an object")
            continue
        path = row.get("path")
        if not isinstance(path, str) or not _valid_relative_glob(path):
            errors.append(f"shared_module_dependents[{index}].path must be a valid relative glob")
            path = str(path or "")
        if path and path in seen:
            errors.append(f"duplicate shared module dependent path: {path}")
        seen.add(path)
        if path and path not in known_shared:
            errors.append(f"shared module dependent path is not a canonical shared module: {path}")
        suite_values = _text_sequence(
            row.get("dependent_suites", []),
            field=f"shared_module_dependents[{index}].dependent_suites",
            errors=errors,
        )
        for suite_id in suite_values:
            if suite_id not in known_ids:
                errors.append(f"unknown dependent suite for {path}: {suite_id}")
        reason = row.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"shared_module_dependents[{index}].reason is required")
            reason = ""
        if not suite_values:
            errors.append(f"shared module {path} must declare dependent suites (or be omitted to escalate)")
        dependents.append(SharedModuleDependency(str(path), tuple(suite_values), str(reason)))
    return tuple(dependents)


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
    core_checkpoint_invalidators = _text_sequence(
        payload.get("core_checkpoint_invalidators", payload.get("full_invalidators", [])),
        field="core_checkpoint_invalidators",
        errors=errors,
    )
    for pattern in core_checkpoint_invalidators:
        if not _valid_relative_glob(pattern):
            errors.append(f"invalid core checkpoint invalidator glob: {pattern}")
    invariants = _parse_invariants(payload.get("mandatory_invariants", []), errors)
    suites = _parse_suites(payload.get("suites", []), domains, errors)
    shared_dependents = _parse_shared_module_dependents(payload, suites, errors)
    evidence_only = _parse_evidence_only_patterns(
        payload.get("evidence_only_patterns", []), errors
    )
    governance_only = _parse_governance_only_patterns(
        payload.get("governance_only_patterns", []), errors
    )
    subsystem_partitions = _parse_subsystem_partitions(
        payload.get("subsystem_partitions", []), suites, errors
    )
    _validate_invariant_targets(invariants, root.resolve(), errors)
    _validate_inventory(suites, root.resolve(), errors)
    if errors:
        raise ManifestValidationError(errors)
    return ValidationManifest(
        schema_version=schema_version,
        domains=domain_values,
        core_checkpoint_invalidators=core_checkpoint_invalidators,
        mandatory_invariants=invariants,
        suites=suites,
        shared_module_dependents=shared_dependents,
        evidence_only_patterns=evidence_only,
        governance_only_patterns=governance_only,
        subsystem_partitions=subsystem_partitions,
    )


__all__ = [
    "CLASSIFICATIONS",
    "SAFETY_CLASSES",
    "SHARED_MODULE_PATHS",
    "EvidenceOnlyPattern",
    "GovernanceOnlyPattern",
    "ManifestValidationError",
    "MandatoryInvariant",
    "SharedModuleDependency",
    "SubsystemPartition",
    "ValidationManifest",
    "ValidationSuite",
    "load_manifest",
]
