import json
from pathlib import Path

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.news import normalize_news_record


ROOT = Path(__file__).parents[2] / "fixtures" / "providers" / "news"
FILES = (
    "representative_cases.json",
    "edge_cases.json",
    "update_cases.json",
    "syndication_cases.json",
)
REQUIRED_METADATA_KEYS = {
    "fixture_id", "origin", "sanitization_status", "source_shape_basis",
    "contains_credentials", "contains_account_data", "contains_real_symbols",
    "contains_live_urls", "provider_record_id_status",
    "publication_timestamp_status", "updated_timestamp_status",
    "received_timestamp_status", "symbol_association_status",
    "revision_status", "expected_normalization_result",
}


def documents():
    return [json.loads((ROOT / name).read_text(encoding="utf-8")) for name in FILES]


def test_fixture_family_has_exactly_thirty_five_classified_cases() -> None:
    cases = [case for document in documents() for case in document["cases"]]
    assert len(cases) == 35
    assert len({case["metadata"]["fixture_id"] for case in cases}) == 35
    for case in cases:
        metadata = case["metadata"]
        assert REQUIRED_METADATA_KEYS <= metadata.keys()
        assert metadata["origin"] in {
            "SANITIZED_REPRESENTATIVE_SAMPLE", "SYNTHETIC_EDGE_CASE"
        }
        assert not metadata["contains_credentials"]
        assert not metadata["contains_account_data"]
        assert not metadata["contains_real_symbols"]
        assert not metadata["contains_live_urls"]


def test_family_metadata_documents_archive_exclusion_and_allowed_origins() -> None:
    metadata = json.loads((ROOT / "fixture_metadata.json").read_text(encoding="utf-8"))
    assert metadata["recorded_sample_found"] is False
    assert metadata["news_snapshot_is_objective_fixture"] is False
    assert metadata["allowed_origins"] == [
        "SANITIZED_REPRESENTATIVE_SAMPLE", "SYNTHETIC_EDGE_CASE"
    ]


def test_every_fixture_matches_expected_acceptance() -> None:
    context = AdapterContext.model_validate_json((ROOT / "context.json").read_text(encoding="utf-8"))
    for document in documents():
        for case in document["cases"]:
            result = normalize_news_record(case["record"], context)
            expected = case["metadata"]["expected_normalization_result"]
            assert result.accepted is expected.startswith("ACCEPT"), case["metadata"]["fixture_id"]


def test_fixture_text_has_no_secrets_live_hosts_or_real_symbols() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in ROOT.glob("*.json")).lower()
    for forbidden in (
        "password", "access_token", "refresh_token", "api_key", "account_id",
        "yahoo.com", "finviz.com", "newsapi.org", "aapl", "amc",
        "c:\\users\\",
    ):
        assert forbidden not in text
    assert "news.example.invalid" in text
