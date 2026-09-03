"""Generate an organized, read-only audit trail for workspace repositories."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from tools.monorepo_guard import GuardError, _load_manifest, _source_git
except ModuleNotFoundError:  # Direct execution: python tools/generate_history_ledger.py
    from monorepo_guard import GuardError, _load_manifest, _source_git


HISTORY_DIR = Path("docs/history")
LEDGER_NAME = "WORK_LEDGER.jsonl"
REFS_NAME = "REFS.json"
INDEX_NAME = "INDEX.md"
IDENTITY_RE = re.compile(r"^(?P<name>.*) <(?P<email>[^>]*)> (?P<epoch>-?\d+) (?P<offset>[+-]\d{4})$")


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise GuardError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _git_bytes(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise GuardError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _parse_identity(value: str) -> dict[str, str]:
    match = IDENTITY_RE.match(value)
    if not match:
        return {"name": value, "email": "", "timestamp": ""}
    offset = match.group("offset")
    sign = 1 if offset[0] == "+" else -1
    minutes = sign * (int(offset[1:3]) * 60 + int(offset[3:]))
    instant = datetime.fromtimestamp(
        int(match.group("epoch")),
        tz=timezone(timedelta(minutes=minutes)),
    )
    return {
        "name": match.group("name"),
        "email": match.group("email"),
        "timestamp": instant.isoformat(),
    }


def parse_commit_object(raw: bytes) -> dict[str, Any]:
    """Parse a raw commit object without normalizing away its message."""

    header_bytes, _, body_bytes = raw.partition(b"\n\n")
    headers = header_bytes.decode("utf-8", "replace").splitlines()
    parents: list[str] = []
    author = {}
    committer = {}
    tree = ""
    for line in headers:
        if line.startswith("tree "):
            tree = line[5:]
        elif line.startswith("parent "):
            parents.append(line[7:])
        elif line.startswith("author "):
            author = _parse_identity(line[7:])
        elif line.startswith("committer "):
            committer = _parse_identity(line[10:])
    message = body_bytes.decode("utf-8", "replace").rstrip("\n")
    subject, separator, body = message.partition("\n")
    if separator:
        body = body.lstrip("\n")
    else:
        body = ""
    return {
        "tree": tree,
        "parents": parents,
        "author": author,
        "committer": committer,
        "subject": subject,
        "body": body,
    }


def rationale_status(subject: str, body: str) -> str:
    if body.strip():
        return "commit-subject-and-body"
    if subject.strip():
        return "commit-subject-only"
    return "not-stated"


def _changed_paths(repo: Path, commit: str, *, source_worktree: bool = False) -> list[dict[str, str]]:
    args = ["diff-tree", "--root", "--no-commit-id", "--name-status", "-r", commit]
    output = (
        _source_git(repo, *args)
        if source_worktree
        else _git(repo, *args)
    )
    changed: list[dict[str, str]] = []
    for line in output.splitlines():
        status, separator, path = line.partition("\t")
        if separator:
            changed.append({"status": status, "path": path})
    return changed


def _ref_tips(repo: Path, *, source_worktree: bool = False) -> dict[str, str]:
    args = ["for-each-ref", "--format=%(refname)%00%(objectname)"]
    output = _source_git(repo, *args) if source_worktree else _git(repo, *args)
    tips: dict[str, str] = {}
    for line in output.splitlines():
        ref, _, object_name = line.partition("\x00")
        if not ref:
            continue
        resolve_args = ["rev-parse", f"{ref}^{{commit}}"]
        commit = (
            _source_git(repo, *resolve_args, check=False)
            if source_worktree
            else _git(repo, *resolve_args, check=False)
        )
        if commit:
            tips[ref] = commit
    return tips


def _all_commits(repo: Path, *, source_worktree: bool = False) -> list[str]:
    return (
        _source_git(repo, "rev-list", "--all").splitlines()
        if source_worktree
        else _git(repo, "rev-list", "--all").splitlines()
    )


def _commits_from_tips(
    repo: Path,
    tips: dict[str, str],
    *,
    source_worktree: bool = False,
) -> list[str]:
    commits: set[str] = set()
    for tip in tips.values():
        output = (
            _source_git(repo, "rev-list", tip)
            if source_worktree
            else _git(repo, "rev-list", tip)
        )
        commits.update(output.splitlines())
    return sorted(commits)


def _build_record(
    repository: str,
    repo: Path,
    commit: str,
    refs: list[str],
    *,
    source_worktree: bool = False,
) -> dict[str, Any]:
    raw = (
        _git_bytes(repo, "cat-file", "commit", commit)
        if not source_worktree
        else subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={repo.resolve()}",
                "cat-file",
                "commit",
                commit,
            ],
            cwd=repo,
            check=True,
            capture_output=True,
        ).stdout
    )
    parsed = parse_commit_object(raw)
    return {
        "repository": repository,
        "commit": commit,
        "short_commit": commit[:12],
        "refs": refs,
        "parents": parsed["parents"],
        "author": parsed["author"],
        "committer": parsed["committer"],
        "subject": parsed["subject"],
        "body": parsed["body"],
        "rationale_status": rationale_status(parsed["subject"], parsed["body"]),
        "changed_paths": _changed_paths(
            repo,
            commit,
            source_worktree=source_worktree,
        ),
    }


def collect_repository_history(
    root: Path,
    repository: str,
    tips_override: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Collect every commit reachable from every local ref for one repo."""

    manifest = _load_manifest(root)
    source_worktree = repository != "parent"
    if source_worktree:
        project = next(
            project for project in manifest["projects"] if project["id"] == repository
        )
        repo = root / project["source_path"]
    else:
        repo = root
    tips = tips_override or _ref_tips(repo, source_worktree=source_worktree)
    refs_by_commit: dict[str, list[str]] = defaultdict(list)
    for ref, commit in tips.items():
        refs_by_commit[commit].append(ref)
    commit_shas = (
        _commits_from_tips(repo, tips, source_worktree=source_worktree)
        if tips_override is not None
        else _all_commits(repo, source_worktree=source_worktree)
    )
    records = [
        _build_record(
            repository,
            repo,
            commit,
            sorted(refs_by_commit.get(commit, [])),
            source_worktree=source_worktree,
        )
        for commit in commit_shas
    ]
    records.sort(key=lambda record: (record["committer"].get("timestamp", ""), record["commit"]))
    return records, tips


def _rationale_excerpt(record: dict[str, Any]) -> str:
    body = str(record["body"]).strip()
    if not body:
        return "Rationale stated in commit subject only."
    excerpt = body.split("\n\n", 1)[0].strip()
    if len(excerpt) > 800:
        excerpt = excerpt[:797].rstrip() + "..."
    return excerpt


def render_repository_markdown(
    repository: str,
    records: list[dict[str, Any]],
) -> str:
    lines = [
        f"# {repository} history",
        "",
        f"Complete chronological commit index for `{repository}`.",
        "The full commit body and changed paths are preserved in the JSONL ledger.",
        "",
    ]
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        date = record["committer"].get("timestamp", "")[:10] or "unknown-date"
        by_date[date].append(record)
    for date in sorted(by_date):
        lines.extend([f"## {date}", ""])
        for record in by_date[date]:
            refs = ", ".join(f"`{ref}`" for ref in record["refs"])
            ref_text = f" — refs: {refs}" if refs else ""
            lines.append(
                f"- `{record['short_commit']}` — {record['subject']}{ref_text}"
            )
            lines.append(
                f"  - Author: {record['author'].get('name', '')} "
                f"({record['author'].get('timestamp', '')})"
            )
            lines.append(
                f"  - Rationale ({record['rationale_status']}): "
                f"{_rationale_excerpt(record)}"
            )
        lines.append("")
    return "\n".join(lines)


def _manifest_projects(root: Path) -> list[dict[str, Any]]:
    return _load_manifest(root)["projects"]


def _render_index(
    records_by_repo: dict[str, list[dict[str, Any]]],
    refs_by_repo: dict[str, dict[str, str]],
) -> str:
    lines = [
        "# Workspace History Audit",
        "",
        "This audit preserves the committed history of the parent workspace and",
        "every commit reachable from every local ref in each independent child",
        "repository available at generation time.",
        "",
        "## How to read this",
        "",
        "- Start with the repository timelines for human-readable chronology.",
        "- Use `WORK_LEDGER.jsonl` for complete commit bodies and changed paths.",
        "- Use `REFS.json` to see which refs and exact tips were captured.",
        "- Rationale is never invented: missing commit bodies are labeled",
        "  `commit-subject-only` or `not-stated`.",
        "",
        "## Repository coverage",
        "",
        "| Repository | Commits | Refs | First commit | Latest commit |",
        "|---|---:|---:|---|---|",
    ]
    for repository in sorted(records_by_repo):
        records = records_by_repo[repository]
        dates = [
            record["committer"].get("timestamp", "")[:10]
            for record in records
            if record["committer"].get("timestamp")
        ]
        lines.append(
            f"| `{repository}` | {len(records)} | {len(refs_by_repo[repository])} | "
            f"{min(dates) if dates else 'unknown'} | {max(dates) if dates else 'unknown'} |"
        )
    lines.extend(
        [
            "",
            "The `integrated-platform`, `governed-ticker-metadata`, and",
            "`equity-data-v1` entries share one underlying Git history because",
            "the latter two are worktrees; each workspace ref set is retained",
            "separately for traceability.",
            "",
            "## Repository timelines",
            "",
        ]
    )
    for repository in sorted(records_by_repo):
        lines.append(f"- [`{repository}`](repositories/{repository}.md)")
    lines.append("")
    return "\n".join(lines)


def _write_outputs(
    output_dir: Path,
    records_by_repo: dict[str, list[dict[str, Any]]],
    refs_by_repo: dict[str, dict[str, str]],
) -> None:
    repo_dir = output_dir / "repositories"
    repo_dir.mkdir(parents=True, exist_ok=True)
    records = [
        record
        for repository in sorted(records_by_repo)
        for record in records_by_repo[repository]
    ]
    (output_dir / LEDGER_NAME).write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    (output_dir / REFS_NAME).write_text(
        json.dumps(
            {"schema_version": 1, "repositories": refs_by_repo},
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    (output_dir / INDEX_NAME).write_text(
        _render_index(records_by_repo, refs_by_repo),
        encoding="utf-8",
    )
    for repository, repository_records in records_by_repo.items():
        (repo_dir / f"{repository}.md").write_text(
            render_repository_markdown(repository, repository_records),
            encoding="utf-8",
        )


def generate(
    root: Path,
    output_dir: Path,
    refs_override: dict[str, dict[str, str]] | None = None,
) -> None:
    """Generate all audit artifacts from the current local refs."""

    records_by_repo: dict[str, list[dict[str, Any]]] = {}
    refs_by_repo: dict[str, dict[str, str]] = {}
    repository_ids = ["parent"] + [project["id"] for project in _manifest_projects(root)]
    for repository in repository_ids:
        records_by_repo[repository], refs_by_repo[repository] = (
            collect_repository_history(
                root,
                repository,
                (refs_override or {}).get(repository),
            )
        )
    _write_outputs(output_dir, records_by_repo, refs_by_repo)


def check_generated(root: Path, output_dir: Path) -> None:
    """Regenerate in isolation and fail when tracked audit output is stale."""

    refs_path = output_dir / REFS_NAME
    try:
        refs_override = json.loads(refs_path.read_text(encoding="utf-8"))["repositories"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise GuardError(f"cannot read captured ref snapshot: {refs_path}: {exc}") from exc
    with tempfile.TemporaryDirectory(prefix="history-audit-") as temporary:
        generated_dir = Path(temporary)
        generate(root, generated_dir, refs_override=refs_override)
        expected = sorted(
            path.relative_to(generated_dir).as_posix()
            for path in generated_dir.rglob("*")
            if path.is_file()
        )
        actual = sorted(
            path.relative_to(output_dir).as_posix()
            for path in output_dir.rglob("*")
            if path.is_file()
        )
        if expected != actual:
            raise GuardError(
                "history audit file set is stale:\n"
                f"expected: {expected}\nactual: {actual}"
            )
        for relative in expected:
            generated = (generated_dir / relative).read_bytes()
            committed = (output_dir / relative).read_bytes()
            if generated != committed:
                raise GuardError(f"history audit artifact is stale: {relative}")


def validate_artifacts(root: Path) -> None:
    """Validate committed audit structure without requiring child checkouts."""

    manifest = _load_manifest(root)
    history = root / HISTORY_DIR
    ledger_path = history / LEDGER_NAME
    refs_path = history / REFS_NAME
    index_path = history / INDEX_NAME
    for path in (ledger_path, refs_path, index_path):
        if not path.is_file():
            raise GuardError(f"missing audit artifact: {path}")
    try:
        refs = json.loads(refs_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GuardError(f"invalid {refs_path}: {exc}") from exc
    if refs.get("schema_version") != 1:
        raise GuardError("REFS.json schema_version must be 1")

    seen: set[tuple[str, str]] = set()
    for line_number, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GuardError(f"invalid ledger JSON on line {line_number}: {exc}") from exc
        key = (record.get("repository", ""), record.get("commit", ""))
        if key in seen:
            raise GuardError(f"duplicate ledger record: {key}")
        seen.add(key)
        if len(key[1]) != 40 or not re.fullmatch(r"[0-9a-f]{40}", key[1]):
            raise GuardError(f"invalid commit SHA on ledger line {line_number}")
        if record.get("rationale_status") not in {
            "commit-subject-and-body",
            "commit-subject-only",
            "not-stated",
        }:
            raise GuardError(f"invalid rationale status on ledger line {line_number}")

    for project in manifest["projects"]:
        key = (project["id"], project["source_commit"])
        if key not in seen:
            raise GuardError(f"manifest source commit missing from ledger: {key}")
        if project["id"] not in refs.get("repositories", {}):
            raise GuardError(f"missing refs entry for {project['id']}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--output-dir", type=Path, default=HISTORY_DIR)
    generate_parser.add_argument("--check", action="store_true")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--ci", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "generate":
            output_dir = (root / args.output_dir).resolve()
            if args.check:
                check_generated(root, output_dir)
                print(f"history audit is current in {output_dir}")
            else:
                generate(root, output_dir)
                print(f"generated history audit in {output_dir}")
        else:
            validate_artifacts(root)
            print("history audit validation passed")
    except (GuardError, OSError, ValueError) as exc:
        print(f"history audit failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
