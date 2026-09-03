"""Capture metadata for SEC FTD archives."""

from __future__ import annotations

from typing import Any

from ..canonical import sha256_bytes
from ..market_data.lifecycle import ObservationLifecycle
from .parser import PARSER_VERSION
from .transport import FtdArchiveCapture

CAPTURE_SCHEMA = "sec_ftd.archive_envelope/1.0.0"


def build_archive_envelope(capture: FtdArchiveCapture, *, record_count: int) -> dict[str, Any]:
    return {
        "schema_version": CAPTURE_SCHEMA,
        "source": "sec_fails_to_deliver",
        "provider": "sec.gov",
        "dataset": "fails-to-deliver",
        "lifecycle": ObservationLifecycle.CAPTURED.value,
        "period_key": capture.period.period_key,
        "source_period": capture.period.label,
        "source_url": capture.source_url,
        "content_hash": capture.content_hash,
        "record_count": record_count,
        "parser_version": PARSER_VERSION,
        "first_observed_time": capture.first_observed_time,
        "retrieved_time": capture.retrieved_time,
        "cache_path": capture.cache_path,
        "replaced_prior_hash": capture.replaced_prior_hash,
        "raw_payload_hash": sha256_bytes(capture.content_bytes),
    }


__all__ = ["CAPTURE_SCHEMA", "build_archive_envelope"]
