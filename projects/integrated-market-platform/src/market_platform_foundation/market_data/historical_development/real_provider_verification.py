"""Bounded real-provider verification for HISTORICAL_DEVELOPMENT (Lane IMP-04-B)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Mapping, Sequence

from ...canonical import canonical_bytes, sha256_bytes
from .builder import HistoricalDevelopmentBuildResult, build_historical_rth_dataset
from .provider import HistoricalMarketDataProvider, MoomooOpendHistoricalMarketDataProvider
from .rth_session import UsEquitySessionDayKind, classify_us_equity_session_day


DEFAULT_SESSION_COUNT = 5
DEFAULT_INSTRUMENTS = ("AAPL",)
OPTIONAL_EXPANSION_INSTRUMENTS = ("AAPL", "MSFT", "SPY")


def _stable_raw_source_fingerprint(manifest: Mapping[str, Any]) -> str:
    shas = sorted(
        str(item.get("sha256") or "")
        for item in manifest.get("source_artifacts") or ()
        if isinstance(item, Mapping) and item.get("sha256")
    )
    return sha256_bytes(canonical_bytes({"source_artifact_sha256": shas}))


def last_n_us_equity_rth_session_dates(
    count: int,
    *,
    end_before: date,
    holidays: frozenset[str] = frozenset(),
    early_closes: frozenset[str] = frozenset(),
    session_kinds: frozenset[UsEquitySessionDayKind] = frozenset({UsEquitySessionDayKind.REGULAR}),
) -> tuple[str, ...]:
    """Walk backward from ``end_before`` (exclusive) for ``count`` matching session dates."""

    if count < 1:
        raise ValueError("SESSION_COUNT_INVALID")
    found: list[str] = []
    day = end_before - timedelta(days=1)
    guard = 0
    while len(found) < count and guard < 366:
        guard += 1
        iso = day.isoformat()
        kind = classify_us_equity_session_day(iso, holidays=holidays, early_closes=early_closes)
        if kind in session_kinds:
            found.append(iso)
        day -= timedelta(days=1)
    if len(found) < count:
        raise ValueError("INSUFFICIENT_SESSION_HISTORY")
    return tuple(reversed(found))


def _session_rows_from_quality(
    quality: Mapping[str, Any],
    session_date: str,
) -> dict[str, Any] | None:
    for item in quality.get("session_summaries") or ():
        if isinstance(item, Mapping) and str(item.get("session_date")) == session_date:
            return dict(item)
    return None


def _session_exclusion_reason(
    session_date: str,
    quality: Mapping[str, Any],
) -> str | None:
    summary = _session_rows_from_quality(quality, session_date)
    if summary is None:
        return "SESSION_SUMMARY_MISSING"
    expected = int(summary.get("expected_minute_count") or 0)
    observed = int(summary.get("observed_minute_count") or 0)
    if expected <= 0:
        return "SESSION_EXPECTED_MINUTES_ZERO"
    if observed == 0:
        return "SESSION_NO_OBSERVED_MINUTES"
    missing_for_day = 0
    for item in quality.get("missing_intervals") or ():
        if isinstance(item, Mapping) and str(item.get("session_date")) == session_date:
            missing_for_day = int(item.get("missing_minute_count") or 0)
            break
    if missing_for_day > 0 and observed < expected // 2:
        return f"SESSION_SHORT:{missing_for_day}_MISSING_MINUTES"
    return None


@dataclass(frozen=True, slots=True)
class MoomooRealHistoricalVerification:
    status: str
    instruments: tuple[str, ...]
    session_dates: tuple[str, ...]
    row_count: int
    fingerprint: str
    quality_status: str
    limitations: tuple[str, ...]
    provider_reason: str | None
    run_id: str | None
    artifact_root: str | None
    dataset_fingerprint: str | None
    normalized_fingerprint: str | None
    quality_fingerprint: str | None
    rerun_fingerprint_match: bool | None
    excluded_sessions: tuple[dict[str, str], ...]

    def as_report_fields(self) -> dict[str, Any]:
        return {
            "MOOMOO_REAL_HISTORICAL": self.status,
            "INSTRUMENTS": list(self.instruments),
            "DATES": list(self.session_dates),
            "ROWS": self.row_count,
            "FINGERPRINT": self.fingerprint,
            "QUALITY": self.quality_status,
            "LIMITATIONS": list(self.limitations),
            "provider_reason": self.provider_reason,
            "run_id": self.run_id,
            "artifact_root": self.artifact_root,
            "dataset_fingerprint": self.dataset_fingerprint,
            "normalized_fingerprint": self.normalized_fingerprint,
            "quality_fingerprint": self.quality_fingerprint,
            "rerun_fingerprint_match": self.rerun_fingerprint_match,
            "excluded_sessions": list(self.excluded_sessions),
        }


def verify_moomoo_real_historical(
    *,
    repository_root,
    artifact_root,
    instruments: Sequence[str] = DEFAULT_INSTRUMENTS,
    session_count: int = DEFAULT_SESSION_COUNT,
    end_before: date | None = None,
    holidays: frozenset[str] = frozenset(),
    early_closes: frozenset[str] = frozenset(),
    provider: HistoricalMarketDataProvider | None = None,
    perform_rerun_check: bool = True,
) -> MoomooRealHistoricalVerification:
    """Fetch a bounded real OpenD corpus or fail closed with PROVIDER_UNVERIFIED."""

    from pathlib import Path

    root = Path(repository_root)
    resolved_provider = provider or MoomooOpendHistoricalMarketDataProvider(repository_root=root)
    gate = resolved_provider.status()
    if not gate.verified:
        return MoomooRealHistoricalVerification(
            status="PROVIDER_UNVERIFIED",
            instruments=tuple(instruments),
            session_dates=(),
            row_count=0,
            fingerprint="",
            quality_status="UNAVAILABLE",
            limitations=(str(gate.reason_code or "PROVIDER_UNVERIFIED"),),
            provider_reason=gate.reason_code,
            run_id=None,
            artifact_root=str(artifact_root),
            dataset_fingerprint=None,
            normalized_fingerprint=None,
            quality_fingerprint=None,
            rerun_fingerprint_match=None,
            excluded_sessions=(),
        )

    anchor = end_before or date.today()
    try:
        session_dates = last_n_us_equity_rth_session_dates(
            session_count,
            end_before=anchor,
            holidays=holidays,
            early_closes=early_closes,
        )
    except ValueError as exc:
        return MoomooRealHistoricalVerification(
            status="PROVIDER_UNVERIFIED",
            instruments=tuple(instruments),
            session_dates=(),
            row_count=0,
            fingerprint="",
            quality_status="UNAVAILABLE",
            limitations=(str(exc),),
            provider_reason=f"SESSION_SELECTION_FAILED:{exc}",
            run_id=None,
            artifact_root=str(artifact_root),
            dataset_fingerprint=None,
            normalized_fingerprint=None,
            quality_fingerprint=None,
            rerun_fingerprint_match=None,
            excluded_sessions=(),
        )

    start_date, end_date = session_dates[0], session_dates[-1]
    limitations: list[str] = []
    excluded: list[dict[str, str]] = []
    total_rows = 0
    primary: HistoricalDevelopmentBuildResult | None = None
    instrument_list = tuple(str(i).upper() for i in instruments)

    for ticker in instrument_list:
        result = build_historical_rth_dataset(
            repository_root=root,
            provider=resolved_provider,
            instrument=ticker,
            start_date=start_date,
            end_date=end_date,
            artifact_root=Path(artifact_root),
            holidays=holidays,
            early_closes=early_closes,
            fixture_only=False,
        )
        if primary is None:
            primary = result
        if not result.ok or not result.manifest:
            reason = result.reason_code or "BUILD_FAILED"
            return MoomooRealHistoricalVerification(
                status="PROVIDER_UNVERIFIED",
                instruments=instrument_list,
                session_dates=session_dates,
                row_count=total_rows,
                fingerprint=result.normalized_fingerprint or "",
                quality_status=str(result.quality.get("quality_status") or "UNAVAILABLE"),
                limitations=(reason,),
                provider_reason=reason,
                run_id=result.run_id,
                artifact_root=str(artifact_root),
                dataset_fingerprint=str(result.manifest.get("dataset_fingerprint") or "") or None,
                normalized_fingerprint=result.normalized_fingerprint or None,
                quality_fingerprint=str(result.quality.get("quality_fingerprint") or "") or None,
                rerun_fingerprint_match=None,
                excluded_sessions=tuple(excluded),
            )
        for day in session_dates:
            exclusion = _session_exclusion_reason(day, result.quality)
            if exclusion:
                excluded.append({"session_date": day, "reason": exclusion, "instrument": ticker})
        total_rows += int(result.manifest.get("row_count") or 0)
        q_status = str(result.quality.get("quality_status") or "")
        if q_status == "FAIL":
            return MoomooRealHistoricalVerification(
                status="PROVIDER_UNVERIFIED",
                instruments=instrument_list,
                session_dates=session_dates,
                row_count=total_rows,
                fingerprint=result.normalized_fingerprint,
                quality_status=q_status,
                limitations=("QUALITY_FAIL",),
                provider_reason="QUALITY_FAIL",
                run_id=result.run_id,
                artifact_root=str(artifact_root),
                dataset_fingerprint=str(result.manifest.get("dataset_fingerprint") or ""),
                normalized_fingerprint=result.normalized_fingerprint,
                quality_fingerprint=str(result.quality.get("quality_fingerprint") or ""),
                rerun_fingerprint_match=None,
                excluded_sessions=tuple(excluded),
            )
        if q_status == "WARN":
            limitations.append(f"{ticker}:QUALITY_WARN")

    assert primary is not None
    rerun_match: bool | None = None
    if perform_rerun_check and len(instrument_list) == 1:
        rerun = build_historical_rth_dataset(
            repository_root=root,
            provider=resolved_provider,
            instrument=instrument_list[0],
            start_date=start_date,
            end_date=end_date,
            artifact_root=Path(artifact_root) / "rerun",
            holidays=holidays,
            early_closes=early_closes,
            fixture_only=False,
        )
        rerun_match = bool(rerun.ok) and _stable_raw_source_fingerprint(rerun.manifest) == _stable_raw_source_fingerprint(
            primary.manifest
        )
        if not rerun_match:
            limitations.append("RERUN_FINGERPRINT_MISMATCH")

    if excluded:
        limitations.append(f"EXCLUDED_SESSIONS:{len(excluded)}")

    fingerprint = primary.normalized_fingerprint or str(primary.manifest.get("dataset_fingerprint") or "")
    return MoomooRealHistoricalVerification(
        status="VERIFIED_BOUNDED",
        instruments=instrument_list,
        session_dates=session_dates,
        row_count=total_rows,
        fingerprint=fingerprint,
        quality_status=str(primary.quality.get("quality_status") or "PASS"),
        limitations=tuple(limitations),
        provider_reason=None,
        run_id=primary.run_id,
        artifact_root=str(artifact_root),
        dataset_fingerprint=str(primary.manifest.get("dataset_fingerprint") or ""),
        normalized_fingerprint=primary.normalized_fingerprint,
        quality_fingerprint=str(primary.quality.get("quality_fingerprint") or ""),
        rerun_fingerprint_match=rerun_match,
        excluded_sessions=tuple(excluded),
    )


@dataclass(frozen=True, slots=True)
class IbkrHistoricalTradesVerification:
    status: str
    interval: dict[str, Any] | None
    trade_count: int
    pagination: dict[str, Any] | None
    complete: bool | None
    limitations: tuple[str, ...]
    reason: str | None

    def as_report_fields(self) -> dict[str, Any]:
        return {
            "IBKR_HISTORICAL_TRADES": self.status,
            "INTERVAL": self.interval,
            "TRADE_COUNT": self.trade_count,
            "PAGINATION": self.pagination,
            "COMPLETENESS": self.complete,
            "LIMITATIONS": list(self.limitations),
            "reason": self.reason,
        }


def probe_ibkr_tws_loopback(
    *,
    host: str = "127.0.0.1",
    port: int = 4001,
    timeout: float = 1.0,
) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def evaluate_ibkr_historical_trades_gate(
    *,
    live_enabled: bool,
    transport: str,
    tws_reachable: bool,
) -> IbkrHistoricalTradesVerification:
    if not live_enabled:
        return IbkrHistoricalTradesVerification(
            status="PROVIDER_UNVERIFIED",
            interval=None,
            trade_count=0,
            pagination=None,
            complete=None,
            limitations=("IMP_IBKR_LIVE_NOT_ENABLED",),
            reason="IMP_IBKR_LIVE_NOT_ENABLED",
        )
    if transport != "tws" or not tws_reachable:
        return IbkrHistoricalTradesVerification(
            status="PROVIDER_UNVERIFIED",
            interval=None,
            trade_count=0,
            pagination=None,
            complete=None,
            limitations=("TWS_LOOPBACK_UNAVAILABLE",),
            reason="TWS_LOOPBACK_UNAVAILABLE",
        )
    return IbkrHistoricalTradesVerification(
        status="PENDING_OPERATOR_FETCH",
        interval=None,
        trade_count=0,
        pagination=None,
        complete=None,
        limitations=("USE_verify_historical_trades_provider_CLI",),
        reason=None,
    )


def build_verification_receipt(
    *,
    increment_id: str,
    moomoo: MoomooRealHistoricalVerification,
    ibkr: IbkrHistoricalTradesVerification,
    code_sha: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "artifact_kind": "imp_research_validation_04_lane_b_real_provider_verification_v1",
        "increment_id": increment_id,
        "evidence_class": "HISTORICAL_DEVELOPMENT",
        "prospective_item9_admission": "NOT_ALLOWED",
        "moomoo": moomoo.as_report_fields(),
        "ibkr": ibkr.as_report_fields(),
        "code_sha": code_sha,
    }
    body["receipt_sha256"] = sha256_bytes(canonical_bytes({k: v for k, v in body.items() if k != "receipt_sha256"}))
    return body


__all__ = [
    "DEFAULT_INSTRUMENTS",
    "DEFAULT_SESSION_COUNT",
    "OPTIONAL_EXPANSION_INSTRUMENTS",
    "IbkrHistoricalTradesVerification",
    "MoomooRealHistoricalVerification",
    "build_verification_receipt",
    "evaluate_ibkr_historical_trades_gate",
    "last_n_us_equity_rth_session_dates",
    "probe_ibkr_tws_loopback",
    "verify_moomoo_real_historical",
]
