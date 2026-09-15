"""Machine validator for ``ftep_catalyst_watch_report`` prospective Finviz receipts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ...news.timestamps import epoch_ns_from_iso
from .ftep_integrity import FTEP_V1_002_EXPECTED_FINGERPRINT

_ARTIFACT_KIND = "ftep_catalyst_watch_report"
_SCHEMA_VERSION = "1.0.0"
_CAMPAIGN_SLUG = "FTEP-V1-002"
_WATCH_MODE_PROSPECTIVE = "PROSPECTIVE_FINVIZ_INGRESS"
_ATTENTION_LIVE = "LIVE_PROSPECTIVE"
_TEST_MODE = "SIGNAL_ONLY"
_INGRESS_ZERO_ROWS = "LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS"
_INGRESS_SUCCESS = "LIVE_INGRESS_SUCCESS"
_INGRESS_FAILED = "LIVE_INGRESS_FAILED"
_LIVE_SOURCE_LABEL = "live:finviz_elite_prospective"

_GOVERNED_SESSION_IDS_FTEP_V1_002: frozenset[str] = frozenset(
    {
        "fts-6DB7771FD9B3A991",
        "fts-D93189A042A1BEF2",
    }
)

VERDICT_VALID = "VALID"
VERDICT_VALID_WITH_LIMITATIONS = "VALID_WITH_LIMITATIONS"
VERDICT_INVALID = "INVALID"

# Hard failures (artifact or prospective claim is unlawful).
REASON_ARTIFACT_KIND_MISMATCH = "ARTIFACT_KIND_MISMATCH"
REASON_SCHEMA_VERSION_UNSUPPORTED = "SCHEMA_VERSION_UNSUPPORTED"
REASON_CAMPAIGN_SLUG_UNSUPPORTED = "CAMPAIGN_SLUG_UNSUPPORTED"
REASON_MANIFEST_FINGERPRINT_MISMATCH = "MANIFEST_FINGERPRINT_MISMATCH"
REASON_GOVERNED_SESSION_IDS_MISSING = "GOVERNED_SESSION_IDS_MISSING"
REASON_GOVERNED_SESSION_IDS_UNEXPECTED = "GOVERNED_SESSION_IDS_UNEXPECTED"
REASON_WATCH_MODE_NOT_PROSPECTIVE = "WATCH_MODE_NOT_PROSPECTIVE"
REASON_FIXTURE_SMOKE_NOT_PROSPECTIVE = "FIXTURE_SMOKE_NOT_PROSPECTIVE"
REASON_ATTENTION_DATA_KIND_NOT_LIVE = "ATTENTION_DATA_KIND_NOT_LIVE_PROSPECTIVE"
REASON_TEST_MODE_NOT_SIGNAL_ONLY = "TEST_MODE_NOT_SIGNAL_ONLY"
REASON_DRY_RUN_NOT_TRUE = "DRY_RUN_NOT_TRUE"
REASON_US_EQUITY_RTH_CLOSED = "US_EQUITY_RTH_CLOSED_FOR_PROSPECTIVE"
REASON_INGRESS_OUTCOME_FAILED = "INGRESS_OUTCOME_FAILED"
REASON_INGRESS_OUTCOME_MISSING = "INGRESS_OUTCOME_MISSING"
REASON_PROVIDER_MISSING = "PROVIDER_MISSING_ON_SUMMARY"
REASON_SOURCE_LABEL_NOT_LIVE = "ATTENTION_SOURCE_NOT_LIVE_PROSPECTIVE"
REASON_PUBLISHED_AFTER_RETRIEVAL = "PUBLISHED_AFTER_RETRIEVAL"
REASON_PUBLISHED_TIME_FUTURE = "PUBLISHED_TIME_FUTURE_DATED"
REASON_EMPIRICAL_LOCK_COUNT_MISSING = "EMPIRICAL_LOCK_COUNT_MISSING"
REASON_EMPIRICAL_LOCK_PRESENT = "EMPIRICAL_LOCK_PRESENT"
REASON_DURABLE_LOCK_PRESENT = "DURABLE_LOCK_PRESENT"
REASON_ORDERS_PRESENT = "ORDERS_PRESENT"
REASON_SUMMARY_COUNT_MISMATCH = "SUMMARY_COUNT_MISMATCH"
REASON_ROW_COUNT_MISMATCH = "PROSPECTIVE_INGRESS_ROW_COUNT_MISMATCH"
REASON_FIXTURE_PROVENANCE = "FIXTURE_PROVENANCE_LIVE_CLAIM"
REASON_SIDECAR_ARTIFACT_HASH_MISMATCH = "SIDECAR_ARTIFACT_HASH_MISMATCH"
REASON_SIDECAR_EVIDENCE_CLASS_UPGRADE = "SIDECAR_EVIDENCE_CLASS_UPGRADE_REJECTED"
REASON_SECRETS_INCLUDED = "SECRETS_INCLUDED_TRUE"

# Limitations (artifact may still be structurally lawful; does not earn program gates).
REASON_RUNTIME_SHA_MISSING = "RUNTIME_SHA_MISSING"
REASON_ZERO_QUALIFYING_ROWS = "LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS"
REASON_DISPOSITION_BLOCKED = "DISPOSITION_BLOCKED"
REASON_NOT_PROSPECTIVE_OBSERVATION = "NOT_PROSPECTIVE_OBSERVATION"

_ERROR_REASONS = frozenset(
    {
        REASON_ARTIFACT_KIND_MISMATCH,
        REASON_SCHEMA_VERSION_UNSUPPORTED,
        REASON_CAMPAIGN_SLUG_UNSUPPORTED,
        REASON_MANIFEST_FINGERPRINT_MISMATCH,
        REASON_GOVERNED_SESSION_IDS_MISSING,
        REASON_GOVERNED_SESSION_IDS_UNEXPECTED,
        REASON_WATCH_MODE_NOT_PROSPECTIVE,
        REASON_FIXTURE_SMOKE_NOT_PROSPECTIVE,
        REASON_ATTENTION_DATA_KIND_NOT_LIVE,
        REASON_TEST_MODE_NOT_SIGNAL_ONLY,
        REASON_DRY_RUN_NOT_TRUE,
        REASON_US_EQUITY_RTH_CLOSED,
        REASON_INGRESS_OUTCOME_FAILED,
        REASON_INGRESS_OUTCOME_MISSING,
        REASON_PROVIDER_MISSING,
        REASON_SOURCE_LABEL_NOT_LIVE,
        REASON_PUBLISHED_AFTER_RETRIEVAL,
        REASON_PUBLISHED_TIME_FUTURE,
        REASON_EMPIRICAL_LOCK_COUNT_MISSING,
        REASON_EMPIRICAL_LOCK_PRESENT,
        REASON_DURABLE_LOCK_PRESENT,
        REASON_ORDERS_PRESENT,
        REASON_SUMMARY_COUNT_MISMATCH,
        REASON_ROW_COUNT_MISMATCH,
        REASON_FIXTURE_PROVENANCE,
        REASON_SIDECAR_ARTIFACT_HASH_MISMATCH,
        REASON_SIDECAR_EVIDENCE_CLASS_UPGRADE,
        REASON_SECRETS_INCLUDED,
    }
)

_LIMITATION_REASONS = frozenset(
    {
        REASON_RUNTIME_SHA_MISSING,
        REASON_ZERO_QUALIFYING_ROWS,
        REASON_DISPOSITION_BLOCKED,
        REASON_NOT_PROSPECTIVE_OBSERVATION,
    }
)


def _artifact_evidence_class(report: Mapping[str, Any]) -> str:
    watch_mode = str(report.get("watch_mode") or "")
    attention_kind = str(report.get("attention_data_kind") or "")
    if watch_mode == "FIXTURE_SMOKE" or attention_kind in {"FIXTURE", "SAMPLE"}:
        return "FIXTURE"
    if watch_mode == _WATCH_MODE_PROSPECTIVE and attention_kind == _ATTENTION_LIVE:
        return "LIVE_PROSPECTIVE"
    return "SOFTWARE"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest().upper()


def _orders_present(report: Mapping[str, Any]) -> bool:
    for key in ("orders_placed", "order_placed", "orders_submitted"):
        if key in report and bool(report.get(key)):
            return True
    order_count = report.get("order_count")
    if order_count is not None and int(order_count) != 0:
        return True
    ingress = report.get("prospective_ingress")
    if isinstance(ingress, dict):
        for key in ("orders_placed", "order_placed"):
            if key in ingress and bool(ingress.get(key)):
                return True
    return False


def _summary_clock_issues(summary: Mapping[str, Any]) -> list[str]:
    metadata = summary.get("metadata")
    if not isinstance(metadata, dict):
        return []
    published = metadata.get("published_time")
    retrieved = metadata.get("retrieved_time")
    if published is None or retrieved is None:
        return []
    pub_ns = epoch_ns_from_iso(str(published))
    ret_ns = epoch_ns_from_iso(str(retrieved))
    if pub_ns is None or ret_ns is None:
        return []
    issues: list[str] = []
    if pub_ns > ret_ns:
        issues.append(REASON_PUBLISHED_AFTER_RETRIEVAL)
    future_now_ns = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000) + 300_000_000_000
    if pub_ns > future_now_ns:
        issues.append(REASON_PUBLISHED_TIME_FUTURE)
    return issues


def validate_finviz_prospective_receipt(
    report: Mapping[str, Any],
    *,
    artifact_path: Path | None = None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a catalyst watch report; optional capture-context sidecar from Lane B."""

    reason_codes: list[str] = []

    if str(report.get("artifact_kind") or "") != _ARTIFACT_KIND:
        reason_codes.append(REASON_ARTIFACT_KIND_MISMATCH)
    if str(report.get("schema_version") or "") != _SCHEMA_VERSION:
        reason_codes.append(REASON_SCHEMA_VERSION_UNSUPPORTED)
    if str(report.get("campaign_slug") or "") != _CAMPAIGN_SLUG:
        reason_codes.append(REASON_CAMPAIGN_SLUG_UNSUPPORTED)
    if report.get("secrets_included") is True:
        reason_codes.append(REASON_SECRETS_INCLUDED)
    if str(report.get("test_mode") or "") != _TEST_MODE:
        reason_codes.append(REASON_TEST_MODE_NOT_SIGNAL_ONLY)
    if report.get("dry_run") is not True:
        reason_codes.append(REASON_DRY_RUN_NOT_TRUE)

    campaign_status = report.get("campaign_status")
    if not isinstance(campaign_status, dict):
        campaign_status = {}
    fingerprint = campaign_status.get("manifest_fingerprint")
    if fingerprint != FTEP_V1_002_EXPECTED_FINGERPRINT:
        reason_codes.append(REASON_MANIFEST_FINGERPRINT_MISMATCH)

    if "empirical_lock_count" not in campaign_status:
        reason_codes.append(REASON_EMPIRICAL_LOCK_COUNT_MISSING)
    elif int(campaign_status.get("empirical_lock_count") or 0) != 0:
        reason_codes.append(REASON_EMPIRICAL_LOCK_PRESENT)

    if _orders_present(report):
        reason_codes.append(REASON_ORDERS_PRESENT)

    ingress = report.get("prospective_ingress")
    if isinstance(ingress, dict) and ingress.get("durable_lock") is True:
        reason_codes.append(REASON_DURABLE_LOCK_PRESENT)

    summaries = report.get("summaries")
    if summaries is None:
        summaries_list: list[Mapping[str, Any]] = []
    elif isinstance(summaries, list):
        summaries_list = [item for item in summaries if isinstance(item, dict)]
    else:
        summaries_list = []
        reason_codes.append(REASON_SUMMARY_COUNT_MISMATCH)

    summary_count = report.get("summary_count")
    if summary_count is not None and int(summary_count) != len(summaries_list):
        reason_codes.append(REASON_SUMMARY_COUNT_MISMATCH)

    if isinstance(ingress, dict):
        ingress_rows = ingress.get("row_count")
        if ingress_rows is not None and int(ingress_rows) != len(summaries_list):
            reason_codes.append(REASON_ROW_COUNT_MISMATCH)

    watch_mode = str(report.get("watch_mode") or "")
    attention_kind = str(report.get("attention_data_kind") or "")
    rth_open = bool(campaign_status.get("us_equity_rth_open"))
    ingress_outcome = report.get("ingress_outcome")
    claiming_prospective = watch_mode == _WATCH_MODE_PROSPECTIVE

    if watch_mode == "FIXTURE_SMOKE":
        reason_codes.append(REASON_FIXTURE_SMOKE_NOT_PROSPECTIVE)
        if attention_kind == _ATTENTION_LIVE or claiming_prospective:
            reason_codes.append(REASON_FIXTURE_PROVENANCE)
    elif claiming_prospective:
        if attention_kind != _ATTENTION_LIVE:
            reason_codes.append(REASON_ATTENTION_DATA_KIND_NOT_LIVE)
        if not rth_open:
            reason_codes.append(REASON_US_EQUITY_RTH_CLOSED)
        session_ids = report.get("governed_session_ids")
        if not isinstance(session_ids, list) or not session_ids:
            reason_codes.append(REASON_GOVERNED_SESSION_IDS_MISSING)
        else:
            observed = frozenset(str(item) for item in session_ids if item)
            if observed != _GOVERNED_SESSION_IDS_FTEP_V1_002:
                reason_codes.append(REASON_GOVERNED_SESSION_IDS_UNEXPECTED)
        if ingress_outcome == _INGRESS_FAILED:
            reason_codes.append(REASON_INGRESS_OUTCOME_FAILED)
        elif ingress_outcome is None:
            reason_codes.append(REASON_INGRESS_OUTCOME_MISSING)
        elif ingress_outcome == _INGRESS_ZERO_ROWS:
            reason_codes.append(REASON_ZERO_QUALIFYING_ROWS)
        elif ingress_outcome != _INGRESS_SUCCESS and ingress_outcome != _INGRESS_ZERO_ROWS:
            reason_codes.append(REASON_INGRESS_OUTCOME_FAILED)
        source_label = str(report.get("attention_source") or "")
        if source_label != _LIVE_SOURCE_LABEL:
            reason_codes.append(REASON_SOURCE_LABEL_NOT_LIVE)
        for summary in summaries_list:
            metadata = summary.get("metadata")
            if not isinstance(metadata, dict):
                if summaries_list:
                    reason_codes.append(REASON_PROVIDER_MISSING)
                continue
            if not str(metadata.get("provider_id") or "").strip():
                reason_codes.append(REASON_PROVIDER_MISSING)
            for issue in _summary_clock_issues(summary):
                if issue not in reason_codes:
                    reason_codes.append(issue)
    elif watch_mode:
        reason_codes.append(REASON_NOT_PROSPECTIVE_OBSERVATION)
    else:
        reason_codes.append(REASON_WATCH_MODE_NOT_PROSPECTIVE)

    if str(report.get("disposition") or "") == "BLOCKED":
        if REASON_NOT_PROSPECTIVE_OBSERVATION not in reason_codes:
            reason_codes.append(REASON_DISPOSITION_BLOCKED)

    runtime_sha = report.get("runtime_git_sha") or report.get("runtime_sha")
    sidecar_valid = False
    if not runtime_sha and context is not None:
        runtime_sha = context.get("runtime_git_sha")
        sidecar_valid = bool(runtime_sha)
        if artifact_path is not None:
            expected_hash = str(context.get("artifact_sha256") or "").upper()
            if expected_hash:
                actual = _sha256_file(artifact_path)
                if actual != expected_hash:
                    reason_codes.append(REASON_SIDECAR_ARTIFACT_HASH_MISMATCH)
        sidecar_class = str(context.get("evidence_class") or "")
        artifact_class = _artifact_evidence_class(report)
        if sidecar_class and sidecar_class != artifact_class:
            if artifact_class == "FIXTURE" and sidecar_class in {"LIVE_PROSPECTIVE", "EMPIRICAL"}:
                reason_codes.append(REASON_SIDECAR_EVIDENCE_CLASS_UPGRADE)
    if not runtime_sha:
        reason_codes.append(REASON_RUNTIME_SHA_MISSING)

    unique_reasons = list(dict.fromkeys(reason_codes))
    errors = [code for code in unique_reasons if code in _ERROR_REASONS]
    limitations = [code for code in unique_reasons if code in _LIMITATION_REASONS]

    prospective_valid = (
        not errors
        and watch_mode == _WATCH_MODE_PROSPECTIVE
        and attention_kind == _ATTENTION_LIVE
        and REASON_FIXTURE_SMOKE_NOT_PROSPECTIVE not in unique_reasons
        and REASON_FIXTURE_PROVENANCE not in unique_reasons
    )

    if errors:
        verdict = VERDICT_INVALID
    elif limitations:
        verdict = VERDICT_VALID_WITH_LIMITATIONS
    else:
        verdict = VERDICT_VALID

    return {
        "validator_schema_version": "1.0.0",
        "artifact_kind": _ARTIFACT_KIND,
        "verdict": verdict,
        "reason_codes": unique_reasons,
        "errors": errors,
        "limitations": limitations,
        "prospective_observation_valid": prospective_valid,
        "artifact_evidence_class": _artifact_evidence_class(report),
        "runtime_git_sha": runtime_sha or None,
        "sidecar_applied": sidecar_valid,
        "program_gate_decision": None,
    }


def load_report_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("report root must be a JSON object")
    return payload


def load_context_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("context root must be a JSON object")
    return payload


__all__ = [
    "VERDICT_INVALID",
    "VERDICT_VALID",
    "VERDICT_VALID_WITH_LIMITATIONS",
    "load_context_json",
    "load_report_json",
    "validate_finviz_prospective_receipt",
]
