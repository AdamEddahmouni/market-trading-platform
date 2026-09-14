"""Research-only SignalV1 adapter for a PIT factor observation.

Does not mint ForecastV1 or OpportunityV1. Knowability clock is
`available_time_ns`, never fiscal period end.
"""

from __future__ import annotations

from ..contracts.common import IntelligenceScope, QualityState
from ..contracts.signal import SignalV1
from ..factors.errors import FactorContractError
from ..factors.observation import FactorObservationV1
from ..factors.promotion import assert_research_only, reject_promotion_fields
from .identity import derive_signal_id


def research_signal_from_factor_observation(observation: FactorObservationV1) -> SignalV1:
    """Map a factor observation to a measurement SignalV1.

    Missing values fail closed. The resulting signal is still
    RESEARCH_CHARACTERISTIC and is not Opportunity Engine ranking input.
    """
    assert_research_only()
    reject_promotion_fields(observation.metadata)
    if observation.value is None:
        raise FactorContractError("FACTOR_SIGNAL_REQUIRES_VALUE")
    if observation.quality.state == QualityState.INVALID:
        raise FactorContractError("FACTOR_SIGNAL_QUALITY_INVALID")
    scope = IntelligenceScope(instrument_ids=(observation.security_id,))
    signal_id = derive_signal_id(
        source_snapshot_id=observation.raw_input_snapshot_hash,
        signal_type=f"quant_factor.{observation.feature_id}",
        scope=scope,
        window_ns=None,
        calculator_id="quant-factor-observation",
        calculator_version=observation.feature_version,
        parameters={
            "construction_spec_id": observation.construction_spec_id,
            "hypothesis_family_id": observation.hypothesis_family_id,
            "evidence_class": observation.evidence_class.value,
        },
    )
    return SignalV1(
        signal_id=signal_id,
        schema_version=observation.schema_version,
        signal_type=f"quant_factor.{observation.feature_id}",
        scope=scope,
        as_of_time_ns=observation.available_time_ns,
        value=float(observation.value),
        quality=observation.quality,
        calculation_lineage={
            "observation_id": observation.observation_id,
            "construction_spec_id": observation.construction_spec_id,
            "export_hash": observation.export_hash,
            "opportunity_engine_ranking_eligible": "false",
        },
        metadata={
            "research_characteristic": "true",
            "hypothesis_family_id": observation.hypothesis_family_id,
            "expression_class": observation.expression_class.value,
            "security_id": observation.security_id,
            "issuer_id": observation.issuer_id,
        },
    )


__all__ = ["research_signal_from_factor_observation"]
