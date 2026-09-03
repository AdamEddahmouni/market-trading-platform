"""Frozen local evidence inputs for Batch 07 -- provenance metadata only, never OHLCV.

Loads the Batch 05 request/artifact manifests (coverage metadata, sha256, byte length)
and recomputes each case's frozen detection boundary id deterministically with the
project's own identifier function. A hard guard refuses to open any ``raw/`` bar file
(CSV/JSONL), so the readiness runtime cannot read OHLCV or forward-outcome values.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..identifiers import deterministic_acquisition_id
from ..models import BoundaryRule
from .models import ArtifactCoverage

# Frozen cohort in exact source order -- never reordered.
FROZEN_COHORT: tuple[tuple[str, str], ...] = (
    ("XNCR", "BATCH01_XNCR_20260718"),
    ("PESI", "BATCH01_PESI_20260718"),
    ("SLS", "BATCH01_SLS_20260718"),
    ("ZNTL", "BATCH01_ZNTL_20260718"),
    ("GPRE", "BATCH01_GPRE_20260718"),
    ("SSPC", "BATCH01_SSPC_20260718"),
    ("LBGJ", "BATCH01_LBGJ_20260718"),
    ("TRVI", "BATCH01_TRVI_20260718"),
    ("LMNX", "BATCH01_LMNX_20260718"),
    ("MGNX", "BATCH01_MGNX_20260718"),
    ("BHVN", "BATCH01_BHVN_20260718"),
    ("OBE", "BATCH01_OBE_20260718"),
    ("AVTX", "BATCH01_AVTX_20260718"),
    ("KLRS", "BATCH01_KLRS_20260718"),
    ("SG", "BATCH01_SG_20260718"),
)

FROZEN_BOUNDARY = datetime(2026, 7, 18, 13, 37, 55, 17661, tzinfo=UTC)
FROZEN_BOUNDARY_RULE = BoundaryRule.ORIGINAL_PLATFORM_SURFACED_TIMESTAMP
DETECTION_CONTEXT_REQUEST = "DETECTION_CONTEXT_PRECEDING_24H"
FORWARD_REQUEST = "FROZEN_FORWARD_24H"
BAR_INTERVAL_LABEL = "1 min"
BAR_INTERVAL_SECONDS = 60
REQUESTED_DURATION_SECONDS = 86400

# The only manifest files Batch 07 is permitted to open. Anything under ``raw/`` is
# categorically refused so OHLCV / forward-outcome values are never read.
ALLOWED_MANIFEST_NAMES = frozenset(
    {"request-manifest.json", "artifact-manifest.json", "sha256-manifest.json"}
)


class OhlcvAccessError(RuntimeError):
    """Raised if anything tries to open a raw bar (OHLCV) artifact from this package."""


def boundary_id_for(case_id: str, symbol: str) -> str:
    """Recompute the frozen detection-boundary id deterministically (not a guess).

    Uses the project's canonical identifier over the same frozen inputs the Batch 01
    freeze used (case attempt id, symbol, boundary rule), so the value is byte-identical
    to the committed Batch 01 boundary freeze without reading or mutating that registry.
    """
    return deterministic_acquisition_id(
        {
            "result_type": "DETECTION_BOUNDARY",
            "case_attempt_id": case_id,
            "symbol": symbol.strip().upper(),
            "rule": FROZEN_BOUNDARY_RULE,
        }
    )


def _guard_manifest_path(path: Path) -> Path:
    parts = {p.lower() for p in path.parts}
    if "raw" in parts or path.suffix.lower() in {".csv", ".jsonl"}:
        raise OhlcvAccessError(
            f"refusing to open a raw bar artifact from operation_readiness: {path.name}"
        )
    if path.name not in ALLOWED_MANIFEST_NAMES:
        raise OhlcvAccessError(f"not an allowed provenance manifest: {path.name}")
    return path


def _load_json(path: Path) -> object:
    _guard_manifest_path(path)
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class DetectionContextEvidence:
    symbol: str
    csv_sha256: str
    csv_byte_length: int
    coverage: ArtifactCoverage


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def load_detection_context_evidence(batch05_root: Path) -> dict[str, DetectionContextEvidence]:
    """Load per-symbol detection-context coverage + artifact identity from frozen manifests."""
    requests = _load_json(batch05_root / "requests" / "request-manifest.json")
    artifacts = _load_json(batch05_root / "provenance" / "artifact-manifest.json")

    coverage_by_symbol: dict[str, dict] = {
        row["symbol"]: row
        for row in requests  # type: ignore[union-attr]
        if row["request_name"] == DETECTION_CONTEXT_REQUEST
    }
    artifact_by_symbol: dict[str, dict] = {
        row["symbol"]: row
        for row in artifacts  # type: ignore[union-attr]
        if row["request_name"] == DETECTION_CONTEXT_REQUEST
    }

    result: dict[str, DetectionContextEvidence] = {}
    for symbol, req in coverage_by_symbol.items():
        art = artifact_by_symbol[symbol]
        observed_end = _parse_utc(req["last_timestamp_utc"])
        max_completion = observed_end + timedelta(seconds=BAR_INTERVAL_SECONDS)
        gap = (FROZEN_BOUNDARY - max_completion) // timedelta(seconds=1)
        coverage = ArtifactCoverage(
            requested_window_start=FROZEN_BOUNDARY
            - timedelta(seconds=REQUESTED_DURATION_SECONDS),
            requested_window_end=FROZEN_BOUNDARY,
            observed_coverage_start=_parse_utc(req["first_timestamp_utc"]),
            observed_coverage_end=observed_end,
            bar_count=int(req["bar_count"]),
            bar_interval=BAR_INTERVAL_LABEL,
            max_possible_final_bar_completion=max_completion,
            gap_seconds_from_definitely_completed_to_boundary=max(gap, 0),
        )
        result[symbol] = DetectionContextEvidence(
            symbol=symbol,
            csv_sha256=art["csv_sha256"],
            csv_byte_length=int(art["csv_byte_length"]),
            coverage=coverage,
        )
    return result


def forward_artifact_identity(batch05_root: Path) -> dict[str, tuple[str, int]]:
    """Filename/sha/byte-length identity of forward artifacts, to prove they are untouched.

    Reads only the artifact manifest metadata; never opens the forward CSV/JSONL bytes.
    """
    artifacts = _load_json(batch05_root / "provenance" / "artifact-manifest.json")
    return {
        row["symbol"]: (row["csv_sha256"], int(row["csv_byte_length"]))
        for row in artifacts  # type: ignore[union-attr]
        if row["request_name"] == FORWARD_REQUEST
    }


__all__ = [
    "FROZEN_COHORT",
    "FROZEN_BOUNDARY",
    "FROZEN_BOUNDARY_RULE",
    "DETECTION_CONTEXT_REQUEST",
    "FORWARD_REQUEST",
    "BAR_INTERVAL_LABEL",
    "BAR_INTERVAL_SECONDS",
    "ALLOWED_MANIFEST_NAMES",
    "OhlcvAccessError",
    "DetectionContextEvidence",
    "boundary_id_for",
    "load_detection_context_evidence",
    "forward_artifact_identity",
]
