"""Output-path policy for tests that reproduce a tracked evidence artifact.

Committed evidence records a measurement at its recorded cutoff. Routine
validation re-measures on whatever host runs it, so writing the result over the
tracked file dirties every checkout with machine-specific timings. Tests write
to the process temporary directory unless a refresh is requested explicitly.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

REFRESH_ENVIRONMENT_VARIABLE = "IMP_REFRESH_TRACKED_EVIDENCE"


def evidence_output_path(tracked_path: Path) -> Path:
    """Return ``tracked_path`` on explicit refresh, otherwise a temporary twin."""

    if os.environ.get(REFRESH_ENVIRONMENT_VARIABLE) == "1":
        return tracked_path
    directory = Path(tempfile.gettempdir()) / "imp-tracked-evidence" / str(os.getpid())
    directory.mkdir(parents=True, exist_ok=True)
    return directory / tracked_path.name


__all__ = ["REFRESH_ENVIRONMENT_VARIABLE", "evidence_output_path"]
