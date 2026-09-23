"""Reset ONLY the namespaced controlled-replay state root."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from tools.controlled_replay.env import controlled_replay_state_dir

CONTROLLED_REPLAY_MARKER = "controlled-replay"


def reset_controlled_replay_state(root: Path) -> dict[str, Any]:
    """Delete ``.local/controlled-replay/`` only.

    Never touches canonical ``.local`` empirical evidence, FTEP state, RTH
    campaign receipts, Paper history outside this namespace, or credentials.
    """

    target = controlled_replay_state_dir(root)
    canonical_local = (root / ".local").resolve()
    if target == canonical_local:
        return {
            "ok": False,
            "reason": "REFUSED_CANONICAL_LOCAL",
            "path": str(target),
        }
    if CONTROLLED_REPLAY_MARKER not in str(target).replace("\\", "/"):
        return {
            "ok": False,
            "reason": "REFUSED_PATH_NOT_NAMESPACED",
            "path": str(target),
        }
    existed = target.exists()
    if existed:
        try:
            shutil.rmtree(target)
        except PermissionError as exc:
            return {
                "ok": False,
                "reason": "STATE_LOCKED_STOP_STACK_FIRST",
                "path": str(target),
                "detail": str(exc),
                "hint": "Run: python tools/imp.py controlled-replay stop",
            }
    target.mkdir(parents=True, exist_ok=True)
    return {
        "ok": True,
        "path": str(target),
        "deleted_prior": existed,
        "evidence_class": "CONTROLLED_REPLAY",
        "note": "Only controlled-replay durable state was reset.",
    }
