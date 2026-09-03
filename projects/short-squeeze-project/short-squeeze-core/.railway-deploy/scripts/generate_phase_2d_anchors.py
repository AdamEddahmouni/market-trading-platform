"""Regenerates tests/fixtures/readiness/expected_phase_2d_readiness_metadata.json and
the Phase 2D CLI demonstration fixtures (phase_2d_cli_demo_observations.jsonl /
phase_2d_readiness_cases.json).

Not part of the runtime package. Builds the required Phase 2D anchor results
(handoff section 28) directly through squeeze_core.readiness, hashes each with the
same canonical_hash used everywhere else in the repository, and writes the result
set plus the raw CLI-output hash to the metadata file. Mirrors
scripts/generate_phase_2c_anchors.py's structure and conventions.

Deterministic: no wall clock, no randomness. Run with the project's .venv:

    .venv/Scripts/python.exe scripts/generate_phase_2d_anchors.py
"""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.adapters import AdapterContext  # noqa: E402
from squeeze_core.adapters.finra import normalize_finra_short_interest_records  # noqa: E402
from squeeze_core.adapters.ibkr import normalize_ibkr_borrow_records  # noqa: E402
from squeeze_core.adapters.market_bars import normalize_market_bar_record  # noqa: E402
from squeeze_core.contracts import AssetClass, EntitlementState, EventType, IngestionMethod  # noqa: E402
from squeeze_core.evidence import (  # noqa: E402
    CoverageDomain,
    PointInTimeEvidencePolicy,
    build_point_in_time_evidence,
)
from squeeze_core.readiness import (  # noqa: E402
    age_alignment_hash,
    build_conflict_summary,
    build_domain_coverage_snapshot,
    build_evidence_age_alignment,
    build_evidence_readiness_snapshot,
    build_input_sufficiency_result,
    build_missingness_summary,
    build_reporting_period_alignment,
    conflict_summary_hash,
    coverage_snapshot_hash,
    missingness_summary_hash,
    readiness_snapshot_hash,
    reporting_alignment_hash,
    serialize_age_alignment,
    serialize_conflict_summary,
    serialize_coverage_snapshot,
    serialize_missingness_summary,
    serialize_readiness_snapshot,
    serialize_reporting_alignment,
    serialize_sufficiency_result,
    sufficiency_result_hash,
)
from squeeze_core.readiness.policies import OPERATION_REQUIREMENT_POLICIES, lookup_policy
from squeeze_core.readiness.models import OperationRequirementPolicy
from squeeze_core.serialization import canonical_hash, serialize_observation  # noqa: E402

AS_OF = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
OUT_PATH = ROOT / "tests" / "fixtures" / "readiness" / "expected_phase_2d_readiness_metadata.json"
CLI_INPUT = ROOT / "tests" / "fixtures" / "readiness" / "phase_2d_cli_demo_observations.jsonl"
CLI_CASE = ROOT / "tests" / "fixtures" / "readiness" / "phase_2d_readiness_cases.json"

SI_PROVIDER = "FINRA-PROVIDER"
BORROW_PROVIDER = "IBKR-PROVIDER"
VOL_PROVIDER = "SIM-VOLUME-PROVIDER"


def _ctx(provider: str, at: str) -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone="UTC",
        provider=provider,
        adapter_version="1.0.0",
        normalization_version="phase-2d-anchor-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="phase-2d-anchor-fixture",
    )


def _si_record(**overrides) -> dict:
    values = {
        "source_record_id": "si-anchor-1",
        "provider_schema": "FINRA_SHORT_INTEREST_V1",
        "record_type": "PUBLISHED_SHORT_INTEREST",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "symbol": "TESTD",
        "short_shares": "1000000",
        "settlement_date": "2026-01-15",
        "publication_date": "2026-01-25",
        "publication_timezone": "UTC",
        "date_only_publication_policy": "END_OF_PUBLICATION_DATE",
        "float_shares": "10000000",
        "short_float_percent": "10",
        "short_float_percent_unit": "PERCENT_POINTS",
        "days_to_cover": "2.5",
    }
    values.update(overrides)
    return values


def _si(ingested_at="2026-01-26T00:00:00Z", **overrides):
    result = normalize_finra_short_interest_records(
        [_si_record(**overrides)], _ctx(SI_PROVIDER, ingested_at)
    )
    assert result.accepted, result.rejection
    return result.observations[0]


def _borrow_record(**overrides) -> dict:
    values = {
        "source_record_id": "ib-anchor-1",
        "symbol": "TESTD",
        "fee_rate": "5.0",
        "fee_rate_unit": "PERCENT_POINTS",
        "available_shares": "100000",
        "lender_count": "10",
        "hard_to_borrow": False,
        "provider_timestamp": "2026-01-10T00:00:00Z",
        "provider_timezone": "UTC",
        "delay_status": "NOT_DELAYED",
    }
    values.update(overrides)
    return values


def _borrow(ingested_at="2026-01-11T00:00:00Z", **overrides):
    result = normalize_ibkr_borrow_records(
        [_borrow_record(**overrides)], _ctx(BORROW_PROVIDER, ingested_at)
    )
    assert result.accepted, result.rejection
    fee = next(o for o in result.observations if o.event_type is EventType.BORROW_FEE)
    availability = next(
        o for o in result.observations if o.event_type is EventType.BORROW_AVAILABILITY
    )
    return fee, availability


def _bar_record(day: int, volume: str, **overrides) -> dict:
    values = {
        "source_record_id": f"anchor-bar-{day}",
        "provider_schema": "MARKET_BAR_V1",
        "record_type": "MARKET_BAR",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "provider": VOL_PROVIDER,
        "provider_record_id": None,
        "symbol": "TESTD",
        "asset_class": "EQUITY",
        "exchange": "XNAS",
        "interval": "1_DAY",
        "bar_start": f"2026-02-{day:02d}T00:00:00Z",
        "bar_end": f"2026-02-{day + 1:02d}T00:00:00Z",
        "open": "10.00",
        "high": "11.00",
        "low": "9.00",
        "close": "10.50",
        "volume": volume,
        "trade_count": "500",
        "vwap": "10.00",
        "volume_unit": "SHARES",
        "session": "REGULAR",
        "session_date": f"2026-02-{day:02d}",
        "timezone": "UTC",
        "status": "COMPLETED",
        "publication_timestamp": f"2026-02-{day:02d}T20:01:00Z",
    }
    values.update(overrides)
    context = _ctx(VOL_PROVIDER, f"2026-02-{day:02d}T21:02:00Z")
    result = normalize_market_bar_record(values, context)
    assert result.accepted, result.rejection
    return result.observations[0]


def _bundle(observations, as_of=AS_OF, **policy_overrides):
    values = dict(allow_stale=True, allow_delayed=True, allow_unknown_freshness=True)
    values.update(policy_overrides)
    return build_point_in_time_evidence(
        "TESTD", observations, PointInTimeEvidencePolicy(as_of=as_of, **values)
    )


def build_anchor_results() -> dict[str, object]:
    results: dict[str, object] = {}

    # 1: all requested domains present
    si = _si()
    fee, availability = _borrow()
    bar1 = _bar_record(10, "500000")
    bundle_full = _bundle(
        [si, fee, availability, bar1], include_market_bars_domain=True,
        include_published_short_interest_domain=True,
    )
    all_domains = (
        CoverageDomain.PUBLISHED_SHORT_INTEREST,
        CoverageDomain.BORROW_FEE,
        CoverageDomain.BORROW_AVAILABILITY,
        CoverageDomain.MARKET_BARS,
    )
    results["all_domains_present_coverage"] = build_domain_coverage_snapshot(
        bundle_full, all_domains
    )

    # 2: missing domain
    bundle_si_only = _bundle([si], include_market_bars_domain=True)
    results["missing_domain_coverage"] = build_domain_coverage_snapshot(
        bundle_si_only, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.MARKET_BARS)
    )

    # 3: unavailable domain (future evidence, not yet eligible)
    future_si = _si(publication_date="2026-04-01", settlement_date="2026-03-25")
    bundle_future = _bundle([future_si])
    results["unavailable_domain_coverage"] = build_domain_coverage_snapshot(
        bundle_future, (CoverageDomain.PUBLISHED_SHORT_INTEREST,)
    )

    # 4: conflicted domain
    conflict_a = _si(source_record_id="si-conf-a", settlement_date="2026-01-15", short_shares="1000000")
    conflict_b = _si(source_record_id="si-conf-b", settlement_date="2026-01-15", short_shares="2000000")
    bundle_conflict = _bundle([conflict_a, conflict_b])
    results["conflicted_domain_coverage"] = build_domain_coverage_snapshot(
        bundle_conflict, (CoverageDomain.PUBLISHED_SHORT_INTEREST,)
    )

    # 5: zero-valued evidence counted present
    zero_si = _si(short_shares="0")
    bundle_zero = _bundle([zero_si])
    results["zero_value_present_coverage"] = build_domain_coverage_snapshot(
        bundle_zero, (CoverageDomain.PUBLISHED_SHORT_INTEREST,)
    )

    # 6-7: age alignment equal / spread
    fee_equal, _ = _borrow(provider_timestamp="2026-02-01T00:00:00Z", ingested_at="2026-02-01T00:00:00Z")
    si_equal = _si(ingested_at="2026-02-01T00:00:00Z")
    bundle_age_equal = _bundle([si_equal, fee_equal], as_of=datetime(2026, 2, 1, tzinfo=UTC))
    results["age_alignment_equal"] = build_evidence_age_alignment(
        bundle_age_equal, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.BORROW_FEE)
    )
    bundle_age_spread = _bundle([si, bar1], include_market_bars_domain=True)
    results["age_alignment_spread"] = build_evidence_age_alignment(
        bundle_age_spread, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.MARKET_BARS)
    )

    # 8-9: reporting period alignment equal / spread
    from squeeze_core.adapters.sec import normalize_sec_filing_record

    def _sec(period, filed_at, accepted_at, sequence):
        record = {
            "source_record_id": f"sec-anchor-{period}",
            "provider_schema": "SEC_FILING_V1",
            "record_type": "SEC_FILING",
            "fixture_origin": "SYNTHETIC_EDGE_CASE",
            "symbol": "TESTD",
            "issuer_cik": "1",
            "company_name": "Test D Corp.",
            "form_type": "10-Q",
            "accession_number": f"0000000001-26-{sequence:06d}",
            "filed_at": filed_at,
            "accepted_at": accepted_at,
            "period_of_report": period,
            "primary_document": "testd-filing.htm",
            "is_amendment": False,
            "document_count": "3",
            "file_number": "001-00001",
            "filing_status": "ORIGINAL",
        }
        result = normalize_sec_filing_record(record, _ctx("SEC-PROVIDER", accepted_at))
        assert result.accepted, result.rejection
        return result.observations[0]

    sec_equal = _sec("2026-01-15", "2026-01-20", "2026-01-20T14:30:00Z", 1)
    bundle_rep_equal = _bundle(
        [si, sec_equal], include_sec_filings_domain=True
    )
    results["reporting_period_alignment_equal"] = build_reporting_period_alignment(
        bundle_rep_equal, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.SEC_FILINGS)
    )
    sec_later = _sec("2026-02-10", "2026-02-20", "2026-02-20T14:30:00Z", 2)
    bundle_rep_spread = _bundle(
        [si, sec_later], include_sec_filings_domain=True
    )
    results["reporting_period_alignment_spread"] = build_reporting_period_alignment(
        bundle_rep_spread, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.SEC_FILINGS)
    )

    # 10-11: conflict summary no-conflict / multi-domain
    results["no_conflict_summary"] = build_conflict_summary(
        bundle_si_only, (CoverageDomain.PUBLISHED_SHORT_INTEREST,)
    )
    results["multi_domain_conflict_summary"] = build_conflict_summary(
        bundle_conflict, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.MARKET_BARS)
    )

    # 12-13: missingness domain case / field case
    dtc_policy = lookup_policy("DAYS_TO_COVER")
    bundle_missing_domain = _bundle([si], include_market_bars_domain=True)
    coverage_for_missingness = build_domain_coverage_snapshot(
        bundle_missing_domain, dtc_policy.required_domains
    )
    results["missingness_domain_case"] = build_missingness_summary(
        bundle_missing_domain, coverage_for_missingness, policy=dtc_policy
    )
    rv_policy = lookup_policy("RELATIVE_VOLUME")
    bundle_missing_field = _bundle([bar1], include_market_bars_domain=True)
    coverage_for_field = build_domain_coverage_snapshot(
        bundle_missing_field, rv_policy.required_domains
    )
    results["missingness_field_case"] = build_missingness_summary(
        bundle_missing_field, coverage_for_field, policy=rv_policy, metric_results=()
    )

    # 14-15: sufficient / insufficient return inputs
    bundle_return_ok = _bundle([bar1], include_market_bars_domain=True)
    results["sufficient_return_inputs"] = build_input_sufficiency_result(
        bundle_return_ok, "ABSOLUTE_RETURN"
    )
    bundle_return_missing = _bundle([si], include_market_bars_domain=True)
    results["insufficient_return_inputs"] = build_input_sufficiency_result(
        bundle_return_missing, "ABSOLUTE_RETURN"
    )

    # 16-17: relative volume sufficient / insufficient history
    from squeeze_core.contracts import Quality, QualityState
    from squeeze_core.metrics import MetricName, MetricUnit, ProviderScopeMode, SampleCounts
    from squeeze_core.metrics.models import MetricResult

    baseline_ok = MetricResult(
        metric_name=MetricName.MEAN_VOLUME_BASELINE,
        metric_version="1.0.0",
        calculation_policy_version="trailing_mean_exclude_current.v1",
        symbol="TESTD",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=bar1.payload.timeframe,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        value=500000,
        unit=MetricUnit.SHARES,
        sample_counts=SampleCounts(requested=3, eligible=3, used=3, missing=0),
        quality=Quality(state=QualityState.KNOWN_VALUE),
    )
    results["sufficient_relative_volume_inputs"] = build_input_sufficiency_result(
        bundle_return_ok, "RELATIVE_VOLUME", metric_results=(baseline_ok,)
    )
    baseline_insufficient = MetricResult(
        metric_name=MetricName.MEAN_VOLUME_BASELINE,
        metric_version="1.0.0",
        calculation_policy_version="trailing_mean_exclude_current.v1",
        symbol="TESTD",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=bar1.payload.timeframe,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        value=500000,
        unit=MetricUnit.SHARES,
        sample_counts=SampleCounts(requested=5, eligible=3, used=3, missing=0),
        quality=Quality(state=QualityState.KNOWN_VALUE),
    )
    results["insufficient_relative_volume_history"] = build_input_sufficiency_result(
        bundle_return_ok, "RELATIVE_VOLUME", metric_results=(baseline_insufficient,)
    )

    # 18-19: days to cover sufficient / insufficient
    bundle_dtc_ok = _bundle(
        [si, bar1], include_market_bars_domain=True, include_published_short_interest_domain=True
    )
    results["sufficient_days_to_cover_inputs"] = build_input_sufficiency_result(
        bundle_dtc_ok, "DAYS_TO_COVER"
    )
    bundle_dtc_missing = _bundle([bar1], include_market_bars_domain=True, include_published_short_interest_domain=True)
    results["insufficient_days_to_cover_inputs"] = build_input_sufficiency_result(
        bundle_dtc_missing, "DAYS_TO_COVER"
    )

    # 20: sufficient borrow fee inputs
    bundle_fee_ok = _bundle([fee])
    results["sufficient_borrow_fee_inputs"] = build_input_sufficiency_result(
        bundle_fee_ok, "BORROW_FEE_ABSOLUTE_CHANGE"
    )

    # 21: incompatible borrow fee units -- demonstrated via a synthetic, script-local
    # test policy (never a real production operation) since canonical borrow-fee
    # payloads normalize units away at the adapter boundary; see docs/phase-2d-
    # design.md Section 11 and docs/phase-2d-progress.md for the documented scope
    # decision.
    unit_test_policy = OperationRequirementPolicy(
        operation="_ANCHOR_UNIT_INCOMPATIBILITY_DEMONSTRATION",
        policy_version="phase_2d_readiness_policy.v1",
        required_domains=(),
        required_metric_names=("BORROW_FEE_ABSOLUTE_CHANGE",),
        required_units=("PERCENTAGE_POINTS",),
    )
    # Registered only for the duration of this one lookup, then removed -- the
    # production policy registry must contain exactly the 17 real operations both
    # before and after anchor generation runs (verified by
    # tests/readiness/test_policies.py::test_all_seventeen_operations_registered,
    # which shares this process's module state when anchor tests run first).
    OPERATION_REQUIREMENT_POLICIES[unit_test_policy.operation] = unit_test_policy
    fee_change_result = MetricResult(
        metric_name=MetricName.ABSOLUTE_RETURN,
        metric_version="1.0.0",
        calculation_policy_version="close_to_close.v1",
        symbol="TESTD",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        source_interval=bar1.payload.timeframe,
        provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
        value=None,
        unit=MetricUnit.PERCENT,
        quality=Quality(state=QualityState.UNAVAILABLE, reasons=("unit demonstration",)),
    )
    fee_change_result = fee_change_result.model_copy(update={"metric_name": MetricName.BORROW_FEE_ABSOLUTE_CHANGE})
    try:
        results["incompatible_borrow_fee_units"] = build_input_sufficiency_result(
            bundle_fee_ok, unit_test_policy.operation, metric_results=(fee_change_result,)
        )
    finally:
        del OPERATION_REQUIREMENT_POLICIES[unit_test_policy.operation]

    # 22-25: readiness states
    results["readiness_sufficient"] = build_evidence_readiness_snapshot(
        bundle_si_only, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    bundle_readiness_insufficient = _bundle([], include_published_short_interest_domain=True)
    results["readiness_insufficient"] = build_evidence_readiness_snapshot(
        bundle_readiness_insufficient, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    bundle_readiness_unknown = _bundle([])
    results["readiness_unknown"] = build_evidence_readiness_snapshot(
        bundle_readiness_unknown, "ABSOLUTE_RETURN"
    )
    results["readiness_conflicted"] = build_evidence_readiness_snapshot(
        bundle_conflict, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )

    # 26-29: before/after correction and cancellation
    corr_original = _si(source_record_id="si-corr-orig", settlement_date="2026-01-15", short_shares="900000")
    corr_revision = _si(
        source_record_id="si-corr-new", settlement_date="2026-01-15", publication_date="2026-02-05",
        short_shares="950000", revision_status="CORRECTED", revision_number=1,
        supersedes_source_record_id="si-corr-orig",
    )
    bundle_before_corr = _bundle([corr_original, corr_revision], as_of=datetime(2026, 1, 26, tzinfo=UTC))
    bundle_after_corr = _bundle([corr_original, corr_revision])
    results["before_correction_readiness"] = build_evidence_readiness_snapshot(
        bundle_before_corr, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    results["after_correction_readiness"] = build_evidence_readiness_snapshot(
        bundle_after_corr, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )

    cancel_original = _si(source_record_id="si-cxl-orig", settlement_date="2026-01-15", short_shares="900000")
    cancel_new = _si(
        source_record_id="si-cxl-new", settlement_date="2026-01-15", publication_date="2026-02-05",
        short_shares="900000", revision_status="CANCELLED", revision_number=1,
        supersedes_source_record_id="si-cxl-orig",
    )
    bundle_before_cxl = _bundle([cancel_original, cancel_new], as_of=datetime(2026, 1, 26, tzinfo=UTC))
    bundle_after_cxl = _bundle([cancel_original, cancel_new])
    results["before_cancellation_readiness"] = build_evidence_readiness_snapshot(
        bundle_before_cxl, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    results["after_cancellation_readiness"] = build_evidence_readiness_snapshot(
        bundle_after_cxl, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )

    return results


_HASH_FUNCS = {
    "DomainCoverageSnapshot": coverage_snapshot_hash,
    "EvidenceAgeAlignment": age_alignment_hash,
    "ReportingPeriodAlignment": reporting_alignment_hash,
    "EvidenceConflictSummary": conflict_summary_hash,
    "EvidenceMissingnessSummary": missingness_summary_hash,
    "InputSufficiencyResult": sufficiency_result_hash,
    "EvidenceReadinessSnapshot": readiness_snapshot_hash,
}
_SERIALIZE_FUNCS = {
    "DomainCoverageSnapshot": serialize_coverage_snapshot,
    "EvidenceAgeAlignment": serialize_age_alignment,
    "ReportingPeriodAlignment": serialize_reporting_alignment,
    "EvidenceConflictSummary": serialize_conflict_summary,
    "EvidenceMissingnessSummary": serialize_missingness_summary,
    "InputSufficiencyResult": serialize_sufficiency_result,
    "EvidenceReadinessSnapshot": serialize_readiness_snapshot,
}


def _cli_fixture_observations():
    si = _si()
    bar1 = _bar_record(10, "500000")
    return [si, bar1]


def main() -> None:
    results = build_anchor_results()
    anchors: dict[str, str] = {}
    for name, result in results.items():
        hash_fn = _HASH_FUNCS[type(result).__name__]
        anchors[name] = hash_fn(result)

    ordered_names = sorted(results)
    collection = [results[name] for name in ordered_names]
    anchors["mixed_phase_2d_output"] = canonical_hash(list(collection))

    def _serialize(item):
        return _SERIALIZE_FUNCS[type(item).__name__](item)

    anchors["serialized_phase_2d_collection"] = hashlib.sha256(
        b"[" + b",".join(_serialize(item) for item in collection) + b"]"
    ).hexdigest()

    observations = _cli_fixture_observations()
    with CLI_INPUT.open("w", encoding="utf-8", newline="\n") as handle:
        for observation in observations:
            handle.write(serialize_observation(observation).decode("utf-8"))
            handle.write("\n")

    case_document = {
        "schema_version": "1.0.0",
        "description": "Phase 2D CLI demonstration case for phase_2d_cli_demo_observations.jsonl. Fixture provenance: SYNTHETIC_EDGE_CASE.",
        "operation": "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE",
    }
    CLI_CASE.write_text(json.dumps(case_document, indent=2) + "\n", encoding="utf-8")

    cli = subprocess.run(
        [
            sys.executable, "-m", "squeeze_core", "build-evidence-readiness",
            "--input", str(CLI_INPUT), "--symbol", "TESTD", "--as-of", "2026-03-01T12:00:00Z",
            "--operation", "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE",
        ],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    anchors["phase_2d_cli_output"] = hashlib.sha256(cli.stdout.encode("utf-8")).hexdigest()

    metadata = {
        "schema_version": "1.0.0",
        "description": "Phase 2D anchor hashes (handoff section 28). Each readiness result value is hashed with its dedicated *_hash() helper in squeeze_core.readiness.serialization; mixed_phase_2d_output is canonical_hash() of the sorted-by-name result list; serialized_phase_2d_collection is sha256 of the concatenated per-result canonical JSON bytes; phase_2d_cli_output is sha256 of build-evidence-readiness stdout for phase_2d_cli_demo_observations.jsonl at as_of=2026-03-01T12:00:00Z. This is a Phase 2D-only anchor manifest, separate from tests/fixtures/compatibility/phase_1_anchor_manifest.json and the Phase 2A/2B/2C metadata files; none of those files is written by this script.",
        "anchor_result_order": ordered_names,
        "anchors": dict(sorted(anchors.items())),
    }
    OUT_PATH.write_text(json.dumps(metadata, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(f"wrote {CLI_INPUT}")
    print(f"wrote {CLI_CASE}")


if __name__ == "__main__":
    main()
