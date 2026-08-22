"""Prospective Finviz discovery capture — file-backed PIT artifacts."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..finviz.config import finviz_capture_root
from .models import CandidateSet

CAPTURE_SCHEMA_VERSION = "finviz.discovery_capture/1.0.0"
NO_RETROACTIVE_INVARIANT = "NO_RETROACTIVE_FINVIZ_SCREEN_RECONSTRUCTION"


def _imp_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def capture_run_directory(candidate_set: CandidateSet) -> Path:
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    return finviz_capture_root() / day / candidate_set.screen_id / candidate_set.run_id


def persist_discovery_capture(candidate_set: CandidateSet) -> Path:
    root = capture_run_directory(candidate_set)
    root.mkdir(parents=True, exist_ok=True)
    artifact = root / "candidate-set.json"
    payload = candidate_set.to_dict()
    payload["capture_schema_version"] = CAPTURE_SCHEMA_VERSION
    payload["imp_commit"] = _imp_commit()
    payload["pit_invariant"] = NO_RETROACTIVE_INVARIANT
    artifact.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    manifest = {
        "capture_id": candidate_set.run_id,
        "screen_id": candidate_set.screen_id,
        "screen_version": candidate_set.screen_version,
        "provider": candidate_set.provider,
        "artifact_path": str(artifact.resolve()),
        "candidate_count": candidate_set.candidate_count,
        "available_time_ns": candidate_set.available_time_ns,
        "received_at": candidate_set.received_at,
        "candidate_symbols": candidate_set.symbols(),
    }
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")
    candidate_set.capture_artifact_path = str(artifact.resolve())
    return artifact


def load_discovery_capture(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("CAPTURE_CORRUPT")
    return raw


def replay_capture_equivalence(live: CandidateSet, replayed: dict[str, Any]) -> dict[str, Any]:
    live_payload = live.to_dict()
    replay_candidates = replayed.get("candidates") or []
    live_candidates = live_payload.get("candidates") or []
    live_symbols = sorted(c.get("instrument_id") for c in live_candidates)
    replay_symbols = sorted(c.get("instrument_id") for c in replay_candidates)
    reasons_match = all(
        live_candidates[i].get("matched_reasons") == replay_candidates[i].get("matched_reasons")
        for i in range(min(len(live_candidates), len(replay_candidates)))
    )
    return {
        "symbols_match": live_symbols == replay_symbols,
        "candidate_count_match": len(live_candidates) == len(replay_candidates),
        "screen_id_match": live_payload.get("screen_id") == replayed.get("screen_id"),
        "screen_version_match": live_payload.get("screen_version") == replayed.get("screen_version"),
        "reasons_match": reasons_match,
        "equivalent": live_symbols == replay_symbols and reasons_match,
    }
