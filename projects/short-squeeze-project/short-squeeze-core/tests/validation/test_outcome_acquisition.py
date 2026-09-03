from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from squeeze_core.validation.outcome_acquisition import (
    AcquisitionDataType,
    AcquisitionEntitlementState,
    AcquisitionResultState,
    build_acquisition_manifest,
    deserialize_acquisition_manifest,
    serialize_acquisition_manifest,
)


START = datetime(2026, 7, 16, 4, 0, tzinfo=UTC)
END = datetime(2026, 7, 21, 20, 42, 17, tzinfo=UTC)
FIRST = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)
LAST = datetime(2026, 7, 21, 20, 41, tzinfo=UTC)
RAW = b'{"chart":{"result":[]}}\n'


def manifest(**overrides: object):
    values: dict[str, object] = {
        "symbol": "biya",
        "provider": "public-chart",
        "data_type": AcquisitionDataType.INTRADAY_MARKET_BARS,
        "requested_start": START,
        "requested_end": END,
        "retrieved_at": END,
        "request_timezone": "America/New_York",
        "response_timezone": "America/New_York",
        "bar_size": "1_MINUTE",
        "session_scope": "REGULAR_AND_EXTENDED",
        "adjustment_policy": "PROVIDER_ADJUSTED",
        "request_parameters": {"interval": "1m", "include_prepost": True},
        "result_state": AcquisitionResultState.SUCCESS,
        "raw_relative_path": "raw/market_bars/BIYA_public-chart_intraday.json",
        "raw_bytes": RAW,
        "record_count": 7,
        "earliest_record_time": FIRST,
        "latest_record_time": LAST,
        "entitlement_state": AcquisitionEntitlementState.NOT_REQUIRED,
    }
    values.update(overrides)
    return build_acquisition_manifest(**values)


@pytest.mark.parametrize(
    "state",
    [
        AcquisitionResultState.SUCCESS,
        AcquisitionResultState.PARTIAL,
        AcquisitionResultState.EMPTY,
        AcquisitionResultState.ENTITLEMENT_REQUIRED,
        AcquisitionResultState.NETWORK_FAILURE,
        AcquisitionResultState.UNSUPPORTED,
    ],
)
def test_manifest_preserves_explicit_result_state(state: AcquisitionResultState) -> None:
    raw = RAW if state in {AcquisitionResultState.SUCCESS, AcquisitionResultState.PARTIAL} else None
    result = manifest(
        result_state=state,
        raw_bytes=raw,
        raw_relative_path=(
            "raw/market_bars/attempt.json" if raw is not None else None
        ),
        record_count=7 if raw is not None else 0,
        earliest_record_time=FIRST if raw is not None else None,
        latest_record_time=LAST if raw is not None else None,
    )
    assert result.result_state is state


def test_manifest_has_stable_id_and_serialization_under_parameter_ordering() -> None:
    first = manifest(request_parameters={"interval": "1m", "include_prepost": True})
    second = manifest(request_parameters={"include_prepost": True, "interval": "1m"})
    assert first.acquisition_id == second.acquisition_id
    assert serialize_acquisition_manifest(first) == serialize_acquisition_manifest(second)
    assert deserialize_acquisition_manifest(serialize_acquisition_manifest(first)) == first


def test_manifest_preserves_hash_count_range_and_retrieval_time() -> None:
    result = manifest()
    assert result.raw_sha256 == "sha256:a6f5504075531bbcf5f04e4784f75864f09b4527dc4568760f23d82a38cce873"
    assert result.record_count == 7
    assert result.earliest_record_time == FIRST
    assert result.latest_record_time == LAST
    assert result.retrieved_at == END
    assert result.request_parameters == {"include_prepost": True, "interval": "1m"}


def test_manifest_sorts_diagnostics_and_limitations() -> None:
    result = manifest(
        warnings=("z-warning", "a-warning"),
        errors=("Z_ERROR", "A_ERROR"),
        limitations=("z-limit", "a-limit"),
    )
    assert result.warnings == ("a-warning", "z-warning")
    assert result.errors == ("A_ERROR", "Z_ERROR")
    assert result.limitations == ("a-limit", "z-limit")


@pytest.mark.parametrize(
    "field,value",
    [
        ("raw_relative_path", r"C:\\private\\raw.json"),
        ("normalized_relative_path", "/private/normalized.jsonl"),
    ],
)
def test_manifest_rejects_absolute_paths(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match="workspace-relative"):
        manifest(**{field: value})


@pytest.mark.parametrize(
    "secret_key",
    ["api_key", "token", "accessToken", "authorization", "cookie", "account_id", "password"],
)
def test_manifest_rejects_credential_or_account_parameters(secret_key: str) -> None:
    with pytest.raises(ValueError, match="sensitive request parameter"):
        manifest(request_parameters={secret_key: "independent-dummy-value"})


def test_manifest_requires_explicit_timezone_aware_retrieval_time() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        manifest(retrieved_at=datetime(2026, 7, 21, 16, 42, 17))


def test_manifest_rejects_success_without_preserved_raw_response() -> None:
    with pytest.raises(ValidationError, match="successful acquisition requires"):
        manifest(raw_bytes=None, raw_relative_path=None)


def test_manifest_rejects_empty_response_with_records() -> None:
    with pytest.raises(ValidationError, match="cannot carry records"):
        manifest(
            result_state=AcquisitionResultState.EMPTY,
            raw_bytes=None,
            raw_relative_path=None,
            record_count=1,
        )
