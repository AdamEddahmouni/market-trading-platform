"""Explicit governed JSONL discovery for Item 7 and RTH status tooling.

Governed evidence lives only at known paths under ``IMP_STATE_DIR`` (or an
explicit persistence root). This module does **not** recursively sweep
``.local/**/*.jsonl`` or ``artifacts/**/*.jsonl``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .corpus_persistence import discover_governed_persistence_paths, resolve_persistence_root

GOVERNED_ITEM7_CAPTURE_RELATIVE = Path("captures") / "item7-opend-prospective-capture.jsonl"


class GovernedJsonlEncodingError(RuntimeError):
    """Governed evidence JSONL must be UTF-8."""

    def __init__(self, path: Path, byte_offset: int | None = None) -> None:
        self.path = path
        self.byte_offset = byte_offset
        suffix = f" (byte offset {byte_offset})" if byte_offset is not None else ""
        super().__init__(
            f"Governed JSONL is not valid UTF-8: {path}{suffix}. "
            "Governed evidence must be UTF-8 encoded."
        )


class GovernedJsonlParseError(RuntimeError):
    """A governed JSONL line failed structural parse."""

    def __init__(self, path: Path, line_index: int, detail: str) -> None:
        self.path = path
        self.line_index = line_index
        self.detail = detail
        super().__init__(f"Governed JSONL parse error at {path}:{line_index}: {detail}")


def discover_governed_outcome_jsonl_paths(
    *,
    persistence_root: Path | None = None,
    extra_paths: Iterable[Path] = (),
) -> tuple[Path, ...]:
    """Return governed intelligence JSONL files that may carry settled outcomes."""

    root = persistence_root if persistence_root is not None else resolve_persistence_root()
    found: list[Path] = []
    if root is not None:
        opts = discover_governed_persistence_paths(root)
        found.extend(opts.intelligence_jsonl_paths)
    seen = {str(path) for path in found}
    for path in extra_paths:
        resolved = path.expanduser().resolve()
        key = str(resolved)
        if resolved.is_file() and key not in seen:
            seen.add(key)
            found.append(resolved)
    return tuple(found)


def read_governed_jsonl_text(path: Path) -> str:
    """Read a governed JSONL file as UTF-8 or fail closed."""

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise GovernedJsonlEncodingError(path, exc.start) from exc


__all__ = [
    "GOVERNED_ITEM7_CAPTURE_RELATIVE",
    "GovernedJsonlEncodingError",
    "GovernedJsonlParseError",
    "discover_governed_outcome_jsonl_paths",
    "read_governed_jsonl_text",
]
