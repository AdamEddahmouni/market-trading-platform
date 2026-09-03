"""Offline Batch 06 semantic-overlay generator tests.

Synthetic private fixtures only: a temp private root, synthetic CSV bytes, and a
synthetic sha256/request manifest. No network, no Gateway, no account data, no real
bars, no committed provider data.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.ibkr_historical_export.cohort import DETECTION_CONTEXT, FROZEN_FORWARD
from tools.ibkr_historical_export.paths import PrivateLayout
from tools.ibkr_historical_export.semantics_overlay import (
    FORWARD_ARTIFACT_STATUS,
    generate_overlays,
)
from tools.ibkr_historical_export.serialization import serialize_bars_csv, sha256_and_length

from ._fakes import make_bar

_SYMBOL = "XNCR"


def _seed_private_root(root: Path) -> PrivateLayout:
    layout = PrivateLayout(root)
    layout.ensure()

    bars = [
        make_bar(
            _SYMBOL,
            DETECTION_CONTEXT,
            111,
            0,
            timestamp_utc="2026-07-18T12:00:00Z",
            timestamp_epoch=1784443200,
        )
    ]
    csv_bytes = serialize_bars_csv(bars)
    layout.raw_csv(_SYMBOL, DETECTION_CONTEXT).write_bytes(csv_bytes)
    sha, length = sha256_and_length(csv_bytes)

    relative = layout.raw_relative_csv(_SYMBOL, DETECTION_CONTEXT)
    layout.sha256_manifest.write_text(
        json.dumps({relative: {"byte_length": length, "sha256": sha}}),
        encoding="utf-8",
    )
    layout.request_manifest.write_text(
        json.dumps(
            [
                {
                    "symbol": _SYMBOL,
                    "request_name": DETECTION_CONTEXT,
                    "retrieval_started_at": "2026-07-24T00:12:49.538012Z",
                    "retrieval_completed_at": "2026-07-24T00:12:52.454270Z",
                    "status": "HISTORICAL_REQUEST_SUCCESS",
                }
            ]
        ),
        encoding="utf-8",
    )
    return layout, sha, length


def test_detection_context_ibkr_volume_semantics_remain_unknown(tmp_path):
    layout, sha, length = _seed_private_root(tmp_path)
    summary = generate_overlays(layout, symbols=(_SYMBOL,))

    assert summary["detection_context_count"] == 1
    item = summary["detection_context_preflight"][0]
    assert item["preflight_status"] == "PREFLIGHT_READY"
    assert item["reason_codes"] == []
    assert "volume_adjustment_semantics" in summary["unresolved_fields"]


def test_resolved_price_is_split_adjusted_in_overlay(tmp_path):
    layout, _, _ = _seed_private_root(tmp_path)
    generate_overlays(layout, symbols=(_SYMBOL,))
    manifest_overlay = json.loads(
        (layout.root / "semantics" / "batch-06" / f"{_SYMBOL}-detection-context-intake-manifest.json")
        .read_text(encoding="utf-8")
    )
    intake = manifest_overlay["intake_manifest"]
    assert intake["price_adjustment_semantics"] == "SPLIT_ADJUSTED"
    assert intake["corporate_action_handling"] == "ADJUSTMENTS_APPLIED"
    assert intake["volume_adjustment_semantics"] == "UNKNOWN"
    assert intake["timestamp_semantics"] == "UNKNOWN"


def test_overlay_preserves_original_provenance(tmp_path):
    layout, sha, length = _seed_private_root(tmp_path)
    generate_overlays(layout, symbols=(_SYMBOL,))
    manifest_overlay = json.loads(
        (layout.root / "semantics" / "batch-06" / f"{_SYMBOL}-detection-context-intake-manifest.json")
        .read_text(encoding="utf-8")
    )
    prov = manifest_overlay["provenance"]
    assert prov["original_artifact_sha256"] == sha
    assert prov["original_artifact_byte_length"] == length
    assert prov["batch_05_request_class"] == DETECTION_CONTEXT


def test_raw_bytes_never_modified(tmp_path):
    layout, sha, _ = _seed_private_root(tmp_path)
    before = layout.raw_csv(_SYMBOL, DETECTION_CONTEXT).read_bytes()
    generate_overlays(layout, symbols=(_SYMBOL,))
    after = layout.raw_csv(_SYMBOL, DETECTION_CONTEXT).read_bytes()
    assert before == after
    assert sha256_and_length(after)[0] == sha


def test_forward_artifacts_excluded_from_forward_use(tmp_path):
    layout, _, _ = _seed_private_root(tmp_path)
    summary = generate_overlays(layout, symbols=(_SYMBOL,))
    forward = summary["forward_artifacts"]
    assert forward["request_class"] == FROZEN_FORWARD
    assert forward["status"] == FORWARD_ARTIFACT_STATUS
    assert forward["re_preflighted_as_forward_evidence"] is False


def test_overlay_generation_is_deterministic(tmp_path):
    layout, _, _ = _seed_private_root(tmp_path)
    generate_overlays(layout, symbols=(_SYMBOL,))
    out_dir = layout.root / "semantics" / "batch-06"
    first = {p.name: p.read_bytes() for p in sorted(out_dir.glob("*.json"))}
    generate_overlays(layout, symbols=(_SYMBOL,))
    second = {p.name: p.read_bytes() for p in sorted(out_dir.glob("*.json"))}
    assert first == second


def test_volume_setting_evidence_records_unresolved(tmp_path):
    layout, _, _ = _seed_private_root(tmp_path)
    generate_overlays(layout, symbols=(_SYMBOL,))
    doc = json.loads(
        (layout.root / "semantics" / "batch-06" / "local-volume-setting-evidence.json")
        .read_text(encoding="utf-8")
    )
    assert doc["historical_us_stock_volume_setting"] == "HISTORICAL_VOLUME_UNIT_UNRESOLVED"


def test_no_outcome_or_case_association_in_reports(tmp_path):
    layout, _, _ = _seed_private_root(tmp_path)
    generate_overlays(layout, symbols=(_SYMBOL,))
    report_overlay = json.loads(
        (layout.root / "semantics" / "batch-06" / f"{_SYMBOL}-detection-context-preflight-report.json")
        .read_text(encoding="utf-8")
    )
    report = report_overlay["readiness_report"]
    assert report["case_association_performed"] is False
    assert report["outcome_capture_performed"] is False
    assert report["phase_3e_started"] is False
