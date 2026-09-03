import json
import sys
from pathlib import Path

from squeeze_core.serialization import canonical_hash


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "evaluation"
sys.path.insert(0, str(ROOT / "scripts"))
from generate_phase_3a_anchors import _hash, build_anchor_results, generate  # noqa: E402


REQUIRED = {
    "price_range_pass", "price_range_fail", "price_range_unknown",
    "percentage_change_pass", "percentage_change_fail", "relative_volume_pass",
    "relative_volume_fail", "relative_volume_insufficient", "float_unknown",
    "short_interest_available", "short_interest_unknown", "short_interest_change_pass",
    "short_interest_change_fail", "days_to_cover_pass", "days_to_cover_fail",
    "days_to_cover_insufficient", "borrow_fee_pass", "borrow_fee_unknown",
    "borrow_availability_zero_known", "borrow_availability_unknown",
    "news_before_as_of_pass", "news_after_as_of_fail", "news_timestamp_unknown",
    "required_domains_pass", "required_domain_missing", "required_domain_conflicted",
    "required_history_insufficient", "no_default_substitution_pass",
    "default_substitution_detected", "biya_earliest_momentum_results",
    "biya_earliest_short_pressure_results", "biya_earliest_catalyst_results",
    "biya_earliest_validity_results", "biya_earliest_complete_evaluation",
    "biya_latest_momentum_results", "biya_latest_short_pressure_results",
    "biya_latest_catalyst_results", "biya_latest_validity_results",
    "biya_latest_complete_evaluation", "mixed_phase_3a_output",
    "phase_3a_cli_output", "serialized_phase_3a_collection",
}


def _recorded():
    return json.loads((FIXTURES / "expected_phase_3a_evaluation_metadata.json").read_text(encoding="utf-8"))["anchors"]


def test_all_required_phase_3a_anchors_are_present():
    assert REQUIRED == set(_recorded())


def test_named_anchor_results_regenerate_deterministically_and_match():
    first = build_anchor_results()
    second = build_anchor_results()
    recorded = _recorded()
    for name in first:
        assert _hash(first[name]) == _hash(second[name]) == recorded[name]


def test_full_fixture_generation_is_byte_identical():
    generate()
    first = {path.name: path.read_bytes() for path in FIXTURES.iterdir() if path.is_file()}
    generate()
    second = {path.name: path.read_bytes() for path in FIXTURES.iterdir() if path.is_file()}
    assert first == second

