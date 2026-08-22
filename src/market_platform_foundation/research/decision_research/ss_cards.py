"""The short-squeeze experiment family as fixed-hash preregistered cards.

The six cards mirror ``SHORT_SQUEEZE_EXPERIMENTS`` (spec §6) with the settled
Task 6 definitions: per-card ``min_sample_oos`` / ``primary_metric`` /
``primary_metric_threshold`` and the 30-minute default horizon. ``SS-BASE``
anchors with the absolute ``oos_positive_base_rate``; every augmentation card
uses ``oos_precision_delta_vs_baseline``.
"""

from __future__ import annotations

from typing import Any

from ...normalization.equity_bars import iso_to_epoch_ns
from .cards import DEFAULT_EVALUATION_WINDOW, DEFAULT_OUTCOME_SPEC, ExperimentCard

PREREG_ISO = "2026-08-22T00:00:00.000000000Z"


def _feature_spec(required: list[str]) -> dict[str, Any]:
    return {
        "required": sorted(required),
        "min_quality": {},
        "min_freshness_ms": {},
    }


def build_ss_family_cards(*, preregistered_at_ns: int | None = None) -> dict[str, ExperimentCard]:
    """Deterministic SS-family card set with fixed hashes (Task 3)."""
    prereg = preregistered_at_ns if preregistered_at_ns is not None else iso_to_epoch_ns(PREREG_ISO)
    cards: dict[str, ExperimentCard] = {}

    def add(
        experiment_id: str,
        label: str,
        added_evidence: tuple[str, ...],
        min_sample_oos: int,
        primary_metric: str,
        threshold: float,
        baseline_id: str = "SS-BASE",
        required: list[str] | None = None,
    ) -> None:
        required = required or (["SQUEEZE_STATE"] + list(added_evidence))
        cards[experiment_id] = ExperimentCard(
            experiment_id=experiment_id,
            family="SHORT_SQUEEZE",
            hypothesis_label=label,
            baseline_id=baseline_id,
            added_evidence=added_evidence,
            feature_spec=_feature_spec(required),
            outcome_spec=dict(DEFAULT_OUTCOME_SPEC),
            inclusion_criteria=("admitted_fixture", "pit_gate_required"),
            exclusion_criteria=("no_retroactive_finviz",),
            primary_metric=primary_metric,
            min_sample_oos=min_sample_oos,
            primary_metric_threshold=threshold,
            evaluation_window=dict(DEFAULT_EVALUATION_WINDOW),
            preregistered_at_ns=prereg,
        )

    add("SS-BASE", "CONFIRMATORY", (), 150, "oos_positive_base_rate", 0.0)
    add("SS-OF", "CONFIRMATORY", ("ORDER_FLOW_CVD",), 30, "oos_precision_delta_vs_baseline", 0.05)
    add("SS-CAT", "CONFIRMATORY", ("CATALYST",), 30, "oos_precision_delta_vs_baseline", 0.05)
    add("SS-MKT", "CONFIRMATORY", ("MARKET_CONTEXT",), 45, "oos_precision_delta_vs_baseline", 0.05)
    add("SS-OF-CAT", "EXPLORATORY", ("ORDER_FLOW_CVD", "CATALYST"), 30, "oos_precision_delta_vs_baseline", 0.05)
    add(
        "SS-FV-DISC",
        "EXPLORATORY",
        ("FINVIZ_DISCOVERY",),
        30,
        "oos_precision_delta_vs_baseline",
        0.05,
        required=["SQUEEZE_STATE", "FINVIZ_DISCOVERY"],
    )
    return cards


__all__ = ["PREREG_ISO", "build_ss_family_cards"]
