"""Environment profile for CONTROLLED REPLAY (never Live, isolated state)."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from tools.controlled_replay import (
    CONTROLLED_REPLAY_FLAG,
    CONTROLLED_REPLAY_STATE_DIRNAME,
)

# Live / broker gates that must stay off for controlled replay.
_FORBIDDEN_LIVE_DEFAULTS = (
    "IMP_LIVE_OBSERVATIONAL",
    "IMP_LIVE_EXECUTION",
    "IMP_BROKER_LIVE_EXECUTION",
    "IMP_MOOMOO_LIVE",
    "IMP_IBKR_LIVE",
    "IMP_FINVIZ_LIVE",
    "IMP_LIVE_FIXTURE_FEED",
    "IMP_LIVE_INTERNAL_SIMULATION",
)


def controlled_replay_state_dir(root: Path) -> Path:
    return (root / ".local" / CONTROLLED_REPLAY_STATE_DIRNAME).resolve()


def build_controlled_replay_environment(
    environ: Mapping[str, str],
    *,
    root: Path,
) -> dict[str, str]:
    """Build backend env for controlled replay.

    Forces FIXTURE_REPLAY posture via absent live gates, isolates durable state
    under ``.local/controlled-replay/``, enables SQLite persistence for the
    golden path (acks / DecisionTrace / TradeReview), and never enables Live
    execution authority.
    """

    result = {str(key): str(value) for key, value in environ.items()}
    state_dir = controlled_replay_state_dir(root)
    state_dir.mkdir(parents=True, exist_ok=True)

    for key in _FORBIDDEN_LIVE_DEFAULTS:
        result.pop(key, None)

    forced = {
        CONTROLLED_REPLAY_FLAG: "1",
        "IMP_PERSIST_STATE": "1",
        "IMP_STATE_DIR": str(state_dir),
        "PYTHONUNBUFFERED": "1",
        # Paper submit stays off — Demo mutations prohibited; preview-only if used.
        "IMP_PAPER_EXECUTION": "0",
    }
    for key, value in forced.items():
        result[key] = value
    return result


def is_controlled_replay_enabled(environ: Mapping[str, str] | None = None) -> bool:
    import os

    env = os.environ if environ is None else environ
    return str(env.get(CONTROLLED_REPLAY_FLAG) or "").strip() in {"1", "true", "yes"}
