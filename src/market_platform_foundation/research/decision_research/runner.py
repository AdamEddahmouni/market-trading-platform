"""Decision research runner.

Compatibility wrapper over the OOS harness: builds the fixed-hash SS-family
cards and runs ``run_harness`` (OOS-only evaluation). The canonical gate path
passes the committed registry via ``tools/research/run_decision_research_gate_validation.py``;
callers without one get run-record-bound (but not registry-presence-checked)
verification (``registry=None``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .harness import run_harness
from .ss_cards import build_ss_family_cards


def run_short_squeeze_family(
    examples: list[dict[str, Any]],
    *,
    registry: Any | None = None,
    family: str = "SHORT_SQUEEZE",
) -> dict[str, Any]:
    """Run the SS family end-to-end (cards -> OOS harness) and summarize."""
    if registry is None:
        registry = _committed_registry_or_none()
    cards = build_ss_family_cards()
    run = run_harness(cards, examples, registry=registry, family=family)
    results = run["results"]
    return {
        "family": family,
        "experiments": [results[cid] for cid in sorted(results)],
        "splits": {
            cid: dict(run["oos_counts"][cid]) for cid in sorted(run["oos_counts"])
        },
        "run_id": run["run_id"],
        "run_root_hash": run["run_root_hash"],
        "execution_authority": "NONE",
        "auto_strategy_promotion": False,
    }


def _committed_registry_or_none() -> Any | None:
    """Use the committed registry when it exists, else None (binding-only).

    The committed registry lives at ``evidence/research/experiment-cards/``;
    Task 10's gate tool materializes it. Until then binding-only verification
    keeps the runner usable in tests.
    """
    from .registry import ExperimentCardRegistry

    root = Path(__file__).resolve().parents[4] / "evidence" / "research" / "experiment-cards"
    registry = ExperimentCardRegistry(root)
    return registry if root.is_dir() else None


__all__ = ["run_short_squeeze_family"]
