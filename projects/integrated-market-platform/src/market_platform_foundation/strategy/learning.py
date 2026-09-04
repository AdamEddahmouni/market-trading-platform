"""Bounded, non-promotional learning boundary for strategy observations.

This module joins existing immutable contracts for research consumption.  It
does not train, select, promote, allocate, or execute anything.  In
particular, trading attribution is an optional, independently labelled
sidecar and is never combined with prediction quality.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..intelligence.contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    QualityState,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    normalize_unique_refs,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)
from ..intelligence.contracts.forecast import (
    ForecastV1,
    forecast_v1_from_dict,
    forecast_v1_to_dict,
)
from ..intelligence.contracts.outcome import (
    OutcomeV1,
    outcome_v1_from_dict,
    outcome_v1_to_dict,
)
from ..intelligence.contracts.strategy_match import (
    StrategyMatch,
    StrategyMatchDisposition,
    strategy_match_from_dict,
    strategy_match_to_dict,
)
from ..intelligence.research_experiments.types import EvidenceTier
from ..portfolio.attribution import (
    StrategyAttributionV1,
    attribution_v1_from_dict,
    attribution_v1_to_dict,
)


LEARNING_POLICY_VERSION = "strategy-learning/1.0.0"


class LearningSettlementState(StrEnum):
    """Whether the prediction outcome has reached a terminal settlement."""

    UNSETTLED = "UNSETTLED"
    SETTLED = "SETTLED"


class LearningLabelState(StrEnum):
    """Whether a settled prediction can provide a learning label."""

    PENDING = "PENDING"
    LABELABLE = "LABELABLE"
    UNLABELABLE = "UNLABELABLE"


class LearningEligibility(StrEnum):
    """Decision returned by the bounded learning gate."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    INCONCLUSIVE = "INCONCLUSIVE"


def _normalize_mode(value: str) -> str:
    normalized = str(value).strip().upper()
    return {"LIVE": "ACTUAL_LIVE"}.get(normalized, normalized)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _ref_key(ref: ContractReference) -> tuple[str, str, str]:
    return ref.kind, ref.id, ref.schema_version


def _normalize_ref(value: ContractReference, *, expected_kind: str) -> ContractReference:
    ref = value if isinstance(value, ContractReference) else contract_reference_from_dict(value)
    if ref.kind != expected_kind:
        raise ValueError(f"LEARNING_{expected_kind.upper()}_REF_KIND_INVALID")
    return ref


@dataclass(frozen=True, slots=True)
class LearningObservationV1:
    """Immutable reference-only observation at a strategy decision boundary."""

    observation_id: str
    account_id: str
    mode: str
    strategy_id: str
    strategy_identity_hash: str
    strategy_match_ref: ContractReference
    forecast_ref: ContractReference
    prediction_outcome_ref: ContractReference | None
    trading_attribution_ref: ContractReference | None
    opportunity_ref: ContractReference | None
    cluster_ref: ContractReference | None
    evidence_tier: EvidenceTier
    evidence_mode: str
    decision_time_ns: int
    settlement_time_ns: int | None
    settlement_state: LearningSettlementState
    label_state: LearningLabelState
    schema_version: str = INTELLIGENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        validate_id(self.observation_id, field_name="observation_id")
        validate_schema_version(self.schema_version)
        validate_id(self.account_id, field_name="account_id")
        validate_id(self.strategy_id, field_name="strategy_id")
        validate_id(self.strategy_identity_hash, field_name="strategy_identity_hash")
        object.__setattr__(self, "mode", _normalize_mode(self.mode))
        object.__setattr__(self, "evidence_mode", str(self.evidence_mode).strip().upper())
        if not self.mode:
            raise ValueError("LEARNING_MODE_REQUIRED")
        if not self.evidence_mode:
            raise ValueError("LEARNING_EVIDENCE_MODE_REQUIRED")
        if not isinstance(self.evidence_tier, EvidenceTier):
            object.__setattr__(self, "evidence_tier", EvidenceTier(str(self.evidence_tier)))
        if not isinstance(self.settlement_state, LearningSettlementState):
            object.__setattr__(
                self,
                "settlement_state",
                LearningSettlementState(str(self.settlement_state)),
            )
        if not isinstance(self.label_state, LearningLabelState):
            object.__setattr__(self, "label_state", LearningLabelState(str(self.label_state)))
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        if self.settlement_time_ns is not None:
            validate_timestamp_ns(self.settlement_time_ns, field_name="settlement_time_ns")
        object.__setattr__(
            self,
            "strategy_match_ref",
            _normalize_ref(self.strategy_match_ref, expected_kind="strategy_match"),
        )
        object.__setattr__(
            self,
            "forecast_ref",
            _normalize_ref(self.forecast_ref, expected_kind="forecast"),
        )
        if self.prediction_outcome_ref is not None:
            object.__setattr__(
                self,
                "prediction_outcome_ref",
                _normalize_ref(self.prediction_outcome_ref, expected_kind="outcome"),
            )
        if self.trading_attribution_ref is not None:
            object.__setattr__(
                self,
                "trading_attribution_ref",
                _normalize_ref(
                    self.trading_attribution_ref,
                    expected_kind="strategy_attribution",
                ),
            )
        if self.opportunity_ref is not None:
            object.__setattr__(
                self,
                "opportunity_ref",
                _normalize_ref(self.opportunity_ref, expected_kind="opportunity"),
            )
        if self.cluster_ref is not None:
            cluster_ref = (
                self.cluster_ref
                if isinstance(self.cluster_ref, ContractReference)
                else contract_reference_from_dict(self.cluster_ref)
            )
            if cluster_ref.kind not in {"cluster", "thesis", "thesis_cluster"}:
                raise ValueError("LEARNING_CLUSTER_REF_KIND_INVALID")
            object.__setattr__(self, "cluster_ref", cluster_ref)
        if self.settlement_state == LearningSettlementState.UNSETTLED:
            if self.settlement_time_ns is not None:
                raise ValueError("UNSETTLED_SETTLEMENT_TIME_FORBIDDEN")
            if self.label_state != LearningLabelState.PENDING:
                raise ValueError("UNSETTLED_LABEL_STATE_INVALID")
        else:
            if self.settlement_time_ns is None:
                raise ValueError("SETTLED_SETTLEMENT_TIME_REQUIRED")
            if self.prediction_outcome_ref is None:
                raise ValueError("SETTLED_OUTCOME_REF_REQUIRED")
            if self.label_state == LearningLabelState.PENDING:
                raise ValueError("SETTLED_LABEL_STATE_REQUIRED")
        if self.label_state == LearningLabelState.LABELABLE and (
            self.settlement_state != LearningSettlementState.SETTLED
        ):
            raise ValueError("LABELABLE_REQUIRES_SETTLED")

    @classmethod
    def create(cls, **kwargs: Any) -> "LearningObservationV1":
        observation_id = kwargs.pop("observation_id", None)
        record = cls(observation_id=observation_id or "LO-PENDING", **kwargs)
        if observation_id is None:
            object.__setattr__(record, "observation_id", f"LO-{record.identity_hash}")
        return record

    @property
    def identity_hash(self) -> str:
        body = learning_observation_v1_to_dict(self, include_identity=False)
        body.pop("observation_id", None)
        return sha256_bytes(canonical_bytes(body))

    @property
    def settled(self) -> bool:
        return self.settlement_state == LearningSettlementState.SETTLED

    @property
    def labelable(self) -> bool:
        return self.label_state == LearningLabelState.LABELABLE


@dataclass(frozen=True, slots=True)
class LearningJoinV1:
    """Immutable materialized join over existing canonical records."""

    observation: LearningObservationV1
    strategy_match: StrategyMatch
    forecast: ForecastV1
    prediction_outcome: OutcomeV1 | None = None
    trading_attribution: StrategyAttributionV1 | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.observation, LearningObservationV1):
            raise ValueError("LEARNING_OBSERVATION_INVALID")
        if not isinstance(self.strategy_match, StrategyMatch):
            raise ValueError("LEARNING_STRATEGY_MATCH_INVALID")
        if not isinstance(self.forecast, ForecastV1):
            raise ValueError("LEARNING_FORECAST_INVALID")
        if self.prediction_outcome is not None and not isinstance(
            self.prediction_outcome, OutcomeV1
        ):
            raise ValueError("LEARNING_OUTCOME_INVALID")
        if self.trading_attribution is not None and not isinstance(
            self.trading_attribution, StrategyAttributionV1
        ):
            raise ValueError("LEARNING_ATTRIBUTION_INVALID")


def learning_join_v1_to_dict(join: LearningJoinV1) -> dict[str, Any]:
    """Serialize a materialized join without inventing a parallel contract."""

    body: dict[str, Any] = {
        "observation": learning_observation_v1_to_dict(join.observation),
        "strategy_match": strategy_match_to_dict(join.strategy_match),
        "forecast": forecast_v1_to_dict(join.forecast),
    }
    if join.prediction_outcome is not None:
        body["prediction_outcome"] = outcome_v1_to_dict(join.prediction_outcome)
    if join.trading_attribution is not None:
        body["trading_attribution"] = attribution_v1_to_dict(join.trading_attribution)
    return body


def learning_join_v1_from_dict(payload: Mapping[str, Any]) -> LearningJoinV1:
    allowed = {
        "observation",
        "strategy_match",
        "forecast",
        "prediction_outcome",
        "trading_attribution",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"UNKNOWN_LEARNING_JOIN_FIELDS:{','.join(unknown)}")
    return LearningJoinV1(
        observation=learning_observation_v1_from_dict(payload["observation"]),
        strategy_match=strategy_match_from_dict(payload["strategy_match"]),
        forecast=forecast_v1_from_dict(payload["forecast"]),
        prediction_outcome=(
            outcome_v1_from_dict(payload["prediction_outcome"])
            if payload.get("prediction_outcome") is not None
            else None
        ),
        trading_attribution=(
            attribution_v1_from_dict(payload["trading_attribution"])
            if payload.get("trading_attribution") is not None
            else None
        ),
    )


def learning_join_v1_canonical_bytes(join: LearningJoinV1) -> bytes:
    return canonical_bytes(learning_join_v1_to_dict(join))


@dataclass(frozen=True, slots=True)
class LearningPolicyV1:
    """Versioned allow-list and gate policy for learning eligibility."""

    policy_id: str
    policy_version: str
    account_id: str | None
    mode: str | None
    minimum_samples: int
    allowed_evidence_tiers: tuple[EvidenceTier, ...]
    allowed_evidence_modes: tuple[str, ...]
    require_pit_clean_lineage: bool = True
    require_settled_labelable_prediction: bool = True
    allow_trading_attribution: bool = True
    require_account_mode_isolation: bool = True
    schema_version: str = INTELLIGENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        validate_id(self.policy_id, field_name="policy_id")
        validate_schema_version(self.schema_version)
        if not str(self.policy_version).strip():
            raise ValueError("LEARNING_POLICY_VERSION_REQUIRED")
        if self.account_id is not None:
            validate_id(self.account_id, field_name="policy.account_id")
        if self.mode is not None:
            mode = _normalize_mode(self.mode)
            if not mode:
                raise ValueError("POLICY_MODE_INVALID")
            object.__setattr__(self, "mode", mode)
        if (
            not isinstance(self.minimum_samples, int)
            or isinstance(self.minimum_samples, bool)
            or self.minimum_samples < 1
        ):
            raise ValueError("LEARNING_MINIMUM_SAMPLES_INVALID")
        tiers = tuple(
            tier if isinstance(tier, EvidenceTier) else EvidenceTier(str(tier))
            for tier in self.allowed_evidence_tiers
        )
        if not tiers:
            raise ValueError("LEARNING_EVIDENCE_TIERS_REQUIRED")
        object.__setattr__(self, "allowed_evidence_tiers", tuple(dict.fromkeys(tiers)))
        modes = tuple(_normalize_mode(value) for value in self.allowed_evidence_modes)
        if not modes or any(not value for value in modes):
            raise ValueError("LEARNING_EVIDENCE_MODES_REQUIRED")
        object.__setattr__(self, "allowed_evidence_modes", tuple(dict.fromkeys(modes)))

    @property
    def identity_hash(self) -> str:
        return sha256_bytes(canonical_bytes(learning_policy_v1_to_dict(self)))


@dataclass(frozen=True, slots=True)
class LearningEvaluationV1:
    """Transparent gate result with separate predictive/trading quality."""

    evaluation_id: str
    schema_version: str
    observation_id: str
    strategy_id: str
    strategy_identity_hash: str
    policy_id: str
    eligibility: LearningEligibility
    sample_count: int
    required_sample_count: int
    prediction_quality: QualityState
    trading_quality: QualityState | None
    counters: Mapping[str, int] = field(default_factory=dict)
    passed_checks: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_id(self.evaluation_id, field_name="evaluation_id")
        validate_schema_version(self.schema_version)
        validate_id(self.observation_id, field_name="observation_id")
        validate_id(self.strategy_id, field_name="strategy_id")
        validate_id(self.strategy_identity_hash, field_name="strategy_identity_hash")
        validate_id(self.policy_id, field_name="policy_id")
        if not isinstance(self.eligibility, LearningEligibility):
            object.__setattr__(
                self,
                "eligibility",
                LearningEligibility(str(self.eligibility)),
            )
        if not isinstance(self.prediction_quality, QualityState):
            object.__setattr__(
                self,
                "prediction_quality",
                QualityState(str(self.prediction_quality)),
            )
        if self.trading_quality is not None and not isinstance(
            self.trading_quality, QualityState
        ):
            object.__setattr__(self, "trading_quality", QualityState(str(self.trading_quality)))
        if self.sample_count < 0 or self.required_sample_count < 1:
            raise ValueError("LEARNING_SAMPLE_COUNT_INVALID")
        object.__setattr__(
            self,
            "counters",
            MappingProxyType(
                {
                    str(key): int(value)
                    for key, value in sorted(dict(self.counters).items())
                }
            ),
        )
        object.__setattr__(self, "passed_checks", tuple(sorted(set(self.passed_checks))))
        object.__setattr__(self, "reasons", tuple(sorted(set(self.reasons))))

    @property
    def identity_hash(self) -> str:
        body = learning_evaluation_v1_to_dict(self, include_identity=False)
        body.pop("evaluation_id", None)
        return sha256_bytes(canonical_bytes(body))


RESEARCH_HANDOFF_AUTHORITIES = (
    "ResearchHypothesisV1",
    "ExperimentManifestV1",
    "ValidationEngine",
    "LockedHoldout",
    "ContaminationCheck",
    "ShadowEvidence",
    "PromotionEngine",
)


@dataclass(frozen=True, slots=True)
class ResearchHandoffV1:
    """Non-promotional seed for the existing governed research lifecycle."""

    handoff_id: str
    schema_version: str
    policy_id: str
    strategy_id: str
    strategy_identity_hash: str
    source_observation_ids: tuple[str, ...]
    source_evaluation_ids: tuple[str, ...]
    candidate_seed: Mapping[str, Any]
    required_downstream_authorities: tuple[str, ...] = RESEARCH_HANDOFF_AUTHORITIES
    promotional: bool = False
    can_promote: bool = False
    can_execute: bool = False
    champion_change_allowed: bool = False

    def __post_init__(self) -> None:
        validate_id(self.handoff_id, field_name="handoff_id")
        validate_schema_version(self.schema_version)
        validate_id(self.policy_id, field_name="policy_id")
        validate_id(self.strategy_id, field_name="strategy_id")
        validate_id(self.strategy_identity_hash, field_name="strategy_identity_hash")
        if not self.source_observation_ids or not self.source_evaluation_ids:
            raise ValueError("RESEARCH_HANDOFF_SOURCES_REQUIRED")
        if self.promotional or self.can_promote or self.can_execute or self.champion_change_allowed:
            raise ValueError("RESEARCH_HANDOFF_MUST_BE_NON_PROMOTIONAL")
        if tuple(self.required_downstream_authorities) != RESEARCH_HANDOFF_AUTHORITIES:
            raise ValueError("RESEARCH_HANDOFF_AUTHORITIES_INVALID")
        object.__setattr__(self, "candidate_seed", _freeze(self.candidate_seed))
        object.__setattr__(
            self,
            "source_observation_ids",
            tuple(sorted(set(self.source_observation_ids))),
        )
        object.__setattr__(
            self,
            "source_evaluation_ids",
            tuple(sorted(set(self.source_evaluation_ids))),
        )

    @property
    def identity_hash(self) -> str:
        body = research_handoff_v1_to_dict(self, include_identity=False)
        body.pop("handoff_id", None)
        return sha256_bytes(canonical_bytes(body))


def _observation_body(record: LearningObservationV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "observation_id": record.observation_id,
        "schema_version": record.schema_version,
        "account_id": record.account_id,
        "mode": record.mode,
        "strategy_id": record.strategy_id,
        "strategy_identity_hash": record.strategy_identity_hash,
        "strategy_match_ref": contract_reference_to_dict(record.strategy_match_ref),
        "forecast_ref": contract_reference_to_dict(record.forecast_ref),
        "evidence_tier": record.evidence_tier.value,
        "evidence_mode": record.evidence_mode,
        "decision_time_ns": record.decision_time_ns,
        "settlement_state": record.settlement_state.value,
        "label_state": record.label_state.value,
    }
    for name in (
        "prediction_outcome_ref",
        "trading_attribution_ref",
        "opportunity_ref",
        "cluster_ref",
    ):
        ref = getattr(record, name)
        if ref is not None:
            body[name] = contract_reference_to_dict(ref)
    if record.settlement_time_ns is not None:
        body["settlement_time_ns"] = record.settlement_time_ns
    return body


def learning_observation_v1_to_dict(
    record: LearningObservationV1,
    *,
    include_identity: bool = True,
) -> dict[str, Any]:
    body = _observation_body(record)
    if include_identity:
        body["identity_hash"] = record.identity_hash
    return body


_OBSERVATION_ALLOWED = dataclass_field_names(LearningObservationV1) | {"identity_hash"}


def learning_observation_v1_from_dict(payload: Mapping[str, Any]) -> LearningObservationV1:
    unknown = sorted(set(payload) - _OBSERVATION_ALLOWED)
    if unknown:
        raise ValueError(f"UNKNOWN_LEARNING_OBSERVATION_FIELDS:{','.join(unknown)}")
    record = LearningObservationV1(
        observation_id=str(payload["observation_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        account_id=str(payload["account_id"]),
        mode=str(payload["mode"]),
        strategy_id=str(payload["strategy_id"]),
        strategy_identity_hash=str(payload["strategy_identity_hash"]),
        strategy_match_ref=contract_reference_from_dict(payload["strategy_match_ref"]),
        forecast_ref=contract_reference_from_dict(payload["forecast_ref"]),
        prediction_outcome_ref=(
            contract_reference_from_dict(payload["prediction_outcome_ref"])
            if payload.get("prediction_outcome_ref") is not None
            else None
        ),
        trading_attribution_ref=(
            contract_reference_from_dict(payload["trading_attribution_ref"])
            if payload.get("trading_attribution_ref") is not None
            else None
        ),
        opportunity_ref=(
            contract_reference_from_dict(payload["opportunity_ref"])
            if payload.get("opportunity_ref") is not None
            else None
        ),
        cluster_ref=(
            contract_reference_from_dict(payload["cluster_ref"])
            if payload.get("cluster_ref") is not None
            else None
        ),
        evidence_tier=EvidenceTier(str(payload["evidence_tier"])),
        evidence_mode=str(payload["evidence_mode"]),
        decision_time_ns=int(payload["decision_time_ns"]),
        settlement_time_ns=(
            int(payload["settlement_time_ns"])
            if payload.get("settlement_time_ns") is not None
            else None
        ),
        settlement_state=LearningSettlementState(str(payload["settlement_state"])),
        label_state=LearningLabelState(str(payload["label_state"])),
    )
    if payload.get("identity_hash") is not None and payload["identity_hash"] != record.identity_hash:
        raise ValueError("LEARNING_OBSERVATION_IDENTITY_HASH_MISMATCH")
    return record


def learning_policy_v1_to_dict(record: LearningPolicyV1) -> dict[str, Any]:
    return {
        "policy_id": record.policy_id,
        "policy_version": record.policy_version,
        "schema_version": record.schema_version,
        "account_id": record.account_id,
        "mode": record.mode,
        "minimum_samples": record.minimum_samples,
        "allowed_evidence_tiers": [tier.value for tier in record.allowed_evidence_tiers],
        "allowed_evidence_modes": list(record.allowed_evidence_modes),
        "require_pit_clean_lineage": record.require_pit_clean_lineage,
        "require_settled_labelable_prediction": record.require_settled_labelable_prediction,
        "allow_trading_attribution": record.allow_trading_attribution,
        "require_account_mode_isolation": record.require_account_mode_isolation,
    }


def learning_policy_v1_from_dict(payload: Mapping[str, Any]) -> LearningPolicyV1:
    allowed = dataclass_field_names(LearningPolicyV1)
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"UNKNOWN_LEARNING_POLICY_FIELDS:{','.join(unknown)}")
    return LearningPolicyV1(
        policy_id=str(payload["policy_id"]),
        policy_version=str(payload["policy_version"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        account_id=payload.get("account_id"),
        mode=payload.get("mode"),
        minimum_samples=int(payload["minimum_samples"]),
        allowed_evidence_tiers=tuple(
            EvidenceTier(str(tier)) for tier in payload["allowed_evidence_tiers"]
        ),
        allowed_evidence_modes=tuple(payload["allowed_evidence_modes"]),
        require_pit_clean_lineage=bool(payload.get("require_pit_clean_lineage", True)),
        require_settled_labelable_prediction=bool(
            payload.get("require_settled_labelable_prediction", True)
        ),
        allow_trading_attribution=bool(payload.get("allow_trading_attribution", True)),
        require_account_mode_isolation=bool(
            payload.get("require_account_mode_isolation", True)
        ),
    )


def learning_observation_v1_canonical_bytes(record: LearningObservationV1) -> bytes:
    return canonical_bytes(learning_observation_v1_to_dict(record))


def learning_policy_v1_canonical_bytes(record: LearningPolicyV1) -> bytes:
    return canonical_bytes(learning_policy_v1_to_dict(record))


def learning_evaluation_v1_from_dict(
    payload: Mapping[str, Any],
) -> LearningEvaluationV1:
    allowed = dataclass_field_names(LearningEvaluationV1) | {"identity_hash"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"UNKNOWN_LEARNING_EVALUATION_FIELDS:{','.join(unknown)}")
    trading_quality = payload.get("trading_quality")
    record = LearningEvaluationV1(
        evaluation_id=str(payload["evaluation_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        observation_id=str(payload["observation_id"]),
        strategy_id=str(payload["strategy_id"]),
        strategy_identity_hash=str(payload["strategy_identity_hash"]),
        policy_id=str(payload["policy_id"]),
        eligibility=LearningEligibility(str(payload["eligibility"])),
        sample_count=int(payload["sample_count"]),
        required_sample_count=int(payload["required_sample_count"]),
        prediction_quality=QualityState(str(payload["prediction_quality"])),
        trading_quality=QualityState(str(trading_quality)) if trading_quality else None,
        counters=dict(payload.get("counters") or {}),
        passed_checks=tuple(payload.get("passed_checks") or ()),
        reasons=tuple(payload.get("reasons") or ()),
    )
    if payload.get("identity_hash") is not None and payload["identity_hash"] != record.identity_hash:
        raise ValueError("LEARNING_EVALUATION_IDENTITY_HASH_MISMATCH")
    return record


def learning_evaluation_v1_canonical_bytes(record: LearningEvaluationV1) -> bytes:
    return canonical_bytes(learning_evaluation_v1_to_dict(record))


def research_handoff_v1_canonical_bytes(record: ResearchHandoffV1) -> bytes:
    return canonical_bytes(research_handoff_v1_to_dict(record))


def learning_evaluation_v1_to_dict(
    record: LearningEvaluationV1,
    *,
    include_identity: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "evaluation_id": record.evaluation_id,
        "schema_version": record.schema_version,
        "observation_id": record.observation_id,
        "strategy_id": record.strategy_id,
        "strategy_identity_hash": record.strategy_identity_hash,
        "policy_id": record.policy_id,
        "eligibility": record.eligibility.value,
        "sample_count": record.sample_count,
        "required_sample_count": record.required_sample_count,
        "prediction_quality": record.prediction_quality.value,
        "trading_quality": (
            record.trading_quality.value if record.trading_quality is not None else None
        ),
        "counters": dict(record.counters),
        "passed_checks": list(record.passed_checks),
        "reasons": list(record.reasons),
    }
    if include_identity:
        body["identity_hash"] = record.identity_hash
    return body


def research_handoff_v1_to_dict(
    record: ResearchHandoffV1,
    *,
    include_identity: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "handoff_id": record.handoff_id,
        "schema_version": record.schema_version,
        "policy_id": record.policy_id,
        "strategy_id": record.strategy_id,
        "strategy_identity_hash": record.strategy_identity_hash,
        "source_observation_ids": list(record.source_observation_ids),
        "source_evaluation_ids": list(record.source_evaluation_ids),
        "candidate_seed": _thaw(record.candidate_seed),
        "required_downstream_authorities": list(record.required_downstream_authorities),
        "promotional": record.promotional,
        "can_promote": record.can_promote,
        "can_execute": record.can_execute,
        "champion_change_allowed": record.champion_change_allowed,
    }
    if include_identity:
        body["identity_hash"] = record.identity_hash
    return body


def research_handoff_v1_from_dict(payload: Mapping[str, Any]) -> ResearchHandoffV1:
    allowed = dataclass_field_names(ResearchHandoffV1) | {"identity_hash"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"UNKNOWN_RESEARCH_HANDOFF_FIELDS:{','.join(unknown)}")
    record = ResearchHandoffV1(
        handoff_id=str(payload["handoff_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        policy_id=str(payload["policy_id"]),
        strategy_id=str(payload["strategy_id"]),
        strategy_identity_hash=str(payload["strategy_identity_hash"]),
        source_observation_ids=tuple(payload["source_observation_ids"]),
        source_evaluation_ids=tuple(payload["source_evaluation_ids"]),
        candidate_seed=dict(payload.get("candidate_seed") or {}),
        required_downstream_authorities=tuple(
            payload.get("required_downstream_authorities") or RESEARCH_HANDOFF_AUTHORITIES
        ),
        promotional=bool(payload.get("promotional", False)),
        can_promote=bool(payload.get("can_promote", False)),
        can_execute=bool(payload.get("can_execute", False)),
        champion_change_allowed=bool(payload.get("champion_change_allowed", False)),
    )
    if payload.get("identity_hash") is not None and payload["identity_hash"] != record.identity_hash:
        raise ValueError("RESEARCH_HANDOFF_IDENTITY_HASH_MISMATCH")
    return record


def _make_evaluation(
    *,
    join: LearningJoinV1,
    policy: LearningPolicyV1,
    eligibility: LearningEligibility,
    sample_count: int,
    counters: Mapping[str, int],
    passed_checks: Sequence[str],
    reasons: Sequence[str],
) -> LearningEvaluationV1:
    observation = join.observation
    provisional = LearningEvaluationV1(
        evaluation_id="LE-PENDING",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        observation_id=observation.observation_id,
        strategy_id=observation.strategy_id,
        strategy_identity_hash=observation.strategy_identity_hash,
        policy_id=policy.policy_id,
        eligibility=eligibility,
        sample_count=sample_count,
        required_sample_count=policy.minimum_samples,
        prediction_quality=join.forecast.quality.state,
        trading_quality=(
            QualityState.GOOD if join.trading_attribution is not None else None
        ),
        counters=counters,
        passed_checks=tuple(passed_checks),
        reasons=tuple(reasons),
    )
    object.__setattr__(provisional, "evaluation_id", f"LE-{provisional.identity_hash}")
    return provisional


def evaluate_learning_join(
    join: LearningJoinV1,
    policy: LearningPolicyV1,
    *,
    sample_count: int = 1,
) -> LearningEvaluationV1:
    """Evaluate one join without mutating or invoking any downstream authority."""

    if not isinstance(join, LearningJoinV1):
        raise ValueError("LEARNING_JOIN_INVALID")
    if not isinstance(policy, LearningPolicyV1):
        raise ValueError("LEARNING_POLICY_INVALID")
    if not isinstance(sample_count, int) or isinstance(sample_count, bool) or sample_count < 0:
        raise ValueError("LEARNING_SAMPLE_COUNT_INVALID")

    observation = join.observation
    match = join.strategy_match
    forecast = join.forecast
    outcome = join.prediction_outcome
    attribution = join.trading_attribution
    hard: list[str] = []
    soft: list[str] = []
    passed: list[str] = []
    counters: dict[str, int] = {
        "joined_observations": 1,
        "prediction_outcome_available": int(outcome is not None),
        "prediction_labelable": int(observation.labelable),
        "trading_attribution_available": int(attribution is not None),
    }

    if observation.account_id != (policy.account_id or observation.account_id):
        hard.append("ACCOUNT_SCOPE_MISMATCH")
    else:
        passed.append("ACCOUNT_SCOPE")
    if policy.mode is not None and observation.mode != policy.mode:
        hard.append("MODE_SCOPE_MISMATCH")
    else:
        passed.append("MODE_SCOPE")
    if observation.evidence_tier not in policy.allowed_evidence_tiers:
        hard.append("EVIDENCE_TIER_NOT_ALLOWED")
    else:
        passed.append("EVIDENCE_TIER")
    if observation.evidence_mode not in policy.allowed_evidence_modes:
        hard.append("EVIDENCE_MODE_NOT_ALLOWED")
    else:
        passed.append("EVIDENCE_MODE")

    if match.match_id != observation.strategy_match_ref.id:
        hard.append("STRATEGY_MATCH_REF_MISMATCH")
    if match.strategy_id != observation.strategy_id:
        hard.append("STRATEGY_ID_MISMATCH")
    if match.strategy_identity_hash != observation.strategy_identity_hash:
        hard.append("STRATEGY_IDENTITY_HASH_MISMATCH")
    if match.disposition != StrategyMatchDisposition.MATCHED:
        hard.append("STRATEGY_MATCH_NOT_MATCHED")
    if (
        ContractReference(kind="forecast", id=forecast.forecast_id)
        not in match.source_forecast_refs
    ):
        hard.append("FORECAST_NOT_IN_MATCH_LINEAGE")
    if forecast.forecast_id != observation.forecast_ref.id:
        hard.append("FORECAST_REF_MISMATCH")

    if policy.require_pit_clean_lineage:
        if match.decision_time_ns > observation.decision_time_ns:
            hard.append("STRATEGY_MATCH_AFTER_DECISION")
        else:
            passed.append("MATCH_PIT_CLEAN")
        if forecast.decision_time_ns > observation.decision_time_ns:
            hard.append("FORECAST_AFTER_DECISION")
        else:
            passed.append("FORECAST_PIT_CLEAN")
        if observation.settlement_time_ns is not None and (
            observation.settlement_time_ns < observation.decision_time_ns
        ):
            hard.append("SETTLEMENT_BEFORE_DECISION")
        if outcome is not None and outcome.adjudicated_at_ns < observation.decision_time_ns:
            hard.append("OUTCOME_BEFORE_DECISION")

    if policy.require_account_mode_isolation:
        match_context = dict(match.context)
        match_account = match_context.get("account_id")
        match_mode = match_context.get("mode")
        if match_account is not None and str(match_account) != observation.account_id:
            hard.append("ACCOUNT_SCOPE_MISMATCH")
        if match_mode is not None and _normalize_mode(str(match_mode)) != observation.mode:
            hard.append("MODE_SCOPE_MISMATCH")
        forecast_metadata = dict(forecast.metadata)
        forecast_account = forecast_metadata.get("account_id")
        forecast_mode = forecast_metadata.get("mode")
        if forecast_account is not None and str(forecast_account) != observation.account_id:
            hard.append("ACCOUNT_SCOPE_MISMATCH")
        if forecast_mode is not None and _normalize_mode(str(forecast_mode)) != observation.mode:
            hard.append("MODE_SCOPE_MISMATCH")

    if outcome is not None:
        if observation.prediction_outcome_ref is None or (
            outcome.outcome_id != observation.prediction_outcome_ref.id
        ):
            hard.append("PREDICTION_OUTCOME_REF_MISMATCH")
        if outcome.forecast_id != forecast.forecast_id:
            hard.append("OUTCOME_FORECAST_REF_MISMATCH")
        if observation.settlement_state == LearningSettlementState.UNSETTLED and (
            outcome.resolution_status.value == "SETTLED"
        ):
            hard.append("SETTLEMENT_STATE_MISMATCH")

    if observation.settled:
        if outcome is None:
            soft.append("PREDICTION_OUTCOME_NOT_AVAILABLE")
        elif outcome.resolution_status.value != "SETTLED":
            soft.append("PREDICTION_NOT_SETTLED")
        elif observation.labelable:
            passed.append("PREDICTION_SETTLED_LABELABLE")
        else:
            soft.append("PREDICTION_UNLABELABLE")
    elif policy.require_settled_labelable_prediction:
        soft.append("PREDICTION_NOT_SETTLED")

    if outcome is not None and outcome.resolution_status.value == "UNLABELABLE":
        soft.append("PREDICTION_UNLABELABLE")
    elif outcome is not None and outcome.resolution_status.value != "SETTLED":
        soft.append("PREDICTION_NOT_SETTLED")

    if observation.trading_attribution_ref is not None:
        if not policy.allow_trading_attribution:
            hard.append("TRADING_ATTRIBUTION_NOT_ALLOWED")
        elif attribution is None:
            hard.append("TRADING_ATTRIBUTION_NOT_AVAILABLE")
        else:
            if attribution.attribution_id != observation.trading_attribution_ref.id:
                hard.append("TRADING_ATTRIBUTION_REF_MISMATCH")
            if attribution.strategy_match_ref.id != match.match_id:
                hard.append("TRADING_MATCH_REF_MISMATCH")
            if (
                attribution.strategy_id != observation.strategy_id
                or attribution.strategy_identity_hash != observation.strategy_identity_hash
            ):
                hard.append("TRADING_STRATEGY_IDENTITY_MISMATCH")
            if attribution.account_id != observation.account_id:
                hard.append("ACCOUNT_SCOPE_MISMATCH")
            if _normalize_mode(attribution.mode) != observation.mode:
                hard.append("MODE_SCOPE_MISMATCH")
            if policy.require_pit_clean_lineage and (
                attribution.point_in_time_ns > observation.decision_time_ns
            ):
                hard.append("TRADING_ATTRIBUTION_AFTER_DECISION")
            else:
                passed.append("TRADING_ATTRIBUTION_PIT_CLEAN")
    elif attribution is not None:
        hard.append("TRADING_ATTRIBUTION_REF_MISSING")

    counters["sample_count"] = sample_count
    counters["minimum_samples"] = policy.minimum_samples
    if sample_count < policy.minimum_samples:
        soft.append("INSUFFICIENT_SAMPLES")
    counters["hard_failures"] = len(set(hard))
    counters["soft_failures"] = len(set(soft))
    if hard:
        eligibility = LearningEligibility.INELIGIBLE
    elif soft:
        eligibility = LearningEligibility.INCONCLUSIVE
    else:
        eligibility = LearningEligibility.ELIGIBLE
    return _make_evaluation(
        join=join,
        policy=policy,
        eligibility=eligibility,
        sample_count=sample_count,
        counters=counters,
        passed_checks=passed,
        reasons=hard + soft,
    )


def evaluate_learning_joins(
    joins: Sequence[LearningJoinV1],
    policy: LearningPolicyV1,
) -> tuple[LearningEvaluationV1, ...]:
    """Evaluate a bounded cohort and apply the minimum-sample gate."""

    if not joins:
        return ()
    provisional = tuple(
        evaluate_learning_join(join, policy, sample_count=len(joins)) for join in joins
    )
    observation_ids = [join.observation.observation_id for join in joins]
    if len(set(observation_ids)) != len(observation_ids):
        duplicate_results: list[LearningEvaluationV1] = []
        for index, result in enumerate(provisional):
            counters = dict(result.counters)
            counters["cohort_scope_count"] = 1
            duplicate_results.append(
                _make_evaluation(
                    join=joins[index],
                    policy=policy,
                    eligibility=LearningEligibility.INELIGIBLE,
                    sample_count=len(joins),
                    counters=counters,
                    passed_checks=result.passed_checks,
                    reasons=(*result.reasons, "DUPLICATE_OBSERVATION"),
                )
            )
        return tuple(duplicate_results)
    scope_keys = {
        (join.observation.account_id, join.observation.mode)
        for join in joins
    }
    if len(scope_keys) > 1:
        contaminated: list[LearningEvaluationV1] = []
        for index, result in enumerate(provisional):
            counters = dict(result.counters)
            counters["cohort_scope_count"] = len(scope_keys)
            contaminated.append(
                _make_evaluation(
                    join=joins[index],
                    policy=policy,
                    eligibility=LearningEligibility.INELIGIBLE,
                    sample_count=len(joins),
                    counters=counters,
                    passed_checks=result.passed_checks,
                    reasons=(*result.reasons, "CROSS_ACCOUNT_OR_MODE_CONTAMINATION"),
                )
            )
        return tuple(contaminated)
    eligible_count = sum(
        result.eligibility == LearningEligibility.ELIGIBLE for result in provisional
    )
    if eligible_count >= policy.minimum_samples:
        return provisional
    output: list[LearningEvaluationV1] = []
    for result in provisional:
        if result.eligibility != LearningEligibility.ELIGIBLE:
            output.append(result)
            continue
        counters = dict(result.counters)
        counters["eligible_sample_count"] = eligible_count
        counters["minimum_samples"] = policy.minimum_samples
        counters["soft_failures"] = len(set((*result.reasons, "INSUFFICIENT_SAMPLES")))
        output.append(
            _make_evaluation(
                join=joins[len(output)],
                policy=policy,
                eligibility=LearningEligibility.INCONCLUSIVE,
                sample_count=eligible_count,
                counters=counters,
                passed_checks=result.passed_checks,
                reasons=(*result.reasons, "INSUFFICIENT_SAMPLES"),
            )
        )
    return tuple(output)


def emit_research_handoff(
    evaluations: Sequence[LearningEvaluationV1],
    *,
    seed: Mapping[str, Any] | None = None,
) -> ResearchHandoffV1:
    """Emit only a research seed; all downstream governance remains required."""

    if not evaluations:
        raise ValueError("RESEARCH_HANDOFF_EVALUATIONS_REQUIRED")
    if any(result.eligibility != LearningEligibility.ELIGIBLE for result in evaluations):
        raise ValueError("RESEARCH_HANDOFF_REQUIRES_ELIGIBLE_EVALUATIONS")
    first = evaluations[0]
    if len({result.evaluation_id for result in evaluations}) != len(evaluations):
        raise ValueError("RESEARCH_HANDOFF_DUPLICATE_EVALUATION")
    if len({result.observation_id for result in evaluations}) != len(evaluations):
        raise ValueError("RESEARCH_HANDOFF_DUPLICATE_OBSERVATION")
    if any(
        result.policy_id != first.policy_id
        or result.strategy_id != first.strategy_id
        or result.strategy_identity_hash != first.strategy_identity_hash
        for result in evaluations
    ):
        raise ValueError("RESEARCH_HANDOFF_SCOPE_MISMATCH")
    provisional = ResearchHandoffV1(
        handoff_id="RH-PENDING",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        policy_id=first.policy_id,
        strategy_id=first.strategy_id,
        strategy_identity_hash=first.strategy_identity_hash,
        source_observation_ids=tuple(result.observation_id for result in evaluations),
        source_evaluation_ids=tuple(result.evaluation_id for result in evaluations),
        candidate_seed=seed or {},
    )
    object.__setattr__(provisional, "handoff_id", f"RH-{provisional.identity_hash}")
    return provisional


__all__ = [
    "LEARNING_POLICY_VERSION",
    "LearningEligibility",
    "LearningEvaluationV1",
    "LearningJoinV1",
    "LearningLabelState",
    "LearningObservationV1",
    "LearningPolicyV1",
    "LearningSettlementState",
    "RESEARCH_HANDOFF_AUTHORITIES",
    "ResearchHandoffV1",
    "emit_research_handoff",
    "evaluate_learning_join",
    "evaluate_learning_joins",
    "learning_evaluation_v1_to_dict",
    "learning_join_v1_canonical_bytes",
    "learning_join_v1_from_dict",
    "learning_join_v1_to_dict",
    "learning_evaluation_v1_canonical_bytes",
    "learning_evaluation_v1_from_dict",
    "learning_observation_v1_canonical_bytes",
    "learning_observation_v1_from_dict",
    "learning_observation_v1_to_dict",
    "learning_policy_v1_canonical_bytes",
    "learning_policy_v1_from_dict",
    "learning_policy_v1_to_dict",
    "research_handoff_v1_canonical_bytes",
    "research_handoff_v1_from_dict",
    "research_handoff_v1_to_dict",
]
