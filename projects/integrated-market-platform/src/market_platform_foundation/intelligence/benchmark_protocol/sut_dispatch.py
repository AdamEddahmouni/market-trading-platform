"""Dispatch IBP SUT runners by frozen profile id."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .facts_sut import run_ibp_facts_sut
from .sut_profiles import IBP_FACTS_SUT_PROFILE_ID, IBP_SYNTHETIC_SUT_PROFILE_ID, SutRunner, resolve_sut_profile
from .synthetic_sut import run_synthetic_intelligence_sut


def resolve_sut_runner(profile_id: str, *, repository_root: Path) -> SutRunner:
    profile = resolve_sut_profile(profile_id)
    if profile.runner_id == "synthetic":
        return run_synthetic_intelligence_sut
    if profile.runner_id == "facts":

        def _facts_runner(blind_input: dict[str, Any]) -> dict[str, Any]:
            return run_ibp_facts_sut(blind_input, repository_root=repository_root)

        return _facts_runner
    raise ValueError(f"IBP_SUT_RUNNER_UNKNOWN:{profile.runner_id}")


__all__ = [
    "IBP_FACTS_SUT_PROFILE_ID",
    "IBP_SYNTHETIC_SUT_PROFILE_ID",
    "resolve_sut_runner",
]
