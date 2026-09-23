"""Operator-facing diagnostic model — composes existing IMP surfaces."""

from __future__ import annotations

from typing import Any

from .operator_truth import (
    OPERATOR_TRUTH_CLASSES,
    build_operator_truth_section,
    map_item9_corpus_progress_truth,
)

__all__ = [
    "OPERATOR_TRUTH_CLASSES",
    "build_operator_diagnostics_snapshot",
    "build_operator_truth_section",
    "map_item9_corpus_progress_truth",
]


def __getattr__(name: str) -> Any:
    # Lazy: snapshot pulls local_state / paper / intelligence; leaf modules
    # (campaign_supervision, campaign_observation_readiness) must stay importable alone.
    if name == "build_operator_diagnostics_snapshot":
        from .snapshot import build_operator_diagnostics_snapshot

        return build_operator_diagnostics_snapshot
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
