import json
from pathlib import Path

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.trades_quotes import normalize_trade_quote_record


ROOT = Path(__file__).parents[2] / "fixtures" / "providers" / "trades_quotes"


def test_fixture_metadata_has_exact_allowed_provenance_and_required_fields():
    document = json.loads((ROOT / "fixture_metadata.json").read_text(encoding="utf-8"))
    assert document["recorded_rows_found"] is False
    assert len(document["families"]) == 6
    required = {
        "fixture_id", "origin", "sanitization_status", "source_shape_basis",
        "contains_credentials", "contains_account_data", "contains_real_symbols",
        "contains_live_urls", "provider", "record_type", "venue_status",
        "sequence_status", "condition_status", "event_timestamp_status",
        "publication_timestamp_status", "capture_timestamp_status",
        "received_timestamp_status", "revision_status", "expected_normalization_result",
    }
    for family in document["families"]:
        assert set(family) == required
        assert family["origin"] in {
            "SANITIZED_REPRESENTATIVE_SAMPLE", "SYNTHETIC_EDGE_CASE"
        }
        assert family["contains_credentials"] is False
        assert family["contains_account_data"] is False
        assert family["contains_real_symbols"] is False
        assert family["contains_live_urls"] is False


def test_all_required_fixture_files_are_local_json_and_contain_expected_cases():
    names = {
        "trade_representative_cases.json", "trade_edge_cases.json",
        "trade_lifecycle_cases.json", "quote_representative_cases.json",
        "quote_edge_cases.json", "quote_lifecycle_cases.json",
    }
    assert names <= {item.name for item in ROOT.glob("*.json")}
    case_ids = {
        case["fixture_id"]
        for name in names
        for case in json.loads((ROOT / name).read_text(encoding="utf-8"))["cases"]
    }
    assert {
        "trade-complete-equity", "trade-missing-size", "trade-zero-size",
        "trade-invalid-price", "trade-fractional-size", "trade-missing-sequence",
        "trade-sequence-reset", "trade-original", "trade-corrected", "trade-cancelled",
        "quote-complete-venue", "quote-bid-only", "quote-ask-only", "quote-nbbo",
        "quote-consolidated", "quote-provider-aggregated", "quote-locked", "quote-crossed",
        "quote-missing-both-sides", "quote-zero-sizes", "quote-size-without-price",
        "quote-unknown-scope", "quote-original", "quote-corrected", "quote-cancelled",
    } <= case_ids


def test_representative_trade_rows_normalize_with_context_only():
    config = json.loads((ROOT / "context.json").read_text(encoding="utf-8"))
    config.pop("ingested_at")
    document = json.loads((ROOT / "trade_representative_cases.json").read_text(encoding="utf-8"))
    for case in document["cases"]:
        result = normalize_trade_quote_record(
            case["record"], AdapterContext(ingested_at=case["ingested_at"], **config)
        )
        assert result.accepted is True
        assert len(result.observations) == 1
