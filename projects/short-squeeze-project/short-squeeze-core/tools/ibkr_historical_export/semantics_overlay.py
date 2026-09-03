"""Offline Batch 06 semantic-overlay generator.

Reads the frozen Batch 05 private manifests, applies the deterministic IBKR semantic
resolver, rebuilds an ``IntakeManifest`` per detection-context symbol with the resolved
semantics, runs the *existing* Batch 04 offline preflight on the exact preserved raw CSV
bytes, and writes new **versioned private overlays** under
``intake/local-bars/ibkr-batch-05/semantics/batch-06/``. The original Batch 05 raw bytes
and manifests are never modified.

No network, no Gateway connection, no account/credential access, no case association, no
outcome work. Only the 13 ``DETECTION_CONTEXT_PRECEDING_24H`` CSVs are re-preflighted; the
``FROZEN_FORWARD_24H`` artifacts are recorded as excluded from forward-outcome use.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from squeeze_core.acquisition.ibkr_semantics import (
    OFFICIAL_CITATIONS,
    OFFICIAL_TRADES_EVIDENCE,
    ResolvedIbkrSemantics,
    resolve_ibkr_semantics,
)
from squeeze_core.acquisition.local_bar_intake.models import IntakeManifest
from squeeze_core.acquisition.local_bar_intake.semantics import (
    ArtifactFormat,
    BarInterval,
    DataTimeBasis,
    IntendedUse,
    ValueAuthenticity,
)
from squeeze_core.serialization.canonical_json import canonical_json_bytes

from .cohort import DETECTION_CONTEXT, FROZEN_FORWARD, FROZEN_SYMBOLS, REQUEST_A
from .paths import PrivateLayout, default_private_root
from .preflight_bundle import (
    ENTITLEMENT_ASSERTION,
    PROVIDER_NAME,
    PROVIDER_PRODUCT,
    build_profile,
    run_preflight_from_bytes,
)
from .statuses import PreflightStatus

# Fixed, explicit access date for the official-documentation research (outside identity;
# never wall-clock) so overlay bytes are reproducible run-to-run.
EVIDENCE_ACCESS_DATE = "2026-07-25"

# The forward artifacts succeeded as requests but their returned coverage is the prior
# Friday session, not the frozen forward window. Recorded verbatim; never promoted.
FORWARD_ARTIFACT_STATUS = (
    "REQUEST_SUCCEEDED_BUT_RETURNED_COVERAGE_DOES_NOT_REPRESENT_FROZEN_FORWARD_WINDOW"
)

BATCH_06_SEMANTICS_VERSION = "phase_3d_ibkr_semantics_resolution.batch06.v1"

_STATUS_MAP = {
    "READY_FOR_FUTURE_ASSOCIATION": PreflightStatus.PREFLIGHT_READY,
    "NOT_READY_QUARANTINED": PreflightStatus.PREFLIGHT_QUARANTINED,
    "NOT_READY_REJECTED": PreflightStatus.PREFLIGHT_REJECTED,
}


@dataclass(frozen=True, slots=True)
class SymbolOverlay:
    symbol: str
    bundle_id: str
    preflight_status: PreflightStatus
    reason_codes: tuple[str, ...]
    original_sha256: str
    original_byte_length: int


def _semantics_dir(layout: PrivateLayout) -> Path:
    return layout.root / "semantics" / "batch-06"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_utc(value: str) -> datetime:
    # Batch 05 recorded ISO-8601 with a trailing 'Z'.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _detection_request_times(request_manifest: list[dict], symbol: str) -> tuple[datetime, datetime]:
    for record in request_manifest:
        if record.get("symbol") == symbol and record.get("request_name") == DETECTION_CONTEXT:
            started = _parse_utc(record["retrieval_started_at"])
            completed = _parse_utc(record["retrieval_completed_at"])
            return started, completed
    raise KeyError(f"no detection-context request record for {symbol}")


def build_resolved_manifest(
    *,
    symbol: str,
    artifact_relative_path: str,
    artifact_sha256: str,
    artifact_byte_length: int,
    retrieval_time: datetime,
    export_time: datetime,
    resolved: ResolvedIbkrSemantics,
    profile_id: str,
) -> IntakeManifest:
    """IBKR intake manifest carrying the Batch 06 resolved semantics (honest)."""
    return IntakeManifest(
        bundle_id=f"IBKR_BATCH05_{symbol}_{DETECTION_CONTEXT}",
        provider_name=PROVIDER_NAME,
        provider_product_or_export_name=PROVIDER_PRODUCT,
        user_entitlement_assertion=ENTITLEMENT_ASSERTION,
        license_or_terms_reference="IB API Non-Commercial License",
        retrieval_time=retrieval_time,
        export_time=export_time,
        artifact_relative_path=artifact_relative_path,
        artifact_sha256=artifact_sha256,
        artifact_byte_length=artifact_byte_length,
        artifact_media_type="text/csv",
        artifact_format=ArtifactFormat.CSV,
        provider_symbol=symbol,
        canonical_symbol=symbol,
        market_or_venue="SMART",
        bar_interval=BarInterval.ONE_MINUTE,
        event_timezone=resolved.event_timezone,
        timestamp_semantics=resolved.timestamp_semantics,
        session_coverage=resolved.session_coverage,
        price_adjustment_semantics=resolved.price_adjustment_semantics,
        volume_adjustment_semantics=resolved.volume_adjustment_semantics,
        corporate_action_handling=resolved.corporate_action_handling,
        data_time_basis=DataTimeBasis.HISTORICAL,
        value_authenticity=ValueAuthenticity.VENDOR_SUPPLIED,
        intended_use=IntendedUse.HISTORICAL_EVIDENCE,
        expected_start_time=REQUEST_A.expected_window_start,
        expected_end_time=REQUEST_A.expected_window_end,
        column_mapping_profile_id=profile_id,
        notes=(
            "Batch 06 resolved semantics: price SPLIT_ADJUSTED (official); volume "
            "adjustment and intraday bar start/end remain UNKNOWN (official docs silent)."
        ),
    )


def _evidence_document(resolved: ResolvedIbkrSemantics) -> dict:
    return {
        "batch_06_semantics_version": BATCH_06_SEMANTICS_VERSION,
        "evidence_access_date": EVIDENCE_ACCESS_DATE,
        "request_evidence": OFFICIAL_TRADES_EVIDENCE.model_dump(mode="python"),
        "citations": [c.model_dump(mode="python") for c in OFFICIAL_CITATIONS],
        "resolved_semantics": resolved.model_dump(mode="python"),
    }


def _volume_setting_document(resolved: ResolvedIbkrSemantics) -> dict:
    return {
        "batch_06_semantics_version": BATCH_06_SEMANTICS_VERSION,
        "evidence_access_date": EVIDENCE_ACCESS_DATE,
        "historical_us_stock_volume_setting": resolved.volume_unit_code.value,
        "evidence_hierarchy": {
            "level_1_batch05_capture": "NOT_CAPTURED",
            "level_2_local_config": "OBFUSCATED_BINARY_ibg_xml; jts.ini has no lots key",
            "level_3_gateway_ui": "DECLINED (live-session invasive; does not gate preflight)",
            "level_4_outcome": resolved.volume_unit_code.value,
        },
        "note": (
            "Volume unit is not an IntakeManifest field and never gates preflight; it is "
            "recorded as provenance only. Never inferred from bar values or build number."
        ),
    }


def _write_canonical(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = payload if isinstance(payload, (bytes, bytearray)) else canonical_json_bytes(payload)
    path.write_bytes(body)


def generate_overlays(
    layout: PrivateLayout | None = None,
    symbols: tuple[str, ...] = FROZEN_SYMBOLS,
) -> dict:
    """Generate all Batch 06 private semantic overlays. Returns a sanitized summary.

    ``symbols`` defaults to the frozen 13; a subset is accepted only for deterministic
    testing against synthetic fixtures and never changes the production cohort.
    """
    layout = layout or PrivateLayout(default_private_root())
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)

    sha_manifest = _load_json(layout.sha256_manifest)
    request_manifest = _load_json(layout.request_manifest)
    out_dir = _semantics_dir(layout)

    # Batch-level evidence documents.
    _write_canonical(out_dir / "ibkr-official-semantics-evidence.json", _evidence_document(resolved))
    _write_canonical(out_dir / "local-volume-setting-evidence.json", _volume_setting_document(resolved))
    _write_canonical(
        out_dir / "semantic-resolution-manifest.json",
        {
            "batch_06_semantics_version": BATCH_06_SEMANTICS_VERSION,
            "resolved_semantics": resolved.model_dump(mode="python"),
            "unresolved_fields": list(resolved.unresolved_fields),
            "filtered_feed_disclosure": resolved.filtered_feed_disclosure,
        },
    )

    overlays: list[SymbolOverlay] = []
    for symbol in symbols:
        relative = layout.raw_relative_csv(symbol, DETECTION_CONTEXT)
        entry = sha_manifest[relative]
        sha256 = entry["sha256"]
        byte_length = entry["byte_length"]
        started, completed = _detection_request_times(request_manifest, symbol)

        profile = build_profile(f"IBKR_BATCH05_{symbol}_{DETECTION_CONTEXT}")
        manifest = build_resolved_manifest(
            symbol=symbol,
            artifact_relative_path=relative,
            artifact_sha256=sha256,
            artifact_byte_length=byte_length,
            retrieval_time=started,
            export_time=completed,
            resolved=resolved,
            profile_id=profile.profile_id,
        )
        csv_bytes = layout.raw_csv(symbol, DETECTION_CONTEXT).read_bytes()
        report = run_preflight_from_bytes(manifest, profile, csv_bytes)
        status = _STATUS_MAP[report.status.value]
        reason_codes = tuple(code.value for code in report.reason_codes)

        # Per-symbol intake manifest overlay with back-provenance.
        _write_canonical(
            out_dir / f"{symbol}-detection-context-intake-manifest.json",
            {
                "batch_06_semantics_version": BATCH_06_SEMANTICS_VERSION,
                "provenance": {
                    "original_artifact_relative_path": relative,
                    "original_artifact_sha256": sha256,
                    "original_artifact_byte_length": byte_length,
                    "batch_05_bundle_id": manifest.bundle_id,
                    "batch_05_request_class": DETECTION_CONTEXT,
                },
                "intake_manifest": manifest.model_dump(mode="python"),
            },
        )
        # Per-symbol preflight report overlay.
        _write_canonical(
            out_dir / f"{symbol}-detection-context-preflight-report.json",
            {
                "batch_06_semantics_version": BATCH_06_SEMANTICS_VERSION,
                "preflight_status": status.value,
                "provenance": {
                    "original_artifact_sha256": sha256,
                    "original_artifact_byte_length": byte_length,
                    "batch_05_request_class": DETECTION_CONTEXT,
                },
                "readiness_report": report.model_dump(mode="python"),
            },
        )
        overlays.append(
            SymbolOverlay(
                symbol=symbol,
                bundle_id=manifest.bundle_id,
                preflight_status=status,
                reason_codes=reason_codes,
                original_sha256=sha256,
                original_byte_length=byte_length,
            )
        )

    summary = {
        "batch_06_semantics_version": BATCH_06_SEMANTICS_VERSION,
        "evidence_access_date": EVIDENCE_ACCESS_DATE,
        "detection_context_count": len(overlays),
        "resolved_semantics": resolved.model_dump(mode="python"),
        "unresolved_fields": list(resolved.unresolved_fields),
        "detection_context_preflight": [
            {
                "symbol": o.symbol,
                "bundle_id": o.bundle_id,
                "preflight_status": o.preflight_status.value,
                "reason_codes": list(o.reason_codes),
                "original_artifact_sha256": o.original_sha256,
                "original_artifact_byte_length": o.original_byte_length,
            }
            for o in overlays
        ],
        "forward_artifacts": {
            "request_class": FROZEN_FORWARD,
            "status": FORWARD_ARTIFACT_STATUS,
            "re_preflighted_as_forward_evidence": False,
        },
    }
    _write_canonical(out_dir / "batch-06-private-summary.json", summary)
    return summary


__all__ = [
    "EVIDENCE_ACCESS_DATE",
    "FORWARD_ARTIFACT_STATUS",
    "BATCH_06_SEMANTICS_VERSION",
    "SymbolOverlay",
    "build_resolved_manifest",
    "generate_overlays",
]
