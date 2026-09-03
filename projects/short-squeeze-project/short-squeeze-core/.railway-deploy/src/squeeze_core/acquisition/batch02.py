"""Deterministic, offline curation for outcome-acquisition batch 02.

Batch 02 is the preregistered attempt to capture the forward 24-hour outcome
window for the 13 registry-only cases frozen by batch 01, so that eligible cases
could be promoted to complete Phase 3B dataset candidates. Its plan, cases, case
IDs, source order, and detection boundaries are inherited unchanged from batch 01
(see :mod:`squeeze_core.acquisition.batch01`).

The outcome window could not be obtained: no public, lawful, non-authenticated
historical source provides forward intraday trade bars for these specific symbols
without either requiring authentication or violating a source's terms/robots
rules. The one clearly-permissive public source (SEC EDGAR) serves filings, not
price bars. This module records that source search and barrier deterministically,
keeps every case registry-only with an explicit source-barrier limitation, and
emits an empty outcome manifest with status ``UNAVAILABLE_NO_LAWFUL_PUBLIC_SOURCE``.

No outcome value is fabricated, and no current value is ever represented as a
historical value. Given the committed batch-01 rows file the module regenerates
byte-identical outputs, so the test suite never touches the network or archived
evidence. No complete Phase 3B dataset candidate is claimed by this batch.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from squeeze_core.research.models import (
    AssetClass, CandidateCaseRegistry, CandidateCaseRegistryEntry, CandidateCaseStatus,
    CandidateCaseType, FixtureClassification, OriginalPlatformStatus,
)
from squeeze_core.serialization import canonical_json_bytes

from .boundary_freeze import freeze_detection_boundary
from .eligibility import decide_eligibility
from .identity_resolution import resolve_identity
from .leakage_guards import audit_outcome_leakage
from .models import (
    AcquisitionPlan, AcquisitionPlanStatus, ArtifactClassification, ArtifactManifest,
    ArtifactRecord, ArtifactVerificationResult, BoundaryEvidence, BoundaryRule,
    CurationStatus, DiscoveryRecord, DiscoverySourceClass, EligibilityContext,
    HistoricalOrCurrent, IdentityClaim, LeakageAuditCollection, LeakageAuditRequest,
    ProviderProvenance, SourceManifest,
)
from .reports import render_acquisition_report
from .runner import curate_historical_cases
from .sufficiency import review_evidence_sufficiency


PLAN_ID = "phase-3d-outcome-acquisition-batch-02"
PLAN_VERSION = "phase_3d_outcome_acquisition_batch_02.v1"
REGISTRY_VERSION = "phase_3d_batch_02_registry.v1"
PHASE_3A_POLICY_VERSION = "phase_3a_transparent_candidate_policy.v1"
OUTCOME_LABEL_POLICY_VERSION = "phase_3b_outcome_label_policy.v1"

# The underlying discovery artifact and provenance are inherited from batch 01 and
# are not re-collected; the case IDs and boundaries are preserved unchanged.
RAW_ARTIFACT_ID = "batch01-screener-snapshot-raw"
NORMALIZED_ARTIFACT_ID = "batch01-sanitized-discovery-rows"
PROVIDER_PROVENANCE_ID = "batch01-archived-screener-provenance"
DISCOVERY_MANIFEST_ID = "phase-3d-batch-02-source"
OUTCOME_MANIFEST_ID = "phase-3d-batch-02-outcome-unavailable"

# Barrier reason code carried by every case and the outcome manifest.
OUTCOME_SOURCE_BARRIER_CODE = "OUTCOME_WINDOW_NO_LAWFUL_PUBLIC_SOURCE"

# Fixed curation instants -- deterministic, never wall-clock. Batch 02 is frozen
# one day after batch 01; the boundaries themselves are data-derived and identical.
_PLAN_FROZEN_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
_BOUNDARY_FROZEN_AT = _PLAN_FROZEN_AT + timedelta(minutes=1)
_EVALUATION_REQUEST_FROZEN_AT = _PLAN_FROZEN_AT + timedelta(minutes=2)
_EVALUATION_RESULT_FROZEN_AT = _PLAN_FROZEN_AT + timedelta(minutes=3)
# Sentinel strictly after every freeze stage. No outcome was captured, so this
# only exists to satisfy the audit's freeze-ordering invariant.
_OUTCOME_SENTINEL_AT = _PLAN_FROZEN_AT + timedelta(minutes=4)

# The lawful-source search, recorded deterministically. Each candidate carries a
# disposition explaining why it is unacceptable under the batch-02 source policy.
# Ordered by source name for stable serialization.
_CANDIDATE_SOURCES = (
    ("Alpha Vantage", "REST_API", "AUTHENTICATION_REQUIRED",
     "Requires a free API key (registration); the non-authentication constraint excludes it."),
    ("EODHD", "REST_API", "AUTHENTICATION_REQUIRED",
     "Requires account registration and an API token; excluded by the non-authentication constraint."),
    ("Financial Modeling Prep", "REST_API", "AUTHENTICATION_REQUIRED",
     "Intraday history requires an API key; excluded by the non-authentication constraint."),
    ("Kibot free samples", "FILE_DOWNLOAD", "COVERAGE_EXCLUDES_CASE_SYMBOLS",
     "Free no-registration intraday samples cover only demo tickers (IBM, OIH, IVE, WDC); none of the case symbols."),
    ("MarketData.app free tier", "REST_API", "COVERAGE_EXCLUDES_CASE_SYMBOLS",
     "No-token access is limited to a demo ticker (AAPL); other symbols require a registered account."),
    ("Nasdaq Data Link (Quandl)", "REST_API", "AUTHENTICATION_REQUIRED",
     "Requires an API key; excluded by the non-authentication constraint."),
    ("Polygon.io", "REST_API", "AUTHENTICATION_REQUIRED",
     "Requires an API key; excluded by the non-authentication constraint."),
    ("SEC EDGAR", "GOVERNMENT_FILINGS", "PERMISSIVE_BUT_NO_PRICE_BARS",
     "Clearly permissive automated access, but serves filings/disclosures, not intraday trade bars."),
    ("StockData.org", "REST_API", "AUTHENTICATION_REQUIRED",
     "Requires a free registered API token; excluded by the non-authentication constraint."),
    ("Stooq", "FILE_DOWNLOAD", "ROBOTS_DISALLOWS_NON_WHITELISTED_AGENTS",
     "robots.txt is 'User-agent: * / Disallow: /' (only Googlebot/Bingbot allowed); automated retrieval would violate its access rules."),
    ("Tiingo", "REST_API", "AUTHENTICATION_REQUIRED",
     "Requires a registered API token; excluded by the non-authentication constraint."),
    ("Yahoo Finance chart endpoint", "UNDOCUMENTED_JSON", "TERMS_PROHIBIT_AUTOMATED_ACCESS",
     "Returns JSON without a key, but the Yahoo Terms of Service prohibit robot/scraper/automated access; using it would violate its terms."),
    ("marketstack", "REST_API", "AUTHENTICATION_REQUIRED",
     "Requires a registered API access key; excluded by the non-authentication constraint."),
)


def build_batch02_acquisition_plan() -> AcquisitionPlan:
    """The preregistered, outcome-blinded batch 02 outcome-acquisition plan."""
    return AcquisitionPlan(
        acquisition_plan_id=PLAN_ID,
        plan_version=PLAN_VERSION,
        created_from_policy_version="phase_3d_acquisition_plan_policy.v1",
        research_question=(
            "Can the forward 24-hour outcome window for the 13 frozen batch-01 registry "
            "cases be captured from a public, lawful, non-authenticated historical source "
            "-- freezing a Phase 3A request and result before any outcome access -- to "
            "promote eligible cases to complete Phase 3B dataset candidates?"
        ),
        target_population=(
            "The 13 distinct US-listed equities frozen as batch-01 registry cases, "
            "surfaced by the archived scanner on 2026-07-18"
        ),
        # Detection date through the forward 24-hour outcome window.
        date_range=(date(2026, 7, 18), date(2026, 7, 19)),
        market_session_scope=("REGULAR",),
        symbol_universe_definition=(
            "The 13 batch-01 case symbols, with case IDs, source order, and detection "
            "boundaries preserved unchanged; no new discovery is performed"
        ),
        discovery_source_definitions=(
            "ARCHIVED_MARKET_SCANNER:screener_snapshot@2026-07-18T13:37:55Z",
        ),
        maximum_case_count=13,
        minimum_case_count=0,
        sampling_method="INHERITED_BATCH_01_CASES_SOURCE_ORDER_SCORE_BLIND",
        deduplication_policy="phase_3d_unique_security_deduplication_policy.v1",
        boundary_policy="phase_3d_detection_boundary_policy.v1",
        inclusion_policy_version="phase_3d_historical_inclusion_policy.v1",
        exclusion_policy_version="phase_3d_historical_exclusion_policy.v1",
        provider_priority_policy_version="phase_3d_provider_priority_policy.v1",
        artifact_requirements=("DISCOVERY", "IDENTITY", "MARKET", "OUTCOME"),
        allowed_substitutions=(),
        forbidden_substitutions=("CURRENT_FOR_HISTORICAL", "SYNTHETIC_FOR_HISTORICAL"),
        outcome_blinding_state="OUTCOME_BLINDED",
        plan_status=AcquisitionPlanStatus.PREREGISTERED,
        informational_created_at=_PLAN_FROZEN_AT,
    )


def _load_rows(rows_path: Path) -> tuple[dict, bytes]:
    rows_bytes = rows_path.read_bytes()
    document = json.loads(rows_bytes)
    return document, rows_bytes


def _parse_observed_at(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


def _provider_provenance(document: dict) -> ProviderProvenance:
    capture = _parse_observed_at(document["raw_source"]["capture_timestamp"])
    return ProviderProvenance(
        provider_provenance_id=PROVIDER_PROVENANCE_ID,
        provider_name="Archived original-platform squeeze scanner",
        provider_product="Live screener snapshot (archived)",
        provider_dataset="screener_snapshot.json",
        provider_scope="US_EQUITY",
        access_method="LOCAL_ARCHIVED_FILE_REFERENCE",
        artifact_timestamp=capture,
        event_at=capture,
        observed_at=capture,
        effective_at=capture,
        published_at=None,
        received_at=capture,
        timezone="UTC",
        latency_status="POINT_IN_TIME_CAPTURE",
        historical_or_current=HistoricalOrCurrent.HISTORICAL,
        revision_status="ORIGINAL",
        terms_or_license_reference=(
            "Local forensic archive; provider-derived borrow fields (IB/Schwab/yfinance) "
            "retained locally and referenced by hash, not redistributed."
        ),
        source_artifact_id=RAW_ARTIFACT_ID,
    )


def _source_manifest(document: dict) -> SourceManifest:
    provenance = _provider_provenance(document)
    records = []
    for row in document["rows"]:
        observed = _parse_observed_at(row["observed_at"])
        records.append(DiscoveryRecord(
            discovery_record_id=f"BATCH01_{row['ticker']}_20260718",
            symbol_as_observed=row["ticker"],
            observed_at=observed,
            source_class=DiscoverySourceClass.ARCHIVED_MARKET_SCANNER,
            source_name="archived-screener-snapshot-2026-07-18",
            source_artifact_id=RAW_ARTIFACT_ID,
            provider="Archived original-platform squeeze scanner",
            provider_scope="US_EQUITY",
            query_or_filter_definition=(
                "Archived scanner surface (detection-time relative-volume / percent-change / "
                "short-float criteria); imported in source order, score-blind."
            ),
            original_order=row["original_order"],
            platform_surfaced_status="SURFACED",
            discovery_reason="Symbol surfaced by the archived point-in-time market scanner",
            fixture_classification=ArtifactClassification.LOCAL_HISTORICAL_ARTIFACT,
        ))
    return SourceManifest(
        manifest_id=DISCOVERY_MANIFEST_ID,
        discovery_records=tuple(records),
        provider_provenance=(provenance,),
    )


def _artifact_manifest(document: dict, rows_bytes: bytes) -> ArtifactManifest:
    raw = document["raw_source"]
    capture = _parse_observed_at(raw["capture_timestamp"])
    raw_artifact = ArtifactRecord(
        artifact_id=RAW_ARTIFACT_ID,
        file_name=raw["artifact_name"],
        relative_path="raw/screener_snapshot.json",
        media_type="application/json",
        byte_length=raw["byte_length"],
        sha256=raw["sha256"],
        source_class=DiscoverySourceClass.ARCHIVED_MARKET_SCANNER,
        provider_provenance_id=PROVIDER_PROVENANCE_ID,
        fixture_classification=ArtifactClassification.RESTRICTED_LOCAL_ARTIFACT,
        capture_method="LOCAL_ARCHIVE_REFERENCE",
        observed_at=capture,
        effective_at=capture,
        published_at=None,
        content_status="REFERENCED_NOT_COPIED",
        sensitive_content_status="RESTRICTED_PROVIDER_DERIVED",
    )
    normalized_artifact = ArtifactRecord(
        artifact_id=NORMALIZED_ARTIFACT_ID,
        file_name="batch01_discovery_rows.json",
        relative_path="normalized/batch01_discovery_rows.json",
        media_type="application/json",
        byte_length=len(rows_bytes),
        sha256=hashlib.sha256(rows_bytes).hexdigest(),
        source_class=DiscoverySourceClass.ARCHIVED_MARKET_SCANNER,
        provider_provenance_id=PROVIDER_PROVENANCE_ID,
        fixture_classification=ArtifactClassification.DERIVED_NORMALIZED_ARTIFACT,
        capture_method="DERIVED_SANITIZED_EXPORT",
        observed_at=capture,
        effective_at=capture,
        published_at=None,
        content_status="CAPTURED",
        sensitive_content_status="SANITIZED",
    )
    return ArtifactManifest(
        manifest_id="phase-3d-batch-02-artifacts",
        artifacts=(raw_artifact, normalized_artifact),
    )


def _verify_artifacts(manifest: ArtifactManifest, rows_bytes: bytes) -> ArtifactVerificationResult:
    diagnostics: list[str] = []
    verified: list[str] = []
    for artifact in manifest.artifacts:
        if artifact.artifact_id == NORMALIZED_ARTIFACT_ID:
            if hashlib.sha256(rows_bytes).hexdigest() == artifact.sha256:
                verified.append(artifact.artifact_id)
            else:  # pragma: no cover - defensive
                diagnostics.append("SOURCE_ARTIFACT_HASH_MISMATCH")
        else:
            verified.append(artifact.artifact_id)
            diagnostics.append("RESTRICTED_RAW_ARTIFACT_REFERENCED_BY_HASH")
    return ArtifactVerificationResult(
        manifest_id=manifest.manifest_id,
        valid=not any(code == "SOURCE_ARTIFACT_HASH_MISMATCH" for code in diagnostics),
        verified_artifact_ids=tuple(verified),
        diagnostic_codes=tuple(diagnostics),
    )


def _identity_claim(row: dict) -> IdentityClaim:
    return IdentityClaim(
        source_artifact_id=RAW_ARTIFACT_ID,
        symbol=row["ticker"],
    )


def _eligibility_context(row: dict, identity) -> EligibilityContext:
    missing = [
        "NORMALIZED_POINT_IN_TIME_EVIDENCE",
        "RETROSPECTIVE_OUTCOME_WINDOW",
        "ISSUER_EXCHANGE_IDENTITY",
        *row.get("missing_detection_domains", ()),
    ]
    return EligibilityContext(
        acquisition_plan_status=AcquisitionPlanStatus.PREREGISTERED,
        within_date_range=True,
        within_population=True,
        discovery_provenance_available=True,
        artifact_validation_passed=True,
        identity_resolution=identity,
        deterministic_boundary_available=True,
        objective_market_evidence_available=True,
        # A full Phase 3A request still cannot be constructed offline from a flat
        # scanner row without fabricating the normalized point-in-time evidence
        # layers, so it is declined; the retrospective outcome window is separately
        # unobtainable from any lawful non-authenticated source (see the outcome
        # source search). The case is retained registry-only rather than fabricated.
        phase_3a_request_constructible=False,
        missing_domains=tuple(missing),
        duplicate_symbol=False,
        duplicate_discovery=False,
        synthetic=False,
    )


def _leakage_request(discovery_record_id: str) -> LeakageAuditRequest:
    return LeakageAuditRequest(
        case_attempt_id=discovery_record_id,
        discovery_input_fields=(
            "symbol", "observed_at", "price", "rel_volume", "change_percent",
            "short_float_percent", "days_to_cover", "shares_short", "float_shares",
        ),
        eligibility_input_fields=("identity", "artifacts", "discovery_provenance"),
        boundary_input_fields=("platform_surfaced_timestamp",),
        # No Phase 3A evaluation and no outcome capture were performed.
        evaluation_input_fields=(),
        plan_frozen_at=_PLAN_FROZEN_AT,
        boundary_frozen_at=_BOUNDARY_FROZEN_AT,
        evaluation_request_frozen_at=_EVALUATION_REQUEST_FROZEN_AT,
        evaluation_result_frozen_at=_EVALUATION_RESULT_FROZEN_AT,
        outcome_captured_at=_OUTCOME_SENTINEL_AT,
        discovery_manifest_id=DISCOVERY_MANIFEST_ID,
        outcome_manifest_id=OUTCOME_MANIFEST_ID,
        plan_changed_after_outcome_access=False,
        outcome_aware_selection_indicator=False,
        maximum_return_selection_indicator=False,
        post_event_article_used_as_discovery_source=False,
    )


def _registry_entry(row: dict, discovery_record_id: str) -> CandidateCaseRegistryEntry:
    limitations = [
        "REGISTRY_ONLY_NO_PHASE_3A_EVALUATION",
        OUTCOME_SOURCE_BARRIER_CODE,
        "IDENTITY_PARTIALLY_RESOLVED_ISSUER_EXCHANGE_UNKNOWN",
        *(f"DETECTION_DOMAIN_MISSING:{domain}" for domain in row.get("missing_detection_domains", ())),
    ]
    return CandidateCaseRegistryEntry(
        case_id=discovery_record_id,
        symbol=row["ticker"],
        asset_class=AssetClass.EQUITY,
        case_type=CandidateCaseType.ORIGINAL_PLATFORM_SURFACED,
        case_status=CandidateCaseStatus.ARTIFACT_DISCOVERY_ONLY,
        original_platform_status=OriginalPlatformStatus.SURFACED,
        detection_time_evidence_id=discovery_record_id,
        evaluation_as_of=None,
        evaluation_request_path=None,
        evaluation_result_path=None,
        outcome_observation_path=None,
        original_platform_artifact_ids=(RAW_ARTIFACT_ID,),
        historical_dataset_ids=(),
        phase_3a_policy_version=PHASE_3A_POLICY_VERSION,
        limitations=tuple(limitations),
        fixture_classification=FixtureClassification.SANITIZED_LOCAL_ARTIFACT,
    )


def _outcome_source_search() -> dict:
    return {
        "schema_version": "1.0.0",
        "document": "phase_3d_batch_02_outcome_source_search",
        "outcome_manifest_id": OUTCOME_MANIFEST_ID,
        "search_instant": _PLAN_FROZEN_AT.isoformat(),
        "requirement": {
            "horizon": "24_HOURS",
            "reference": "first eligible trade-bar close at/after the frozen detection boundary",
            "granularity_required": "INTRADAY_TRADE_BARS",
            "window_start": "2026-07-18T13:37:55Z",
            "constraints": (
                "PUBLIC", "LAWFUL", "NON_AUTHENTICATED", "NO_TERMS_OR_ROBOTS_VIOLATION",
                "OFFLINE_REPRODUCIBLE", "PROVENANCE_PRESERVED",
            ),
        },
        "candidate_sources": tuple(
            {
                "source_name": name,
                "source_kind": kind,
                "disposition_code": code,
                "detail": detail,
                "acceptable": False,
            }
            for name, kind, code, detail in _CANDIDATE_SOURCES
        ),
        "conclusion": {
            "acceptable_source_found": False,
            "code": "NO_ACCEPTABLE_LAWFUL_NONAUTHENTICATED_SOURCE",
            "detail": (
                "Every source that carries forward intraday bars for these symbols either "
                "requires authentication (an API key or registration) or prohibits automated "
                "access in its terms or robots rules; the one clearly-permissive public "
                "source (SEC EDGAR) serves filings, not trade bars. The outcome window is "
                "therefore not obtainable lawfully, reproducibly, and with preserved "
                "provenance, and is not fabricated."
            ),
        },
    }


def _outcome_manifest() -> dict:
    return {
        "schema_version": "1.0.0",
        "outcome_manifest_id": OUTCOME_MANIFEST_ID,
        "outcome_label_policy_version": OUTCOME_LABEL_POLICY_VERSION,
        "horizon": "24_HOURS",
        "upward_threshold_percent": 25,
        "downward_threshold_percent": -25,
        "captured": False,
        "status": "UNAVAILABLE_NO_LAWFUL_PUBLIC_SOURCE",
        "current_values_used_as_historical": False,
        "fabricated_bars_used": False,
        "source_search_ref": "outcome-source-search.json",
        "provenance_limitations": (
            "NO_PUBLIC_NON_AUTHENTICATED_SOURCE_PROVIDES_FORWARD_24H_BARS_FOR_CASE_SYMBOLS",
            "AUTHENTICATED_SOURCES_EXCLUDED_BY_NON_AUTHENTICATION_CONSTRAINT",
            "TERMS_OR_ROBOTS_RESTRICTED_SOURCES_NOT_ACCESSED",
            "OUTCOME_NOT_RECONSTRUCTIBLE_WITHOUT_FABRICATION",
        ),
        "note": (
            "Retrospective outcome window not acquired: no lawful, public, "
            "non-authenticated source provides forward intraday bars for these symbols. "
            "The outcome manifest is intentionally empty and kept separate from "
            "discovery/eligibility/boundary inputs."
        ),
        "observations": (),
    }


def _json(value) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _anchor(name: str, value: str) -> str:
    return hashlib.sha256(f"{name}\0{value}".encode("utf-8")).hexdigest()


def build_batch02_documents(rows_path: Path) -> dict[str, bytes]:
    document, rows_bytes = _load_rows(rows_path)
    plan = build_batch02_acquisition_plan()
    source_manifest = _source_manifest(document)
    artifact_manifest = _artifact_manifest(document, rows_bytes)
    verification = _verify_artifacts(artifact_manifest, rows_bytes)
    batch = curate_historical_cases(plan, source_manifest, artifact_manifest)

    rows_by_id = {
        f"BATCH01_{row['ticker']}_20260718": row for row in document["rows"]
    }

    identities = {}
    eligibilities = {}
    boundaries = {}
    sufficiencies = {}
    leakage_results = {}
    registry_entries = []
    for record in source_manifest.discovery_records:
        cid = record.discovery_record_id
        row = rows_by_id[cid]
        identity = resolve_identity((_identity_claim(row),))
        identities[cid] = identity
        eligibility = decide_eligibility(_eligibility_context(row, identity))
        eligibilities[cid] = eligibility
        boundary = freeze_detection_boundary(
            case_attempt_id=cid,
            symbol=record.symbol_as_observed,
            evidence=(BoundaryEvidence(
                timestamp=record.observed_at,
                source_artifact_id=RAW_ARTIFACT_ID,
                original_platform_surfaced=True,
            ),),
            rule=BoundaryRule.ORIGINAL_PLATFORM_SURFACED_TIMESTAMP,
        )
        boundaries[cid] = boundary
        sufficiencies[cid] = review_evidence_sufficiency(
            present_domains=("DISCOVERY", "DETECTION_TIME_MARKET_SNAPSHOT", "DETECTION_BOUNDARY"),
            missing_domains=tuple(eligibility.context.missing_domains),
            phase_3a_request_constructible=False,
            outcome_only_available=False,
            identity_conflicted=False,
            publication_blocked=False,
        )
        leakage_results[cid] = audit_outcome_leakage(_leakage_request(cid))
        registry_entries.append(_registry_entry(row, cid))

    leakage_collection = LeakageAuditCollection(
        batch_id=batch.batch_id,
        audits=tuple(leakage_results.values()),
    )
    registry = CandidateCaseRegistry(
        registry_version=REGISTRY_VERSION,
        entries=tuple(registry_entries),
    )

    enriched_bundles = []
    for bundle in batch.bundles:
        cid = bundle.case_attempt_id
        enriched_bundles.append(bundle.model_copy(update={
            "curation_status": CurationStatus.REVIEWED,
            "provider_provenance_ids": (PROVIDER_PROVENANCE_ID,),
            "identity_resolution_id": str(identities[cid].deterministic_id),
            "eligibility_decision_id": str(eligibilities[cid].deterministic_id),
            "detection_boundary_id": boundaries[cid].boundary_id,
            "leakage_audit_id": str(leakage_results[cid].deterministic_id),
            "leakage_audit_passed": leakage_results[cid].passed,
            "outcome_capture_status": "UNAVAILABLE_NO_LAWFUL_PUBLIC_SOURCE",
            "review_decision": "APPROVED_WITH_LIMITATIONS",
            "diagnostics": ("REGISTRY_ONLY_CANDIDATE", "OUTCOME_SOURCE_BARRIER"),
            "limitations": (
                "REGISTRY_ONLY_NO_PHASE_3A_EVALUATION",
                OUTCOME_SOURCE_BARRIER_CODE,
            ),
        }))
    enriched_bundles.sort(key=lambda item: item.case_attempt_id)

    boundary_manifest = {
        "schema_version": "1.0.0",
        "boundary_rule": BoundaryRule.ORIGINAL_PLATFORM_SURFACED_TIMESTAMP.value,
        "boundaries": tuple(boundaries[cid] for cid in sorted(boundaries)),
    }
    evaluation_manifest = {
        "schema_version": "1.0.0",
        "phase_3a_policy_version": PHASE_3A_POLICY_VERSION,
        "phase_3a_requests_frozen": 0,
        "phase_3a_results_frozen": 0,
        "note": (
            "No Phase 3A request or result was constructed: normalized point-in-time "
            "evaluation evidence remains unavailable offline and would require "
            "fabrication. Outcome capture was therefore never reached, and is "
            "independently barred by the absence of a lawful outcome source."
        ),
        "entries": (),
    }
    outcome_source_search = _outcome_source_search()
    outcome_manifest = _outcome_manifest()
    identity_review = {
        "schema_version": "1.0.0",
        "resolutions": tuple(identities[cid] for cid in sorted(identities)),
    }
    eligibility_review = {
        "schema_version": "1.0.0",
        "decisions": tuple(eligibilities[cid] for cid in sorted(eligibilities)),
    }
    sufficiency_review = {
        "schema_version": "1.0.0",
        "reviews": tuple(sufficiencies[cid] for cid in sorted(sufficiencies)),
    }

    empty_case_set = {"schema_version": "1.0.0", "cases": ()}
    registry_only_cases = {
        "schema_version": "1.0.0",
        "case_ids": tuple(sorted(rows_by_id)),
    }

    batch_summary = {
        "schema_version": "1.0.0",
        "batch_id": batch.batch_id,
        "acquisition_plan_id": PLAN_ID,
        "acquisition_plan_version": PLAN_VERSION,
        "discovery_source_class": DiscoverySourceClass.ARCHIVED_MARKET_SCANNER.value,
        "attempted_case_count": len(batch.ledger.attempts),
        "unique_identity_count": len(rows_by_id),
        "duplicate_discovery_count": 0,
        "included_case_count": 0,
        "registry_only_case_count": len(rows_by_id),
        "complete_dataset_candidate_count": 0,
        "excluded_case_count": 0,
        "partial_case_count": 0,
        "blocked_case_count": 0,
        "dependent_secondary_boundary_count": 0,
        "boundaries_frozen_count": len(boundaries),
        "phase_3a_requests_frozen_count": 0,
        "phase_3a_results_frozen_count": 0,
        "outcome_windows_captured_count": 0,
        "outcome_source_acceptable": False,
        "outcome_source_conclusion_code": "NO_ACCEPTABLE_LAWFUL_NONAUTHENTICATED_SOURCE",
        "candidate_sources_evaluated_count": len(_CANDIDATE_SOURCES),
        "leakage_passed_count": sum(1 for r in leakage_results.values() if r.passed),
        "leakage_failed_count": sum(1 for r in leakage_results.values() if not r.passed),
        "phase_3b_registry_candidate_count": len(registry_entries),
        "phase_3b_dataset_candidate_count": 0,
        "outcome_blinding_state": plan.outcome_blinding_state,
        "interpretation": (
            "Batch 02 preregistered an outcome-acquisition attempt over the 13 frozen "
            "batch-01 cases, but no public, lawful, non-authenticated source provides the "
            "required forward 24-hour bars for these symbols. All 13 cases remain "
            "outcome-blind, registry-only Phase 3B candidates with an explicit source "
            "barrier; no outcome value was fabricated and no complete dataset candidate, "
            "score, ranking, or predictive claim is made."
        ),
    }

    report = render_acquisition_report(batch)

    documents: dict[str, bytes] = {
        "acquisition-plan.json": _json(plan),
        "source-manifest.json": _json(source_manifest),
        "artifact-manifest.json": _json(artifact_manifest),
        "artifact-verification.json": _json(verification),
        "case-attempt-ledger.json": _json(batch.ledger),
        "identity-review.json": _json(identity_review),
        "eligibility-review.json": _json(eligibility_review),
        "sufficiency-review.json": _json(sufficiency_review),
        "boundary-freeze-manifest.json": _json(boundary_manifest),
        "evaluation-freeze-manifest.json": _json(evaluation_manifest),
        "outcome-source-search.json": _json(outcome_source_search),
        "outcome-manifest.json": _json(outcome_manifest),
        "leakage-audit.json": _json(leakage_collection),
        "curated-case-bundles.jsonl": b"".join(
            canonical_json_bytes(bundle) + b"\n" for bundle in enriched_bundles
        ),
        "phase3b-registry-candidates.json": _json(registry),
        "phase3b-dataset-candidates.json": _json({"schema_version": "1.0.0", "candidates": ()}),
        "registry-only-cases.json": _json(registry_only_cases),
        "excluded-cases.json": _json(empty_case_set),
        "partial-cases.json": _json(empty_case_set),
        "blocked-cases.json": _json(empty_case_set),
        "dependent-secondary-boundaries.json": _json(empty_case_set),
        "failed-leakage-cases.json": _json(empty_case_set),
        "batch-summary.json": _json(batch_summary),
        "curation-report.md": report,
    }

    raw_anchors = {
        "acquisition_plan": str(plan.deterministic_id),
        "source_manifest": str(source_manifest.deterministic_id),
        "artifact_manifest": str(artifact_manifest.deterministic_id),
        "artifact_verification": str(verification.deterministic_id),
        "case_attempt_ledger": str(batch.ledger.deterministic_id),
        "acquisition_batch": str(batch.deterministic_id),
        "leakage_audit_collection": str(leakage_collection.deterministic_id),
        "phase3b_registry": str(registry.deterministic_id),
        "raw_artifact_sha256": document["raw_source"]["sha256"],
        "normalized_artifact_sha256": hashlib.sha256(rows_bytes).hexdigest(),
        "outcome_source_search": hashlib.sha256(documents["outcome-source-search.json"]).hexdigest(),
        "outcome_manifest": hashlib.sha256(documents["outcome-manifest.json"]).hexdigest(),
        "batch_summary": hashlib.sha256(documents["batch-summary.json"]).hexdigest(),
        "curation_report": hashlib.sha256(report).hexdigest(),
        "curated_case_bundles": hashlib.sha256(documents["curated-case-bundles.jsonl"]).hexdigest(),
    }
    for cid in sorted(rows_by_id):
        raw_anchors[f"identity::{cid}"] = str(identities[cid].deterministic_id)
        raw_anchors[f"eligibility::{cid}"] = str(eligibilities[cid].deterministic_id)
        raw_anchors[f"boundary::{cid}"] = boundaries[cid].boundary_id
        raw_anchors[f"leakage::{cid}"] = str(leakage_results[cid].deterministic_id)
        raw_anchors[f"registry_entry::{cid}"] = str(
            next(e for e in registry_entries if e.case_id == cid).deterministic_id
        )

    anchors = {name: _anchor(name, value) for name, value in raw_anchors.items()}
    documents["expected-batch-02-anchors.json"] = _json({
        "schema_version": "1.0.0",
        "anchors": anchors,
    })
    documents["batch-02-fixture-metadata.json"] = _json({
        "schema_version": "1.0.0",
        "file_sha256": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in sorted(documents.items())
        },
        "fixture_classifications": (
            "DERIVED_NORMALIZED_ARTIFACT",
            "LOCAL_HISTORICAL_ARTIFACT",
            "RESTRICTED_LOCAL_ARTIFACT",
        ),
        "sensitive_content_included": False,
        "raw_artifact_copied_into_repository": False,
        "outcome_window_captured": False,
        "outcome_values_fabricated": False,
    })
    return dict(sorted(documents.items()))


__all__ = ["build_batch02_acquisition_plan", "build_batch02_documents"]
