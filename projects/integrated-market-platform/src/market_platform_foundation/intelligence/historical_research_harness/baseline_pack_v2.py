"""Frozen Historical Baseline Pack v2 (OpenD real corpus; definition-only lane)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...canonical import canonical_bytes, sha256_bytes
from ...paper.calibration.bar_ohlcv_prospective_proof import resolve_runtime_git_sha
from ...paper.calibration.dual_corpus import CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
from ...market_data.historical_development.builder import (
    HistoricalDevelopmentBuildResult,
    load_historical_development_build_from_evidence_corpus,
)
from .baseline_pack import (
    compute_experiment_definition_hash,
    default_baseline_pack_run_parameters,
    verify_frozen_experiment_definition,
)
from .features import DEFAULT_HISTORICAL_RESEARCH_FEATURES, HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION
from .strategies import (
    BASELINE_STRATEGY_MEAN_REVERSION_5M_SIGN_V1,
    BASELINE_STRATEGY_MOMENTUM_5M_SIGN_V1,
    BASELINE_STRATEGY_NO_TRADE_V1,
    BASELINE_STRATEGY_VOLUME_MOMENTUM_5M_V1,
)
from .types import HISTORICAL_RESEARCH_HARNESS_VERSION

HISTORICAL_BASELINE_PACK_V2 = "HISTORICAL_BASELINE_V2_OPEND"
HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID = "imp-integrate-experiment-05-r2-opend-baseline-pack-v2"
HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID = "LANE-E-HYP-OPEND-MULTI-SESSION-V2"
HISTORICAL_BASELINE_PACK_V2_DEFINITION_KIND = "historical_baseline_pack_experiment_definition_v2"
HISTORICAL_BASELINE_PACK_V2_DEFINITION_SCHEMA = "imp.historical-baseline-pack/2.0.0"
HISTORICAL_BASELINE_PACK_V2_RANDOM_SEED = 0

OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT = (
    "355FDBB852B94B964B62331839B58C3A336D1B52DB2F17FA05D30BA31389885B"
)
OPEND_AAPL_VERIFIED_SESSION_DATES: tuple[str, ...] = (
    "2026-09-10",
    "2026-09-11",
    "2026-09-14",
    "2026-09-15",
    "2026-09-16",
)
LANE_B_VERIFICATION_RECEIPT_REL = "evidence/market_data/lane_b/real-historical-provider-verification.json"

CANONICAL_BASELINE_PACK_V2_EVIDENCE_REL = (
    "evidence/historical-research/imp-integrate-experiment-05-r2-opend-baseline-pack-v2"
)

_BASELINE_STRATEGY_SPECS: tuple[dict[str, Any], ...] = (
    {
        "baseline_index": 0,
        "strategy_id": BASELINE_STRATEGY_NO_TRADE_V1,
        "strategy_version": "1.0.0",
        "description": "Null / no-edge: abstain all decisions (no simulated directional edge).",
    },
    {
        "baseline_index": 1,
        "strategy_id": BASELINE_STRATEGY_MOMENTUM_5M_SIGN_V1,
        "strategy_version": "1.0.0",
        "description": "Short-horizon momentum: sign(momentum_5m); abstain when feature missing.",
        "lookback_bars": 5,
    },
    {
        "baseline_index": 2,
        "strategy_id": BASELINE_STRATEGY_MEAN_REVERSION_5M_SIGN_V1,
        "strategy_version": "1.0.0",
        "description": "Short-horizon mean reversion: inverse sign of momentum_5m.",
        "lookback_bars": 5,
    },
    {
        "baseline_index": 3,
        "strategy_id": BASELINE_STRATEGY_VOLUME_MOMENTUM_5M_V1,
        "strategy_version": "1.0.0",
        "description": "Volume-aware momentum: sign(momentum_5m) when relative_volume_10m >= 1.0.",
        "lookback_bars": 5,
        "relative_volume_threshold": 1.0,
    },
)


def canonical_baseline_pack_v2_evidence_dir(repository_root: Path) -> Path:
    return repository_root / CANONICAL_BASELINE_PACK_V2_EVIDENCE_REL


def recompute_normalized_corpus_fingerprint(
    *,
    bars: Sequence[Mapping[str, Any]],
    historical_provenance: Mapping[str, Any],
) -> str:
    """Canonical normalized bar fingerprint (bars + provenance), Lane B compatible."""

    return sha256_bytes(
        canonical_bytes(
            {
                "bars": list(bars),
                "provenance": dict(historical_provenance),
            }
        )
    )


def verify_pinned_opend_corpus_fingerprint(
    *,
    repository_root: Path,
    corpus_dir: Path,
    expected_normalized_fingerprint: str = OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT,
) -> dict[str, Any]:
    """Recompute normalized fingerprint from pinned corpus; fail closed on mismatch."""

    manifest_path = corpus_dir / "dataset_manifest.json"
    if not manifest_path.is_file():
        return {
            "ok": False,
            "reason_code": "CORPUS_MANIFEST_MISSING",
            "expected_normalized_fingerprint": expected_normalized_fingerprint,
            "computed_normalized_fingerprint": None,
        }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provenance = (manifest.get("lineage") or {}).get("historical_provenance")
    if not isinstance(provenance, dict):
        return {
            "ok": False,
            "reason_code": "HISTORICAL_PROVENANCE_MISSING",
            "expected_normalized_fingerprint": expected_normalized_fingerprint,
            "computed_normalized_fingerprint": None,
        }
    normalized_files = sorted((corpus_dir / "normalized").glob("*_normalized.json"))
    if not normalized_files:
        return {
            "ok": False,
            "reason_code": "CORPUS_NORMALIZED_MISSING",
            "expected_normalized_fingerprint": expected_normalized_fingerprint,
            "computed_normalized_fingerprint": None,
        }
    bars = json.loads(normalized_files[0].read_text(encoding="utf-8"))
    computed = recompute_normalized_corpus_fingerprint(bars=bars, historical_provenance=provenance)
    session_dates = list((manifest.get("interval") or {}).get("session_dates") or [])
    row_count = int(manifest.get("row_count") or len(bars))
    lane_b_path = repository_root / LANE_B_VERIFICATION_RECEIPT_REL
    lane_b_fp = None
    if lane_b_path.is_file():
        lane_b = json.loads(lane_b_path.read_text(encoding="utf-8"))
        lane_b_fp = str((lane_b.get("moomoo") or {}).get("normalized_fingerprint") or "")
    ok = computed == expected_normalized_fingerprint
    if ok and lane_b_fp and lane_b_fp != expected_normalized_fingerprint:
        ok = False
        reason = "LANE_B_RECEIPT_FINGERPRINT_MISMATCH"
    elif not ok:
        reason = "DATASET_REPRODUCIBILITY_FAILURE"
    else:
        reason = None
    return {
        "ok": ok,
        "reason_code": reason,
        "expected_normalized_fingerprint": expected_normalized_fingerprint,
        "computed_normalized_fingerprint": computed,
        "manifest_dataset_fingerprint": str(manifest.get("dataset_fingerprint") or ""),
        "row_count": row_count,
        "session_dates": session_dates,
        "lane_b_receipt_fingerprint": lane_b_fp,
        "verification_method": "recompute_normalized_corpus_fingerprint(bars, lineage.historical_provenance)",
    }


def build_opend_v2_dataset_identity(
    *,
    repository_root: Path,
    corpus_dir: Path,
    fingerprint_verification: Mapping[str, Any],
) -> dict[str, Any]:
    manifest = json.loads((corpus_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    interval = manifest.get("interval") or {}
    return {
        "dataset_id": str(manifest.get("dataset_id") or "HIST-DEV-AAPL"),
        "dataset_fingerprint": str(fingerprint_verification["computed_normalized_fingerprint"]),
        "manifest_dataset_fingerprint": str(manifest.get("dataset_fingerprint") or ""),
        "provider_id": "moomoo.real_historical",
        "provider_lineage_id": str(
            ((manifest.get("lineage") or {}).get("historical_provenance") or {}).get("provider_id")
            or "moomoo.opend"
        ),
        "instrument": "AAPL",
        "start_date": str(interval.get("start_date") or OPEND_AAPL_VERIFIED_SESSION_DATES[0]),
        "end_date": str(interval.get("end_date") or OPEND_AAPL_VERIFIED_SESSION_DATES[-1]),
        "session_dates": list(interval.get("session_dates") or OPEND_AAPL_VERIFIED_SESSION_DATES),
        "row_count": int(fingerprint_verification.get("row_count") or manifest.get("row_count") or 0),
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "corpus_pin_path": corpus_dir.relative_to(repository_root).as_posix(),
        "lane_b_verification_receipt_path": LANE_B_VERIFICATION_RECEIPT_REL,
    }


def build_frozen_baseline_pack_v2_experiment_definition(
    *,
    repository_root: Path,
    dataset_identity: dict[str, Any],
    code_sha: str | None = None,
    created_timestamp_ns: int | None = None,
) -> dict[str, Any]:
    research_code_sha = code_sha or resolve_runtime_git_sha(start=repository_root)
    feature_specs = [
        {
            "feature_id": spec.feature_id,
            "schema_version": spec.schema_version,
            "lookback_bars": spec.lookback_bars,
            "missing_data_behavior": spec.missing_data_behavior.value,
        }
        for spec in DEFAULT_HISTORICAL_RESEARCH_FEATURES
    ]
    body: dict[str, Any] = {
        "artifact_kind": HISTORICAL_BASELINE_PACK_V2_DEFINITION_KIND,
        "schema_version": HISTORICAL_BASELINE_PACK_V2_DEFINITION_SCHEMA,
        "evidence_label": HISTORICAL_BASELINE_PACK_V2,
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "experiment_id": HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID,
        "harness_version": HISTORICAL_RESEARCH_HARNESS_VERSION,
        "feature_version": HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION,
        "execution_status": "DEFINITION_FROZEN_NOT_EXECUTED",
        "target_definition": {
            "label_kind": "historical_research_forward_return_label_v1",
            "forward_horizon_bars": 1,
        },
        "feature_definitions": feature_specs,
        "baseline_strategies": list(_BASELINE_STRATEGY_SPECS),
        "run_parameters": default_baseline_pack_run_parameters(),
        "dataset": dataset_identity,
        "research_code_sha": research_code_sha,
        "created_timestamp_ns": created_timestamp_ns if created_timestamp_ns is not None else time.time_ns(),
        "governance": {
            "authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            "item9_effect": "NONE",
            "item7_effect": "NONE",
            "ftep_effect": "NONE",
            "live_authority": "NONE",
            "promotional_language_forbidden": True,
            "prior_frozen_experiment_immutable": "imp-research-validation-04-lane-c-baseline-pack-v1",
        },
    }
    body["experiment_definition_hash"] = sha256_bytes(canonical_bytes(body))
    return body


def freeze_baseline_pack_v2_definition_to_disk(
    *,
    repository_root: Path,
    corpus_dir: Path | None = None,
    artifact_root: Path | None = None,
    code_sha: str | None = None,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    evidence_dir = artifact_root or canonical_baseline_pack_v2_evidence_dir(repository_root)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    pinned_corpus = corpus_dir or (evidence_dir / "corpus_pin")
    fingerprint_verification = verify_pinned_opend_corpus_fingerprint(
        repository_root=repository_root,
        corpus_dir=pinned_corpus,
    )
    if not fingerprint_verification.get("ok"):
        raise ValueError(str(fingerprint_verification.get("reason_code") or "DATASET_REPRODUCIBILITY_FAILURE"))
    dataset_identity = build_opend_v2_dataset_identity(
        repository_root=repository_root,
        corpus_dir=pinned_corpus,
        fingerprint_verification=fingerprint_verification,
    )
    definition = build_frozen_baseline_pack_v2_experiment_definition(
        repository_root=repository_root,
        dataset_identity=dataset_identity,
        code_sha=code_sha,
    )
    frozen_path = evidence_dir / "frozen_experiment_definition.json"
    frozen_path.write_text(json.dumps(definition, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verification_path = evidence_dir / "dataset_fingerprint_verification.json"
    verification_body = {
        **fingerprint_verification,
        "experiment_id": HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID,
        "corpus_pin_path": pinned_corpus.relative_to(repository_root).as_posix(),
    }
    verification_path.write_text(json.dumps(verification_body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    freeze_receipt = {
        "artifact_kind": "historical_baseline_pack_v2_freeze_receipt_v1",
        "EXPERIMENT_DEFINITION_FROZEN": "YES",
        "execution_status": "NOT_EXECUTED",
        "performance_run": "NO",
        "experiment_id": HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID,
        "experiment_definition_hash": definition["experiment_definition_hash"],
        "dataset_fingerprint": dataset_identity["dataset_fingerprint"],
        "research_code_sha": definition["research_code_sha"],
        "frozen_definition_path": frozen_path.relative_to(repository_root).as_posix(),
        "dataset_fingerprint_verification_path": verification_path.relative_to(repository_root).as_posix(),
        "canonical_evidence_dir": CANONICAL_BASELINE_PACK_V2_EVIDENCE_REL,
    }
    receipt_path = evidence_dir / "baseline_pack_v2_freeze_receipt.json"
    receipt_path.write_text(json.dumps(freeze_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return frozen_path, definition, freeze_receipt


def load_pinned_opend_build(repository_root: Path) -> HistoricalDevelopmentBuildResult:
    """Load pinned OpenD corpus for integrity checks (not execution)."""

    corpus_dir = canonical_baseline_pack_v2_evidence_dir(repository_root) / "corpus_pin"
    return load_historical_development_build_from_evidence_corpus(
        repository_root=repository_root,
        corpus_dir=corpus_dir,
    )


__all__ = [
    "CANONICAL_BASELINE_PACK_V2_EVIDENCE_REL",
    "HISTORICAL_BASELINE_PACK_V2",
    "HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID",
    "HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID",
    "OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT",
    "OPEND_AAPL_VERIFIED_SESSION_DATES",
    "build_frozen_baseline_pack_v2_experiment_definition",
    "build_opend_v2_dataset_identity",
    "canonical_baseline_pack_v2_evidence_dir",
    "compute_experiment_definition_hash",
    "freeze_baseline_pack_v2_definition_to_disk",
    "load_pinned_opend_build",
    "recompute_normalized_corpus_fingerprint",
    "verify_frozen_experiment_definition",
    "verify_pinned_opend_corpus_fingerprint",
]
