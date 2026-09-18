"""Build historical RTH development datasets with dual-corpus authority."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...canonical import canonical_bytes, sha256_bytes
from ...paper.calibration.bar_ohlcv_prospective_proof import resolve_runtime_git_sha
from ...paper.calibration.dual_corpus import (
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    build_historical_development_dataset_manifest,
    build_historical_development_provenance,
    normalize_historical_development_bars,
    validate_historical_development_dataset_manifest,
)
from ...paper.calibration.dual_corpus.evidence_authority import (
    resolve_effective_corpus_evidence_authority,
)
from .artifacts import RunArtifactPaths, run_artifact_paths
from .instrument import resolve_us_equity_instrument_id, symbol_from_instrument_id
from .provider import HistoricalMarketDataProvider, ProviderFetchStatus
from .quality import build_quality_report, count_incomplete_final_bars
from .rth_session import (
    US_EQUITY_BAR_TZ,
    US_EQUITY_RTH_SESSION_POLICY,
    classify_us_equity_session_day,
    expected_rth_minute_keys,
    filter_raw_rows_rth,
    iter_us_equity_session_dates,
    ohlc_row_valid,
    parse_moomoo_time_key_local,
    sort_raw_rows_by_time_key,
)

BAR_RESOLUTION = "1_MINUTE"
TIMEZONE_POLICY = "America/New_York"
RAW_TIMESTAMP_SEMANTICS = "bar_start_local"
AVAILABILITY_SEMANTICS = "bar_end_available"
CORPORATE_ACTION_DEFAULT = "PROVIDER_QFQ_NOT_RECONCILED"


def _artifact_ref(path: Path, repository_root: Path) -> str:
    try:
        return str(path.relative_to(repository_root))
    except ValueError:
        return str(path)


@dataclass(frozen=True, slots=True)
class HistoricalDevelopmentBuildResult:
    ok: bool
    run_id: str
    paths: RunArtifactPaths
    manifest: dict[str, Any]
    quality: dict[str, Any]
    provider_status: ProviderFetchStatus
    normalized_fingerprint: str
    reason_code: str | None = None


def _dedupe_raw_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    dups = 0
    empty_time_keys = 0
    for row in rows:
        key = str(row.get("time_key") or "")
        if not key:
            empty_time_keys += 1
            continue
        if key in seen:
            dups += 1
            continue
        seen.add(key)
        kept.append(dict(row))
    kept.sort(key=lambda item: str(item.get("time_key") or ""))
    return kept, dups, empty_time_keys


def _interval_ns(start_date: str, end_date: str) -> tuple[int, int]:
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=US_EQUITY_BAR_TZ)
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=US_EQUITY_BAR_TZ
    )
    return int(start_dt.timestamp() * 1_000_000_000), int(end_dt.timestamp() * 1_000_000_000)


def build_historical_rth_dataset(
    *,
    repository_root: Path,
    provider: HistoricalMarketDataProvider,
    instrument: str,
    start_date: str,
    end_date: str,
    session_policy: str = US_EQUITY_RTH_SESSION_POLICY,
    dataset_id: str | None = None,
    dataset_version: str = "0.1.0",
    run_id: str | None = None,
    artifact_root: Path | None = None,
    holidays: frozenset[str] = frozenset(),
    early_closes: frozenset[str] = frozenset(),
    fixture_only: bool = False,
) -> HistoricalDevelopmentBuildResult:
    if session_policy != US_EQUITY_RTH_SESSION_POLICY:
        raise ValueError("SESSION_POLICY_UNSUPPORTED")
    instrument_id = resolve_us_equity_instrument_id(instrument)
    ticker = symbol_from_instrument_id(instrument_id)
    session_dates = iter_us_equity_session_dates(
        start_date,
        end_date,
        holidays=holidays,
        early_closes=early_closes,
    )
    resolved_run = run_id or f"hist-rth-{ticker}-{uuid.uuid4().hex[:10]}"
    paths = run_artifact_paths(repository_root, run_id=resolved_run, artifact_root=artifact_root)
    for directory in (
        paths.raw_dir,
        paths.normalized_dir,
        paths.manifests_dir,
        paths.quality_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    provider_status = provider.status()
    all_raw: list[dict[str, Any]] = []
    source_artifacts: list[dict[str, Any]] = []
    provider_gap_pages = 0
    fetch_errors: list[str] = []
    req_start_ns, req_end_ns = _interval_ns(start_date, end_date)
    code_sha = resolve_runtime_git_sha(start=repository_root)
    retrieval_ts = time.time_ns()

    for day in session_dates:
        pages = provider.fetch_session_day(instrument_id, day)
        day_rows: list[dict[str, Any]] = []
        for page in pages:
            if page.reason_code:
                fetch_errors.append(f"{day}:{page.reason_code}")
            if page.provider_gap:
                provider_gap_pages += 1
            day_rows.extend(page.raw_rows)
        raw_path = paths.raw_dir / f"{ticker}_{day}.json"
        raw_path.write_text(
            json.dumps(day_rows, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raw_sha = sha256_bytes(canonical_bytes({"rows": day_rows}))
        source_artifacts.append(
            {
                "session_date": day,
                "path": _artifact_ref(raw_path, repository_root),
                "sha256": raw_sha,
                "provider_response_identity": pages[-1].provider_response_identity if pages else f"empty:{day}",
            }
        )
        all_raw.extend(day_rows)
        if not fixture_only:
            time.sleep(0.05)

    rth_rows, outside_session = filter_raw_rows_rth(all_raw, early_closes=early_closes)
    deduped, duplicate_count, empty_time_key_count = _dedupe_raw_rows(rth_rows)
    malformed = empty_time_key_count + sum(
        1 for row in deduped if parse_moomoo_time_key_local(str(row.get("time_key") or "")) is None
    )
    invalid_ohlc_count = sum(1 for row in deduped if not ohlc_row_valid(row))
    excluded = outside_session + invalid_ohlc_count + malformed
    valid_rows = [
        row
        for row in deduped
        if parse_moomoo_time_key_local(str(row.get("time_key") or "")) is not None and ohlc_row_valid(row)
    ]
    valid_rows = sort_raw_rows_by_time_key(valid_rows)

    fetched_at_ns = req_end_ns + 86_400_000_000_000
    combined_raw_sha = sha256_bytes(canonical_bytes({"rows": valid_rows}))
    provenance = build_historical_development_provenance(
        provider_id=provider.provider_id,
        capability_id=provider.capability_id,
        instrument_id=instrument_id,
        request_params={
            "start_date": start_date,
            "end_date": end_date,
            "session_policy": session_policy,
            "bar_resolution": BAR_RESOLUTION,
            "ticker": ticker,
        },
        requested_interval_start_ns=req_start_ns,
        requested_interval_end_ns=req_end_ns,
        returned_interval_start_ns=req_start_ns,
        returned_interval_end_ns=req_end_ns,
        timezone_policy=TIMEZONE_POLICY,
        session_policy=session_policy,
        bar_resolution=BAR_RESOLUTION,
        raw_timestamp_semantics=RAW_TIMESTAMP_SEMANTICS,
        availability_semantics=AVAILABILITY_SEMANTICS,
        retrieval_timestamp_ns=retrieval_ts,
        provider_response_identity=source_artifacts[-1]["provider_response_identity"] if source_artifacts else "none",
        raw_payload_ref=_artifact_ref(paths.raw_dir, repository_root),
        raw_payload_sha256=combined_raw_sha,
        dataset_id=dataset_id or f"HIST-DEV-{ticker}",
        dataset_version=dataset_version,
        code_sha=code_sha,
        transformation_lineage=("provider_fetch", "rth_filter", "dedupe", "normalize_moomoo_kline_row"),
        inclusion_reason="historical_development_rth_build",
        exclusion_reason=None if not fetch_errors else ";".join(fetch_errors[:5]),
    )
    normalized_result = normalize_historical_development_bars(
        valid_rows,
        provenance=provenance,
        fetched_at_ns=fetched_at_ns,
    )
    if not normalized_result.get("ok"):
        return HistoricalDevelopmentBuildResult(
            ok=False,
            run_id=resolved_run,
            paths=paths,
            manifest={},
            quality={},
            provider_status=provider_status,
            normalized_fingerprint="",
            reason_code=str(normalized_result.get("reason_code")),
        )
    bars = tuple(normalized_result.get("bars") or ())
    normalized_path = paths.normalized_dir / f"{ticker}_normalized.json"
    normalized_path.write_text(
        json.dumps(list(bars), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    fingerprint = str(normalized_result.get("fingerprint") or "")
    missing_intervals: list[dict[str, Any]] = []
    for day in session_dates:
        expected_keys = set(expected_rth_minute_keys(day, early_closes=early_closes))
        present = set()
        for row in valid_rows:
            if not str(row.get("time_key") or "").startswith(day):
                continue
            parsed = parse_moomoo_time_key_local(str(row.get("time_key") or ""))
            if parsed is not None:
                present.add(parsed.strftime("%Y-%m-%d %H:%M:%S"))
        gap = sorted(expected_keys - present)
        if gap:
            missing_intervals.append(
                {
                    "session_date": day,
                    "session_kind": classify_us_equity_session_day(
                        day, holidays=holidays, early_closes=early_closes
                    ).value,
                    "missing_minute_count": len(gap),
                    "sample": gap[:3],
                }
            )

    manifest = build_historical_development_dataset_manifest(
        dataset_id=dataset_id or f"HIST-DEV-{ticker}",
        dataset_version=dataset_version,
        providers=[provider.provider_id],
        universe=[instrument_id],
        interval={
            "start_date": start_date,
            "end_date": end_date,
            "session_dates": list(session_dates),
        },
        session_policy=session_policy,
        bar_resolution=BAR_RESOLUTION,
        source_artifacts=source_artifacts,
        normalized_artifact_ref=_artifact_ref(normalized_path, repository_root),
        row_count=len(bars),
        duplicate_row_count=duplicate_count,
        excluded_row_count=excluded,
        missing_intervals=missing_intervals,
        lineage={"historical_provenance": provenance},
        code_sha=code_sha,
        created_at_ns=retrieval_ts,
    )
    manifest_gate = validate_historical_development_dataset_manifest(manifest)
    authority = resolve_effective_corpus_evidence_authority(manifest_authority=manifest["corpus_evidence_authority"])
    if not manifest_gate.get("ok") or authority.get("effective_authority") != CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT:
        return HistoricalDevelopmentBuildResult(
            ok=False,
            run_id=resolved_run,
            paths=paths,
            manifest=manifest,
            quality={},
            provider_status=provider_status,
            normalized_fingerprint=fingerprint,
            reason_code=str(manifest_gate.get("reason_code") or "AUTHORITY_INVALID"),
        )
    manifest_path = paths.manifests_dir / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    quality = build_quality_report(
        start_date=start_date,
        end_date=end_date,
        session_dates=session_dates,
        raw_rows=valid_rows,
        normalized_bars=bars,
        duplicate_row_count=duplicate_count,
        excluded_row_count=excluded,
        malformed_timestamp_count=malformed,
        outside_session_count=outside_session,
        incomplete_final_bar_count=count_incomplete_final_bars(
            session_dates,
            valid_rows,
            early_closes=early_closes,
        ),
        provider_gap_pages=provider_gap_pages,
        holidays=sorted(holidays),
        early_closes=sorted(early_closes),
        corporate_action_status=CORPORATE_ACTION_DEFAULT,
        volume_anomaly_count=0,
    )
    quality_path = paths.quality_dir / "quality_report.json"
    quality_path.write_text(json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ok = bool(bars) or fixture_only
    if fetch_errors and not fixture_only and not provider_status.verified:
        ok = bool(bars)
    return HistoricalDevelopmentBuildResult(
        ok=ok,
        run_id=resolved_run,
        paths=paths,
        manifest=manifest,
        quality=quality,
        provider_status=provider_status,
        normalized_fingerprint=fingerprint,
        reason_code=None if ok else (fetch_errors[0] if fetch_errors else "EMPTY_DATASET"),
    )


__all__ = ["HistoricalDevelopmentBuildResult", "build_historical_rth_dataset"]
