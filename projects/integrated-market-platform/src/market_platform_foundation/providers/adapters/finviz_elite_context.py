"""Finviz Elite screening/news context overlay. Not L1 and not a comparator."""

from __future__ import annotations

from typing import Any, Callable, Mapping, MutableMapping

from ...clock import monotonic_wall_ns
from ...finviz.provider_role import EXECUTION_ROLE
from ...finviz.redaction import redact_payload
from ..contracts import ProviderResult

FINVIZ_CONTEXT_PROVIDER_ID = "finviz.elite.context"
FINVIZ_CONTEXT_CAPABILITY = "equity_context"
FINVIZ_CONTEXT_ROLE = "CONTEXT"
FINVIZ_CONTEXT_TIMELINESS = "DELAYED"
FINVIZ_NORMALIZATION_VERSION = "finviz.elite.context/1.0.0"

FINVIZ_TOKEN_NAMES = (
    "FINVIZ_API_KEY",
    "FINVIZ_AUTH_TOKEN",
    "FINVIZ_API_TOKEN",
    "FINVIZ_ELITE_TOKEN",
    "IMP_FINVIZ_ELITE_TOKEN",
    "IMP_FINVIZ_TOKEN",
)

FINVIZ_LOGIN_NAMES = (
    "FINVIZ_USERNAME",
    "FINVIZ_PASSWORD",
)

_PLACEHOLDERS = frozenset({"", "CHANGEME", "EXAMPLE", "PLACEHOLDER", "NOT_A_SECRET"})
_ES_OR_FUTURES = frozenset({"ES", "MES", "NQ", "MNQ", "YM", "RTY", "CL", "GC", "SI"})
_LIVE_TRUTHY = frozenset({"1", "true", "yes"})

ClientFactory = Callable[[str], tuple[Any, Any]]


def _env_mapping(env: Mapping[str, str] | None) -> Mapping[str, str]:
    if env is not None:
        return env
    import os

    return os.environ


def token_value_present(value: str | None) -> bool:
    return str(value or "").strip().upper() not in _PLACEHOLDERS


def token_names_present(env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    mapping = _env_mapping(env)
    present: list[str] = []
    for name in FINVIZ_TOKEN_NAMES:
        if token_value_present(mapping.get(name)):
            present.append(name)
    return tuple(present)


def configured_token(env: Mapping[str, str] | None = None) -> str | None:
    """Return the first configured token. Callers must never log or persist it."""

    mapping = _env_mapping(env)
    for name in FINVIZ_TOKEN_NAMES:
        value = mapping.get(name)
        if token_value_present(value):
            return str(value).strip()
    if env is not None:
        return None
    from ...finviz.config import finviz_api_key

    token = finviz_api_key()
    return token if token_value_present(token) else None


def finviz_live_enabled(env: Mapping[str, str] | None = None) -> bool:
    mapping = _env_mapping(env)
    return str(mapping.get("IMP_FINVIZ_LIVE", "")).strip().lower() in _LIVE_TRUTHY


def _is_es_or_futures(symbol: str) -> bool:
    wanted = str(symbol or "").strip().upper()
    if wanted in _ES_OR_FUTURES:
        return True
    return wanted.endswith(".FUT") or wanted.startswith("FUT.")


class FinvizEliteContextProvider:
    """Fail-closed Finviz Elite context. Screening/news only; never ticks or ES."""

    provider_id = FINVIZ_CONTEXT_PROVIDER_ID
    capability = FINVIZ_CONTEXT_CAPABILITY
    timeliness = FINVIZ_CONTEXT_TIMELINESS
    role = FINVIZ_CONTEXT_ROLE

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        screener: Any | None = None,
        news_client: Any | None = None,
        client_factory: ClientFactory | None = None,
        overlay_token: str | None = None,
    ) -> None:
        self._env = env
        self._screener = screener
        self._news_client = news_client
        self._client_factory = client_factory
        self._overlay_token = overlay_token if token_value_present(overlay_token) else None

    def token_names_present(self) -> tuple[str, ...]:
        return token_names_present(self._env)

    def bind_overlay_token(self, token: str) -> None:
        """Keep a fetched Elite token in-process for overlay use only. Never log it."""

        if token_value_present(token):
            self._overlay_token = str(token).strip()

    def overlay_token_present(self) -> bool:
        return token_value_present(self._overlay_token)

    def _resolved_token(self) -> str | None:
        if token_value_present(self._overlay_token):
            return str(self._overlay_token).strip()
        return configured_token(self._env)

    def configured(self) -> bool:
        return bool(self._resolved_token())

    def live_enabled(self) -> bool:
        return finviz_live_enabled(self._env)

    def has_injected_transport(self) -> bool:
        return (
            self._screener is not None
            or self._news_client is not None
            or self._client_factory is not None
        )

    def fetch_context(self, symbol: str) -> ProviderResult:
        wanted = str(symbol or "").strip().upper()
        if not wanted:
            return self._unavailable("INSTRUMENT_ID_REQUIRED")
        if _is_es_or_futures(wanted):
            return self._unavailable("FINVIZ_NOT_ES_OR_FUTURES")
        token = self._resolved_token()
        if not token:
            return self._unavailable("NOT_CONFIGURED")
        screener, news_client = self._resolve_clients(token)
        if screener is None and news_client is None:
            return self._unavailable("LIVE_DISABLED")
        received_ns = monotonic_wall_ns()
        screen_payload = self._fetch_screen(screener, wanted)
        news_payload = self._fetch_news(news_client, wanted)
        event = {
            "capability": self.capability,
            "clocks": {
                "event_time_ns": received_ns,
                "provider_time_ns": received_ns,
                "received_time_ns": received_ns,
            },
            "entitlement": "FINVIZ_ELITE",
            "execution_role": EXECUTION_ROLE,
            "instrument_id": wanted,
            "news": news_payload,
            "normalization_version": FINVIZ_NORMALIZATION_VERSION,
            "provider": self.provider_id,
            "provider_symbol": wanted,
            "role": self.role,
            "screen": screen_payload,
            "timeliness": self.timeliness,
        }
        return ProviderResult(
            status="available",
            events=(redact_payload(event),),
            provider_id=self.provider_id,
            capability=self.capability,
        )

    def _resolve_clients(self, token: str) -> tuple[Any | None, Any | None]:
        if self._screener is not None or self._news_client is not None:
            return self._screener, self._news_client
        if self._client_factory is not None:
            return self._client_factory(token)
        if not self.live_enabled():
            return None, None
        from ...finviz.news import FinvizNewsClient
        from ...finviz.screener import FinvizScreenerClient

        return FinvizScreenerClient(api_key=token), FinvizNewsClient(api_key=token)

    def _fetch_screen(self, screener: Any | None, symbol: str) -> dict[str, Any]:
        if screener is None:
            return {"success": False, "error": "SCREENER_NOT_ATTACHED", "row": None}
        result = screener.fetch_symbol(symbol)
        if not isinstance(result, dict):
            return {"success": False, "error": "MALFORMED_RECORD", "row": None}
        row = result.get("row")
        screen = {
            "success": bool(result.get("success")),
            "error": result.get("error"),
            "row": row.as_dict() if row is not None and hasattr(row, "as_dict") else row,
            "kind": "SCREEN_SNAPSHOT",
        }
        return redact_payload(screen)

    def _fetch_news(self, news_client: Any | None, symbol: str) -> dict[str, Any]:
        if news_client is None:
            return {"success": False, "error": "NEWS_NOT_ATTACHED", "items": []}
        result = news_client.fetch_news()
        if not isinstance(result, dict):
            return {"success": False, "error": "MALFORMED_RECORD", "items": []}
        items = list(result.get("items") or [])
        if hasattr(news_client, "news_for_symbol"):
            items = list(news_client.news_for_symbol(symbol, items))
        news = {
            "success": bool(result.get("success")),
            "error": result.get("error"),
            "items": items,
        }
        return redact_payload(news)

    def _unavailable(self, reason_code: str) -> ProviderResult:
        return ProviderResult(
            status="unavailable",
            reason_code=reason_code,
            provider_id=self.provider_id,
            capability=self.capability,
        )


def attach_finviz_context(
    composition: Any,
    provider: FinvizEliteContextProvider,
) -> Any:
    """Inject the Finviz overlay into a composition that exposes ``equity_context``."""

    if not hasattr(composition, "equity_context"):
        raise AttributeError("EQUITY_CONTEXT_SLOT_MISSING")
    composition.equity_context = provider
    return composition


def overlay_payload(
    *,
    discovery: Mapping[str, Any],
    result: ProviderResult,
) -> dict[str, Any]:
    """JSON-safe overlay summary. Never includes token values."""

    payload: MutableMapping[str, Any] = {
        "discovery": dict(discovery),
        "result": {
            "capability": result.capability,
            "event_count": len(result.events),
            "is_l1": False,
            "is_paper_comparator": False,
            "provider_id": result.provider_id,
            "reason_code": result.reason_code,
            "role": FINVIZ_CONTEXT_ROLE,
            "status": result.status,
            "timeliness": FINVIZ_CONTEXT_TIMELINESS,
        },
    }
    return redact_payload(dict(payload))


__all__ = [
    "FINVIZ_CONTEXT_CAPABILITY",
    "FINVIZ_CONTEXT_PROVIDER_ID",
    "FINVIZ_CONTEXT_ROLE",
    "FINVIZ_CONTEXT_TIMELINESS",
    "FINVIZ_LOGIN_NAMES",
    "FINVIZ_TOKEN_NAMES",
    "FinvizEliteContextProvider",
    "attach_finviz_context",
    "configured_token",
    "finviz_live_enabled",
    "overlay_payload",
    "token_names_present",
    "token_value_present",
]
