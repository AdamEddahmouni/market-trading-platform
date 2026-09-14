"""LuxAlgo Market Trackers third-party dump adapters (replaceable aggregators).

IMP treats Market Trackers as a convenience normalization layer over primary
government filings. Primary EDGAR provenance remains authoritative.
"""

from .sec_insider import (
    ADAPTER_PREP_VERSION,
    UPSTREAM_PIN,
    build_adapter_prep_bundle,
    characterize_record,
)

__all__ = [
    "ADAPTER_PREP_VERSION",
    "UPSTREAM_PIN",
    "build_adapter_prep_bundle",
    "characterize_record",
]
