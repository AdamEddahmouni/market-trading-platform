"""Point-in-time quantitative factor experiment contract.

Reusable interfaces for construction, observation, and experiment
registration. Not a strategy. Not Opportunity Engine ranking. Not Live.
"""

from .construction import (
    FactorConstructionSpecV1,
    build_construction_spec,
    construction_spec_from_dict,
    construction_spec_to_dict,
)
from .errors import FactorContractError
from .experiment import (
    FactorExperimentManifestV1,
    build_experiment_manifest,
    experiment_manifest_from_dict,
    experiment_manifest_to_dict,
)
from .families import (
    CharacteristicTransform,
    FactorEvidenceClass,
    FactorExpressionClass,
    FactorFamily,
    FactorSign,
    InvalidDenominatorRule,
    MissingnessRule,
    MultiplicityPolicy,
    Neutralization,
)
from .observation import (
    FactorObservationV1,
    build_factor_observation,
    factor_observation_from_dict,
    factor_observation_to_dict,
)
from .promotion import (
    LIVE_ELIGIBLE,
    OPPORTUNITY_ENGINE_RANKING_ELIGIBLE,
    assert_not_opportunity_engine_input,
    assert_research_only,
)
from .security import (
    FactorSecurityBindingV1,
    bind_factor_observation,
    build_security_binding,
    security_binding_from_dict,
    security_binding_to_dict,
)

__all__ = [
    "CharacteristicTransform",
    "FactorConstructionSpecV1",
    "FactorContractError",
    "FactorEvidenceClass",
    "FactorExperimentManifestV1",
    "FactorExpressionClass",
    "FactorFamily",
    "FactorObservationV1",
    "FactorSecurityBindingV1",
    "FactorSign",
    "InvalidDenominatorRule",
    "LIVE_ELIGIBLE",
    "MissingnessRule",
    "MultiplicityPolicy",
    "Neutralization",
    "OPPORTUNITY_ENGINE_RANKING_ELIGIBLE",
    "assert_not_opportunity_engine_input",
    "assert_research_only",
    "bind_factor_observation",
    "build_construction_spec",
    "build_experiment_manifest",
    "build_factor_observation",
    "build_security_binding",
    "construction_spec_from_dict",
    "construction_spec_to_dict",
    "experiment_manifest_from_dict",
    "experiment_manifest_to_dict",
    "factor_observation_from_dict",
    "factor_observation_to_dict",
    "security_binding_from_dict",
    "security_binding_to_dict",
]
