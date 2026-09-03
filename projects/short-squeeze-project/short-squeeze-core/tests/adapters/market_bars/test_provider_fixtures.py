import json
from pathlib import Path

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.market_bars import normalize_market_bar_record


ROOT = Path(__file__).parents[2] / "fixtures" / "providers" / "market_bars"
FILES = (
    "representative_cases.json",
    "edge_cases.json",
    "lifecycle_cases.json",
    "session_cases.json",
)
REQUIRED_IDS = {
    "bar-complete-one-minute",
    "bar-complete-five-minute",
    "bar-complete-fifteen-minute",
    "bar-complete-one-hour",
    "bar-complete-daily",
    "bar-partial",
    "bar-partial-to-complete",
    "bar-corrected-completed",
    "bar-cancelled",
    "bar-missing-volume",
    "bar-zero-volume",
    "bar-missing-trade-count",
    "bar-zero-trade-count",
    "bar-missing-vwap",
    "bar-negative-volume",
    "bar-fractional-volume",
    "bar-invalid-ohlc",
    "bar-missing-open",
    "bar-missing-high",
    "bar-missing-low",
    "bar-missing-close",
    "bar-date-only-daily",
    "bar-time-only-intraday",
    "bar-missing-timezone",
    "bar-unknown-session",
    "bar-premarket",
    "bar-regular-session",
    "bar-after-hours",
    "bar-overnight",
    "bar-exact-duplicate",
    "bar-same-id-changed-content",
    "bar-same-boundary-provider-conflict",
    "bar-different-boundaries",
    "bar-publication-after-as-of",
    "bar-receipt-after-as-of",
    "bar-correction-after-as-of",
    "bar-out-of-order",
    "bar-multiple-symbols",
    "bar-unsupported-interval",
    "bar-unsupported-asset-class",
    "bar-session-date-mismatch",
    "bar-dst-ambiguity",
    "bar-sanitized-provider-metadata",
}
METADATA_KEYS = {
    "fixture_id",
    "origin",
    "sanitization_status",
    "source_shape_basis",
    "contains_credentials",
    "contains_account_data",
    "contains_real_symbols",
    "provider",
    "interval_status",
    "session_status",
    "contains_live_urls",
    "provider_record_type",
    "bar_boundary_status",
    "publication_timestamp_status",
    "capture_timestamp_status",
    "received_timestamp_status",
    "completion_status",
    "revision_status",
    "expected_normalization_result",
}


def _cases():
    return [
        case
        for filename in FILES
        for case in json.loads((ROOT / filename).read_text(encoding="utf-8"))["cases"]
    ]


def test_manifest_contains_all_required_cases_once():
    cases = _cases()
    ids = [case["metadata"]["fixture_id"] for case in cases]
    assert len(ids) == 43
    assert len(set(ids)) == 43
    assert set(ids) == REQUIRED_IDS


def test_every_case_has_exact_non_secret_provenance_metadata():
    for case in _cases():
        metadata = case["metadata"]
        assert set(metadata) == METADATA_KEYS
        assert metadata["origin"] in {
            "SANITIZED_REPRESENTATIVE_SAMPLE",
            "SYNTHETIC_EDGE_CASE",
        }
        assert metadata["sanitization_status"] == "SANITIZED"
        assert metadata["contains_credentials"] is False
        assert metadata["contains_account_data"] is False
        assert metadata["contains_real_symbols"] is False
        assert metadata["contains_live_urls"] is False
        assert metadata["provider_record_type"] == "MARKET_BAR"
        assert case["record"]["fixture_origin"] == metadata["origin"]


def test_fixture_family_manifest_does_not_overstate_recorded_provenance():
    metadata = json.loads((ROOT / "fixture_metadata.json").read_text(encoding="utf-8"))
    assert metadata["recorded_sample_found"] is False
    assert metadata["case_count"] == 43
    assert metadata["allowed_origins"] == [
        "SANITIZED_REPRESENTATIVE_SAMPLE",
        "SYNTHETIC_EDGE_CASE",
    ]


def test_expected_acceptance_matches_offline_normalizer():
    adapter_context = AdapterContext.model_validate_json(
        (ROOT / "context.json").read_text(encoding="utf-8")
    )
    for case in _cases():
        expectation = case["metadata"]["expected_normalization_result"]
        result = normalize_market_bar_record(case["record"], adapter_context)
        assert result.accepted is expectation.startswith("ACCEPT"), case["metadata"]["fixture_id"]


def test_fixture_text_has_no_live_urls_or_secret_markers():
    text = "\n".join((ROOT / filename).read_text(encoding="utf-8") for filename in FILES)
    lowered = text.lower()
    assert "http://" not in lowered and "https://" not in lowered
    assert "api_key" not in lowered
    assert "access_token" not in lowered
    assert "account_id" not in lowered
