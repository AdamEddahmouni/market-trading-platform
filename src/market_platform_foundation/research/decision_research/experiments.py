"""Short squeeze decision research experiment family (DECISION-RESEARCH-001 §6).

``SHORT_SQUEEZE_EXPERIMENTS`` remains the declared family source (spec §2/§6).
``evaluate_experiment`` is card-driven: it requires a hash-bound
``ExperimentCard`` (raising fail-closed without one), reports **OOS-only**
metrics, and derives status from the card's ``min_sample_oos`` /
``primary_metric`` / ``primary_metric_threshold`` instead of hard-coded 5/20
thresholds.

Settled Task 6 semantics (see implementation plan). ``|subset|`` means the
card's **evidence-bearing pool** (``pool_count``, passed by the harness);
precision/base-rate are computed only over the actually-held-out OOS examples
(``DEC-OOS-001``):
- ``|subset| == 0`` -> ``INSUFFICIENT_DATA``, except when a required evidence
  family is a prospective-capture family (``FINVIZ_DISCOVERY``), which means
  the card is blocked on capture -> ``NEEDS_PROSPECTIVE_VALIDATION``.
- ``0 < |subset| < min_sample_oos`` -> ``NEEDS_PROSPECTIVE_VALIDATION``.
- ``|subset| >= min_sample_oos``:
  - SS-BASE anchor (absolute ``oos_positive_base_rate``) -> ``INCONCLUSIVE`` and
    never ``SUPPORTED`` (guard test).
  - augmentation (``oos_precision_delta_vs_baseline``): ``SUPPORTED`` iff
    CONFIRMATORY and ``delta >= threshold`` and ``delta > 0``; an EXPLORATORY
    edge resolves ``NOT_SUPPORTED`` (preregistered rule); otherwise
    ``NOT_SUPPORTED``.
"""

from __future__ import annotations

from typing import Any

from .cards import ExperimentCard
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

# Evidence families whose labeled data can only be produced prospectively
# (never reconstructed from history — DEC-FV-001). A card blocked on one of
# these resolves NEEDS_PROSPECTIVE_VALIDATION rather than INSUFFICIENT_DATA.
PROSPECTIVE_CAPTURE_FAMILIES = frozenset({"FINVIZ_DISCOVERY"})


def evaluate_experiment(
    card: ExperimentCard,
    oos_examples: list[dict[str, Any]],
    *,
    baseline_rate: float | None = None,
    registry: Any | None = None,
    pool_count: int | None = None,
) -> dict[str, Any]:
    """Card-driven, OOS-only evaluation. Fail-closed on a missing card.

    ``oos_examples`` must already be the PIT-validated, evidence-bearing OOS
    slice the harness held out (metrics are OOS-only). ``pool_count`` is the
    card's full evidence-bearing pool size in this run and gates the
    ``min_sample_oos`` threshold (settled semantics: ``|subset| >= min_sample_oos``).
    """
    if not isinstance(card, ExperimentCard):
        raise ValueError("EXPERIMENT_CARD_REQUIRED")
    if registry is not None and not registry.has(card.card_hash):
        raise ValueError(f"EXPERIMENT_CARD_NOT_REGISTERED: {card.card_hash}")

    from .pit_gate import validate_temporal_example

    valid = [ex for ex in oos_examples if validate_temporal_example(ex)[0]]
    n = len(valid)
    hits = sum(1 for ex in valid if (ex.get("outcome") or {}).get("positive"))
    precision = hits / n if n else 0.0
    required = [str(f) for f in (card.feature_spec or {}).get("required", [])]
    pool = pool_count if pool_count is not None else n

    delta: float | None
    if pool == 0:
        if any(f in PROSPECTIVE_CAPTURE_FAMILIES for f in required):
            status = ResearchResultStatus.NEEDS_PROSPECTIVE_VALIDATION
        else:
            status = ResearchResultStatus.INSUFFICIENT_DATA
        delta = None
    elif pool < card.min_sample_oos:
        status = ResearchResultStatus.NEEDS_PROSPECTIVE_VALIDATION
        delta = round(precision - baseline_rate, 6) if baseline_rate is not None else None
    else:
        if card.primary_metric == "oos_positive_base_rate":
            # SS-BASE anchor: measured, never adjudicated (never SUPPORTED).
            status = ResearchResultStatus.INCONCLUSIVE
            delta = 0.0
        else:
            base = baseline_rate if baseline_rate is not None else 0.0
            delta = round(precision - base, 6)
            edge = delta >= card.primary_metric_threshold and delta > 0.0
            if not edge or card.hypothesis_label == HypothesisLabel.EXPLORATORY.value:
                status = ResearchResultStatus.NOT_SUPPORTED
            else:
                status = ResearchResultStatus.SUPPORTED

    return {
        "experiment_id": card.experiment_id,
        "baseline_id": card.baseline_id,
        "added_evidence": list(card.added_evidence),
        "sample_count": n,
        "status": status.value,
        "metrics": {
            "oos_count": n,
            "oos_precision": round(precision, 6),
            "oos_positive_base_rate": round(hits / n, 6) if n else 0.0,
            "pool_count": pool,
        },
        "incremental_vs_baseline": {
            "baseline_rate": baseline_rate,
            "delta_vs_baseline": delta,
        },
        "card_hash": card.card_hash,
        "strategy_promotion": "NONE",
    }


__all__ = [
    "PROSPECTIVE_CAPTURE_FAMILIES",
    "SHORT_SQUEEZE_EXPERIMENTS",
    "evaluate_experiment",
]
