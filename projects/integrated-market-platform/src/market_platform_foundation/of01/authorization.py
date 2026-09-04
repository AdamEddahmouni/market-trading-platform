"""OF-01 authorization verification boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .errors import OF01Error, OF01ErrorCode


@dataclass(frozen=True, slots=True)
class AuthorizationGrant:
    issuer_identity: str
    reference: str
    capability_id: str
    ledger_authority_id: str
    input_hash: str
    initiator_ref: str
    allowed_role: str
    not_before_ns: int
    expires_at_ns: int
    revoked: bool
    revocation_version: int


class AuthorizationVerifier(Protocol):
    def verify(
        self,
        reference: str,
        *,
        capability_id: str,
        ledger_authority_id: str,
        input_hash: str,
        initiator_ref: str,
        observed_at_ns: int,
    ) -> AuthorizationGrant: ...


class FakeAuthorizationVerifier:
    def __init__(self, grants: dict[str, AuthorizationGrant]) -> None:
        self._grants = dict(grants)

    def verify(
        self,
        reference: str,
        *,
        capability_id: str,
        ledger_authority_id: str,
        input_hash: str,
        initiator_ref: str,
        observed_at_ns: int,
    ) -> AuthorizationGrant:
        grant = self._grants.get(reference)
        if grant is None:
            raise OF01Error(
                OF01ErrorCode.AUTHORIZATION_REQUIRED,
                "authorization reference unknown",
                {"reference": reference},
            )
        if grant.revoked:
            raise OF01Error(
                OF01ErrorCode.AUTHORIZATION_REQUIRED,
                "authorization revoked",
                {"reference": reference},
            )
        if observed_at_ns < grant.not_before_ns or observed_at_ns > grant.expires_at_ns:
            raise OF01Error(
                OF01ErrorCode.AUTHORIZATION_REQUIRED,
                "authorization outside validity window",
                {"reference": reference},
            )
        if grant.capability_id != capability_id:
            raise OF01Error(
                OF01ErrorCode.AUTHORIZATION_REQUIRED,
                "capability mismatch",
                {"reference": reference},
            )
        if grant.ledger_authority_id != ledger_authority_id:
            raise OF01Error(
                OF01ErrorCode.AUTHORIZATION_REQUIRED,
                "authority mismatch",
                {"reference": reference},
            )
        if grant.input_hash != input_hash:
            raise OF01Error(
                OF01ErrorCode.AUTHORIZATION_REQUIRED,
                "input hash mismatch",
                {"reference": reference},
            )
        if grant.initiator_ref != initiator_ref:
            raise OF01Error(
                OF01ErrorCode.AUTHORIZATION_REQUIRED,
                "initiator mismatch",
                {"reference": reference},
            )
        return grant
