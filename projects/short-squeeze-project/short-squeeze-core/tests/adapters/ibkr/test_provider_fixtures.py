import inspect
import json
from datetime import timedelta
from pathlib import Path

from squeeze_core.adapters import AdapterContext, DiagnosticCode
from squeeze_core.adapters.ibkr import normalize_ibkr_borrow_record
from squeeze_core.serialization import canonical_hash


FIXTURE_ROOT = Path("tests/fixtures/providers/ibkr")
ALLOWED_ORIGINS = {
    "SANITIZED_RECORDED_SAMPLE",
    "SANITIZED_REPRESENTATIVE_SAMPLE",
    "SYNTHETIC_EDGE_CASE",
}
REQUIRED_METADATA = {
    "fixture_id",
    "fixture_type",
    "origin",
    "sanitization_status",
    "contains_real_account_data",
    "contains_credentials",
    "created_at",
    "source_shape_basis",
    "expected_normalization_result",
}


def load_cases(filename: str) -> list[dict]:
    return json.loads((FIXTURE_ROOT / filename).read_text(encoding="utf-8"))["cases"]


def load_context() -> AdapterContext:
    return AdapterContext.model_validate_json((FIXTURE_ROOT / "context.json").read_text())


def test_every_fixture_case_has_complete_honest_provenance() -> None:
    cases = load_cases("representative_cases.json") + load_cases("edge_cases.json")

    assert len(cases) >= 14
    for case in cases:
        metadata = case["metadata"]
        assert REQUIRED_METADATA <= metadata.keys()
        assert metadata["origin"] in ALLOWED_ORIGINS
        assert metadata["origin"] != "SANITIZED_RECORDED_SAMPLE"
        assert metadata["contains_real_account_data"] is False
        assert metadata["contains_credentials"] is False
        assert metadata["sanitization_status"] == "SANITIZED_NO_SECRETS"


def test_fixture_family_covers_required_normalization_cases() -> None:
    cases = load_cases("representative_cases.json") + load_cases("edge_cases.json")
    fixture_types = {case["metadata"]["fixture_type"] for case in cases}

    assert {
        "COMPLETE_RECORD",
        "EXPLICIT_ZERO_FEE",
        "EXPLICIT_ZERO_AVAILABILITY",
        "MISSING_FEE",
        "MISSING_AVAILABILITY",
        "MISSING_PROVIDER_TIMESTAMP",
        "UNKNOWN_TIMEZONE",
        "DELAYED_RECORD",
        "NON_NUMERIC_FEE",
        "FRACTIONAL_AVAILABILITY",
        "NEGATIVE_AVAILABILITY",
        "UNSUPPORTED_PERCENT_UNIT",
        "DUPLICATE_SOURCE_RECORD",
        "CONFLICTING_RECORDS",
    } <= fixture_types


def test_fixture_expectations_match_normalization_behavior() -> None:
    context = load_context()
    cases = load_cases("representative_cases.json")
    by_type = {case["metadata"]["fixture_type"]: case for case in cases}

    missing_fee = normalize_ibkr_borrow_record(by_type["MISSING_FEE"]["record"], context)
    zero_fee = normalize_ibkr_borrow_record(by_type["EXPLICIT_ZERO_FEE"]["record"], context)
    missing_timestamp = normalize_ibkr_borrow_record(
        by_type["MISSING_PROVIDER_TIMESTAMP"]["record"], context
    )
    assert DiagnosticCode.MISSING_BORROW_FEE in {item.code for item in missing_fee.diagnostics}
    assert DiagnosticCode.EXPLICIT_ZERO_BORROW_FEE in {item.code for item in zero_fee.diagnostics}
    assert DiagnosticCode.MISSING_PROVIDER_TIMESTAMP in {
        item.code for item in missing_timestamp.diagnostics
    }


def test_raw_record_hash_is_stable_and_changes_with_content() -> None:
    complete = load_cases("representative_cases.json")[0]["record"]

    assert canonical_hash(complete) == canonical_hash(json.loads(json.dumps(complete)))
    changed = {**complete, "available_shares": "999"}
    assert canonical_hash(complete) != canonical_hash(changed)


def test_changing_only_ingested_at_changes_only_ingestion_dependent_fields() -> None:
    complete = load_cases("representative_cases.json")[0]["record"]
    first_context = load_context()
    second_context = first_context.model_copy(
        update={"ingested_at": first_context.ingested_at + timedelta(seconds=30)}
    )
    first = normalize_ibkr_borrow_record(complete, first_context).observations
    second = normalize_ibkr_borrow_record(complete, second_context).observations

    assert [item.observation_id for item in first] == [item.observation_id for item in second]
    assert [item.raw_payload_hash for item in first] == [item.raw_payload_hash for item in second]
    assert [item.source_timestamp for item in first] == [item.source_timestamp for item in second]
    assert [item.payload for item in first] == [item.payload for item in second]
    assert [item.received_timestamp for item in first] != [item.received_timestamp for item in second]
    assert [item.quality.evaluated_at for item in first] != [
        item.quality.evaluated_at for item in second
    ]
    assert [canonical_hash(item) for item in first] != [canonical_hash(item) for item in second]


def test_adapter_path_has_no_wall_clock_network_environment_sdk_or_database_access() -> None:
    import squeeze_core.adapters.base as base
    import squeeze_core.adapters.ibkr.normalizer as normalizer

    source = inspect.getsource(base) + inspect.getsource(normalizer)
    forbidden = (
        "datetime.now(",
        "datetime.utcnow(",
        "os.environ",
        "getenv(",
        "socket",
        "requests",
        "httpx",
        "urllib",
        "ib_async",
        "ib_insync",
        "pymongo",
        "motor",
        "placeOrder",
    )
    assert not any(term in source for term in forbidden)
