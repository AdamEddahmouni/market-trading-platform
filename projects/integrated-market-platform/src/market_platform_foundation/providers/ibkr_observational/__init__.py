"""Canonical IBKR observational L1/L2 provider adapter (G6).

IBKR TWS / IB Gateway market-data callbacks → this adapter → canonical
instrument identity → canonical L1 quote / canonical ``DepthUpdate`` →
``ObservationalStateStore`` → ``IncrementalOrderBook`` → snapshots / OFI /
CVD / projections.

The adapter is transport-agnostic (a fake transport in tests; the optional
ib_insync-backed transport remains in ``tools/ibkr`` and is never imported
by runtime ``src`` code). It exposes NO execution capability — Live
execution remains blocked by LIVE-001.
"""

from __future__ import annotations

from .adapter import (
    CallbackResult,
    IbkrObservationalAdapter,
    IbkrObservationalConfig,
    IbkrOfflineError,
    IbkrTransport,
    SubscribeResult,
)
from .capability import (
    IBKR_CAPABILITY_CONTRACT_RESOLUTION,
    IBKR_CAPABILITY_L1,
    IBKR_CAPABILITY_L2,
    IBKR_FORBIDDEN_CAPABILITIES,
    IBKR_PROVIDER_ID,
    register_ibkr_observational,
)
from .contracts import (
    AdapterDiagnostics,
    CapabilityKind,
    ContractQualification,
    DepthTranslationOutcome,
    EntitlementState,
    IbkrConnectionState,
    IbkrErrorCategory,
    IbkrProviderError,
    IbkrSubscriptionRecord,
    IbkrSubscriptionState,
    L1QuoteFacts,
    PacingReport,
    RankLevel,
)
from .identity import (
    AdmittedInstrument,
    IdentityAdmissionError,
    InstrumentLookup,
    Xa01Admission,
)
from .lifecycle import (
    IbkrLifecycle,
    SubscriptionAlreadyActive,
    SubscriptionCapExceeded,
    SubscriptionRegistry,
    UnknownReqIdError,
)
from .mapping import (
    UnknownIbOperation,
    UnknownIbSide,
    classify_tick_field,
    decode_depth_operation,
    decode_depth_side,
    exact_price,
    exact_size,
    is_delayed_tick_field,
    is_verified_depth_operation,
    is_verified_depth_side,
    normalize_error,
)
from .pacing import LocalPacingState, SubscriptionCapPolicy
from .rank import SubscriptionRankState, translate_depth_callback

__all__ = [
    "AdapterDiagnostics",
    "AdmittedInstrument",
    "CallbackResult",
    "CapabilityKind",
    "ContractQualification",
    "DepthTranslationOutcome",
    "EntitlementState",
    "IBKR_CAPABILITY_CONTRACT_RESOLUTION",
    "IBKR_CAPABILITY_L1",
    "IBKR_CAPABILITY_L2",
    "IBKR_FORBIDDEN_CAPABILITIES",
    "IBKR_PROVIDER_ID",
    "IbkrConnectionState",
    "IbkrErrorCategory",
    "IbkrLifecycle",
    "IbkrObservationalAdapter",
    "IbkrObservationalConfig",
    "IbkrOfflineError",
    "IbkrProviderError",
    "IbkrSubscriptionRecord",
    "IbkrSubscriptionState",
    "IbkrTransport",
    "IdentityAdmissionError",
    "InstrumentLookup",
    "L1QuoteFacts",
    "LocalPacingState",
    "PacingReport",
    "RankLevel",
    "SubscribeResult",
    "SubscriptionAlreadyActive",
    "SubscriptionCapExceeded",
    "SubscriptionCapPolicy",
    "SubscriptionRankState",
    "SubscriptionRegistry",
    "UnknownIbOperation",
    "UnknownIbSide",
    "UnknownReqIdError",
    "Xa01Admission",
    "classify_tick_field",
    "decode_depth_operation",
    "decode_depth_side",
    "exact_price",
    "exact_size",
    "is_delayed_tick_field",
    "is_verified_depth_operation",
    "is_verified_depth_side",
    "normalize_error",
    "register_ibkr_observational",
    "translate_depth_callback",
]