"""Executable strategy-readiness vector.

Implements ``docs/research/STRATEGY_READINESS_MODEL.md`` so canonical status
is a ten-axis vector, not a single ``maturity`` field. Live eligibility is never
inferred from research, OOS, Paper, or calibration states.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

READINESS_SCHEMA_VERSION = "research/strategy_readiness/1.0.0"

_FORBIDDEN_KEYS = frozenset({"maturity", "overall_maturity", "readiness"})


class ReadinessAxis(StrEnum):
    RESEARCH_MATURITY = "research_maturity"
    DATA_READINESS_AND_RIGHTS = "data_readiness_and_rights"
    SIGNAL_STRATEGY_IMPLEMENTATION = "signal_strategy_implementation"
    HISTORICAL_OOS_VALIDATION = "historical_oos_validation"
    PROSPECTIVE_SHADOW = "prospective_shadow"
    PAPER_EXECUTION = "paper_execution"
    EXECUTION_MODEL_CALIBRATION = "execution_model_calibration"
    OPPORTUNITY_ENGINE_INTEGRATION = "opportunity_engine_integration"
    PORTFOLIO_RISK_INTEGRATION = "portfolio_risk_integration"
    LIVE_ELIGIBILITY = "live_eligibility"


class ReadinessAxisState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    PLANNED = "PLANNED"
    IMPLEMENTED = "IMPLEMENTED"
    VALIDATED = "VALIDATED"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


_READY_STATES = frozenset({ReadinessAxisState.IMPLEMENTED, ReadinessAxisState.VALIDATED})


class StrategyReadinessError(ValueError):
    """Fail-closed readiness-vector contract error."""


@dataclass(frozen=True, slots=True)
class ReadinessAxisRecord:
    state: ReadinessAxisState
    evidence_refs: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"state": self.state.value}
        if self.evidence_refs:
            payload["evidence_refs"] = list(self.evidence_refs)
        if self.notes:
            payload["notes"] = self.notes
        return payload


@dataclass(frozen=True, slots=True)
class StrategyReadinessVector:
    family_id: str
    axes: dict[ReadinessAxis, ReadinessAxisRecord]
    schema_version: str = READINESS_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "family_id": self.family_id,
            "axes": {axis.value: record.to_dict() for axis, record in self.axes.items()},
        }


def _parse_axis_record(raw: Any, *, axis: ReadinessAxis) -> ReadinessAxisRecord:
    if not isinstance(raw, Mapping):
        raise StrategyReadinessError(f"READINESS_AXIS_RECORD_INVALID:{axis.value}")
    try:
        state = ReadinessAxisState(str(raw.get("state") or "").strip())
    except ValueError as exc:
        raise StrategyReadinessError(f"READINESS_AXIS_STATE_INVALID:{axis.value}") from exc
    refs_raw = raw.get("evidence_refs") or ()
    if isinstance(refs_raw, str) or not isinstance(refs_raw, (list, tuple)):
        raise StrategyReadinessError(f"READINESS_EVIDENCE_REFS_INVALID:{axis.value}")
    evidence_refs = tuple(str(item).strip() for item in refs_raw if str(item).strip())
    if state is ReadinessAxisState.VALIDATED and not evidence_refs:
        raise StrategyReadinessError(f"READINESS_VALIDATED_EVIDENCE_REQUIRED:{axis.value}")
    notes = str(raw.get("notes") or "")
    return ReadinessAxisRecord(state=state, evidence_refs=evidence_refs, notes=notes)


def validate_readiness_vector(
    family_id: str,
    axes_payload: Mapping[str, Any],
) -> StrategyReadinessVector:
    family = str(family_id or "").strip().upper()
    if not family:
        raise StrategyReadinessError("STRATEGY_FAMILY_ID_REQUIRED")
    if not isinstance(axes_payload, Mapping):
        raise StrategyReadinessError("READINESS_AXES_REQUIRED")
    forbidden = _FORBIDDEN_KEYS.intersection(axes_payload)
    if forbidden:
        raise StrategyReadinessError("READINESS_MATURITY_FIELD_FORBIDDEN")
    missing = [axis.value for axis in ReadinessAxis if axis.value not in axes_payload]
    if missing:
        raise StrategyReadinessError(f"READINESS_AXIS_MISSING:{','.join(missing)}")
    extra = [key for key in axes_payload if key not in {axis.value for axis in ReadinessAxis}]
    if extra:
        raise StrategyReadinessError(f"READINESS_AXIS_UNKNOWN:{','.join(sorted(extra))}")
    axes = {
        axis: _parse_axis_record(axes_payload[axis.value], axis=axis) for axis in ReadinessAxis
    }
    return StrategyReadinessVector(family_id=family, axes=axes)


def live_eligibility_state(vector: StrategyReadinessVector) -> ReadinessAxisState:
    return vector.axes[ReadinessAxis.LIVE_ELIGIBILITY].state


def _axis_ready(vector: StrategyReadinessVector, axis: ReadinessAxis) -> bool:
    return vector.axes[axis].state in _READY_STATES


def derive_summary_label(vector: StrategyReadinessVector) -> str:
    """Compact label derived from the vector. Never infers Live eligibility."""

    live = live_eligibility_state(vector)
    research_core = (
        _axis_ready(vector, ReadinessAxis.RESEARCH_MATURITY)
        and _axis_ready(vector, ReadinessAxis.DATA_READINESS_AND_RIGHTS)
        and _axis_ready(vector, ReadinessAxis.SIGNAL_STRATEGY_IMPLEMENTATION)
    )
    oos_ready = research_core and _axis_ready(vector, ReadinessAxis.HISTORICAL_OOS_VALIDATION)
    shadow_ready = oos_ready and _axis_ready(vector, ReadinessAxis.PROSPECTIVE_SHADOW)
    paper_ready = (
        shadow_ready
        and _axis_ready(vector, ReadinessAxis.PAPER_EXECUTION)
        and _axis_ready(vector, ReadinessAxis.EXECUTION_MODEL_CALIBRATION)
    )
    if live is ReadinessAxisState.VALIDATED:
        return "LIVE_ELIGIBLE"
    if paper_ready:
        return "PAPER_READY"
    if shadow_ready:
        return "SHADOW_READY"
    if oos_ready:
        return "OOS_READY"
    if research_core:
        return "RESEARCH_READY"
    if any(record.state is ReadinessAxisState.BLOCKED for record in vector.axes.values()):
        return "BLOCKED"
    return "NOT_STARTED"


def _record(
    state: ReadinessAxisState,
    *evidence_refs: str,
    notes: str = "",
) -> dict[str, object]:
    payload: dict[str, object] = {"state": state.value}
    if evidence_refs:
        payload["evidence_refs"] = list(evidence_refs)
    if notes:
        payload["notes"] = notes
    return payload


def _planned_family(
    family_id: str,
    *,
    implementation: ReadinessAxisState = ReadinessAxisState.PLANNED,
    impl_refs: tuple[str, ...] = (),
    impl_notes: str = "",
    research_state: ReadinessAxisState = ReadinessAxisState.PLANNED,
    research_refs: tuple[str, ...] = (),
    data_state: ReadinessAxisState = ReadinessAxisState.PLANNED,
    data_refs: tuple[str, ...] = (),
    oos_state: ReadinessAxisState = ReadinessAxisState.NOT_STARTED,
    oos_refs: tuple[str, ...] = (),
    oos_notes: str = "",
) -> StrategyReadinessVector:
    payload = {
        ReadinessAxis.RESEARCH_MATURITY.value: _record(research_state, *research_refs),
        ReadinessAxis.DATA_READINESS_AND_RIGHTS.value: _record(data_state, *data_refs),
        ReadinessAxis.SIGNAL_STRATEGY_IMPLEMENTATION.value: _record(
            implementation, *impl_refs, notes=impl_notes
        ),
        ReadinessAxis.HISTORICAL_OOS_VALIDATION.value: _record(oos_state, *oos_refs, notes=oos_notes),
        ReadinessAxis.PROSPECTIVE_SHADOW.value: _record(ReadinessAxisState.NOT_STARTED),
        ReadinessAxis.PAPER_EXECUTION.value: _record(ReadinessAxisState.PLANNED),
        ReadinessAxis.EXECUTION_MODEL_CALIBRATION.value: _record(
            ReadinessAxisState.BLOCKED,
            notes="Paper simulator calibration numerics remain UNSET/BLOCKING.",
        ),
        ReadinessAxis.OPPORTUNITY_ENGINE_INTEGRATION.value: _record(ReadinessAxisState.PLANNED),
        ReadinessAxis.PORTFOLIO_RISK_INTEGRATION.value: _record(ReadinessAxisState.PLANNED),
        ReadinessAxis.LIVE_ELIGIBILITY.value: _record(
            ReadinessAxisState.BLOCKED,
            notes="Live eligibility is independently governed and is not inferred.",
        ),
    }
    return validate_readiness_vector(family_id, payload)


class StrategyReadinessRegistry:
    """Fail-closed in-memory registry. Unknown families do not invent status."""

    def __init__(self, vectors: tuple[StrategyReadinessVector, ...] = ()) -> None:
        self._by_family = {row.family_id: row for row in vectors}

    def require(self, family_id: str) -> StrategyReadinessVector:
        key = str(family_id or "").strip().upper()
        try:
            return self._by_family[key]
        except KeyError as exc:
            raise StrategyReadinessError(f"UNKNOWN_STRATEGY_FAMILY:{key}") from exc

    def list_families(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_family))


def builtin_family_catalog() -> StrategyReadinessRegistry:
    """Honest seed vectors from existing research code. No Live. No invented edge."""

    squeeze = _planned_family(
        "SHORT_SQUEEZE",
        research_state=ReadinessAxisState.IMPLEMENTED,
        research_refs=(
            "src/market_platform_foundation/research/decision_research/ss_cards.py",
            "docs/research/STRATEGY_READINESS_MODEL.md",
        ),
        data_state=ReadinessAxisState.IMPLEMENTED,
        data_refs=("src/market_platform_foundation/research/decision_research/pit_gate.py",),
        implementation=ReadinessAxisState.IMPLEMENTED,
        impl_refs=(
            "src/market_platform_foundation/research/squeeze_models/",
            "src/market_platform_foundation/research/decision_research/",
        ),
        oos_state=ReadinessAxisState.IMPLEMENTED,
        oos_refs=("evidence/research/decision-research-gate-report.json",),
        oos_notes="SS-BASE INCONCLUSIVE; other SS cards need prospective data. Not VALIDATED.",
    )
    news = _planned_family(
        "NEWS_CATALYST",
        research_state=ReadinessAxisState.IMPLEMENTED,
        research_refs=("docs/architecture/NEWS_STRATEGY_EVALUATION.md",),
        data_state=ReadinessAxisState.IMPLEMENTED,
        data_refs=("src/market_platform_foundation/news/",),
        implementation=ReadinessAxisState.IMPLEMENTED,
        impl_refs=("src/market_platform_foundation/intelligence/news_strategy_evaluation/",),
        oos_state=ReadinessAxisState.IMPLEMENTED,
        oos_refs=("src/market_platform_foundation/intelligence/news_strategy_evaluation/",),
        oos_notes="Fixture/replay laboratory only; campaigns remain RECORDED_ARTIFACTS_ONLY.",
    )
    crypto = _planned_family(
        "CRYPTO_ONCHAIN",
        implementation=ReadinessAxisState.NOT_STARTED,
        impl_notes="Planning docs only; no runtime adapter.",
        research_state=ReadinessAxisState.PLANNED,
        research_refs=("docs/architecture/ON_CHAIN_INTELLIGENCE.md",),
        data_state=ReadinessAxisState.NOT_STARTED,
        oos_state=ReadinessAxisState.NOT_STARTED,
    )
    return StrategyReadinessRegistry((squeeze, news, crypto))


__all__ = [
    "READINESS_SCHEMA_VERSION",
    "ReadinessAxis",
    "ReadinessAxisRecord",
    "ReadinessAxisState",
    "StrategyReadinessError",
    "StrategyReadinessRegistry",
    "StrategyReadinessVector",
    "builtin_family_catalog",
    "derive_summary_label",
    "live_eligibility_state",
    "validate_readiness_vector",
]
