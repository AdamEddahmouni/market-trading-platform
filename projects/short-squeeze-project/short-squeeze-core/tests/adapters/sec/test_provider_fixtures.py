import json
from pathlib import Path

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.sec import normalize_sec_filing_record


ROOT = Path(__file__).parents[2] / "fixtures" / "providers" / "sec"


REQUIRED_METADATA = {
    "fixture_id",
    "origin",
    "sanitization_status",
    "source_shape_basis",
    "contains_credentials",
    "contains_account_data",
    "contains_real_symbols",
    "contains_remote_urls",
    "accession_status",
    "acceptance_timestamp_status",
    "publication_timestamp_status",
    "received_timestamp_status",
    "amendment_status",
    "expected_normalization_result",
}


def documents():
    for name in ("representative_cases.json", "edge_cases.json", "amendment_cases.json"):
        yield json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_fixture_family_does_not_claim_recorded_provenance() -> None:
    metadata = json.loads((ROOT / "fixture_metadata.json").read_text(encoding="utf-8"))
    assert metadata["recorded_sample_found"] is False
    assert metadata["archive_sec_metadata_found"] is False
    assert metadata["allowed_origins"] == [
        "SANITIZED_REPRESENTATIVE_SAMPLE",
        "SYNTHETIC_EDGE_CASE",
    ]


def test_every_fixture_has_complete_safe_provenance_metadata() -> None:
    cases = [case for document in documents() for case in document["cases"]]
    assert len(cases) >= 19
    for case in cases:
        metadata = case["metadata"]
        assert REQUIRED_METADATA <= metadata.keys()
        assert metadata["origin"] in {
            "SANITIZED_REPRESENTATIVE_SAMPLE",
            "SYNTHETIC_EDGE_CASE",
        }
        assert metadata["contains_credentials"] is False
        assert metadata["contains_account_data"] is False
        assert metadata["contains_real_symbols"] is False
        assert metadata["contains_remote_urls"] is False
        assert case["record"].get("fixture_origin") == metadata["origin"]
        assert str(case["record"].get("symbol", "TESTA")).startswith("TEST")


def test_required_case_semantics_are_covered() -> None:
    ids = {case["metadata"]["fixture_id"] for document in documents() for case in document["cases"]}
    required = {
        "sec-complete-original-v1",
        "sec-explicit-publication-v1",
        "sec-date-only-filed-v1",
        "sec-date-only-publication-v1",
        "sec-missing-acceptance-v1",
        "sec-missing-accession-v1",
        "sec-invalid-accession-v1",
        "sec-compact-accession-v1",
        "sec-missing-cik-v1",
        "sec-unpadded-cik-v1",
        "sec-invalid-cik-v1",
        "sec-missing-form-v1",
        "sec-missing-period-v1",
        "sec-missing-document-v1",
        "sec-future-availability-v1",
        "sec-amendment-v1",
        "sec-amendment-missing-link-v1",
        "sec-duplicate-v1",
        "sec-same-accession-conflict-v1",
    }
    assert required <= ids


def test_representative_complete_fixture_normalizes_deterministically() -> None:
    document = json.loads((ROOT / "representative_cases.json").read_text(encoding="utf-8"))
    case = next(item for item in document["cases"] if item["metadata"]["fixture_id"] == "sec-complete-original-v1")
    context = AdapterContext.model_validate_json((ROOT / "context.json").read_text(encoding="utf-8"))
    first = normalize_sec_filing_record(case["record"], context)
    second = normalize_sec_filing_record(case["record"], context)
    assert first == second
    assert first.accepted and len(first.observations) == 1
