"""Value-blind Finviz Elite context discovery. Never prints secret values."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping

from .adapters.finviz_elite_context import (
    FINVIZ_CONTEXT_PROVIDER_ID,
    FINVIZ_CONTEXT_ROLE,
    FINVIZ_CONTEXT_TIMELINESS,
    FINVIZ_LOGIN_NAMES,
    FINVIZ_TOKEN_NAMES,
    FinvizEliteContextProvider,
    overlay_payload,
    token_names_present,
    token_value_present,
)
from .contracts import ProviderResult

_YAHOO_IDENTITIES = frozenset({"yahoo.finance.delayed", "yahoo", "YAHOO"})

TokenFetcher = Callable[[], str | None]
SessionFactory = Callable[[], Any]


@dataclass(frozen=True, slots=True)
class FinvizContextDiscovery:
    provider_id: str
    classification: str
    timeliness: str
    reason_code: str
    role: str
    token_names_present: tuple[str, ...]
    live_enabled: bool
    is_l1: bool
    is_paper_comparator: bool
    auto_fetch_status: str = "NOT_ATTEMPTED"
    login_credential_names_present: tuple[str, ...] = ()
    overlay_token_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["token_names_present"] = list(self.token_names_present)
        payload["login_credential_names_present"] = list(self.login_credential_names_present)
        return payload


def login_credential_names_present(env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Return login env names that are set. Values are never included."""

    if env is None:
        return ()
    present: list[str] = []
    for name in FINVIZ_LOGIN_NAMES:
        if token_value_present(env.get(name)):
            present.append(name)
    return tuple(present)


def _login_pair(env: Mapping[str, str] | None) -> tuple[str | None, str | None]:
    """Read Elite login from existing local provider info only. Never log the pair.

    Isolated ``env`` mappings stay in-process (tests). Operator runtime
    (``env is None``) uses the existing stores: ``.private/finviz-login.json``,
    then ``.private/providers.env`` / ``IMP_PROVIDER_ENV``, then the same
    ``FINVIZ_USERNAME`` / ``FINVIZ_PASSWORD`` process-env names.
    """

    if env is not None:
        username = env.get("FINVIZ_USERNAME")
        password = env.get("FINVIZ_PASSWORD")
        if token_value_present(username) and token_value_present(password):
            return str(username).strip(), str(password)
        return None, None

    from ..finviz.credential_manager import read_login_credentials_from_env
    from ..finviz.secure_store import read_login_credentials

    username, password = read_login_credentials()
    if token_value_present(username) and token_value_present(password):
        return str(username).strip(), str(password)
    username, password = read_login_credentials_from_env()
    if token_value_present(username) and token_value_present(password):
        return str(username).strip(), str(password)
    import os

    username = os.environ.get("FINVIZ_USERNAME")
    password = os.environ.get("FINVIZ_PASSWORD")
    if token_value_present(username) and token_value_present(password):
        return str(username).strip(), str(password)
    return None, None


def autofetch_overlay_token(
    *,
    env: Mapping[str, str] | None = None,
    token_fetcher: TokenFetcher | None = None,
    session_factory: SessionFactory | None = None,
) -> tuple[str | None, str]:
    """Refresh the Elite export token from local provider info. Operator-zero.

    A static long-lived token is not required. Fetch failure returns
    ``(None, FETCH_FAILED | CREDENTIALS_ABSENT)``. Callers must never log the
    token. Isolated env mappings do not touch operator files or live HTTP
    unless a test injects ``token_fetcher`` or ``session_factory``.
    """

    if token_fetcher is not None:
        try:
            token = token_fetcher()
        except Exception:
            return None, "FETCH_FAILED"
        if token_value_present(token):
            return str(token).strip(), "FETCHED"
        return None, "FETCH_FAILED"

    username, password = _login_pair(env)
    if not username or not password:
        return None, "CREDENTIALS_ABSENT"

    persist = env is None
    if env is not None and session_factory is None:
        return None, "NOT_ATTEMPTED"

    from ..finviz.login_recovery import LoginRecoveryStatus, recover_token_via_login

    try:
        result = recover_token_via_login(
            username=username,
            password=password,
            session_factory=session_factory,
        )
    except Exception:
        return None, "FETCH_FAILED"
    if result.status != LoginRecoveryStatus.REFRESHED or not token_value_present(result.token):
        return None, "FETCH_FAILED"
    token = str(result.token).strip()
    if persist:
        from ..finviz.secure_store import write_secure_token

        write_secure_token(token)
    return token, "FETCHED"


def discover_finviz_context_stack(
    *,
    env: Mapping[str, str] | None = None,
    provider: FinvizEliteContextProvider | None = None,
    token_fetcher: TokenFetcher | None = None,
    session_factory: SessionFactory | None = None,
) -> tuple[FinvizEliteContextProvider, FinvizContextDiscovery]:
    """Always return the Finviz context adapter. Never Yahoo-as-Finviz.

    Token absence is ``NOT_CONFIGURED``. When the export token is missing, hop
    overlay discovery auto-fetches it from existing local provider info (no
    operator prompt). Fetch failure stays ``NOT_CONFIGURED``. A present token
    without ``IMP_FINVIZ_LIVE`` and without injected clients is
    ``CONFIGURED_BLOCKED`` (``LIVE_DISABLED``). Classification is never
    ``REAL_TIME`` and never an ES/L1 identity.
    """

    adapter = provider or FinvizEliteContextProvider(env=env)
    if adapter.provider_id in _YAHOO_IDENTITIES:
        raise ValueError("FINVIZ_YAHOO_IDENTITY_FORBIDDEN")
    names = token_names_present(env)
    login_names = login_credential_names_present(env)
    live = adapter.live_enabled()
    fetch_status = "NOT_ATTEMPTED"
    if not adapter.configured():
        token, fetch_status = autofetch_overlay_token(
            env=env,
            token_fetcher=token_fetcher,
            session_factory=session_factory,
        )
        if token_value_present(token):
            adapter.bind_overlay_token(str(token))
    if not adapter.configured():
        classification = "NOT_CONFIGURED"
        reason = "NOT_CONFIGURED"
    elif not live and not adapter.has_injected_transport():
        classification = "CONFIGURED_BLOCKED"
        reason = "LIVE_DISABLED"
    else:
        classification = "CONFIGURED"
        reason = "FINVIZ_CONTEXT_OVERLAY"
    discovery = FinvizContextDiscovery(
        provider_id=FINVIZ_CONTEXT_PROVIDER_ID,
        classification=classification,
        timeliness=FINVIZ_CONTEXT_TIMELINESS,
        reason_code=reason,
        role=FINVIZ_CONTEXT_ROLE,
        token_names_present=names,
        live_enabled=live,
        is_l1=False,
        is_paper_comparator=False,
        auto_fetch_status=fetch_status,
        login_credential_names_present=login_names,
        overlay_token_present=adapter.overlay_token_present(),
    )
    return adapter, discovery


def run_finviz_context_overlay(
    symbol: str,
    *,
    env: Mapping[str, str] | None = None,
    provider: FinvizEliteContextProvider | None = None,
    token_fetcher: TokenFetcher | None = None,
    session_factory: SessionFactory | None = None,
) -> dict[str, Any]:
    """Canonical pipeline overlay: classify, then fetch context fail-closed."""

    adapter, discovery = discover_finviz_context_stack(
        env=env,
        provider=provider,
        token_fetcher=token_fetcher,
        session_factory=session_factory,
    )
    result: ProviderResult = adapter.fetch_context(symbol)
    return overlay_payload(discovery=discovery.to_dict(), result=result)


__all__ = [
    "FINVIZ_LOGIN_NAMES",
    "FINVIZ_TOKEN_NAMES",
    "FinvizContextDiscovery",
    "autofetch_overlay_token",
    "discover_finviz_context_stack",
    "login_credential_names_present",
    "run_finviz_context_overlay",
    "token_names_present",
]
