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
    login_source: str = "NONE"

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


def _login_pair(env: Mapping[str, str] | None) -> tuple[str | None, str | None, str]:
    """Read Elite login from existing local provider info only. Never log the pair.

    Isolated ``env`` mappings stay in-process (tests). Operator runtime
    (``env is None``) uses existing stores, in order:

    1. Canonical IMP ``.private/finviz-login.json`` (or ``IMP_FINVIZ_SECRET_DIR``)
    2. Leftover nested ``integrated-market-platform/.private/finviz-login.json``
    3. ``.private/providers.env`` / short-squeeze ``providers.env`` / ``IMP_PROVIDER_ENV``
    4. Process-env ``FINVIZ_USERNAME`` / ``FINVIZ_PASSWORD``
    """

    if env is not None:
        username = env.get("FINVIZ_USERNAME")
        password = env.get("FINVIZ_PASSWORD")
        if token_value_present(username) and token_value_present(password):
            return str(username).strip(), str(password), "ENV_MAPPING"
        return None, None, "NONE"

    from ..finviz.config import extra_operator_login_files
    from ..finviz.credential_manager import read_login_credentials_from_env
    from ..finviz.secure_store import read_login_credentials, read_login_file

    username, password = read_login_credentials()
    if token_value_present(username) and token_value_present(password):
        return str(username).strip(), str(password), "CANONICAL_LOGIN_FILE"
    for path in extra_operator_login_files():
        username, password = read_login_file(path)
        if token_value_present(username) and token_value_present(password):
            return str(username).strip(), str(password), "NESTED_LOGIN_FILE"
    username, password = read_login_credentials_from_env()
    if token_value_present(username) and token_value_present(password):
        return str(username).strip(), str(password), "PROVIDER_ENV_FILE"
    import os

    username = os.environ.get("FINVIZ_USERNAME")
    password = os.environ.get("FINVIZ_PASSWORD")
    if token_value_present(username) and token_value_present(password):
        return str(username).strip(), str(password), "ENVIRONMENT"
    return None, None, "NONE"


def autofetch_overlay_token(
    *,
    env: Mapping[str, str] | None = None,
    token_fetcher: TokenFetcher | None = None,
    session_factory: SessionFactory | None = None,
) -> tuple[str | None, str, str]:
    """Refresh the Elite export token from local provider info. Operator-zero.

    A static long-lived token is not required. Fetch failure returns
    ``(None, FETCH_FAILED | CREDENTIALS_ABSENT, login_source)``. Callers must
    never log the token. Isolated env mappings do not touch operator files or
    live HTTP unless a test injects ``token_fetcher`` or ``session_factory``.
    Successful runtime fetch persists the token into canonical gitignored
    ``.private`` and repairs login there when it was found on a leftover path.
    """

    if token_fetcher is not None:
        try:
            token = token_fetcher()
        except Exception:
            return None, "FETCH_FAILED", "TOKEN_FETCHER"
        if token_value_present(token):
            return str(token).strip(), "FETCHED", "TOKEN_FETCHER"
        return None, "FETCH_FAILED", "TOKEN_FETCHER"

    username, password, login_source = _login_pair(env)
    if not username or not password:
        return None, "CREDENTIALS_ABSENT", login_source

    persist = env is None
    if env is not None and session_factory is None:
        return None, "NOT_ATTEMPTED", login_source

    from ..finviz.login_recovery import LoginRecoveryStatus, recover_token_via_login

    try:
        result = recover_token_via_login(
            username=username,
            password=password,
            session_factory=session_factory,
        )
    except Exception:
        return None, "FETCH_FAILED", login_source
    if result.status != LoginRecoveryStatus.REFRESHED or not token_value_present(result.token):
        return None, "FETCH_FAILED", login_source
    token = str(result.token).strip()
    if persist:
        from ..finviz.secure_store import (
            read_login_credentials,
            write_login_credentials,
            write_secure_token,
        )

        write_secure_token(token)
        if login_source in {"NESTED_LOGIN_FILE", "PROVIDER_ENV_FILE"}:
            existing_user, existing_password = read_login_credentials()
            if not (
                token_value_present(existing_user) and token_value_present(existing_password)
            ):
                write_login_credentials(username, password)
    return token, "FETCHED", login_source


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
    login_source = "NONE"
    should_fetch = not adapter.configured()
    if env is None and not adapter.overlay_token_present():
        _, _, login_source = _login_pair(env)
        if login_source not in {"NONE"}:
            should_fetch = True
    if should_fetch:
        token, fetch_status, login_source = autofetch_overlay_token(
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
        login_source=login_source,
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
