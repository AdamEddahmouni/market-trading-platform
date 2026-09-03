"""Safe import and validation tooling for the parent workspace monorepo."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


MANIFEST_NAME = "workspace-manifest.json"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class GuardError(RuntimeError):
    """Raised when a monorepo safety invariant is violated."""


def validate_manifest_data(manifest: dict[str, Any]) -> list[str]:
    """Return contract violations without touching Git or child repositories."""

    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]
    if manifest.get("version") != 1:
        errors.append("version must be 1")

    parent = manifest.get("parent")
    if not isinstance(parent, dict):
        errors.append("parent must be an object")
    else:
        if not parent.get("repository"):
            errors.append("parent.repository is required")
        if parent.get("visibility") != "private":
            errors.append("parent.visibility must be private")

    projects = manifest.get("projects")
    if not isinstance(projects, list) or not projects:
        return errors + ["projects must be a non-empty array"]

    ids: set[str] = set()
    snapshots: set[str] = set()
    for index, project in enumerate(projects):
        prefix = f"projects[{index}]"
        if not isinstance(project, dict):
            errors.append(f"{prefix} must be an object")
            continue
        project_id = project.get("id")
        if not isinstance(project_id, str) or not project_id:
            errors.append(f"{prefix}.id is required")
        elif project_id in ids:
            errors.append(f"duplicate project id: {project_id}")
        else:
            ids.add(project_id)

        source_path = _relative_path(project.get("source_path"))
        if source_path is None:
            errors.append(f"{prefix}.source_path must be a relative path")

        snapshot_path = _relative_path(project.get("snapshot_path"))
        if snapshot_path is None:
            errors.append(f"{prefix}.snapshot_path must be a relative path")
        elif not snapshot_path.startswith("projects/"):
            errors.append("snapshot_path must be under projects/")
        elif snapshot_path in snapshots:
            errors.append(f"duplicate snapshot path: {snapshot_path}")
        else:
            snapshots.add(snapshot_path)

        if not isinstance(project.get("source_ref"), str) or not project["source_ref"]:
            errors.append(f"{prefix}.source_ref is required")
        source_commit = project.get("source_commit")
        if not isinstance(source_commit, str) or not COMMIT_RE.fullmatch(source_commit):
            errors.append(f"{prefix}.source_commit must be a 40-character commit SHA")

        if project.get("expected_visibility") not in {"private", "public"}:
            errors.append(f"{prefix}.expected_visibility must be private or public")
        if project.get("source_policy") != "unchanged":
            errors.append(f"{prefix}.source_policy must be unchanged")
        if not isinstance(project.get("source_remote"), str) or not project["source_remote"]:
            errors.append(f"{prefix}.source_remote is required")

    return errors


def validate_snapshot_entries(entries: Iterable[tuple[str, str]]) -> None:
    """Reject nested repositories represented as Git submodule gitlinks."""

    for mode, path in entries:
        if mode == "160000":
            raise GuardError(f"embedded Git repository/gitlink found: {path}")


def _relative_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        return None
    return path.as_posix().rstrip("/")


def _git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise GuardError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _git_succeeds(root: Path, *args: str) -> bool:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _source_git(source: Path, *args: str, check: bool = True) -> str:
    """Run a read-only Git command against a child, including worktrees."""

    return _git(
        source,
        "-c",
        f"safe.directory={source.resolve()}",
        *args,
        check=check,
    )


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_NAME
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardError(f"cannot read {MANIFEST_NAME}: {exc}") from exc
    errors = validate_manifest_data(manifest)
    if errors:
        raise GuardError("invalid workspace manifest:\n- " + "\n- ".join(errors))
    return manifest


def _project(manifest: dict[str, Any], project_id: str) -> dict[str, Any]:
    for project in manifest["projects"]:
        if project["id"] == project_id:
            return project
    raise GuardError(f"unknown project id: {project_id}")


def _snapshot_entries(root: Path, snapshot_path: str) -> list[tuple[str, str]]:
    output = _git(root, "ls-tree", "-r", "HEAD", "--", snapshot_path)
    entries: list[tuple[str, str]] = []
    for line in output.splitlines():
        fields = line.split(maxsplit=3)
        if len(fields) == 4:
            entries.append((fields[0], fields[3]))
    return entries


def _source_state(source: Path) -> tuple[str, str, str]:
    return (
        _source_git(source, "rev-parse", "--abbrev-ref", "HEAD"),
        _source_git(source, "rev-parse", "HEAD"),
        _source_git(source, "status", "--porcelain=v1", "--untracked-files=all"),
    )


def validate_repository(root: Path, *, ci: bool = False, remote: bool = False) -> None:
    """Validate parent structure and, locally, child source contracts."""

    manifest = _load_manifest(root)
    actual_root = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
    if actual_root != root.resolve():
        raise GuardError("root is not the parent Git repository")

    expected_remote = f"https://github.com/{manifest['parent']['repository']}.git"
    actual_remote = _git(root, "remote", "get-url", "origin", check=False)
    if not actual_remote or actual_remote.rstrip("/") != expected_remote.rstrip("/"):
        raise GuardError(f"origin must be {expected_remote}, found {actual_remote}")

    for project in manifest["projects"]:
        snapshot = project["snapshot_path"]
        tree = _git(root, "ls-tree", "HEAD", "--", snapshot)
        if not tree:
            raise GuardError(f"missing snapshot: {snapshot}")
        mode = tree.split(maxsplit=1)[0]
        if mode == "160000":
            raise GuardError(f"snapshot is a gitlink, not ordinary files: {snapshot}")
        entries = _snapshot_entries(root, snapshot)
        if not entries:
            raise GuardError(f"snapshot contains no files: {snapshot}")
        validate_snapshot_entries(entries)

        if ci:
            continue
        source = root / project["source_path"]
        if not source.exists():
            raise GuardError(f"missing local source repository: {source}")
        source_remote = _source_git(source, "remote", "get-url", "origin", check=False)
        if source_remote.rstrip("/") != project["source_remote"].rstrip("/"):
            raise GuardError(
                f"{project['id']} origin mismatch: expected {project['source_remote']}, "
                f"found {source_remote}"
            )
        resolved = _source_git(source, "rev-parse", f"{project['source_ref']}^{{commit}}")
        if resolved != project["source_commit"]:
            raise GuardError(
                f"{project['id']} source ref moved: manifest {project['source_commit']}, "
                f"resolved {resolved}"
            )
        if not _git_succeeds(root, "check-ignore", "--", project["source_path"]):
            raise GuardError(f"original source must be ignored by parent: {project['source_path']}")
        if remote:
            _validate_remote_visibility(project)
    if remote:
        _validate_repository_visibility(
            manifest["parent"]["repository"],
            manifest["parent"]["visibility"],
        )


def _validate_remote_visibility(project: dict[str, Any]) -> None:
    repository = project["source_remote"].split("github.com/", 1)[-1].removesuffix(".git")
    _validate_repository_visibility(repository, project["expected_visibility"])


def _validate_repository_visibility(repository: str, expected: str) -> None:
    result = subprocess.run(
        ["gh", "repo", "view", repository, "--json", "isPrivate", "--jq", ".isPrivate"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise GuardError(f"cannot verify visibility for {repository}: {result.stderr.strip()}")
    actual = "private" if result.stdout.strip().lower() == "true" else "public"
    if actual != expected:
        raise GuardError(
            f"{repository} visibility is {actual}, expected {expected}"
        )


def _require_import_branch(root: Path) -> None:
    branch = _git(root, "branch", "--show-current")
    if branch in {"", "main", "master"}:
        raise GuardError("imports must run on a reviewable branch, never directly on main")
    if not _git_succeeds(root, "diff", "--quiet"):
        raise GuardError("parent has unstaged changes; commit or stash them before importing")
    if not _git_succeeds(root, "diff", "--cached", "--quiet"):
        raise GuardError("parent has staged changes; commit them before importing")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise GuardError("parent has untracked files; commit or remove them before importing")


def import_project(root: Path, project_id: str, source_ref: str | None = None) -> None:
    """Import one source ref into the parent snapshot without touching its repo."""

    manifest = _load_manifest(root)
    _require_import_branch(root)
    project = _project(manifest, project_id)
    source = root / project["source_path"]
    if not source.exists():
        raise GuardError(f"missing local source repository: {source}")

    ref = source_ref or project["source_ref"]
    resolved = _source_git(source, "rev-parse", f"{ref}^{{commit}}")
    before = _source_state(source)
    parent_before = _git(root, "rev-parse", "HEAD")
    _git(
        root,
        "subtree",
        "pull",
        "--prefix=" + project["snapshot_path"],
        str(source),
        ref,
        "--squash",
    )
    if _source_state(source) != before:
        raise GuardError("source repository changed during import; aborting")
    if _git(root, "rev-parse", "HEAD") == parent_before:
        raise GuardError("source is already imported; no parent commit was created")

    project["source_ref"] = ref
    project["source_commit"] = resolved
    (root / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    _git(root, "add", MANIFEST_NAME)
    _git(root, "commit", "--amend", "--no-edit")
    validate_repository(root)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--ci", action="store_true")
    validate.add_argument("--remote", action="store_true")

    importer = subparsers.add_parser("import")
    importer.add_argument("project_id")
    importer.add_argument("--source-ref")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "validate":
            validate_repository(root, ci=args.ci, remote=args.remote)
            print("monorepo validation passed")
        else:
            import_project(root, args.project_id, args.source_ref)
            print(f"imported {args.project_id} into parent monorepo")
    except GuardError as exc:
        print(f"monorepo guard failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
