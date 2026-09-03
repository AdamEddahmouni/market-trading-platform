import json
from pathlib import Path
from urllib.error import URLError

import pytest

from scripts.acquisition.acquire_biya_history import acquire, main
from squeeze_core.validation.outcome_acquisition import (
    AcquisitionResultState,
    deserialize_acquisition_manifest,
)


END = "2026-07-21T16:45:30-04:00"


def args(output: Path, **overrides: str) -> list[str]:
    values = {
        "provider": "public-chart",
        "data_type": "INTRADAY_MARKET_BARS",
        "start": "2026-07-16T00:00:00-04:00",
        "end": END,
        "retrieved_at": END,
        "timezone": "America/New_York",
        "session_scope": "REGULAR_AND_EXTENDED",
        "bar_size": "1_MINUTE",
        "adjustment_policy": "PROVIDER_ADJUSTED",
        "output": str(output),
        "source_url": "https://public.example.test/chart/BIYA",
    }
    values.update(overrides)
    result = ["--symbol", "BIYA"]
    for key, value in values.items():
        result.extend(("--" + key.replace("_", "-"), value))
    result.extend(("--request-parameter", "interval=1m"))
    return result


def chart_payload() -> bytes:
    return json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "timestamp": [1784203200, 1784203260],
                        "indicators": {"quote": [{"open": [3.1, 3.2]}]},
                    }
                ],
                "error": None,
            }
        },
        separators=(",", ":"),
    ).encode("utf-8")


class Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_success_preserves_raw_bytes_and_manifest(tmp_path: Path) -> None:
    payload = chart_payload()
    manifest = acquire(args(tmp_path), fetcher=lambda request, timeout: Response(payload))
    assert manifest.result_state is AcquisitionResultState.SUCCESS
    assert manifest.record_count == 2
    assert manifest.raw_relative_path is not None
    raw_path = tmp_path / manifest.raw_relative_path
    assert raw_path.read_bytes() == payload
    manifest_path = tmp_path / "manifests" / f"{manifest.acquisition_id}.json"
    assert deserialize_acquisition_manifest(manifest_path.read_bytes()) == manifest
    assert "adame" not in manifest_path.name.lower()


def test_acquisition_never_overwrites_existing_raw_or_manifest(tmp_path: Path) -> None:
    payload = chart_payload()
    acquire(args(tmp_path), fetcher=lambda request, timeout: Response(payload))
    with pytest.raises(FileExistsError):
        acquire(args(tmp_path), fetcher=lambda request, timeout: Response(payload))


def test_network_failure_writes_failure_manifest_without_raw_file(tmp_path: Path) -> None:
    def fail(request: object, timeout: int):
        raise URLError("synthetic DNS failure")

    manifest = acquire(args(tmp_path), fetcher=fail)
    assert manifest.result_state is AcquisitionResultState.NETWORK_FAILURE
    assert manifest.record_count == 0
    assert manifest.raw_relative_path is None
    assert manifest.errors == ("ACQUISITION_NETWORK_FAILURE",)
    assert list((tmp_path / "manifests").glob("*.json"))
    assert not list((tmp_path / "raw").rglob("*.*"))


def test_explicit_unsupported_attempt_requires_no_network(tmp_path: Path) -> None:
    manifest = acquire(
        args(
            tmp_path,
            provider="ibkr",
            source_url="",
            result_state="UNAVAILABLE",
            failure_code="ACQUISITION_GATEWAY_UNAVAILABLE",
        )
    )
    assert manifest.result_state is AcquisitionResultState.UNAVAILABLE
    assert manifest.errors == ("ACQUISITION_GATEWAY_UNAVAILABLE",)


def test_invalid_request_exits_nonzero_with_structured_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(args(tmp_path, end="not-a-time"))
    assert code == 1
    error = json.loads(capsys.readouterr().err)
    assert error["valid"] is False
    assert error["command"] == "acquire-biya-history"


def test_cli_does_not_print_source_url_or_credentials(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        args(tmp_path),
        fetcher=lambda request, timeout: Response(chart_payload()),
    )
    assert code == 0
    output = capsys.readouterr().out
    assert "public.example.test" not in output
    assert "source_url" not in output


def test_news_json_counts_articles_and_preserves_publication_range(tmp_path: Path) -> None:
    payload = json.dumps(
        {
            "news": [
                {"title": "First", "providerPublishTime": 1784290000},
                {"title": "Second", "providerPublishTime": 1784300000},
            ]
        }
    ).encode("utf-8")
    manifest = acquire(
        args(tmp_path, data_type="NEWS", bar_size="NOT_APPLICABLE"),
        fetcher=lambda request, timeout: Response(payload),
    )
    assert manifest.result_state is AcquisitionResultState.SUCCESS
    assert manifest.record_count == 2
    assert manifest.earliest_record_time is not None
    assert manifest.latest_record_time is not None


def test_finra_pipe_file_counts_only_requested_symbol(tmp_path: Path) -> None:
    payload = (
        b"Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n"
        b"20260717|BIYA|7329980|100|12500000|Q,N\n"
        b"20260717|OTHER|10|0|100|Q\n"
    )
    manifest = acquire(
        args(
            tmp_path,
            data_type="FINRA_SHORT_SALE_VOLUME",
            bar_size="1_DAY",
            adjustment_policy="NOT_APPLICABLE",
        ),
        fetcher=lambda request, timeout: Response(payload),
    )
    assert manifest.result_state is AcquisitionResultState.SUCCESS
    assert manifest.record_count == 1
    assert manifest.earliest_record_time == manifest.latest_record_time


def test_chart_split_event_counts_as_corporate_action(tmp_path: Path) -> None:
    payload = json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "timestamp": [],
                        "events": {
                            "splits": {
                                "1783935000": {
                                    "date": 1783935000,
                                    "numerator": 1,
                                    "denominator": 10,
                                    "splitRatio": "1:10",
                                }
                            }
                        },
                    }
                ],
                "error": None,
            }
        }
    ).encode("utf-8")
    manifest = acquire(
        args(tmp_path, data_type="CORPORATE_ACTIONS", bar_size="NOT_APPLICABLE"),
        fetcher=lambda request, timeout: Response(payload),
    )
    assert manifest.result_state is AcquisitionResultState.SUCCESS
    assert manifest.record_count == 1
