"""Git SHA + simulator identity for reconstructable forward-test runs."""

from __future__ import annotations

from typing import Any

from ...execution.simulator import SIMULATOR_VERSION
from ...git_ref import read_git_head


def run_identity() -> dict[str, str]:
    return {
        "git_sha": read_git_head() or "UNAVAILABLE",
        "simulator_version": SIMULATOR_VERSION,
    }


def stamp_provenance(provenance: dict[str, Any]) -> dict[str, Any]:
    stamped = dict(provenance)
    identity = run_identity()
    stamped.setdefault("git_sha", identity["git_sha"])
    stamped.setdefault("simulator_version", identity["simulator_version"])
    return stamped
