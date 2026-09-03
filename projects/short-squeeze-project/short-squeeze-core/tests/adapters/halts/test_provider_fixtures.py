import json
from pathlib import Path

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.halts import normalize_trading_halt_record


ROOT = Path(__file__).parents[2] / "fixtures" / "providers" / "halts"
REQUIRED_METADATA_KEYS = {
    "fixture_id",
    "origin",
    "sanitization_status",
    "source_shape_basis",
    "contains_credentials",
    "contains_account_data",
    "contains_real_symbols",
    "exchange",
    "halt_code_status",
    "announcement_timestamp_status",
    "halt_timestamp_status",
    "quote_resumption_status",
    "trade_resumption_status",
    "received_timestamp_status",
    "revision_status",
    "expected_normalization_result",
}


def documents():
    return [
        json.loads((ROOT / name).read_text(encoding="utf-8"))
        for name in ("representative_cases.json", "edge_cases.json", "lifecycle_cases.json")
    ]


def test_fixture_family_has_exactly_thirty_classified_cases() -> None:
    cases = [case for document in documents() for case in document["cases"]]
    assert len(cases) == 30
    assert len({case["metadata"]["fixture_id"] for case in cases}) == 30
    for case in cases:
        metadata = case["metadata"]
        assert REQUIRED_METADATA_KEYS <= metadata.keys()
        assert metadata["origin"] in {
            "SANITIZED_REPRESENTATIVE_SAMPLE",
            "SYNTHETIC_EDGE_CASE",
        }
        assert metadata["origin"] != "SANITIZED_RECORDED_SAMPLE"
        assert not metadata["contains_credentials"]
        assert not metadata["contains_account_data"]
        assert not metadata["contains_real_symbols"]
        assert case["record"].get("symbol", case["record"].get("ticker")) in {
            "TESTA",
            "TESTB",
            "TESTC",
            "bad symbol",
        }


def test_family_metadata_records_archive_absence() -> None:
    metadata = json.loads((ROOT / "fixture_metadata.json").read_text(encoding="utf-8"))
    assert metadata["recorded_sample_found"] is False
    assert metadata["archive_halt_metadata_found"] is False
    assert metadata["allowed_origins"] == [
        "SANITIZED_REPRESENTATIVE_SAMPLE",
        "SYNTHETIC_EDGE_CASE",
    ]


def test_every_fixture_matches_its_expected_acceptance_class() -> None:
    context = AdapterContext.model_validate_json((ROOT / "context.json").read_text(encoding="utf-8"))
    for document in documents():
        for case in document["cases"]:
            result = normalize_trading_halt_record(case["record"], context)
            expected = case["metadata"]["expected_normalization_result"]
            assert result.accepted is expected.startswith("ACCEPT"), case["metadata"]["fixture_id"]


def test_fixture_text_contains_no_sensitive_or_live_transport_material() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in ROOT.glob("*.json"))
    lowered = text.lower()
    for forbidden in (
        "password",
        "access_token",
        "refresh_token",
        "api_key",
        "account_id",
        "https://",
        "http://",
        "ws://",
        "wss://",
        "c:\\users\\",
    ):
        assert forbidden not in lowered
