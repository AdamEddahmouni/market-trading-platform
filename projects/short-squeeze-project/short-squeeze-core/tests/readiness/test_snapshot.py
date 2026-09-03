from squeeze_core.readiness import StructuralState, build_evidence_readiness_snapshot

from .conftest import build_bundle, make_bar, make_borrow, make_short_interest


def test_structurally_sufficient_operation():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    snapshot = build_evidence_readiness_snapshot(
        bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert snapshot.structural_state is StructuralState.SUFFICIENT
    assert not snapshot.missing_inputs


def test_structurally_insufficient_operation():
    bundle = build_bundle(
        "TESTD", [], "2026-03-01T12:00:00Z", include_published_short_interest_domain=True
    )
    snapshot = build_evidence_readiness_snapshot(
        bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert snapshot.structural_state is StructuralState.INSUFFICIENT
    assert "domain:PUBLISHED_SHORT_INTEREST" in snapshot.missing_inputs


def test_unknown_due_to_availability_uncertainty():
    bundle = build_bundle("TESTD", [], "2026-03-01T12:00:00Z")
    snapshot = build_evidence_readiness_snapshot(bundle, "ABSOLUTE_RETURN")
    assert snapshot.structural_state is StructuralState.UNKNOWN


def test_conflicted_required_input():
    a = make_short_interest(source_record_id="si-a", settlement_date="2026-01-15", short_shares="1000000")
    b = make_short_interest(source_record_id="si-b", settlement_date="2026-01-15", short_shares="2000000")
    bundle = build_bundle("TESTD", [a, b], "2026-03-01T12:00:00Z")
    snapshot = build_evidence_readiness_snapshot(
        bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert snapshot.structural_state is StructuralState.CONFLICTED
    assert "domain:PUBLISHED_SHORT_INTEREST" in snapshot.conflicted_inputs


def test_optional_domain_missing_but_operation_sufficient():
    # BORROW_FEE_ABSOLUTE_CHANGE has no optional domains today, so this exercises the
    # general principle via a required-domain-only policy: an unrelated domain being
    # entirely absent from the bundle (never requested) does not affect sufficiency.
    from squeeze_core.evidence import CoverageDomain

    fee, _ = make_borrow()
    bundle = build_bundle("TESTD", [fee], "2026-03-01T12:00:00Z")
    snapshot = build_evidence_readiness_snapshot(bundle, "BORROW_FEE_ABSOLUTE_CHANGE")
    assert snapshot.structural_state is StructuralState.SUFFICIENT
    assert CoverageDomain.NEWS not in snapshot.required_domains


def test_required_domain_missing():
    bundle = build_bundle(
        "TESTD", [], "2026-03-01T12:00:00Z", include_published_short_interest_domain=True
    )
    snapshot = build_evidence_readiness_snapshot(
        bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert snapshot.structural_state is StructuralState.INSUFFICIENT


def test_required_metric_missing():
    bar = make_bar()
    bundle = build_bundle("TESTD", [bar], "2026-03-01T12:00:00Z", include_market_bars_domain=True)
    snapshot = build_evidence_readiness_snapshot(bundle, "RELATIVE_VOLUME")
    assert snapshot.structural_state is StructuralState.INSUFFICIENT
    assert "metric:MEAN_VOLUME_BASELINE" in snapshot.missing_inputs


def test_before_correction_readiness_differs_from_after():
    original = make_short_interest(
        source_record_id="si-orig", settlement_date="2026-01-15", short_shares="900000"
    )
    correction = make_short_interest(
        source_record_id="si-corr",
        settlement_date="2026-01-15",
        publication_date="2026-02-05",
        short_shares="950000",
        revision_status="CORRECTED",
        revision_number=1,
        supersedes_source_record_id="si-orig",
    )
    before_bundle = build_bundle("TESTD", [original, correction], "2026-01-26T00:00:00Z")
    after_bundle = build_bundle("TESTD", [original, correction], "2026-03-01T12:00:00Z")

    before = build_evidence_readiness_snapshot(
        before_bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    after = build_evidence_readiness_snapshot(
        after_bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert correction.observation_id not in before.input_observation_ids
    assert correction.observation_id in after.input_observation_ids
    assert before.deterministic_id != after.deterministic_id


def test_before_cancellation_active_after_cancellation_present_but_not_active():
    original = make_short_interest(
        source_record_id="si-cancel-orig", settlement_date="2026-01-15", short_shares="900000"
    )
    cancellation = make_short_interest(
        source_record_id="si-cancel-new",
        settlement_date="2026-01-15",
        publication_date="2026-02-05",
        short_shares="900000",
        revision_status="CANCELLED",
        revision_number=1,
        supersedes_source_record_id="si-cancel-orig",
    )
    before_bundle = build_bundle("TESTD", [original, cancellation], "2026-01-26T00:00:00Z")
    after_bundle = build_bundle("TESTD", [original, cancellation], "2026-03-01T12:00:00Z")

    before = build_evidence_readiness_snapshot(
        before_bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    after = build_evidence_readiness_snapshot(
        after_bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert before.structural_state is StructuralState.SUFFICIENT
    assert cancellation.observation_id not in before.input_observation_ids
    assert cancellation.observation_id in after.input_observation_ids


def test_historical_snapshot_remains_byte_identical_on_rebuild():
    si = make_short_interest()
    bundle_a = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    bundle_b = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    a = build_evidence_readiness_snapshot(bundle_a, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE")
    b = build_evidence_readiness_snapshot(bundle_b, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE")
    from squeeze_core.readiness import serialize_readiness_snapshot

    assert serialize_readiness_snapshot(a) == serialize_readiness_snapshot(b)


def test_later_snapshot_changes_deterministically():
    si = make_short_interest()
    bundle_early = build_bundle("TESTD", [si], "2026-01-27T00:00:00Z")
    bundle_later = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    early = build_evidence_readiness_snapshot(
        bundle_early, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    later = build_evidence_readiness_snapshot(
        bundle_later, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert early.deterministic_id != later.deterministic_id
    assert early.as_of != later.as_of


def test_input_reordering_invariance():
    si = make_short_interest()
    fee, availability = make_borrow()
    bundle_a = build_bundle("TESTD", [si, fee, availability], "2026-03-01T12:00:00Z")
    bundle_b = build_bundle("TESTD", [availability, si, fee], "2026-03-01T12:00:00Z")
    a = build_evidence_readiness_snapshot(bundle_a, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE")
    b = build_evidence_readiness_snapshot(bundle_b, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE")
    assert a.deterministic_id == b.deterministic_id


def test_no_score_rank_recommendation_or_qualitative_label_fields():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    snapshot = build_evidence_readiness_snapshot(
        bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    field_names = {name.lower() for name in type(snapshot).model_fields}
    forbidden = (
        "score",
        "rank",
        "recommendation",
        "bullish",
        "bearish",
        "prime",
        "subprime",
        "confidence",
        "alert",
    )
    for term in forbidden:
        assert not any(term in field_name for field_name in field_names)


def test_structural_state_explicitly_scoped_to_operation():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    snapshot = build_evidence_readiness_snapshot(
        bundle, "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    )
    assert snapshot.operation == "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE"
    assert snapshot.structural_state is StructuralState.SUFFICIENT
