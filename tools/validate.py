"""Manifest-driven validation selection and orchestration."""

from __future__ import annotations

import argparse
import concurrent.futures
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:  # Supports both ``python -m tools.validate`` and ``python tools/validate.py``.
    from tools.validation_manifest import (
        ManifestValidationError,
        ValidationManifest,
        ValidationSuite,
        load_manifest,
    )
except ModuleNotFoundError:  # pragma: no cover - exercised by CLI integration tests.
    from validation_manifest import (  # type: ignore[no-redef]
        ManifestValidationError,
        ValidationManifest,
        ValidationSuite,
        load_manifest,
    )


EXECUTABLE_SUFFIXES = frozenset(
    {".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml"}
)
EXECUTABLE_ROOTS = frozenset({"src", "tools", "ui", "manifests"})
SECRET_FILE_NAMES = frozenset({"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"})
SECRET_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"})
CORE_DIAGNOSTIC_IDS = ("validation", "phase0", "contracts", "runtime", "providers")
DEFAULT_WORKERS = 2
LIVE_GATES: dict[str, tuple[str, ...]] = {
    "cboe": ("IMP_CBOE_REGSHO_LIVE",),
    "cboe_options": ("IMP_CBOE_OPTIONS_LIVE",),
    "cftc": ("RUN_LIVE_CFTC",),
    "eia": ("IMP_EIA_LIVE",),
    "finra": ("IMP_FINRA_LIVE", "IMP_FINRA_OTC_THRESHOLD_LIVE"),
    "fred": ("IMP_FRED_LIVE",),
    "moomoo": ("IMP_MOOMOO_LIVE",),
    "nasdaq": ("IMP_NASDAQ_REGSHO_LIVE",),
    "nyse": ("IMP_NYSE_REGSHO_LIVE",),
    "sec": ("SEC_LIVE_TESTS",),
    "sec_ftd": ("IMP_SEC_FTD_LIVE",),
    "weather": ("IMP_WEATHER_LIVE",),
}
ALL_LIVE_GATES = frozenset(gate for gates in LIVE_GATES.values() for gate in gates)


class ValidationSelectionError(ValueError):
    """Raised when requested validation scope is invalid or unsafe."""


@dataclass(frozen=True, slots=True)
class ValidationSelection:
    mode: str
    changed_files: tuple[str, ...] = ()
    selected_suite_ids: tuple[str, ...] = ()
    selection_reasons: dict[str, tuple[str, ...]] | None = None
    mandatory_selectors: tuple[str, ...] = ()
    omitted_domains: tuple[str, ...] = ()
    cheap_checks: tuple[str, ...] = ()
    full_suite_required: bool = False
    global_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.selection_reasons is None:
            object.__setattr__(self, "selection_reasons", {})


def normalize_repository_path(value: str) -> str:
    """Return a canonical repository-relative POSIX path or fail closed."""

    normalized = value.replace("\\", "/")
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise ValidationSelectionError(f"path is not repository-relative: {value!r}")
    path = PurePosixPath(normalized)
    if ".." in path.parts or path.parts[0] in {"", "."}:
        raise ValidationSelectionError(f"path traversal is not allowed: {value!r}")
    return path.as_posix()


def _matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _ordered_suite_ids(manifest: ValidationManifest, selected: set[str]) -> tuple[str, ...]:
    return tuple(suite.id for suite in manifest.suites if suite.id in selected)


def _mandatory_selectors(manifest: ValidationManifest) -> tuple[str, ...]:
    return tuple(invariant.selector for invariant in manifest.mandatory_invariants)


def _offline_core_diagnostics(manifest: ValidationManifest) -> tuple[str, ...]:
    offline_by_id = {
        suite.id: suite
        for suite in manifest.suites
        if suite.classification == "offline" and "full" in suite.tiers
    }
    preferred = tuple(suite_id for suite_id in CORE_DIAGNOSTIC_IDS if suite_id in offline_by_id)
    if preferred:
        return preferred
    return tuple(
        suite.id
        for suite in manifest.suites
        if suite.classification == "offline" and "core" in suite.domains and "full" in suite.tiers
    )


def _is_documentation(path: str) -> bool:
    return path.startswith("docs/") or path in {"README.md", "CONTRIBUTING.md", "AGENTS.md"}


def _is_evidence(path: str) -> bool:
    return path.startswith("evidence/") or path.startswith("reports/")


def _is_executable_or_config(path: str) -> bool:
    pure = PurePosixPath(path)
    if pure.parts and pure.parts[0] in EXECUTABLE_ROOTS and pure.suffix.lower() in EXECUTABLE_SUFFIXES:
        return True
    return path in {"phase0-dependency-lock.json", ".env.example"}


def select_changed(
    manifest: ValidationManifest, changed_paths: Iterable[str]
) -> ValidationSelection:
    paths = tuple(sorted({normalize_repository_path(path) for path in changed_paths}))
    if paths and all(_is_documentation(path) for path in paths):
        return ValidationSelection(
            mode="changed", changed_files=paths, cheap_checks=("documentation",)
        )
    if paths and all(_is_evidence(path) for path in paths):
        return ValidationSelection(
            mode="changed",
            changed_files=paths,
            cheap_checks=("evidence-json", "secret-redaction"),
        )

    selected: set[str] = set()
    reasons: dict[str, list[str]] = {}
    direct_source_suites: set[str] = set()
    global_reasons: list[str] = []
    full_required = False

    def add(suite_id: str, reason: str) -> None:
        selected.add(suite_id)
        bucket = reasons.setdefault(suite_id, [])
        if reason not in bucket:
            bucket.append(reason)

    for path in paths:
        if _matches(path, manifest.full_invalidators):
            full_required = True
            if "FULL_INVALIDATOR" not in global_reasons:
                global_reasons.append("FULL_INVALIDATOR")
        matched = False
        test_only = path.startswith("tests/")
        for suite in manifest.suites:
            if suite.classification not in {"offline", "extended"}:
                continue
            if _matches(path, suite.test_globs):
                add(suite.id, f"{path}: direct test ownership")
                matched = True
            if _matches(path, suite.source_globs):
                add(suite.id, f"{path}: direct source ownership")
                direct_source_suites.add(suite.id)
                matched = True
        if not matched and _is_executable_or_config(path):
            full_required = True
            if "UNKNOWN_EXECUTABLE_PATH" not in global_reasons:
                global_reasons.append("UNKNOWN_EXECUTABLE_PATH")
        if test_only:
            continue

    for suite_id in tuple(direct_source_suites):
        suite = manifest.suite_by_id(suite_id)
        for neighbor_id in suite.neighbors:
            neighbor = manifest.suite_by_id(neighbor_id)
            if neighbor.classification == "offline":
                add(neighbor_id, f"neighbor of {suite_id}")

    if full_required:
        for suite_id in _offline_core_diagnostics(manifest):
            add(suite_id, "broad core diagnostic for required full checkpoint")

    check_values: list[str] = []
    if any(_is_documentation(path) for path in paths):
        check_values.append("documentation")
    if any(_is_evidence(path) for path in paths):
        check_values.extend(("evidence-json", "secret-redaction"))
    domains_selected = {
        domain
        for suite in manifest.suites
        if suite.id in selected
        for domain in suite.domains
    }
    omitted = tuple(domain for domain in manifest.domains if domain not in domains_selected)
    return ValidationSelection(
        mode="changed",
        changed_files=paths,
        selected_suite_ids=_ordered_suite_ids(manifest, selected),
        selection_reasons={key: tuple(value) for key, value in reasons.items()},
        mandatory_selectors=_mandatory_selectors(manifest) if paths else (),
        omitted_domains=omitted,
        cheap_checks=tuple(dict.fromkeys(check_values)),
        full_suite_required=full_required,
        global_reasons=tuple(global_reasons),
    )


def select_domain(manifest: ValidationManifest, domain: str) -> ValidationSelection:
    if domain not in manifest.domains:
        raise ValidationSelectionError(f"unknown validation domain: {domain}")
    selected = tuple(
        suite.id
        for suite in manifest.suites
        if suite.classification == "offline" and "full" in suite.tiers and domain in suite.domains
    )
    return ValidationSelection(mode="domain", selected_suite_ids=selected)


def select_full(manifest: ValidationManifest) -> ValidationSelection:
    selected = tuple(
        suite.id
        for suite in manifest.suites
        if suite.classification == "offline" and "full" in suite.tiers
    )
    return ValidationSelection(mode="full", selected_suite_ids=selected)


def select_live(manifest: ValidationManifest, provider: str, *, deep: bool = False) -> ValidationSelection:
    del deep  # Current providers have no separately owned deep suite directories.
    selected = tuple(
        suite.id
        for suite in manifest.suites
        if suite.classification == "live" and suite.live_provider == provider
    )
    if not selected:
        raise ValidationSelectionError(f"unknown or unconfigured live provider: {provider}")
    return ValidationSelection(mode="live", selected_suite_ids=selected)


def select_extended(manifest: ValidationManifest) -> ValidationSelection:
    selected = tuple(
        suite.id for suite in manifest.suites if suite.classification == "extended"
    )
    return ValidationSelection(mode="extended", selected_suite_ids=selected)


def _git_names(repository_root: Path, arguments: list[str]) -> tuple[str, ...]:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValidationSelectionError(f"Git path discovery failed: {message}")
    return tuple(
        normalize_repository_path(value.decode("utf-8", errors="surrogateescape"))
        for value in completed.stdout.split(b"\0")
        if value
    )


def changed_paths_from_git(repository_root: Path) -> tuple[str, ...]:
    """Return tracked modifications/deletions plus nonignored untracked files."""

    root = Path(repository_root).resolve()
    unstaged = _git_names(root, ["diff", "--name-only", "-z"])
    staged = _git_names(root, ["diff", "--cached", "--name-only", "-z"])
    untracked = _git_names(root, ["ls-files", "--others", "--exclude-standard", "-z"])
    return tuple(sorted(set(unstaged) | set(staged) | set(untracked)))


def _is_secret_path(path: str) -> bool:
    leaf = PurePosixPath(path).name.lower()
    return (
        leaf.startswith(".env")
        or leaf in SECRET_FILE_NAMES
        or PurePosixPath(leaf).suffix.lower() in SECRET_SUFFIXES
        or re.match(r"^(credentials?|secrets?|tokens?)(\.|$)", leaf) is not None
    )


def _current_inventory(repository_root: Path, *, exclude: frozenset[str] = frozenset()) -> list[dict[str, str]]:
    root = Path(repository_root).resolve()
    tracked = _git_names(root, ["ls-files", "-z"])
    untracked = _git_names(root, ["ls-files", "--others", "--exclude-standard", "-z"])
    rows: list[dict[str, str]] = []
    for classification, paths in (("tracked", tracked), ("untracked", untracked)):
        for path in paths:
            if path in exclude or _is_secret_path(path):
                continue
            target = root / PurePosixPath(path)
            if not target.is_file():
                continue
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            rows.append({"path": path, "sha256": digest, "classification": classification})
    return sorted(rows, key=lambda row: row["path"])


def create_baseline_snapshot(repository_root: Path) -> dict[str, Any]:
    return {"schema_version": "1.0", "files": _current_inventory(Path(repository_root))}


def changed_paths_from_baseline(repository_root: Path, baseline_path: Path) -> tuple[str, ...]:
    root = Path(repository_root).resolve()
    resolved_baseline = Path(baseline_path).resolve()
    try:
        baseline_relative = resolved_baseline.relative_to(root).as_posix()
    except ValueError:
        baseline_relative = ""
    try:
        payload = json.loads(resolved_baseline.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationSelectionError(f"cannot read baseline snapshot: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
        raise ValidationSelectionError("baseline snapshot must contain a files array")
    before: dict[str, tuple[str, str]] = {}
    for row in payload["files"]:
        if not isinstance(row, dict):
            raise ValidationSelectionError("baseline file entries must be objects")
        path = normalize_repository_path(str(row.get("path", "")))
        digest = row.get("sha256")
        classification = row.get("classification")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-fA-F]{64}", digest) is None:
            raise ValidationSelectionError(f"invalid baseline hash for {path}")
        if classification not in {"tracked", "untracked"}:
            raise ValidationSelectionError(f"invalid baseline classification for {path}")
        before[path] = (digest.lower(), str(classification))
    excluded = frozenset({baseline_relative}) if baseline_relative else frozenset()
    after = {
        row["path"]: (row["sha256"], row["classification"])
        for row in _current_inventory(root, exclude=excluded)
    }
    return tuple(
        sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))
    )


@dataclass(frozen=True, slots=True)
class WorkerJob:
    id: str
    suite_id: str
    suite_path: str | None
    selectors: tuple[str, ...]
    safety: str
    resource_weight: int


class WorkerProcessRegistry:
    """Tracks only child processes spawned by one validation invocation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: set[subprocess.Popen[str]] = set()

    def add(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._processes.add(process)

    def discard(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._processes.discard(process)

    def terminate_all(self) -> None:
        with self._lock:
            processes = tuple(self._processes)
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def _sanitize_worker_text(value: str) -> str:
    sanitized = re.sub(
        r"(?i)(api[_-]?key|token|secret|password)=([^\s&]+)",
        r"\1=<redacted>",
        value,
    )
    return re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)([^\s]+)",
        r"\1<redacted>",
        sanitized,
    )


def _error_worker_result(suite_id: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "suite_id": suite_id,
        "selectors": [],
        "status": "error",
        "tests_run": 0,
        "passes": 0,
        "skips": 0,
        "failures": 0,
        "errors": 1,
        "expected_failures": 0,
        "unexpected_successes": 0,
        "discovery_seconds": 0.0,
        "wall_seconds": 0.0,
        "per_test_durations": [],
        "slowest_tests": [],
        "failure_details": [],
        "error_details": [],
        "worker_error": _sanitize_worker_text(message),
    }


def _child_environment(repository_root: Path, live_provider: str | None) -> dict[str, str]:
    environment = dict(os.environ)
    for gate in ALL_LIVE_GATES:
        environment.pop(gate, None)
    if live_provider is not None:
        gates = LIVE_GATES.get(live_provider)
        if gates is None:
            raise ValidationSelectionError(f"no child gate mapping for live provider: {live_provider}")
        for gate in gates:
            environment[gate] = "1"
    roots = [str(repository_root / "src"), str(repository_root)]
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(roots + ([existing] if existing else []))
    return environment


def run_worker_process(
    *,
    repository_root: Path,
    suite_id: str,
    suite_path: str | None = None,
    selectors: tuple[str, ...] = (),
    live_provider: str | None = None,
    profile_fixtures: bool = False,
    worker_path: Path | None = None,
    registry: WorkerProcessRegistry | None = None,
) -> dict[str, Any]:
    """Run one worker process and treat malformed/crashed output as an error."""

    root = Path(repository_root).resolve()
    worker = Path(worker_path) if worker_path is not None else Path(__file__).with_name(
        "validation_worker.py"
    )
    command = [
        sys.executable,
        str(worker),
        "--repository-root",
        str(root),
        "--suite-id",
        suite_id,
    ]
    if suite_path is not None:
        command.extend(("--suite-path", suite_path))
    for selector in selectors:
        command.extend(("--selector", selector))
    if profile_fixtures:
        command.append("--profile-fixtures")
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=str(root),
        env=_child_environment(root, live_provider),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if registry is not None:
        registry.add(process)
    try:
        stdout, stderr = process.communicate()
    finally:
        if registry is not None:
            registry.discard(process)
    elapsed = time.perf_counter() - started
    stripped = stdout.strip()
    if not stripped:
        return _error_worker_result(
            suite_id,
            f"worker exited {process.returncode} without JSON"
            + (f": {_sanitize_worker_text(stderr.strip())}" if stderr.strip() else ""),
        )
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        return _error_worker_result(
            suite_id,
            f"malformed worker JSON (exit {process.returncode}): {exc}",
        )
    if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
        return _error_worker_result(suite_id, "malformed worker JSON: root/status invalid")
    if process.returncode not in {0, 1}:
        return _error_worker_result(
            suite_id,
            f"worker exited {process.returncode}: {_sanitize_worker_text(stderr.strip())}",
        )
    payload["process_wall_seconds"] = elapsed
    if stderr.strip():
        payload["worker_stderr"] = _sanitize_worker_text(stderr.strip())
    return payload


def _mandatory_jobs(
    manifest: ValidationManifest, selectors: tuple[str, ...]
) -> list[WorkerJob]:
    wanted = set(selectors)
    isolated = [
        invariant
        for invariant in manifest.mandatory_invariants
        if invariant.selector in wanted and invariant.isolation == "isolated"
    ]
    shared = tuple(
        invariant.selector
        for invariant in manifest.mandatory_invariants
        if invariant.selector in wanted and invariant.isolation == "shared"
    )
    jobs = [
        WorkerJob(
            id=f"mandatory-isolated-{invariant.id}",
            suite_id=f"mandatory-isolated-{invariant.id}",
            suite_path=None,
            selectors=(invariant.selector,),
            safety="SERIAL_REQUIRED",
            resource_weight=1,
        )
        for invariant in isolated
    ]
    if shared:
        jobs.append(
            WorkerJob(
                id="mandatory-shared",
                suite_id="mandatory-shared",
                suite_path=None,
                selectors=shared,
                safety="SERIAL_REQUIRED",
                resource_weight=1,
            )
        )
    return jobs


def _suite_jobs(manifest: ValidationManifest, selection: ValidationSelection) -> list[WorkerJob]:
    selected = set(selection.selected_suite_ids)
    return [
        WorkerJob(
            id=suite.id,
            suite_id=suite.id,
            suite_path=suite.path,
            selectors=(),
            safety=suite.parallel_safety,
            resource_weight=suite.resource_weight,
        )
        for suite in manifest.suites
        if suite.id in selected
    ]


def _run_parallel_jobs(
    jobs: list[WorkerJob],
    *,
    concurrency: int,
    run_job: Any,
    fail_fast: bool,
) -> list[tuple[WorkerJob, dict[str, Any]]]:
    if not jobs:
        return []
    results: list[tuple[WorkerJob, dict[str, Any]]] = []
    iterator = iter(jobs)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        pending: dict[concurrent.futures.Future[dict[str, Any]], WorkerJob] = {}
        for _ in range(max(1, concurrency)):
            try:
                job = next(iterator)
            except StopIteration:
                break
            pending[executor.submit(run_job, job)] = job
        stop = False
        while pending:
            done, _ = concurrent.futures.wait(
                pending, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for future in done:
                job = pending.pop(future)
                payload = future.result()
                results.append((job, payload))
                if fail_fast and payload.get("status") != "passed":
                    stop = True
            while not stop and len(pending) < max(1, concurrency):
                try:
                    job = next(iterator)
                except StopIteration:
                    break
                pending[executor.submit(run_job, job)] = job
    order = {job.id: index for index, job in enumerate(jobs)}
    return sorted(results, key=lambda row: order[row[0].id])


def _run_cheap_checks(repository_root: Path, selection: ValidationSelection) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for check in selection.cheap_checks:
        status = "passed"
        detail = ""
        try:
            if check == "documentation":
                for relative in selection.changed_files:
                    if _is_documentation(relative):
                        path = repository_root / relative
                        if path.exists() and path.is_file():
                            path.read_text(encoding="utf-8")
            elif check == "evidence-json":
                for relative in selection.changed_files:
                    path = repository_root / relative
                    if _is_evidence(relative) and path.suffix.lower() == ".json" and path.exists():
                        json.loads(path.read_text(encoding="utf-8"))
            elif check == "secret-redaction":
                leak = re.compile(
                    r"(?i)(api[_-]?key|token|password|authorization)"
                    r"\s*[:=]\s*[\"']?(?!<redacted>|none|null)[A-Za-z0-9_\-]{12,}"
                )
                for relative in selection.changed_files:
                    path = repository_root / relative
                    if _is_evidence(relative) and path.exists() and path.is_file():
                        if leak.search(path.read_text(encoding="utf-8", errors="replace")):
                            raise ValueError(f"possible unredacted secret in {relative}")
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            status = "failed"
            detail = _sanitize_worker_text(str(exc))
        results.append({"check": check, "status": status, "detail": detail})
    return results


def execute_selection(
    *,
    repository_root: Path,
    manifest: ValidationManifest,
    selection: ValidationSelection,
    workers: int = DEFAULT_WORKERS,
    fail_fast: bool = False,
    live_provider: str | None = None,
    profile_fixtures: bool = False,
) -> dict[str, Any]:
    """Execute a validated selection with suite-process isolation."""

    if workers < 1:
        raise ValidationSelectionError("workers must be at least 1")
    root = Path(repository_root).resolve()
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    registry = WorkerProcessRegistry()
    mandatory_jobs = _mandatory_jobs(manifest, selection.mandatory_selectors)
    suite_jobs = _suite_jobs(manifest, selection)
    all_order = {job.id: index for index, job in enumerate(mandatory_jobs + suite_jobs)}
    executed: list[tuple[WorkerJob, dict[str, Any]]] = []

    def run_job(job: WorkerJob) -> dict[str, Any]:
        return run_worker_process(
            repository_root=root,
            suite_id=job.suite_id,
            suite_path=job.suite_path,
            selectors=job.selectors,
            live_provider=live_provider if job.safety == "LIVE_EXCLUSIVE" else None,
            profile_fixtures=profile_fixtures,
            registry=registry,
        )

    stopped = False
    interrupted = False
    try:
        for job in mandatory_jobs:
            payload = run_job(job)
            executed.append((job, payload))
            if fail_fast and payload.get("status") != "passed":
                stopped = True
                break
        groups = (
            [
                job
                for job in suite_jobs
                if job.safety in {"SERIAL_REQUIRED", "GLOBAL_STATE_MUTATION", "LIVE_EXCLUSIVE"}
            ],
            [job for job in suite_jobs if job.safety == "PARALLEL_SAFE"],
            [job for job in suite_jobs if job.safety == "RESOURCE_HEAVY"],
        )
        if not stopped:
            for job in groups[0]:
                payload = run_job(job)
                executed.append((job, payload))
                if fail_fast and payload.get("status") != "passed":
                    stopped = True
                    break
        if not stopped:
            parallel_results = _run_parallel_jobs(
                groups[1], concurrency=workers, run_job=run_job, fail_fast=fail_fast
            )
            executed.extend(parallel_results)
            stopped = fail_fast and any(
                payload.get("status") != "passed" for _, payload in parallel_results
            )
        if not stopped:
            heavy_results = _run_parallel_jobs(
                groups[2], concurrency=min(2, workers), run_job=run_job, fail_fast=fail_fast
            )
            executed.extend(heavy_results)
            stopped = fail_fast and any(
                payload.get("status") != "passed" for _, payload in heavy_results
            )
    except KeyboardInterrupt:
        interrupted = True
        registry.terminate_all()

    executed.sort(key=lambda row: all_order[row[0].id])
    worker_results = [payload for _, payload in executed]
    suite_results = [
        payload for job, payload in executed if job.id in set(selection.selected_suite_ids)
    ]
    executed_suite_ids = {row.get("suite_id") for row in suite_results}
    not_run = [
        suite_id for suite_id in selection.selected_suite_ids if suite_id not in executed_suite_ids
    ]
    cheap_results = _run_cheap_checks(root, selection)
    statuses = [str(row.get("status")) for row in worker_results]
    if interrupted:
        status = "interrupted"
    elif "error" in statuses:
        status = "error"
    elif any(value != "passed" for value in statuses) or any(
        row["status"] != "passed" for row in cheap_results
    ):
        status = "failed"
    else:
        status = "passed"
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "mode": selection.mode,
        "started_at": started_at,
        "status": status,
        "changed_files": list(selection.changed_files),
        "selected_suites": list(selection.selected_suite_ids),
        "selection_reasons": {
            key: list(value) for key, value in (selection.selection_reasons or {}).items()
        },
        "omitted_domains": list(selection.omitted_domains),
        "mandatory_invariants": list(selection.mandatory_selectors),
        "full_suite_required": selection.full_suite_required,
        "global_reasons": list(selection.global_reasons),
        "workers": workers,
        "resource_heavy_workers": min(2, workers),
        "process_launches": len(worker_results),
        "tests_run": sum(int(row.get("tests_run", 0)) for row in worker_results),
        "passes": sum(int(row.get("passes", 0)) for row in worker_results),
        "skips": sum(int(row.get("skips", 0)) for row in worker_results),
        "failures": sum(int(row.get("failures", 0)) for row in worker_results),
        "errors": sum(int(row.get("errors", 0)) for row in worker_results),
        "expected_failures": sum(
            int(row.get("expected_failures", 0)) for row in worker_results
        ),
        "unexpected_successes": sum(
            int(row.get("unexpected_successes", 0)) for row in worker_results
        ),
        "discovery_seconds": sum(
            float(row.get("discovery_seconds", 0.0)) for row in worker_results
        ),
        "worker_results": worker_results,
        "suite_results": suite_results,
        "cheap_check_results": cheap_results,
        "not_run_suites": not_run,
        "interrupted": interrupted,
        "wall_seconds": time.perf_counter() - started,
    }
    return result


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Atomically replace a JSON result without leaving partial output."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("fast", "changed", "domain", "full", "live", "extended", "benchmark")
    )
    parser.add_argument("target", nargs="?")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--profile-fixtures", action="store_true", help=argparse.SUPPRESS)
    return parser


def _selection_for_arguments(
    arguments: argparse.Namespace,
    manifest: ValidationManifest,
    repository_root: Path,
) -> ValidationSelection:
    if arguments.mode == "fast":
        return ValidationSelection(
            mode="fast", mandatory_selectors=_mandatory_selectors(manifest)
        )
    if arguments.mode == "changed":
        paths = (
            changed_paths_from_baseline(repository_root, arguments.baseline)
            if arguments.baseline is not None
            else changed_paths_from_git(repository_root)
        )
        return select_changed(manifest, paths)
    if arguments.mode == "domain":
        if not arguments.target:
            raise ValidationSelectionError("domain mode requires a domain name")
        return select_domain(manifest, arguments.target)
    if arguments.mode == "full":
        return select_full(manifest)
    if arguments.mode == "live":
        if not arguments.target:
            raise ValidationSelectionError("live mode requires a provider name")
        return select_live(manifest, arguments.target, deep=arguments.deep)
    if arguments.mode == "extended":
        return select_extended(manifest)
    raise ValidationSelectionError("benchmark mode is not yet delegated")


def _print_explanation(selection: ValidationSelection) -> None:
    for path in selection.changed_files:
        print(path)
    for suite_id in selection.selected_suite_ids:
        print(f"  -> {suite_id}")
        for reason in (selection.selection_reasons or {}).get(suite_id, ()):
            print(f"     {reason}")
    if selection.global_reasons:
        print("reasons: " + ", ".join(selection.global_reasons))
    print(f"full_suite_required={str(selection.full_suite_required).lower()}")
    if selection.omitted_domains:
        print("omitted_domains=" + ",".join(selection.omitted_domains))


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    repository_root = Path(__file__).resolve().parents[1]
    if arguments.mode == "benchmark":
        try:
            try:
                from tools.benchmark import run_benchmarks
            except ModuleNotFoundError:  # pragma: no cover - direct script execution path.
                from benchmark import run_benchmarks  # type: ignore[no-redef]

            report = run_benchmarks(repository_root)
        except ValueError as exc:
            print(f"benchmark configuration error: {exc}", file=sys.stderr)
            return 2
        if arguments.json_path is not None:
            write_json_atomic(arguments.json_path, report)
        if arguments.verbose:
            print(json.dumps(report, sort_keys=True, indent=2))
        print("PASSED benchmark: informational timings recorded; no timing gate applied")
        return 0
    manifest_path = arguments.manifest or repository_root / "tools" / "validation_manifest.json"
    try:
        manifest = load_manifest(manifest_path, repository_root=repository_root)
        selection = _selection_for_arguments(arguments, manifest, repository_root)
        if arguments.explain:
            _print_explanation(selection)
        result = execute_selection(
            repository_root=repository_root,
            manifest=manifest,
            selection=selection,
            workers=arguments.workers,
            fail_fast=arguments.fail_fast,
            live_provider=arguments.target if arguments.mode == "live" else None,
            profile_fixtures=arguments.profile_fixtures,
        )
    except (ManifestValidationError, ValidationSelectionError) as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 2
    if arguments.json_path is not None:
        write_json_atomic(arguments.json_path, result)
    print(
        f"{result['status'].upper()} {result['mode']}: {result['tests_run']} tests, "
        f"{result['skips']} skipped, {result['failures']} failures, "
        f"{result['errors']} errors in {result['wall_seconds']:.3f}s"
    )
    if result["full_suite_required"]:
        print("full_suite_required=true")
    if arguments.verbose or result["status"] != "passed":
        for worker_result in result["worker_results"]:
            if worker_result.get("status") != "passed" or arguments.verbose:
                print(
                    f"{worker_result.get('suite_id')}: {worker_result.get('status')} "
                    f"({worker_result.get('tests_run', 0)} tests)"
                )
                if worker_result.get("worker_error"):
                    print(worker_result["worker_error"])
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ValidationSelection",
    "ValidationSelectionError",
    "execute_selection",
    "run_worker_process",
    "changed_paths_from_baseline",
    "changed_paths_from_git",
    "create_baseline_snapshot",
    "normalize_repository_path",
    "select_changed",
    "select_domain",
    "select_extended",
    "select_full",
    "select_live",
    "write_json_atomic",
]
