"""Isolated unittest worker that emits one structured JSON result."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import time
import traceback
import unittest
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Iterator


SELECTOR_PATTERN = re.compile(
    r"^(tests/[A-Za-z0-9_.\-/]+\.py)::([A-Za-z_][A-Za-z0-9_]*)::"
    r"([A-Za-z_][A-Za-z0-9_]*)$"
)
SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|secret|password)=([^\s&]+)"),
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)([^\s]+)"),
)


def sanitize_diagnostic(value: str) -> str:
    """Apply conservative redaction to worker-owned diagnostic strings."""

    sanitized = value
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1=<redacted>", sanitized)
    return sanitized


def _flatten(suite: unittest.TestSuite | unittest.TestCase) -> Iterator[unittest.TestCase]:
    if isinstance(suite, unittest.TestSuite):
        for child in suite:
            yield from _flatten(child)
    else:
        yield suite


def _selector_for_test(test: unittest.TestCase, repository_root: Path) -> str:
    explicit = getattr(test, "_validation_selector", None)
    if isinstance(explicit, str):
        return explicit
    module = sys.modules.get(test.__class__.__module__)
    module_file = Path(getattr(module, "__file__", "")) if module is not None else Path()
    try:
        relative = module_file.resolve().relative_to(repository_root).as_posix()
    except (OSError, ValueError):
        relative = module_file.as_posix() or test.__class__.__module__
    method = getattr(test, "_testMethodName", str(test))
    return f"{relative}::{test.__class__.__name__}::{method}"


class StructuredTestResult(unittest.TestResult):
    """TestResult with exact counts and per-test durations."""

    def __init__(self, repository_root: Path) -> None:
        super().__init__()
        self.repository_root = repository_root
        self.successes: list[unittest.TestCase] = []
        self._started: dict[int, float] = {}
        self.duration_rows: list[dict[str, Any]] = []

    def startTest(self, test: unittest.TestCase) -> None:  # noqa: N802 - unittest API
        self._started[id(test)] = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test: unittest.TestCase) -> None:  # noqa: N802 - unittest API
        started = self._started.pop(id(test), time.perf_counter())
        self.duration_rows.append(
            {
                "selector": _selector_for_test(test, self.repository_root),
                "seconds": max(0.0, time.perf_counter() - started),
            }
        )
        super().stopTest(test)

    def addSuccess(self, test: unittest.TestCase) -> None:  # noqa: N802 - unittest API
        self.successes.append(test)
        super().addSuccess(test)


class FixtureAudit:
    """Worker-local audit-hook collector for fixture reads."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root
        self.opens: Counter[str] = Counter()
        self.sizes: dict[str, int] = {}

    def install(self) -> None:
        sys.addaudithook(self._audit)

    def _audit(self, event: str, args: tuple[Any, ...]) -> None:
        if event != "open" or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        try:
            path = Path(args[0]).resolve()
        except (OSError, TypeError, ValueError):
            return
        lowered = tuple(part.lower() for part in path.parts)
        if not any(
            lowered[index : index + 2] == ("tests", "fixtures")
            for index in range(max(0, len(lowered) - 1))
        ):
            return
        try:
            display = path.relative_to(self.repository_root).as_posix()
        except ValueError:
            display = f"<external-fixture>/{path.name}"
        self.opens[display] += 1
        if display not in self.sizes:
            try:
                self.sizes[display] = path.stat().st_size
            except OSError:
                self.sizes[display] = 0

    def as_dict(self) -> dict[str, Any]:
        files = [
            {
                "path": path,
                "opens": count,
                "bytes": self.sizes.get(path, 0),
            }
            for path, count in sorted(self.opens.items(), key=lambda item: (-item[1], item[0]))
        ]
        return {
            "opens": sum(self.opens.values()),
            "estimated_bytes": sum(row["opens"] * row["bytes"] for row in files),
            "files": files,
        }


def _load_module(path: Path) -> ModuleType:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
    module_name = f"_validation_selector_{digest}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load selector file: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_selectors(
    selectors: tuple[str, ...], repository_root: Path
) -> tuple[unittest.TestSuite, float]:
    started = time.perf_counter()
    loader = unittest.TestLoader()
    modules: dict[Path, list[unittest.TestCase]] = {}
    parsed: list[tuple[str, Path, str, str]] = []
    for selector in selectors:
        match = SELECTOR_PATTERN.fullmatch(selector)
        if match is None:
            raise ValueError(f"invalid selector: {selector}")
        relative_path, class_name, method_name = match.groups()
        path = (repository_root / relative_path).resolve()
        try:
            path.relative_to(repository_root)
        except ValueError as exc:
            raise ValueError(f"selector path escapes repository: {selector}") from exc
        if not path.is_file():
            raise ValueError(f"selector file not found: {selector}")
        if path not in modules:
            modules[path] = list(_flatten(loader.loadTestsFromModule(_load_module(path))))
        parsed.append((selector, path, class_name, method_name))
    selected: list[unittest.TestCase] = []
    for selector, path, class_name, method_name in parsed:
        matches = [
            test
            for test in modules[path]
            if test.__class__.__name__ == class_name
            and getattr(test, "_testMethodName", None) == method_name
        ]
        if len(matches) != 1:
            raise ValueError(f"selector not found or ambiguous: {selector}")
        setattr(matches[0], "_validation_selector", selector)
        selected.append(matches[0])
    return unittest.TestSuite(selected), time.perf_counter() - started


def _load_suite(suite_path: str, repository_root: Path) -> tuple[unittest.TestSuite, float]:
    target = (repository_root / suite_path).resolve()
    try:
        target.relative_to(repository_root)
    except ValueError as exc:
        raise ValueError(f"suite path escapes repository: {suite_path}") from exc
    if not target.is_dir():
        raise ValueError(f"suite path not found: {suite_path}")
    started = time.perf_counter()
    loader = unittest.TestLoader()
    suite = loader.discover(str(target), pattern="test_*.py")
    elapsed = time.perf_counter() - started
    if loader.errors:
        # Failed imports are represented as _FailedTest cases and will produce
        # structured errors when run. Keep loader diagnostics out of stdout.
        pass
    return suite, elapsed


def _failure_rows(
    rows: Iterable[tuple[unittest.TestCase, str]], repository_root: Path
) -> list[dict[str, str]]:
    return sorted(
        (
            {
                "selector": _selector_for_test(test, repository_root),
                "traceback": sanitize_diagnostic(details),
            }
            for test, details in rows
        ),
        key=lambda row: row["selector"],
    )


def _empty_result(suite_id: str, selectors: tuple[str, ...]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "suite_id": suite_id,
        "selectors": list(selectors),
        "worker_pid": os.getpid(),
        "status": "error",
        "discovery_seconds": 0.0,
        "wall_seconds": 0.0,
        "tests_run": 0,
        "passes": 0,
        "skips": 0,
        "failures": 0,
        "errors": 0,
        "expected_failures": 0,
        "unexpected_successes": 0,
        "per_test_durations": [],
        "slowest_tests": [],
        "failure_details": [],
        "error_details": [],
        "worker_error": "",
    }


def run_worker(
    *,
    repository_root: Path,
    suite_id: str,
    suite_path: str | None = None,
    selectors: tuple[str, ...] = (),
    profile_fixtures: bool = False,
) -> dict[str, Any]:
    """Discover and run one isolated suite or explicit selector collection."""

    root = Path(repository_root).resolve()
    result_payload = _empty_result(suite_id, selectors)
    prior_cwd = Path.cwd()
    prior_path = list(sys.path)
    fixture_audit = FixtureAudit(root) if profile_fixtures else None
    if fixture_audit is not None:
        fixture_audit.install()
    try:
        os.chdir(root)
        sys.path[:0] = [str(root / "src"), str(root)]
        if selectors:
            suite, discovery_seconds = _load_selectors(selectors, root)
        elif suite_path is not None:
            suite, discovery_seconds = _load_suite(suite_path, root)
        else:
            raise ValueError("suite_path or selectors is required")
        if suite.countTestCases() == 0:
            raise ValueError("worker selection contains zero tests")
        structured = StructuredTestResult(root)
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        started = time.perf_counter()
        with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
            suite.run(structured)
        wall_seconds = time.perf_counter() - started
        duration_rows = sorted(structured.duration_rows, key=lambda row: row["selector"])
        slowest = sorted(
            duration_rows, key=lambda row: (-float(row["seconds"]), str(row["selector"]))
        )[:10]
        result_payload.update(
            {
                "status": "passed" if structured.wasSuccessful() else "failed",
                "discovery_seconds": discovery_seconds,
                "wall_seconds": wall_seconds,
                "tests_run": structured.testsRun,
                "passes": len(structured.successes),
                "skips": len(structured.skipped),
                "failures": len(structured.failures),
                "errors": len(structured.errors),
                "expected_failures": len(structured.expectedFailures),
                "unexpected_successes": len(structured.unexpectedSuccesses),
                "per_test_durations": duration_rows,
                "slowest_tests": slowest,
                "failure_details": _failure_rows(structured.failures, root),
                "error_details": _failure_rows(structured.errors, root),
                "worker_error": "",
            }
        )
    except BaseException as exc:  # Worker must serialize discovery/import failures.
        result_payload["worker_error"] = sanitize_diagnostic(
            "".join(traceback.format_exception_only(type(exc), exc)).strip()
        )
    finally:
        os.chdir(prior_cwd)
        sys.path[:] = prior_path
    if fixture_audit is not None:
        result_payload["fixture_io"] = fixture_audit.as_dict()
    return result_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--suite-id", required=True)
    parser.add_argument("--suite-path")
    parser.add_argument("--selector", action="append", default=[])
    parser.add_argument("--profile-fixtures", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    payload = run_worker(
        repository_root=arguments.repository_root,
        suite_id=arguments.suite_id,
        suite_path=arguments.suite_path,
        selectors=tuple(arguments.selector),
        profile_fixtures=arguments.profile_fixtures,
    )
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
