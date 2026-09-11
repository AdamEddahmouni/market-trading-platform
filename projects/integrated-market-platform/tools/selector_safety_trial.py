"""Explicit CHANGED-vs-FULL selector-safety trial with machine-readable receipt."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.validation_manifest import load_manifest
    from tools.validate import (
        SELECTOR_VERSION,
        ValidationSelectionError,
        build_selection_plan,
        changed_paths_from_file,
        changed_paths_from_git,
        execute_selection,
        manifest_fingerprint,
        select_changed,
        select_full,
        write_json_atomic,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution.
    from validation_manifest import load_manifest  # type: ignore[no-redef]
    from validate import (  # type: ignore[no-redef]
        SELECTOR_VERSION,
        ValidationSelectionError,
        build_selection_plan,
        changed_paths_from_file,
        changed_paths_from_git,
        execute_selection,
        manifest_fingerprint,
        select_changed,
        select_full,
        write_json_atomic,
    )


def _git_head(repository_root: Path) -> str:
    import subprocess

    completed = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip()


def _summarize_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "passed": int(payload.get("passes", 0)),
        "skipped": int(payload.get("skips", 0)),
        "failed": int(payload.get("failures", 0)),
        "errors": int(payload.get("errors", 0)),
        "tests_run": int(payload.get("tests_run", 0)),
        "wall_seconds": float(payload.get("wall_seconds", 0.0)),
    }


def _observed_selector_misses(
    changed_payload: dict[str, Any],
    full_payload: dict[str, Any],
) -> list[dict[str, str]]:
    """Return failures present in FULL worker output but absent from changed run."""

    def failure_keys(payload: dict[str, Any]) -> set[tuple[str, str]]:
        keys: set[tuple[str, str]] = set()
        for worker in payload.get("worker_results", []):
            suite_id = str(worker.get("suite_id", ""))
            for row in worker.get("failure_details", []):
                selector = str(row.get("selector", ""))
                if selector:
                    keys.add((suite_id, selector))
        return keys

    full_only = failure_keys(full_payload) - failure_keys(changed_payload)
    return [
        {"suite_id": suite_id, "selector": selector}
        for suite_id, selector in sorted(full_only)
    ]


def run_trial(
    *,
    repository_root: Path,
    paths: tuple[str, ...] | None = None,
    workers: int = 2,
    baseline_sha: str | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    manifest_path = root / "tools" / "validation_manifest.json"
    manifest = load_manifest(manifest_path, repository_root=root)
    if paths is None:
        paths = changed_paths_from_git(root)
    changed_selection = select_changed(manifest, paths)
    plan = build_selection_plan(changed_selection, manifest, manifest_path=manifest_path)
    started = datetime.now(timezone.utc).isoformat()
    changed_payload = execute_selection(
        repository_root=root,
        manifest=manifest,
        selection=changed_selection,
        workers=workers,
    )
    full_selection = select_full(manifest)
    full_payload = execute_selection(
        repository_root=root,
        manifest=manifest,
        selection=full_selection,
        workers=workers,
    )
    misses = _observed_selector_misses(changed_payload, full_payload)
    return {
        "schema_version": "1.0",
        "report_type": "selector_safety_trial",
        "trial_id": str(uuid.uuid4()),
        "generated_at": started,
        "baseline_sha": baseline_sha or "unknown",
        "head_sha": _git_head(root),
        "selector_version": SELECTOR_VERSION,
        "manifest_hash": manifest_fingerprint(manifest),
        "changed_paths": list(paths),
        "path_classifications": plan["classifications"],
        "selected_suites": list(changed_selection.selected_suite_ids),
        "selected_test_count": int(changed_payload.get("tests_run", 0)),
        "core_checkpoint_required": changed_selection.core_checkpoint_required,
        "core_checkpoint_reasons": list(changed_selection.global_reasons),
        "changed_result": _summarize_result(changed_payload),
        "full_result": _summarize_result(full_payload),
        "observed_selector_misses": len(misses),
        "observed_selector_miss_details": misses,
        "limitations": [
            "Trial compares executed changed selection against one FULL run on the same tree.",
            "Unrelated flaky FULL failures are not automatically excluded.",
            "Sample size of one trial does not prove mathematical selector recall.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths-file", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--baseline-sha")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    repository_root = Path(__file__).resolve().parents[1]
    try:
        if arguments.paths_file is not None:
            paths_file = Path(arguments.paths_file)
            if not paths_file.is_absolute():
                paths_file = repository_root / paths_file
            paths = changed_paths_from_file(paths_file, repository_root)
        else:
            paths = None
        receipt = run_trial(
            repository_root=repository_root,
            paths=paths,
            workers=arguments.workers,
            baseline_sha=arguments.baseline_sha,
        )
    except ValidationSelectionError as exc:
        print(f"selector safety trial error: {exc}", file=sys.stderr)
        return 2
    write_json_atomic(arguments.json_path, receipt)
    print(
        f"TRIAL {receipt['trial_id']}: changed={receipt['changed_result']['tests_run']} tests "
        f"full={receipt['full_result']['tests_run']} tests "
        f"observed_selector_misses={receipt['observed_selector_misses']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
