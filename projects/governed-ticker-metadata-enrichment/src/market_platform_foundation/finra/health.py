"""FINRA source health. Reachable is not 'a new short-interest print exists'."""

from __future__ import annotations

from dataclasses import dataclass

from .auth import FinraTokenManager
from .client_config import FinraCredentials, credential_health, resolve_expiry
from .transport import FinraTransport
from ..short_intelligence.contracts import CredentialHealthState


@dataclass(frozen=True, slots=True)
class FinraHealth:
    oauth_healthy: bool
    last_token_refresh_count: int
    api_reachable: bool
    last_status: str
    last_request_id: str
    last_successful_query: str
    last_dataset_publication_observed: str
    last_error: str
    credential_rotation_status: str
    credential_expires_on: str
    license_constraint: str = "INDIVIDUAL_PUBLIC_RESEARCH_ONLY"


def health_from_runtime(
    *,
    credentials: FinraCredentials,
    tokens: FinraTokenManager | None,
    transport: FinraTransport | None,
    last_dataset_publication_observed: str = "",
    auth_failed: bool = False,
) -> FinraHealth:
    expiry = resolve_expiry(credentials)
    rotation = credential_health(credentials, auth_failed=auth_failed)
    return FinraHealth(
        oauth_healthy=bool(tokens and tokens.last_error == "" and tokens.refresh_count > 0 and not auth_failed),
        last_token_refresh_count=int(getattr(tokens, "refresh_count", 0) or 0),
        api_reachable=bool(transport and transport.last_status == "ok"),
        last_status=str(getattr(transport, "last_status", "idle")),
        last_request_id=str(getattr(transport, "last_request_id", "")),
        last_successful_query="yes" if transport and transport.last_success_monotonic else "",
        last_dataset_publication_observed=last_dataset_publication_observed,
        last_error=str(getattr(tokens, "last_error", "") or getattr(transport, "last_status", "")),
        credential_rotation_status=rotation.value,
        credential_expires_on=expiry.isoformat() if expiry else "",
    )


def rotation_is_not_publication(health: FinraHealth) -> bool:
    return health.credential_rotation_status != CredentialHealthState.HEALTHY.value or True
