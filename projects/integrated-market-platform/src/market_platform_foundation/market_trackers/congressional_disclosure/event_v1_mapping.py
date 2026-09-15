"""EventV1 mapping contract for congressional PTR rows (runtime registry wired in Lane F)."""

from __future__ import annotations

from typing import Any, Mapping

from .event_map import EventMapPrep, PROVIDER_ID, map_event_v1_prep
from .pin import ADAPTER_PREP_VERSION

EVENT_FAMILY = "REGULATORY_DISCLOSURE"
EVENT_TYPE = "CONGRESSIONAL_PTR_ROW"
SOURCE_TYPE = "REGULATORY_DISCLOSURE"
NORMALIZATION_VERSION = "intelligence/normalization/market_trackers_congressional_disclosure/1"

PROPOSED_REGISTRY_ENTRIES: tuple[dict[str, str], ...] = (
    {"provider_key": "market_trackers.congressional_disclosure", "callable": "normalize_congressional_disclosure_row"},
    {
        "provider_key": "market_trackers.congressional_disclosure.row",
        "callable": "normalize_congressional_disclosure_row",
    },
)


def event_v1_mapping_contract(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic EventV1 field plan without emitting a full EventV1 instance."""
    prep: EventMapPrep = map_event_v1_prep(row)
    return {
        "adapter_id": prep.adapter_id,
        "adapter_version": ADAPTER_PREP_VERSION,
        "event_family": EVENT_FAMILY,
        "event_type": EVENT_TYPE,
        "normalization_version": NORMALIZATION_VERSION,
        "payload_core": prep.payload_core,
        "provider_id": PROVIDER_ID,
        "publisher_id": prep.publisher_id,
        "source_type": SOURCE_TYPE,
        "instrument_qualified_id": prep.instrument_qualified_id,
        "identity_flags": list(prep.identity_flags),
    }


__all__ = [
    "ADAPTER_PREP_VERSION",
    "EVENT_FAMILY",
    "EVENT_TYPE",
    "NORMALIZATION_VERSION",
    "PROPOSED_REGISTRY_ENTRIES",
    "PROVIDER_ID",
    "SOURCE_TYPE",
    "event_v1_mapping_contract",
    "map_event_v1_prep",
]
