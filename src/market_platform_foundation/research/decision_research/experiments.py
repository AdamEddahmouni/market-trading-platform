"""Short squeeze decision research experiment family."""

from __future__ import annotations

from typing import Any

from .models import HypothesisLabel, ResearchHypothesis, ResearchResultStatus

SHORT_SQUEEZE_EXPERIMENTS: dict[str, ResearchHypothesis] = {
    "SS-BASE": ResearchHypothesis(
        hypothesis_id="SS-BASE",
        description="Canonical Short Squeeze baseline",
        label=HypothesisLabel.CONFIRMATORY,
        baseline_id="SS-BASE",
        added_evidence=(),
    ),
    "SS-OF": ResearchHypothesis(
        hypothesis_id="SS-OF",
        description="Baseline + Order Flow/CVD",
        label=HypothesisLabel.CONFIRMATORY,
        baseline_id="SS-BASE",
        added_evidence=("ORDER_FLOW_CVD",),
    ),
    "SS-CAT": ResearchHypothesis(
        hypothesis_id="SS-CAT",
        description="Baseline + Catalyst",
        label=HypothesisLabel.CONFIRMATORY,
        baseline_id="SS-BASE",
        added_evidence=("CATALYST",),
    ),
    "SS-MKT": ResearchHypothesis(
        hypothesis_id="SS-MKT",
        description="Baseline + Market Context",
        label=HypothesisLabel.CONFIRMATORY,
        baseline_id="SS-BASE",
        added_evidence=("MARKET_CONTEXT",),
    ),
    "SS-OF-CAT": ResearchHypothesis(
        hypothesis_id="SS-OF-CAT",
        description="Baseline + Order Flow + Catalyst",
        label=HypothesisLabel.EXPLORATORY,
        baseline_id="SS-BASE",
        added_evidence=("ORDER_FLOW_CVD", "CATALYST"),
    ),
    "SS-FV-DISC": ResearchHypothesis(
        hypothesis_id="SS-FV-DISC",
        description="Finviz discovery candidate + canonical lane",
        label=HypothesisLabel.EXPLORATORY,
        baseline_id="SS-BASE",
        added_evidence=("FINVIZ_DISCOVERY",),
    ),
}


def evaluate_experiment(
    hypothesis: ResearchHypothesis,
    examples: list[dict[str, Any]],
) -> dict[str, Any]:
    from .pit_gate import validate_temporal_example

    valid_examples = []
    for example in examples:
        ok, _ = validate_temporal_example(example)
        if ok:
            valid_examples.append(example)
    n = len(valid_examples)
    if n < 5:
        status = ResearchResultStatus.INSUFFICIENT_DATA
    elif n < 20:
        status = ResearchResultStatus.NEEDS_PROSPECTIVE_VALIDATION
    else:
        status = ResearchResultStatus.INCONCLUSIVE
    precision = 0.0
    if valid_examples:
        hits = sum(1 for ex in valid_examples if ex.get("outcome", {}).get("positive"))
        precision = hits / len(valid_examples)
    return {
        "experiment_id": hypothesis.hypothesis_id,
        "baseline_id": hypothesis.baseline_id,
        "added_evidence": list(hypothesis.added_evidence),
        "sample_count": n,
        "status": status.value,
        "metrics": {"precision": precision, "false_positive_rate": 1.0 - precision if precision else None},
        "strategy_promotion": "NONE",
    }
