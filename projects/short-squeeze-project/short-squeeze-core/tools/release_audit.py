"""Privacy and credential audit for staged integration releases.

Findings intentionally omit matched text. The scanner is designed for a clean
allowlisted staging directory, not as a replacement for provider credential
rotation or Git-history review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

TEXT_SUFFIXES = {
    "",
    ".css",
    ".csv",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
FORBIDDEN_PARTS = {
    ".git",
    ".private",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "provider-cache",
}
SKIPPED_PARTS = {
    ".railway-deploy",
    ".pytest-run",
    "tests",
}
FORBIDDEN_NAMES = {
    ".env",
    ".env.local",
    "coverage.xml",
    "junit.xml",
}
SAFE_SECRET_VALUES = (
    "replace_with_",
    "your_",
    "example",
    "placeholder",
    "not_configured",
)
PATTERNS = (
    (
        "CREDENTIAL",
        re.compile(
            r"(?im)^[A-Z][A-Z0-9_]*(?:API_KEY|_KEY|_TOKEN|_PASSWORD|_SECRET)"
            r"\s*=\s*(?![\"']?(?:replace_with_|your_|example|placeholder))"
            r"[\"']?[A-Za-z0-9+/_.:@=-]{8,}[\"']?\s*$"
        ),
    ),
    (
        "CREDENTIAL",
        re.compile(
            r"(?i)[\"'](?:api[_-]?key|token|password|secret|authorization)[\"']"
            r"\s*:\s*(?![\"']?(?:replace_with_|your_|example|placeholder))"
            r"[\"'][A-Za-z0-9+/_.:@=-]{8,}[\"']"
        ),
    ),
    ("CREDENTIAL", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")),
    ("CREDENTIAL", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    (
        "AUTHENTICATED_URL",
        re.compile(r"https?://[^/\s:@]+:[^/\s@]+@[^/\s]+", re.IGNORECASE),
    ),
    (
        "EMAIL",
        re.compile(
            r"\b[A-Z0-9._%+-]+@(?!example\.invalid\b)[A-Z0-9.-]+\.[A-Z]{2,}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PHONE",
        re.compile(
            r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)"
        ),
    ),
    ("WINDOWS_USER_PATH", re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s]+")),
    ("UNIX_HOME_PATH", re.compile(r"(?<![\w/])/(?:home|Users)/[^/\s]+")),
    (
        "ACADEMIC_OR_PERSONAL",
        re.compile(
            r"(?i)\b(?:professor|student|course\s*(?:number|code|#|\d)|"
            r"class\s+project|assignment|meeting\s+transcript|grading)\b"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class Finding:
    category: str
    path: str
    line: int | None
    message: str


@dataclass(frozen=True, slots=True)
class AuditResult:
    root_label: str
    files_scanned: int
    findings: tuple[Finding, ...]
    reviewed_allowlist_matches: int = 0

    @property
    def passed(self) -> bool:
        return not self.findings

    def public_dict(self) -> dict[str, object]:
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.category] = counts.get(finding.category, 0) + 1
        return {
            "status": "PASS" if self.passed else "FAIL",
            "root": self.root_label,
            "files_scanned": self.files_scanned,
            "finding_counts": dict(sorted(counts.items())),
            "reviewed_allowlist_matches": self.reviewed_allowlist_matches,
            "findings": [asdict(finding) for finding in self.findings],
        }

    def to_json(self) -> str:
        return json.dumps(self.public_dict(), sort_keys=True)


def _forbidden(relative: Path) -> bool:
    parts = {part.lower() for part in relative.parts}
    return (
        relative.name.lower() in FORBIDDEN_NAMES
        or bool(parts & {part.lower() for part in FORBIDDEN_PARTS})
        or any(part.endswith(".egg-info") for part in parts)
        or relative.suffix.lower() in {".pyc", ".pyo"}
    )


def _skipped(relative: Path) -> bool:
    parts = {part.lower() for part in relative.parts}
    return bool(parts & {part.lower() for part in SKIPPED_PARTS})


def _is_text(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name == ".env.example"


def _line_number(text: str, start: int) -> int:
    return text.count("\n", 0, start) + 1


def _extra_patterns(path: Path | None) -> tuple[re.Pattern[str], ...]:
    if path is None or not path.is_file():
        return ()
    patterns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            patterns.append(re.compile(re.escape(value), re.IGNORECASE))
    return tuple(patterns)


def _reviewed_allowlist(
    path: Path | None,
) -> tuple[tuple[str, str, re.Pattern[str]], ...]:
    if path is None or not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = payload.get("entries", [])
        return tuple(
            (
                str(entry["category"]),
                str(entry["path"]),
                re.compile(str(entry["line_pattern"])),
            )
            for entry in entries
        )
    except (json.JSONDecodeError, KeyError, TypeError, re.error) as exc:
        raise ValueError("release audit allowlist is invalid") from exc


def _is_reviewed(
    rules: tuple[tuple[str, str, re.Pattern[str]], ...],
    *,
    category: str,
    relative_path: str,
    line_text: str,
) -> bool:
    return any(
        rule_category == category
        and rule_path == relative_path
        and pattern.search(line_text)
        for rule_category, rule_path, pattern in rules
    )


def audit_directory(
    root: Path,
    *,
    allowlist_path: Path | None = None,
    extra_patterns_path: Path | None = None,
) -> AuditResult:
    root = root.resolve()
    findings: list[Finding] = []
    files_scanned = 0
    reviewed_matches = 0
    private_patterns = _extra_patterns(extra_patterns_path)
    reviewed_rules = _reviewed_allowlist(allowlist_path)
    resolved_allowlist = allowlist_path.resolve() if allowlist_path else None
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if resolved_allowlist is not None and path.resolve() == resolved_allowlist:
            continue
        if reviewed_rules and path.name == "release-audit-allowlist.json":
            continue
        relative = path.relative_to(root)
        relative_text = relative.as_posix()
        if _skipped(relative):
            continue
        files_scanned += 1
        if _forbidden(relative):
            findings.append(
                Finding(
                    "FORBIDDEN_FILE",
                    relative_text,
                    None,
                    "File or parent directory is prohibited in a release.",
                )
            )
            continue
        if not _is_text(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lines = text.splitlines()
        for category, pattern in PATTERNS:
            for match in pattern.finditer(text):
                if category == "CREDENTIAL":
                    matched_lower = match.group(0).lower()
                    if any(safe in matched_lower for safe in SAFE_SECRET_VALUES):
                        continue
                line_number = _line_number(text, match.start())
                line_text = lines[line_number - 1] if line_number <= len(lines) else ""
                if _is_reviewed(
                    reviewed_rules,
                    category=category,
                    relative_path=relative_text,
                    line_text=line_text,
                ):
                    reviewed_matches += 1
                    continue
                findings.append(
                    Finding(
                        category,
                        relative_text,
                        line_number,
                        "Prohibited content category detected; matched text withheld.",
                    )
                )
        for pattern in private_patterns:
            for match in pattern.finditer(text):
                findings.append(
                    Finding(
                        "PRIVATE_EXTRA_PATTERN",
                        relative_text,
                        _line_number(text, match.start()),
                        "Private audit pattern detected; matched text withheld.",
                    )
                )
    return AuditResult(root.name, files_scanned, tuple(findings), reviewed_matches)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--extra-patterns", type=Path)
    parser.add_argument("--allowlist", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    allowlist_path = args.allowlist
    if allowlist_path is None:
        staged_allowlist = args.directory / "release-audit-allowlist.json"
        if staged_allowlist.is_file():
            allowlist_path = staged_allowlist
    result = audit_directory(
        args.directory,
        allowlist_path=allowlist_path,
        extra_patterns_path=args.extra_patterns,
    )
    if args.as_json:
        print(result.to_json())
    else:
        print(f"RELEASE_AUDIT: {'PASS' if result.passed else 'FAIL'}")
        print(f"FILES_SCANNED: {result.files_scanned}")
        for category, count in result.public_dict()["finding_counts"].items():
            print(f"{category}: {count}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["AuditResult", "Finding", "audit_directory", "main"]
