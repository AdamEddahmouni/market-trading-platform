"""Acquire one explicit BIYA historical dataset and preserve its manifest.

Provider authentication is deliberately absent. Authenticated providers that cannot be
used without touching archived credential state are recorded as explicit failed
attempts. Public HTTP retrieval accepts only a caller-supplied URL and never stores or
prints that URL.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from squeeze_core.serialization import canonical_json_bytes
from squeeze_core.validation.outcome_acquisition import (
    AcquisitionDataType,
    AcquisitionEntitlementState,
    AcquisitionResultState,
    build_acquisition_manifest,
    serialize_acquisition_manifest,
)


Fetcher = Callable[[Request, int], Any]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acquire-biya-history")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--data-type", choices=tuple(item.value for item in AcquisitionDataType), required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument("--timezone", required=True)
    parser.add_argument("--session-scope", required=True)
    parser.add_argument("--bar-size", required=True)
    parser.add_argument("--adjustment-policy", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-url", default="")
    parser.add_argument("--request-parameter", action="append", default=[])
    parser.add_argument("--result-state", choices=tuple(item.value for item in AcquisitionResultState))
    parser.add_argument("--failure-code")
    parser.add_argument("--entitlement-state", choices=tuple(item.value for item in AcquisitionEntitlementState), default="UNKNOWN")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    return parser


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware ISO-8601 values")
    return parsed.astimezone(UTC)


def _parameters(values: Sequence[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in values:
        if "=" not in item:
            raise ValueError("--request-parameter must use KEY=VALUE")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("request parameter key is required")
        lowered = value.strip().lower()
        result[key] = True if lowered == "true" else False if lowered == "false" else value.strip()
    return result


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _inspect_payload(
    payload: bytes,
    data_type: AcquisitionDataType,
    symbol: str,
) -> tuple[int, datetime | None, datetime | None]:
    if data_type is AcquisitionDataType.FINRA_SHORT_SALE_VOLUME:
        lines = payload.decode("utf-8-sig").splitlines()
        rows = [line.split("|") for line in lines[1:] if line.strip()]
        matching = [row for row in rows if len(row) >= 2 and row[1].strip().upper() == symbol]
        moments = [
            datetime.strptime(row[0].strip(), "%Y%m%d").replace(tzinfo=UTC)
            for row in matching
        ]
        return len(matching), min(moments, default=None), max(moments, default=None)

    if data_type is AcquisitionDataType.PUBLISHED_SHORT_INTEREST:
        import csv
        import io

        lines = payload.decode("utf-8-sig").splitlines()
        if not lines:
            return 0, None, None
        delimiter = "|" if "|" in lines[0] else ","
        reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
        settlements: list[datetime] = []
        for row in reader:
            row_symbol = (
                row.get("Symbol")
                or row.get("symbol")
                or row.get("SYMBOL")
                or ""
            ).strip().upper()
            if row_symbol != symbol:
                continue
            settlement = (
                row.get("Settlement Date")
                or row.get("settlement_date")
                or row.get("SettlementDate")
                or ""
            ).strip()
            if not settlement:
                continue
            settlements.append(datetime.strptime(settlement, "%Y-%m-%d").replace(tzinfo=UTC))
        return len(settlements), min(settlements, default=None), max(settlements, default=None)

    document = json.loads(payload)
    timestamps: list[datetime] = []
    count = 0
    if isinstance(document, list):
        count = len(document)
        for row in document:
            if isinstance(row, dict):
                raw = row.get("timestamp") or row.get("date") or row.get("published_at")
                if isinstance(raw, str):
                    timestamps.append(_time(raw))
    elif isinstance(document, dict):
        if data_type is AcquisitionDataType.NEWS and isinstance(document.get("news"), list):
            news = document["news"]
            count = len(news)
            timestamps.extend(
                datetime.fromtimestamp(int(row["providerPublishTime"]), tz=UTC)
                for row in news
                if isinstance(row, dict) and row.get("providerPublishTime") is not None
            )
            return count, min(timestamps, default=None), max(timestamps, default=None)
        chart = document.get("chart")
        results = chart.get("result") if isinstance(chart, dict) else None
        if isinstance(results, list) and results:
            first_result = results[0] if isinstance(results[0], dict) else {}
            if data_type is AcquisitionDataType.CORPORATE_ACTIONS:
                events = first_result.get("events")
                splits = events.get("splits") if isinstance(events, dict) else None
                records = list(splits.values()) if isinstance(splits, dict) else []
                timestamps.extend(
                    datetime.fromtimestamp(int(row["date"]), tz=UTC)
                    for row in records
                    if isinstance(row, dict) and row.get("date") is not None
                )
                return len(records), min(timestamps, default=None), max(timestamps, default=None)
            raw_times = first_result.get("timestamp")
            if isinstance(raw_times, list):
                count = len(raw_times)
                timestamps.extend(
                    datetime.fromtimestamp(int(raw), tz=UTC)
                    for raw in raw_times
                    if raw is not None
                )
        elif isinstance(document.get("records"), list):
            records = document["records"]
            count = len(records)
            for row in records:
                if isinstance(row, dict):
                    raw = row.get("timestamp") or row.get("date") or row.get("published_at")
                    if isinstance(raw, str):
                        timestamps.append(_time(raw))
    return count, min(timestamps, default=None), max(timestamps, default=None)


def _raw_relative_path(args: argparse.Namespace, retrieved_at: datetime) -> Path:
    data_folder = args.data_type.lower()
    name = "_".join(
        (
            args.symbol.strip().upper(),
            args.provider.strip().lower().replace("_", "-"),
            data_folder,
            _stamp(_time(args.start)),
            _stamp(_time(args.end)),
            _stamp(retrieved_at),
        )
    ) + ".json"
    return Path("raw") / data_folder / name


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)


def acquire(argv: Sequence[str], *, fetcher: Fetcher | None = None):
    args = _parser().parse_args(argv)
    start = _time(args.start)
    end = _time(args.end)
    retrieved_at = _time(args.retrieved_at)
    request_parameters = _parameters(args.request_parameter)
    entitlement = AcquisitionEntitlementState(args.entitlement_state)
    output = args.output.resolve()

    raw_bytes: bytes | None = None
    raw_relative: Path | None = None
    count = 0
    earliest = latest = None
    errors: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    if not args.source_url:
        if args.result_state is None:
            raise ValueError("--source-url or an explicit --result-state is required")
        state = AcquisitionResultState(args.result_state)
        errors = (args.failure_code or f"ACQUISITION_{state.value}",)
        limitations = ("provider access was unavailable under the preserved local configuration",)
    else:
        request = Request(args.source_url, headers={"User-Agent": "short-squeeze-core-phase2v/1.0"})
        try:
            opener = fetcher or (lambda req, timeout: urlopen(req, timeout=timeout))
            with opener(request, args.timeout_seconds) as response:
                raw_bytes = response.read()
            raw_relative = _raw_relative_path(args, retrieved_at)
            try:
                count, earliest, latest = _inspect_payload(
                    raw_bytes,
                    AcquisitionDataType(args.data_type),
                    args.symbol.strip().upper(),
                )
                state = AcquisitionResultState.SUCCESS if count else AcquisitionResultState.EMPTY
            except (json.JSONDecodeError, TypeError, ValueError, OverflowError):
                state = AcquisitionResultState.INVALID_RESPONSE
                errors = ("ACQUISITION_INVALID_RESPONSE",)
                limitations = ("provider response could not be parsed as the requested dataset",)
        except HTTPError as error:
            state = (
                AcquisitionResultState.RATE_LIMITED
                if error.code == 429
                else AcquisitionResultState.ENTITLEMENT_REQUIRED
                if error.code in {401, 403}
                else AcquisitionResultState.NETWORK_FAILURE
            )
            errors = (f"ACQUISITION_HTTP_{error.code}",)
        except (URLError, TimeoutError, OSError):
            state = AcquisitionResultState.NETWORK_FAILURE
            errors = ("ACQUISITION_NETWORK_FAILURE",)

    manifest = build_acquisition_manifest(
        symbol=args.symbol,
        provider=args.provider,
        data_type=AcquisitionDataType(args.data_type),
        requested_start=start,
        requested_end=end,
        retrieved_at=retrieved_at,
        request_timezone=args.timezone,
        response_timezone=args.timezone if raw_bytes is not None else None,
        bar_size=args.bar_size,
        session_scope=args.session_scope,
        adjustment_policy=args.adjustment_policy,
        request_parameters=request_parameters,
        result_state=state,
        raw_relative_path=None if raw_relative is None else raw_relative.as_posix(),
        raw_bytes=raw_bytes,
        record_count=count,
        earliest_record_time=earliest,
        latest_record_time=latest,
        entitlement_state=entitlement,
        errors=errors,
        limitations=limitations,
    )

    if raw_bytes is not None and raw_relative is not None:
        _write_new(output / raw_relative, raw_bytes)
    _write_new(
        output / "manifests" / f"{manifest.acquisition_id}.json",
        serialize_acquisition_manifest(manifest) + b"\n",
    )
    return manifest


def main(argv: Sequence[str] | None = None, *, fetcher: Fetcher | None = None) -> int:
    try:
        manifest = acquire(sys.argv[1:] if argv is None else argv, fetcher=fetcher)
        public_result = {
            "command": "acquire-biya-history",
            "acquisition_id": manifest.acquisition_id,
            "provider": manifest.provider,
            "data_type": manifest.data_type,
            "result_state": manifest.result_state,
            "record_count": manifest.record_count,
            "raw_sha256": manifest.raw_sha256,
            "valid": manifest.result_state in {
                AcquisitionResultState.SUCCESS,
                AcquisitionResultState.PARTIAL,
                AcquisitionResultState.EMPTY,
            },
        }
        target = sys.stdout if public_result["valid"] else sys.stderr
        print(canonical_json_bytes(public_result).decode("utf-8"), file=target)
        return 0 if public_result["valid"] else 1
    except Exception as error:
        output = {
            "command": "acquire-biya-history",
            "error": str(error),
            "valid": False,
        }
        print(canonical_json_bytes(output).decode("utf-8"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
