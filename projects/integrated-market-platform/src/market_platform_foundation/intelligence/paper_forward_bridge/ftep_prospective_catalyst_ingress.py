"""Opt-in Finviz Elite prospective catalyst ingress for FTEP watch (SIGNAL_ONLY, no writes)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ...news.config import default_pipeline_config
from ...news.contracts import PipelineConfig
from ...news.normalize import normalize_finviz_export_item
from ...news.pipeline import NewsPipeline
from ...news.poll_evidence import build_poll_rejection_summary
from ...news.sources import SourceTrustCatalog
from ...providers.adapters.finviz_elite_context import (
    configured_token,
    finviz_live_enabled,
    token_value_present,
)
from .activation import ActivationManifest, load_activation_manifest, manifest_universe_symbols

_INGRESS_ENV = "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS"
_SOURCE_LABEL = "live:finviz_elite_prospective"
_TRUTHY = frozenset({"1", "true", "yes"})

CLASS_NOT_ATTEMPTED = "NOT_ATTEMPTED"
CLASS_GATES_INACTIVE = "GATES_INACTIVE"
CLASS_TOKEN_ABSENT = "TOKEN_ABSENT"
CLASS_SECRET_DIR_MISSING = "SECRET_DIR_MISSING"
CLASS_HTTP_429 = "HTTP_429"
CLASS_PROVIDER_FAILURE = "PROVIDER_FAILURE"
CLASS_SUCCESS = "SUCCESS"
CLASS_SUCCESS_EMPTY = "SUCCESS_EMPTY"
CLASS_SESSION_UNAVAILABLE = "SESSION_UNAVAILABLE"
CLASS_TIMEOUT = "TIMEOUT"
CLASS_MALFORMED_RESPONSE = "MALFORMED_RESPONSE"

REASON_LIVE_INGRESS_NOT_REQUESTED = "LIVE_INGRESS_NOT_REQUESTED"
REASON_LIVE_INGRESS_UNAVAILABLE = "LIVE_INGRESS_UNAVAILABLE"
REASON_INGRESS_GATES_INACTIVE = "INGRESS_GATES_INACTIVE"
REASON_TOKEN_ABSENT = "FINVIZ_TOKEN_ABSENT"
REASON_SECRET_DIR_MISSING = "FINVIZ_SECRET_DIR_MISSING"
REASON_HTTP_429 = "FINVIZ_HTTP_429"
REASON_FETCH_FAILED = "FINVIZ_FETCH_FAILED"

SECRET_DIR_CONFIGURED = "CONFIGURED_SECRET_DIR"
SECRET_DIR_PRIMARY_PRIVATE = "PRIMARY_PRIVATE"
SECRET_DIR_REPOSITORY_PRIVATE = "REPOSITORY_PRIVATE"

TOKEN_SOURCE_ENVIRONMENT = "ENVIRONMENT"
TOKEN_SOURCE_SECRET_DIR = "SECRET_DIR"
TOKEN_SOURCE_NONE = "NONE"

_HTTP_429_MARKERS = frozenset({"HTTP_429", "HTTP 429", "TOO MANY REQUESTS", "RATE_LIMITED"})


def _env_mapping(env: Mapping[str, str] | None) -> Mapping[str, str]:
    if env is not None:
        return env
    return os.environ


def prospective_catalyst_ingress_gates_active(env: Mapping[str, str] | None = None) -> bool:
    """Env flags only: IMP_FINVIZ_LIVE and IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS."""

    mapping = _env_mapping(env)
    if not finviz_live_enabled(mapping):
        return False
    return str(mapping.get(_INGRESS_ENV, "")).strip().lower() in _TRUTHY


def _infer_classification(result: ProspectiveCatalystIngressResult) -> str:
    if result.classification:
        return result.classification
    if not result.attempted:
        return CLASS_NOT_ATTEMPTED
    if result.ready and result.rows:
        return CLASS_SUCCESS
    if result.ready:
        return CLASS_SUCCESS_EMPTY
    reason = result.reason or ""
    return {
        REASON_INGRESS_GATES_INACTIVE: CLASS_GATES_INACTIVE,
        REASON_TOKEN_ABSENT: CLASS_TOKEN_ABSENT,
        REASON_SECRET_DIR_MISSING: CLASS_SECRET_DIR_MISSING,
        REASON_HTTP_429: CLASS_HTTP_429,
        REASON_FETCH_FAILED: CLASS_PROVIDER_FAILURE,
        REASON_LIVE_INGRESS_NOT_REQUESTED: CLASS_NOT_ATTEMPTED,
        REASON_LIVE_INGRESS_UNAVAILABLE: CLASS_SESSION_UNAVAILABLE,
    }.get(reason, CLASS_PROVIDER_FAILURE)


def session_unavailable_ingress_report(
    *,
    rth_open: bool,
    governed_count: int,
    fixture_only: bool,
) -> dict[str, object]:
    """Structured receipt when --live-ingress is refused before provider fetch."""

    if fixture_only:
        detail = "FIXTURE_MODE"
    elif governed_count == 0:
        detail = "NO_GOVERNED_SESSION"
    elif not rth_open:
        detail = "RTH_CLOSED"
    else:
        detail = "SESSION_UNAVAILABLE"
    return {
        "attempted": False,
        "ready": False,
        "reason": REASON_LIVE_INGRESS_UNAVAILABLE,
        "classification": CLASS_SESSION_UNAVAILABLE,
        "source_label": "",
        "row_count": 0,
        "stats": {"session_blocker": detail},
        "fetch_error": detail,
        "retry_attempted": False,
        "retry_count": 0,
        "test_mode": "SIGNAL_ONLY",
        "durable_lock": False,
    }


@dataclass(frozen=True)
class FinvizIngressSecretDir:
    path: Path | None
    source: str
    present: bool


@dataclass(frozen=True)
class ProspectiveCatalystIngressResult:
    attempted: bool
    ready: bool
    reason: str | None
    source_label: str
    rows: tuple[dict[str, object], ...]
    stats: dict[str, object]
    fetch_error: str | None = None
    classification: str = ""
    secret_dir_source: str | None = None
    secret_dir_present: bool = False
    secret_dir_path: str | None = None
    token_source: str = TOKEN_SOURCE_NONE
    retry_attempted: bool = False
    retry_count: int = 0

    def to_report_dict(self) -> dict[str, object]:
        return {
            "attempted": self.attempted,
            "ready": self.ready,
            "reason": self.reason,
            "classification": _infer_classification(self),
            "source_label": self.source_label,
            "row_count": len(self.rows),
            "stats": self.stats,
            "fetch_error": self.fetch_error,
            "secret_dir_source": self.secret_dir_source,
            "secret_dir_present": self.secret_dir_present,
            "secret_dir_path": self.secret_dir_path,
            "token_source": self.token_source,
            "retry_attempted": self.retry_attempted,
            "retry_count": self.retry_count,
            "test_mode": "SIGNAL_ONLY",
            "durable_lock": False,
        }


def resolve_finviz_ingress_secret_dir(
    repository_root: Path,
    *,
    env: Mapping[str, str] | None = None,
    primary_root: Path | None = None,
) -> FinvizIngressSecretDir:
    """Prefer configured ``IMP_FINVIZ_SECRET_DIR``, else primary checkout ``.private``.

    Isolated env mappings never search leftover nested clones. Missing dirs fail
    closed with ``present=False`` instead of hopping to another tree.
    """

    mapping = _env_mapping(env)
    override = str(mapping.get("IMP_FINVIZ_SECRET_DIR") or "").strip()
    if override:
        path = Path(override).expanduser()
        try:
            path = path.resolve()
        except OSError:
            return FinvizIngressSecretDir(path=None, source=SECRET_DIR_CONFIGURED, present=False)
        try:
            present = path.is_dir()
        except OSError:
            present = False
        return FinvizIngressSecretDir(path=path, source=SECRET_DIR_CONFIGURED, present=present)

    preferred: Path | None = None
    source = SECRET_DIR_REPOSITORY_PRIVATE
    if env is None:
        resolved_primary = primary_root
        if resolved_primary is None:
            from .ftep_catalyst_watch import operator_primary_imp_root_for_evidence

            resolved_primary = operator_primary_imp_root_for_evidence(repository_root)
        if resolved_primary is not None:
            preferred = resolved_primary / ".private"
            source = SECRET_DIR_PRIMARY_PRIVATE
    if preferred is None:
        preferred = repository_root / ".private"
        source = SECRET_DIR_REPOSITORY_PRIVATE
    try:
        present = preferred.is_dir()
        path = preferred.resolve() if present or preferred.exists() else preferred
    except OSError:
        return FinvizIngressSecretDir(path=preferred, source=source, present=False)
    return FinvizIngressSecretDir(path=path, source=source, present=present)


def _token_from_secret_dir(secret_dir: Path) -> str | None:
    path = secret_dir / "finviz-token.txt"
    try:
        if not path.is_file():
            return None
        token = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return token if token_value_present(token) else None


def resolve_finviz_ingress_token(
    repository_root: Path,
    *,
    env: Mapping[str, str] | None = None,
    primary_root: Path | None = None,
) -> tuple[str | None, FinvizIngressSecretDir, str]:
    """Env token names first, then the resolved secret dir. Never leftover clones."""

    mapping = env if env is not None else os.environ
    secret = resolve_finviz_ingress_secret_dir(
        repository_root,
        env=env,
        primary_root=primary_root,
    )
    token = configured_token(mapping)
    if token_value_present(token):
        return str(token).strip(), secret, TOKEN_SOURCE_ENVIRONMENT
    if str(mapping.get("IMP_FINVIZ_SECRET_DIR") or "").strip() and not secret.present:
        return None, secret, TOKEN_SOURCE_NONE
    if env is None and not secret.present:
        return None, secret, TOKEN_SOURCE_NONE
    if secret.present and secret.path is not None:
        file_token = _token_from_secret_dir(secret.path)
        if token_value_present(file_token):
            return str(file_token).strip(), secret, TOKEN_SOURCE_SECRET_DIR
    return None, secret, TOKEN_SOURCE_NONE


def prospective_catalyst_ingress_enabled(
    env: Mapping[str, str] | None = None,
    *,
    repository_root: Path | None = None,
) -> bool:
    """Master gate: explicit opt-in + Finviz live + resolved token (fail closed)."""

    if not prospective_catalyst_ingress_gates_active(env):
        return False
    root = repository_root
    if root is None:
        from ...local_state.paths import REPO_ROOT as imp_root

        root = imp_root
    token, _, _ = resolve_finviz_ingress_token(root, env=env)
    return bool(token)


def pipeline_config_from_manifest(manifest: ActivationManifest) -> PipelineConfig:
    """Frozen manifest catalyst binding → governed pipeline config (no manifest mutation)."""

    binding = manifest.raw.get("catalyst_taxonomy_binding") or {}
    if not isinstance(binding, dict):
        binding = {}
    enabled_catalysts = frozenset(
        str(item) for item in (binding.get("enabled_catalyst_ids") or []) if item
    )
    registry_version = str(binding.get("registry_version") or "news/catalysts/1.0.0")
    base = default_pipeline_config()
    return PipelineConfig(
        recency_max_age_seconds=base.recency_max_age_seconds,
        recency_reject_future_seconds=base.recency_reject_future_seconds,
        recency_unknown_publication_policy=base.recency_unknown_publication_policy,
        require_catalyst_match=True,
        source_policy_version=base.source_policy_version,
        catalyst_registry_version=registry_version,
        filter_chain_version=base.filter_chain_version,
        enabled_source_ids=frozenset({"finviz_elite"}),
        enabled_catalyst_ids=enabled_catalysts or base.enabled_catalyst_ids,
    )


def _tier_for_event(event: Any, catalog: SourceTrustCatalog) -> int:
    entry = catalog.resolve_for_event(
        source_id=event.source_id,
        publisher_source=event.publisher_source,
    )
    if entry is None:
        return 3
    return int(entry.tier)


def _pipeline_result_to_attention_row(result: Any, *, tier: int) -> dict[str, object]:
    event = result.event
    symbol = ""
    if event.instrument_linkages:
        symbol = str(event.instrument_linkages[0].instrument_id or "").upper()
    catalyst_ids: tuple[str, ...] = ()
    for decision in result.decisions:
        if decision.matched_catalyst_ids:
            catalyst_ids = decision.matched_catalyst_ids
            break
    return {
        "attention_id": f"att-live-{event.event_id[:24]}",
        "symbol": symbol,
        "headline": event.headline,
        "tier": tier,
        "catalyst_ids": catalyst_ids,
        "attention_data_kind": "LIVE_PROSPECTIVE",
        "provider_id": event.provider_id,
        "source_id": event.source_id,
        "published_time": event.published_time,
        "retrieved_time": event.retrieved_time,
        "source_event_id": event.event_id,
    }


def _looks_like_http_429(*, status_code: int | None = None, text: str = "") -> bool:
    if status_code == 429:
        return True
    upper = str(text or "").upper()
    if "429" in upper:
        return True
    return any(marker in upper for marker in _HTTP_429_MARKERS)


def classify_finviz_fetch_exception(exc: BaseException) -> tuple[str, str]:
    """Classify provider exceptions without retrying. Never returns secret values."""

    current: BaseException | None = exc
    depth = 0
    messages: list[str] = []
    while current is not None and depth < 8:
        code = getattr(current, "code", None)
        if code is None:
            code = getattr(current, "status_code", None)
        try:
            code_int = int(code) if code is not None else None
        except (TypeError, ValueError):
            code_int = None
        message = str(current)
        messages.append(message)
        if _looks_like_http_429(status_code=code_int, text=message):
            return CLASS_HTTP_429, "HTTP_429"
        upper = message.upper()
        if "TIMEOUT" in upper or "TIMED OUT" in upper:
            return CLASS_TIMEOUT, "TIMEOUT"
        current = current.__cause__ or current.__context__
        depth += 1
    detail = messages[0] if messages else exc.__class__.__name__
    return CLASS_PROVIDER_FAILURE, detail


def _blocked(
    *,
    reason: str,
    classification: str,
    secret: FinvizIngressSecretDir,
    token_source: str = TOKEN_SOURCE_NONE,
    fetch_error: str | None = None,
    stats: dict[str, object] | None = None,
) -> ProspectiveCatalystIngressResult:
    path = str(secret.path) if secret.path is not None else None
    return ProspectiveCatalystIngressResult(
        attempted=True,
        ready=False,
        reason=reason,
        source_label="",
        rows=(),
        stats=stats or {},
        fetch_error=fetch_error,
        classification=classification,
        secret_dir_source=secret.source,
        secret_dir_present=secret.present,
        secret_dir_path=path,
        token_source=token_source,
        retry_attempted=False,
        retry_count=0,
    )


def collect_finviz_prospective_attention_rows(
    repository_root: Path,
    campaign_slug: str,
    *,
    live_ingress: bool,
    news_client: Any | None = None,
    as_of_ns: int | None = None,
    env: Mapping[str, str] | None = None,
    primary_root: Path | None = None,
) -> ProspectiveCatalystIngressResult:
    """Fetch Finviz news at ingest time, normalize, filter, map to attention rows.

    One-shot: HTTP 429 and provider failures return a structured result. This
    path does not retry.
    """

    empty_stats: dict[str, object] = {}
    secret = resolve_finviz_ingress_secret_dir(
        repository_root,
        env=env,
        primary_root=primary_root,
    )
    if not live_ingress:
        return ProspectiveCatalystIngressResult(
            attempted=False,
            ready=False,
            reason=REASON_LIVE_INGRESS_NOT_REQUESTED,
            source_label="",
            rows=(),
            stats=empty_stats,
            classification=CLASS_NOT_ATTEMPTED,
            secret_dir_source=secret.source,
            secret_dir_present=secret.present,
            secret_dir_path=str(secret.path) if secret.path is not None else None,
        )
    if not prospective_catalyst_ingress_gates_active(env):
        return _blocked(
            reason=REASON_INGRESS_GATES_INACTIVE,
            classification=CLASS_GATES_INACTIVE,
            secret=secret,
        )

    token, secret, token_source = resolve_finviz_ingress_token(
        repository_root,
        env=env,
        primary_root=primary_root,
    )
    override = str(_env_mapping(env).get("IMP_FINVIZ_SECRET_DIR") or "").strip()
    if not token and override and not secret.present:
        return _blocked(
            reason=REASON_SECRET_DIR_MISSING,
            classification=CLASS_SECRET_DIR_MISSING,
            secret=secret,
            token_source=token_source,
        )
    if not token and env is None and not secret.present:
        return _blocked(
            reason=REASON_SECRET_DIR_MISSING,
            classification=CLASS_SECRET_DIR_MISSING,
            secret=secret,
            token_source=token_source,
        )
    if not token:
        return _blocked(
            reason=REASON_TOKEN_ABSENT,
            classification=CLASS_TOKEN_ABSENT,
            secret=secret,
            token_source=token_source,
        )

    manifest = load_activation_manifest(campaign_slug)
    universe = frozenset(manifest_universe_symbols(manifest))
    pipeline_config = pipeline_config_from_manifest(manifest)
    catalog = SourceTrustCatalog()
    pipeline = NewsPipeline()
    as_of = as_of_ns if as_of_ns is not None else time.time_ns()

    if news_client is None:
        from ...finviz.news import FinvizNewsClient

        news_client = FinvizNewsClient(api_key=token)

    try:
        fetch = news_client.fetch_news(force=True)
    except Exception as exc:
        classification, detail = classify_finviz_fetch_exception(exc)
        reason = REASON_HTTP_429 if classification == CLASS_HTTP_429 else REASON_FETCH_FAILED
        return _blocked(
            reason=reason,
            classification=classification,
            secret=secret,
            token_source=token_source,
            fetch_error=detail,
        )

    if not isinstance(fetch, dict):
        return _blocked(
            reason=REASON_FETCH_FAILED,
            classification=CLASS_MALFORMED_RESPONSE,
            secret=secret,
            token_source=token_source,
            fetch_error="MALFORMED_FETCH_PAYLOAD",
        )

    if not fetch.get("success"):
        error = str(fetch.get("error") or "UNKNOWN")
        status_raw = fetch.get("status_code")
        try:
            status_code = int(status_raw) if status_raw is not None else None
        except (TypeError, ValueError):
            status_code = None
        if _looks_like_http_429(status_code=status_code, text=error):
            return _blocked(
                reason=REASON_HTTP_429,
                classification=CLASS_HTTP_429,
                secret=secret,
                token_source=token_source,
                fetch_error="HTTP_429",
            )
        upper = error.upper()
        if "MALFORMED" in upper or "PARSE" in upper or "INVALID JSON" in upper:
            return _blocked(
                reason=REASON_FETCH_FAILED,
                classification=CLASS_MALFORMED_RESPONSE,
                secret=secret,
                token_source=token_source,
                fetch_error=error,
            )
        if "TIMEOUT" in upper or "TIMED OUT" in upper:
            return _blocked(
                reason=REASON_FETCH_FAILED,
                classification=CLASS_TIMEOUT,
                secret=secret,
                token_source=token_source,
                fetch_error=error,
            )
        return _blocked(
            reason=REASON_FETCH_FAILED,
            classification=CLASS_PROVIDER_FAILURE,
            secret=secret,
            token_source=token_source,
            fetch_error=error,
        )

    received_at = str(fetch.get("received_at") or "")
    items = [item for item in (fetch.get("items") or []) if isinstance(item, dict)]
    events = [
        normalize_finviz_export_item(item, retrieved_time=received_at) for item in items
    ]
    results = pipeline.process(events, as_of_ns=as_of, config=pipeline_config)
    rows: list[dict[str, object]] = []
    ingested = len(events)
    accepted = 0
    universe_filtered = 0
    for result in results:
        if not result.accepted:
            continue
        row = _pipeline_result_to_attention_row(
            result,
            tier=_tier_for_event(result.event, catalog),
        )
        symbol = str(row.get("symbol") or "")
        if universe and symbol not in universe:
            universe_filtered += 1
            continue
        if not symbol:
            continue
        accepted += 1
        rows.append(row)

    # Bounded diagnostic only — does not change qualification criteria.
    rejection_summary = build_poll_rejection_summary(
        fetched_count=len(items),
        events=events,
        results=results,
        universe=universe,
    )
    stats = {
        "as_of_ns": as_of,
        "ingested_events": ingested,
        "accepted_pipeline_events": accepted,
        "universe_filtered": universe_filtered,
        "manifest_universe_size": len(universe),
        "pipeline_config": pipeline_config.to_dict(),
        "rejection_summary": rejection_summary.to_dict(),
    }
    classification = CLASS_SUCCESS if rows else CLASS_SUCCESS_EMPTY
    return ProspectiveCatalystIngressResult(
        attempted=True,
        ready=True,
        reason=None,
        source_label=_SOURCE_LABEL,
        rows=tuple(rows),
        stats=stats,
        classification=classification,
        secret_dir_source=secret.source,
        secret_dir_present=secret.present,
        secret_dir_path=str(secret.path) if secret.path is not None else None,
        token_source=token_source,
        retry_attempted=False,
        retry_count=0,
    )


__all__ = [
    "CLASS_GATES_INACTIVE",
    "CLASS_HTTP_429",
    "CLASS_NOT_ATTEMPTED",
    "CLASS_PROVIDER_FAILURE",
    "CLASS_SECRET_DIR_MISSING",
    "CLASS_SUCCESS",
    "CLASS_SUCCESS_EMPTY",
    "CLASS_SESSION_UNAVAILABLE",
    "CLASS_TIMEOUT",
    "CLASS_MALFORMED_RESPONSE",
    "CLASS_TOKEN_ABSENT",
    "FinvizIngressSecretDir",
    "ProspectiveCatalystIngressResult",
    "classify_finviz_fetch_exception",
    "collect_finviz_prospective_attention_rows",
    "pipeline_config_from_manifest",
    "prospective_catalyst_ingress_enabled",
    "prospective_catalyst_ingress_gates_active",
    "resolve_finviz_ingress_secret_dir",
    "resolve_finviz_ingress_token",
    "session_unavailable_ingress_report",
]
