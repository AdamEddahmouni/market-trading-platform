import inspect
import json
from pathlib import Path

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.finviz import normalize_finviz_snapshot_record
from squeeze_core.serialization import canonical_hash


FIXTURE_ROOT = Path("tests/fixtures/providers/finviz")
ALLOWED_ORIGINS = {"SANITIZED_REPRESENTATIVE_SAMPLE", "SYNTHETIC_EDGE_CASE"}
REQUIRED_METADATA = {
    "fixture_id",
    "fixture_type",
    "origin",
    "sanitization_status",
    "source_shape_basis",
    "contains_credentials",
    "contains_account_data",
    "contains_real_symbols",
    "provider_timestamp_status",
    "capture_timestamp_status",
    "expected_normalization_result",
}


def cases(name: str) -> list[dict]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))["cases"]


def test_finviz_fixtures_have_complete_honest_non_recorded_provenance() -> None:
    all_cases = cases("representative_cases.json") + cases("edge_cases.json")

    assert len(all_cases) >= 15
    for case in all_cases:
        metadata = case["metadata"]
        assert REQUIRED_METADATA <= metadata.keys()
        assert metadata["origin"] in ALLOWED_ORIGINS
        assert metadata["origin"] != "SANITIZED_RECORDED_SAMPLE"
        assert metadata["contains_credentials"] is False
        assert metadata["contains_account_data"] is False
        assert metadata["contains_real_symbols"] is False
        assert metadata["sanitization_status"] == "SANITIZED_NO_SECRETS"


def test_fixture_family_covers_required_finviz_cases() -> None:
    all_cases = cases("representative_cases.json") + cases("edge_cases.json")
    fixture_types = {case["metadata"]["fixture_type"] for case in all_cases}

    assert {
        "COMPLETE_RECORD",
        "EXPLICIT_ZERO_VALUES",
        "MISSING_VALUES",
        "CAPTURE_TIME_ONLY",
        "MISSING_ALL_TIMESTAMPS",
        "KNOWN_DELAYED",
        "ABBREVIATED_QUANTITIES",
        "INVALID_PRICE",
        "NEGATIVE_PRICE",
        "UNSUPPORTED_PERCENT_UNIT",
        "INVALID_QUANTITY_SUFFIX",
        "AMBIGUOUS_EARNINGS",
        "DUPLICATE_SOURCE_RECORD",
        "CONFLICTING_RECORDS",
        "OTHER_SYMBOL",
        "OTHER_EXCHANGE",
    } <= fixture_types


def test_complete_fixture_normalizes_with_exact_raw_hash() -> None:
    complete = next(
        case for case in cases("representative_cases.json")
        if case["metadata"]["fixture_type"] == "COMPLETE_RECORD"
    )
    context = AdapterContext.model_validate_json((FIXTURE_ROOT / "context.json").read_text())
    result = normalize_finviz_snapshot_record(complete["record"], context)

    assert result.accepted is True
    assert result.observations[0].raw_payload_hash == canonical_hash(complete["record"])


def test_finviz_normalization_path_has_no_live_or_stateful_dependencies() -> None:
    import squeeze_core.adapters.finviz.normalizer as normalizer
    import squeeze_core.adapters.finviz.parsing as parsing

    source = inspect.getsource(normalizer) + inspect.getsource(parsing)
    forbidden = (
        "datetime.now(",
        "datetime.utcnow(",
        "os.environ",
        "getenv(",
        "requests",
        "httpx",
        "urllib",
        "socket",
        "selenium",
        "playwright",
        "curl_cffi",
        "pymongo",
        "ib_async",
        "placeOrder",
    )
    assert not any(term in source for term in forbidden)
