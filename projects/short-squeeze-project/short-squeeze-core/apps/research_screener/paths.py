"""Artifact location plus the forward-window access guard.

The application reads the private Batch 05 / Batch 08 / Batch 09 artifact root. It is
read-only: nothing here opens a file for writing, and :func:`guard_readable` refuses any
path that belongs to a frozen forward outcome window, so no code path in the application
can reach outcome bars even by accident.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Marks an artifact as belonging to the forward outcome window. Never readable here.
FORWARD_WINDOW_MARKERS = ("frozen-forward", "FROZEN_FORWARD")

#: Environment override for the private artifact root.
ARTIFACT_ROOT_ENV = "SQUEEZE_ARTIFACT_ROOT"

#: Default private root, relative to the repository root.
DEFAULT_RELATIVE_ROOT = Path("intake") / "local-bars" / "ibkr-batch-05"


class ForwardWindowAccessError(RuntimeError):
    """Raised when anything tries to read a frozen forward outcome artifact."""


def repository_root() -> Path:
    """The repository root, derived from this file's location.

    ``<root>/apps/research_screener/paths.py`` -> ``<root>``.
    """
    return Path(__file__).resolve().parents[2]


def artifact_root() -> Path:
    """The private artifact root, overridable for tests via ``SQUEEZE_ARTIFACT_ROOT``."""
    override = os.environ.get(ARTIFACT_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return (repository_root() / DEFAULT_RELATIVE_ROOT).resolve()


def guard_readable(path: Path | str) -> Path:
    """Return ``path`` unchanged, or raise if it is a forward outcome artifact."""
    text = str(path)
    for marker in FORWARD_WINDOW_MARKERS:
        if marker in text:
            raise ForwardWindowAccessError(
                f"refusing to read forward outcome artifact {text!r}: "
                "forward windows are outside this application's evidence boundary"
            )
    return Path(path)


def read_text(path: Path | str, encoding: str = "utf-8") -> str:
    """Guarded read. Every artifact read in this package goes through here."""
    return guard_readable(path).read_text(encoding=encoding)


class FrozenLayout:
    """Paths inside the private artifact root used by the frozen research mode."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else artifact_root()

    @property
    def batch08(self) -> Path:
        return self.root / "phase3a" / "batch-08"

    @property
    def batch_summary(self) -> Path:
        return self.batch08 / "batch-summary.json"

    @property
    def results_dir(self) -> Path:
        return self.batch08 / "results"

    @property
    def requests_dir(self) -> Path:
        return self.batch08 / "requests"

    @property
    def metrics_dir(self) -> Path:
        return self.batch08 / "metrics"

    @property
    def manifest(self) -> Path:
        return self.batch08 / "manifests" / "case-manifest.json"

    @property
    def preview_dir(self) -> Path:
        return self.root / "phase3b-preview-batch-09"

    @property
    def detection_preview(self) -> Path:
        return self.preview_dir / "detection-preview.json"

    @property
    def preview_summary(self) -> Path:
        return self.preview_dir / "preview-summary.json"

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    def detection_context_csv(self, symbol: str) -> Path:
        """Detection-context bars only. The sibling forward file is unreachable."""
        return guard_readable(self.raw_dir / f"{symbol}-detection-context.csv")

    @property
    def available(self) -> bool:
        return self.batch_summary.is_file() and self.results_dir.is_dir()


__all__ = [
    "ARTIFACT_ROOT_ENV",
    "DEFAULT_RELATIVE_ROOT",
    "FORWARD_WINDOW_MARKERS",
    "ForwardWindowAccessError",
    "FrozenLayout",
    "artifact_root",
    "guard_readable",
    "read_text",
    "repository_root",
]
