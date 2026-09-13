"""Real (non-fixture) Paper/Demo strategy catalog for the Path A one-shot hop.

This wires the existing, already-shipped baseline strategy interpretations
(``FORECAST_MOMENTUM`` / ``WHALE_ALIGNED`` / ``WHALE_CONTRARIAN`` from
``strategy/evaluation.py``) into the ``UniversalStrategyScanner`` contract so
Path A's Paper/Demo honesty invoke stops shipping ``strategies=()``.

Honesty boundary: these alignments are documented (``strategy_spec.py``) as
``baseline_only`` interpretations of a naive last-value score — "not tradable
edges". Catalog evaluators never mint a Phase-6 record at eval time. They receive a
previously persisted Phase-6 record from ``build_paper_demo_path_a_invoke``
only when identity matches and ``registered_at`` is before quote
``event_time_ns``; otherwise ``preregistration=None`` and evaluation
legitimately abstains on ``ABSTAIN_NO_PREREGISTRATION`` (whale alignments also
``ABSTAIN_INSTITUTIONAL_UNAVAILABLE`` — no ``WhaleLedger`` on this hop).
This module never returns a hardcoded ``MATCHED`` disposition.

A scanner MATCHED from a lawful loaded record is still not an Opportunity
Engine EMIT unless a PRODUCTION ``ForecastV1`` is produced or loaded through
the fail-closed hop. Create on the hop is ``produce_paper_demo_forecast``
(BUILD 14 fusion) from caller-supplied PRODUCTION contributors plus a
pre-existing calibrator; absent either input is ``FORECAST_UNAVAILABLE``.
The catalog never mints a probability from last_price and never calls
``build_preregistration``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..intelligence.contracts import StrategyMatchDisposition
from ..research.forecast import build_forecast, verify_forecast_interface
from .evaluation import (
    default_forecast_momentum_spec,
    default_whale_aligned_spec,
    default_whale_contrarian_spec,
)
from .interpretation import interpret_strategy
from .scanning import StrategyEvaluationContext, StrategyEvaluationResult, StrategyRegistration
from .strategy_spec import StrategyDefinition, coerce_strategy_spec

PATH_A_CATALOG_HORIZON_NS = 300_000_000_000

NO_PREREGISTRATION_REASON = "ABSTAIN_NO_PREREGISTRATION"
NO_QUOTE_OBSERVATION_REASON = "FCAST_NO_QUOTE_OBSERVATION"

_CATALOG_SPEC_FACTORIES = (
    default_forecast_momentum_spec,
    default_whale_aligned_spec,
    default_whale_contrarian_spec,
)


def _quote_score(quote: Mapping[str, Any] | None) -> tuple[str, bool]:
    if not isinstance(quote, Mapping):
        return "0", False
    last_price = quote.get("last_price")
    if last_price is None:
        return "0", False
    try:
        return str(float(last_price)), True
    except (TypeError, ValueError):
        return "0", False


def _forecast_for_context(context: StrategyEvaluationContext) -> tuple[dict[str, Any], int]:
    decision_time_ns = context.capability_snapshot.as_of_time_ns
    raw_context = context.capability_snapshot.context
    quote = raw_context.get("quote") if isinstance(raw_context, Mapping) else None
    score, observed = _quote_score(quote)
    observation_time_ns = decision_time_ns
    if observed and isinstance(quote, Mapping):
        candidate = quote.get("event_time_ns")
        if isinstance(candidate, int) and 0 <= candidate <= decision_time_ns:
            observation_time_ns = candidate
    forecast = (
        build_forecast(
            score=score,
            prediction_cutoff=decision_time_ns,
            horizon_ns=PATH_A_CATALOG_HORIZON_NS,
        )
        if observed
        else build_forecast(
            score=score,
            prediction_cutoff=decision_time_ns,
            horizon_ns=PATH_A_CATALOG_HORIZON_NS,
            status="fallback",
            fallback_reason_code=NO_QUOTE_OBSERVATION_REASON,
        )
    )
    return forecast, observation_time_ns


def _baseline_interpretation_evaluator(
    spec: dict[str, Any],
    preregistration: dict[str, Any] | None = None,
):
    def evaluator(context: StrategyEvaluationContext) -> StrategyEvaluationResult:
        forecast, observation_time_ns = _forecast_for_context(context)
        forecast_status, _ = verify_forecast_interface(forecast)
        decision_time_ns = context.capability_snapshot.as_of_time_ns
        # Loaded by the invoke builder, not minted here. preregistration=None
        # when no stored record is eligible.
        loaded = preregistration
        interpretation = interpret_strategy(
            strategy_spec=spec,
            preregistration=loaded,
            forecast=forecast,
            forecast_status=forecast_status,
            prediction_cutoff=decision_time_ns,
            observation_time=observation_time_ns,
        )
        if interpretation["outcome"] == "signal":
            return StrategyEvaluationResult(disposition=StrategyMatchDisposition.MATCHED)
        reasons = tuple(interpretation.get("abstention_reason_codes") or ())
        return StrategyEvaluationResult(
            disposition=StrategyMatchDisposition.ABSTAINED,
            abstention_reasons=reasons or (NO_PREREGISTRATION_REASON,),
        )

    return evaluator


def _registration_for_spec(
    spec: dict[str, Any],
    preregistration: dict[str, Any] | None = None,
) -> StrategyRegistration:
    definition = StrategyDefinition.from_legacy_spec(spec)
    alignment = str(spec["alignment_type"]).lower().replace("_", "-")
    return StrategyRegistration(
        strategy_id=f"path-a-baseline-{alignment}",
        definition=definition,
        evaluator=_baseline_interpretation_evaluator(
            coerce_strategy_spec(spec),
            preregistration=preregistration,
        ),
    )


def paper_demo_catalog_specs() -> tuple[dict[str, Any], ...]:
    return tuple(factory() for factory in _CATALOG_SPEC_FACTORIES)


def build_paper_demo_strategy_catalog(
    preregistrations: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[StrategyRegistration, ...]:
    """Real (non-fixture) baseline strategy catalog for Paper/Demo Path A.

    Every entry is a genuine ``StrategyRegistration`` backed by the existing
    production ``interpret_strategy`` evaluator — never a hardcoded
    disposition. ``preregistrations`` is an identity-hash map of records the
    invoke builder already selected as eligible. Missing keys stay
    ``preregistration=None``.
    """

    loaded = preregistrations or {}
    rows: list[StrategyRegistration] = []
    for spec in paper_demo_catalog_specs():
        identity = str(spec["strategy_identity_hash"])
        record = loaded.get(identity)
        record_dict = dict(record) if isinstance(record, Mapping) else None
        rows.append(_registration_for_spec(spec, preregistration=record_dict))
    return tuple(rows)


__all__ = [
    "NO_PREREGISTRATION_REASON",
    "NO_QUOTE_OBSERVATION_REASON",
    "PATH_A_CATALOG_HORIZON_NS",
    "build_paper_demo_strategy_catalog",
    "paper_demo_catalog_specs",
]
