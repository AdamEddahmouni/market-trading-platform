import json
from pathlib import Path

from squeeze_core.adapters import AdapterContext, DiagnosticCode
from squeeze_core.adapters.finra import normalize_finra_short_interest_record


ROOT = Path(__file__).parents[2] / "fixtures" / "providers" / "finra"

REQUIRED_CASES = {
    "finra-complete-v1",
    "finra-zero-short-shares-v1",
    "finra-missing-short-shares-v1",
    "finra-missing-settlement-v1",
    "finra-missing-publication-v1",
    "finra-date-only-publication-v1",
    "finra-unknown-publication-timezone-v1",
    "finra-publication-before-receipt-v1",
    "finra-receipt-before-publication-v1",
    "finra-published-after-as-of-v1",
    "finra-received-after-as-of-v1",
    "finra-corrected-v1",
    "finra-revised-v1",
    "finra-duplicate-v1",
    "finra-conflicting-same-period-v1",
    "finra-different-period-v1",
    "finra-missing-float-v1",
    "finra-missing-short-float-v1",
    "finra-missing-days-to-cover-v1",
    "finra-invalid-numeric-v1",
    "finra-daily-short-volume-v1",
    "finra-partial-defensible-v1",
}

METADATA_KEYS = {
    "fixture_id",
    "origin",
    "sanitization_status",
    "source_shape_basis",
    "contains_credentials",
    "contains_account_data",
    "contains_real_symbols",
    "settlement_date_status",
    "publication_date_status",
    "received_date_status",
    "revision_status",
    "expected_normalization_result",
}


def documents() -> list[dict[str, object]]:
    return [
        json.loads((ROOT / name).read_text(encoding="utf-8"))
        for name in ("representative_cases.json", "edge_cases.json", "revision_cases.json")
    ]


def test_fixture_family_contains_every_required_case_with_exact_provenance_metadata() -> None:
    cases = [case for document in documents() for case in document["cases"]]
    ids = {case["metadata"]["fixture_id"] for case in cases}

    assert ids == REQUIRED_CASES
    for case in cases:
        metadata = case["metadata"]
        assert set(metadata) == METADATA_KEYS
        assert metadata["origin"] in {
            "SANITIZED_REPRESENTATIVE_SAMPLE",
            "SYNTHETIC_EDGE_CASE",
        }
        assert metadata["origin"] != "SANITIZED_RECORDED_SAMPLE"
        assert metadata["contains_credentials"] is False
        assert metadata["contains_account_data"] is False
        assert metadata["contains_real_symbols"] is False
        assert case["record"].get("symbol", case["record"].get("Symbol")) in {
            "TESTA",
            "TESTB",
            "TESTC",
        }


def test_fixture_metadata_documents_absence_of_recorded_finra_sample() -> None:
    metadata = json.loads((ROOT / "fixture_metadata.json").read_text(encoding="utf-8"))

    assert metadata["recorded_sample_found"] is False
    assert metadata["archive_finra_feed_found"] is False
    assert metadata["allowed_origins"] == [
        "SANITIZED_REPRESENTATIVE_SAMPLE",
        "SYNTHETIC_EDGE_CASE",
    ]
    assert "test_yfinance_float_api.py" in metadata["source_shape_basis"]


def test_complete_fixture_normalizes_and_daily_volume_fixture_rejects() -> None:
    context = AdapterContext.model_validate_json((ROOT / "context.json").read_text())
    cases = [case for document in documents() for case in document["cases"]]
    by_id = {case["metadata"]["fixture_id"]: case for case in cases}

    complete = normalize_finra_short_interest_record(
        by_id["finra-complete-v1"]["record"], context
    )
    daily = normalize_finra_short_interest_record(
        by_id["finra-daily-short-volume-v1"]["record"], context
    )

    assert complete.accepted and len(complete.observations) == 1
    assert daily.accepted is False
    assert daily.rejection is not None
    assert daily.rejection.code is DiagnosticCode.FINRA_DAILY_SHORT_VOLUME_NOT_SUPPORTED


def test_fixture_text_has_no_secret_or_private_path_markers() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in ROOT.glob("*.json"))
    lowered = text.lower()
    for forbidden in (
        "password",
        "api_key",
        "access_token",
        "account_id",
        "mongodb://",
        "https://",
        "c:\\users\\",
    ):
        assert forbidden not in lowered
