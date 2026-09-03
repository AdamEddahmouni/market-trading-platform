"""Decision-research OOS gate validation (DECISION-RESEARCH-001 §12).

Loads the committed card + example fixtures, materializes the registry under
``evidence/research/experiment-cards/``, runs the OOS harness, asserts the
DEC-* invariants plus the empirically pinned expected statuses on the current
fixture scope, and writes ``evidence/research/decision-research-gate-report.json``.
The aggregate gate is PASS only if every assertion holds.

Usage:
    python tools/research/run_decision_research_gate_validation.py
        [--registry-root evidence/research/experiment-cards]
        [--report evidence/research/decision-research-gate-report.json]
        [--fail-fast]

Exit code 0 = PASS; non-zero = FAIL. Fails closed on any assertion violation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import load_json_strict, write_canonical_json
from market_platform_foundation.research.decision_research.cards import ExperimentCard
from market_platform_foundation.research.decision_research.harness import run_harness
from market_platform_foundation.research.decision_research.registry import ExperimentCardRegistry
from market_platform_foundation.research.decision_research.ss_cards import build_ss_family_cards

DEFAULT_REGISTRY_ROOT = ROOT / "evidence" / "research" / "experiment-cards"
DEFAULT_REPORT = ROOT / "evidence" / "research" / "decision-research-gate-report.json"
CARDS_FIXTURE = ROOT / "tests" / "fixtures" / "research" / "experiment_cards.json"
EXAMPLES_FIXTURE = ROOT / "tests" / "fixtures" / "research" / "ss_family_examples.json"

# Empirically verified expected gate report on the current fixture scope
# (pinned 2026-08-22). SS-BASE anchors INCONCLUSIVE and is never SUPPORTED.
EXPECTED_STATUSES: dict[str, str] = {
    "SS-BASE": "INCONCLUSIVE",
    "SS-OF": "INSUFFICIENT_DATA",
    "SS-CAT": "NEEDS_PROSPECTIVE_VALIDATION",
    "SS-MKT": "NEEDS_PROSPECTIVE_VALIDATION",
    "SS-OF-CAT": "INSUFFICIENT_DATA",
    "SS-FV-DISC": "NEEDS_PROSPECTIVE_VALIDATION",
}


def _assertion_checks(run: dict[str, Any]) -> list[str]:
    """Return a list of every violated DEC-* invariant (empty == all PASS)."""
    violations: list[str] = []
    # DEC-MAN-001 / DEC-PRE-001: authority + preregistration binding
    if run.get("execution_authority") != "NONE":
        violations.append("DEC-MAN-001: execution_authority != NONE")
    if run.get("auto_strategy_promotion") is not False:
        violations.append("DEC-MAN-001: auto_strategy_promotion != False")
    bound = set(run["bound_card_hashes"].values())
    for result in run["results"].values():
        if result.get("strategy_promotion") != "NONE":
            violations.append(f"DEC-MAN-001: {result['experiment_id']} strategy_promotion != NONE")
        if result.get("card_hash") not in bound:
            violations.append(f"DEC-PRE-001: {result['experiment_id']} result not registry-bound")
    # DEC-PIT-001: fold PIT statuses all PASS
    if set(run["fold_pit_status"].values()) != {"PASS"}:
        violations.append("DEC-PIT-001: a card had a failing fold-PIT status")
    # DEC-OOS-001: SS-BASE OOS = sum of fold test counts, never the full pool
    order_plan = run["fold_plan"]["SS-BASE"]
    if sum(f["test_count"] for f in order_plan) != run["results"]["SS-BASE"]["metrics"]["oos_count"]:
        violations.append("DEC-OOS-001: SS-BASE OOS count != sum of fold test counts")
    # DEC-INC-001 + expected statuses (fail closed, never SUPPORTED here)
    for eid, expected in EXPECTED_STATUSES.items():
        actual = run["results"][eid]["status"]
        if actual == "SUPPORTED":
            violations.append(f"DEC-INC-001: {eid} reached SUPPORTED on fixture scope")
        if actual != expected:
            violations.append(f"GATE_EXPECTED_STATUS: {eid}={actual} (expected {expected})")
    # DEC-DET-001: rerun produces an identical record (no RNG, no I/O drift)
    rerun = run_harness(
        build_ss_family_cards(), _load_examples(), registry=None
    )
    if rerun["run_root_hash"] != run["run_root_hash"]:
        violations.append("DEC-DET-001: rerun hash drifted")
    return violations


def _load_examples() -> list[dict[str, Any]]:
    return load_json_strict(EXAMPLES_FIXTURE)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-root", default=str(DEFAULT_REGISTRY_ROOT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    registry = ExperimentCardRegistry(Path(args.registry_root))
    cards = build_ss_family_cards()
    for payload in load_json_strict(CARDS_FIXTURE):
        registry.register(ExperimentCard.from_dict(payload))

    examples = _load_examples()
    run = run_harness(cards, examples, registry=registry)
    violations = _assertion_checks(run)

    aggregate = "PASS" if not violations else "FAIL"
    report = {
        "aggregate": aggregate,
        "run_id": run["run_id"],
        "run_root_hash": run["run_root_hash"],
        "family": run["family"],
        "card_count": len(cards),
        "example_count": len(examples),
        "results": run["results"],
        "oos_counts": run["oos_counts"],
        "fold_pit_status": run["fold_pit_status"],
        "execution_authority": run["execution_authority"],
        "auto_strategy_promotion": run["auto_strategy_promotion"],
        "registry_root": str(Path(args.registry_root)),
        "expected_statuses": EXPECTED_STATUSES,
        "violations": violations,
        "schema": "decision-research-gate-report",
    }
    write_canonical_json(Path(args.report), report)

    print(f"gate aggregate: {aggregate}")
    print(f"  run_id: {run['run_id']}")
    print(f"  run_root_hash: {run['run_root_hash']}")
    for eid in sorted(run["results"]):
        status = run["results"][eid]["status"]
        print(f"  {eid:10s} {status}")
        if status == "SUPPORTED":
            print(f"    !! {eid} adjudicated SUPPORTED on fixture scope")
    if violations:
        print("violations:")
        for violation in violations:
            print(f"  - {violation}")
    print(f"report: {Path(args.report)}")
    return 0 if aggregate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
