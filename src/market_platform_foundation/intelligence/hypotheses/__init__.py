"""BUILD 13 composite hypothesis engines."""

from __future__ import annotations

from .adapters import (
    DEFAULT_PRODUCTION_ADAPTER_REGISTRY,
    HypothesisEvidenceAdapter,
    HypothesisEvidenceAdapterRegistry,
    MicrostructureShortSqueezeEvidenceAdapter,
)
from .contributions import ContributionStance, HypothesisContribution
from .engine import CompositeHypothesisEngine, FactorEvaluator
from .errors import (
    HypothesisConfigurationError,
    HypothesisEngineError,
    HypothesisEvidenceError,
    HypothesisIntegrityError,
)
from .factors import (
    FactorEvaluation,
    FactorState,
    ShortSqueezeFactor,
    falsification_codes,
    falsification_receipt,
)
from .identity import HYPOTHESIS_IDENTITY_VERSION, derive_hypothesis_id
from .policy import DEFAULT_SHORT_SQUEEZE_POLICY, ShortSqueezeHypothesisPolicy
from .registry import DEFAULT_HYPOTHESIS_ENGINE_REGISTRY, HypothesisEngineRegistry
from .service import HypothesisEvaluationService, emitted
from .short_squeeze import ShortSqueezeHypothesisEngine
from .types import (
    HypothesisDiagnostic,
    HypothesisDiagnosticCode,
    HypothesisEvaluationContext,
    HypothesisEvaluationResult,
    HypothesisEvaluationStatus,
    HypothesisEvidencePhasePolicy,
    HypothesisType,
)

__all__ = [
    "CompositeHypothesisEngine",
    "ContributionStance",
    "DEFAULT_HYPOTHESIS_ENGINE_REGISTRY",
    "DEFAULT_PRODUCTION_ADAPTER_REGISTRY",
    "DEFAULT_SHORT_SQUEEZE_POLICY",
    "FactorEvaluator",
    "FactorEvaluation",
    "FactorState",
    "HYPOTHESIS_IDENTITY_VERSION",
    "HypothesisConfigurationError",
    "HypothesisContribution",
    "HypothesisDiagnostic",
    "HypothesisDiagnosticCode",
    "HypothesisEngineError",
    "HypothesisEngineRegistry",
    "HypothesisEvaluationContext",
    "HypothesisEvaluationResult",
    "HypothesisEvaluationService",
    "HypothesisEvaluationStatus",
    "HypothesisEvidenceAdapter",
    "HypothesisEvidenceAdapterRegistry",
    "HypothesisEvidenceError",
    "HypothesisEvidencePhasePolicy",
    "HypothesisIntegrityError",
    "HypothesisType",
    "MicrostructureShortSqueezeEvidenceAdapter",
    "ShortSqueezeFactor",
    "ShortSqueezeHypothesisEngine",
    "ShortSqueezeHypothesisPolicy",
    "derive_hypothesis_id",
    "emitted",
    "falsification_codes",
    "falsification_receipt",
]
