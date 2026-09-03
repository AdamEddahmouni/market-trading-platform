"""SOP/workflow document existence and whitespace-normalized section hashing."""

from __future__ import annotations

import re
from pathlib import Path

from market_platform_foundation.canonical import sha256_bytes


_HEADING = re.compile(r"^## (.+?)(?:\s+—\s+.*)?\s*$")


def normalize_section(text: str) -> bytes:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return ("\n".join(lines) + "\n").encode("utf-8")


def extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    duplicates: set[str] = set()
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            ident = match.group(1).strip()
            if ident in sections:
                duplicates.add(ident)
            sections[ident] = [line]
            current = ident
            continue
        if current is not None:
            sections[current].append(line)
    if duplicates:
        raise ValueError(f"duplicate headings: {sorted(duplicates)}")
    return {key: "\n".join(lines) for key, lines in sections.items()}


def section_hash(text: str) -> str:
    return sha256_bytes(normalize_section(text))


def read_document_sections(repository_root: Path, relative_path: str) -> dict[str, str]:
    path = repository_root / relative_path
    if not path.is_file():
        raise FileNotFoundError(relative_path)
    return extract_sections(path.read_text(encoding="utf-8"))
