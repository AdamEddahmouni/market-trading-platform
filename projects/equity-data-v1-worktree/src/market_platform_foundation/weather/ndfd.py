"""Metadata-only NDFD archive characterization; GRIB2 decoding is deferred."""

from __future__ import annotations

from typing import Any

from .quality import WeatherQualityFlag

NDFD_PERIOD_OF_RECORD_START = "2004-06-06"
NDFD_CLOUD_ACCESS_START = "2020-04-16"
NDFD_DECODE_STATUS = WeatherQualityFlag.ARCHIVE_AVAILABLE_DECODE_DEFERRED.value
MAX_NDFD_PROBE_BYTES = 16_384


def characterize_ndfd_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    period = metadata.get("period_of_record")
    period = period if isinstance(period, dict) else {}
    access = metadata.get("access")
    access = access if isinstance(access, list) else []
    formats = [str(value).upper() for value in metadata.get("formats") or []]
    access_methods = [
        {
            "kind": str(item.get("kind") or ""),
            "url": str(item.get("url") or ""),
        }
        for item in access
        if isinstance(item, dict)
    ]
    archive_available = bool(access_methods)
    return {
        "source": str(metadata.get("source") or "NOAA_NCEI"),
        "product": str(metadata.get("product") or "National Digital Forecast Database"),
        "archive_available": archive_available,
        "period_of_record_start": str(
            period.get("by_wmo_header_start") or NDFD_PERIOD_OF_RECORD_START
        ),
        "online_history": str(period.get("online_history") or "APPROXIMATELY_TEN_YEARS"),
        "cloud_access_start": str(period.get("cloud_start") or NDFD_CLOUD_ACCESS_START),
        "access_methods": access_methods,
        "format": "GRIB2" if "GRIB2" in formats else (formats[0] if formats else "GRIB2"),
        "decode_status": NDFD_DECODE_STATUS,
        "quality_flags": [
            WeatherQualityFlag.NDFD_DECODE_UNAVAILABLE.value,
            WeatherQualityFlag.ARCHIVE_AVAILABLE_DECODE_DEFERRED.value,
        ],
        "catalog_entry_count": sum(
            1 for item in metadata.get("catalog_entries") or [] if isinstance(item, dict)
        ),
        "bulk_download_performed": False,
        "decoder_dependencies_added": [],
    }


def recognize_grib2(prefix: bytes) -> bool:
    """Recognize a GRIB2 indicator in a bounded byte-range prefix; never decode it."""

    if len(prefix) > MAX_NDFD_PROBE_BYTES:
        raise ValueError("NDFD_PROBE_TOO_LARGE")
    offset = prefix.find(b"GRIB")
    while offset >= 0:
        edition_offset = offset + 7
        if edition_offset < len(prefix) and prefix[edition_offset] == 2:
            return True
        offset = prefix.find(b"GRIB", offset + 4)
    return False


__all__ = [
    "MAX_NDFD_PROBE_BYTES",
    "NDFD_CLOUD_ACCESS_START",
    "NDFD_DECODE_STATUS",
    "NDFD_PERIOD_OF_RECORD_START",
    "characterize_ndfd_metadata",
    "recognize_grib2",
]
