"""FRED / ALFRED dual-API macroeconomic evidence family."""

from .contracts import (
    CrossAssetRegimeContext,
    MacroDomain,
    MacroFeatureLayer,
    MacroIndicatorValue,
    MacroObservation,
    MacroRegimeState,
    MacroReleaseEvent,
    observation_to_dict,
)
from .cross_asset import CFTC_SYNTHESIS_MATRIX, build_cross_asset_regime_context
from .derived import DERIVED_VERSION, derive_us_2s10s, derive_us_3m10y, revision_delta
from .health import capability_report, live_probe_v1, live_probe_v2
from .live import api_key_present, live_enabled, transport_from_env
from .pit import DEFAULT_REVISION_FIXTURE, macro_as_of, macro_state_as_of
from .quality import FredQualityFlag, quality_blocks_macro
from .reconcile import reconcile_current_values
from .redaction import redact_text, sanitize_error
from .registry import TIER1_REGISTRY, lookup_canonical, lookup_series, registry_table_rows
from .store import FredStore
from .sync import FredSync, sync_fred_from_env
from .v1_client import FredV1Client
from .v2_client import FredV2Client, V2ReleaseSnapshot

__all__ = [
    "CFTC_SYNTHESIS_MATRIX",
    "DEFAULT_REVISION_FIXTURE",
    "DERIVED_VERSION",
    "CrossAssetRegimeContext",
    "FredQualityFlag",
    "FredStore",
    "FredSync",
    "FredV1Client",
    "FredV2Client",
    "MacroDomain",
    "MacroFeatureLayer",
    "MacroIndicatorValue",
    "MacroObservation",
    "MacroRegimeState",
    "MacroReleaseEvent",
    "TIER1_REGISTRY",
    "V2ReleaseSnapshot",
    "api_key_present",
    "build_cross_asset_regime_context",
    "capability_report",
    "derive_us_2s10s",
    "derive_us_3m10y",
    "live_enabled",
    "live_probe_v1",
    "live_probe_v2",
    "lookup_canonical",
    "lookup_series",
    "macro_as_of",
    "macro_state_as_of",
    "observation_to_dict",
    "quality_blocks_macro",
    "reconcile_current_values",
    "redact_text",
    "registry_table_rows",
    "revision_delta",
    "sanitize_error",
    "sync_fred_from_env",
    "transport_from_env",
]
