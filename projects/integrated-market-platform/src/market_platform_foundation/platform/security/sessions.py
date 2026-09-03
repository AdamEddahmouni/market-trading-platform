"""In-memory operator session store (TD-005)."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any

from .principals import PrincipalRecord


@dataclass(frozen=True)
class OperatorSession:
    token: str
    principal_id: str
    role: str
    display_name: str
    permitted_accounts: frozenset[str]
    issued_at_ns: int
    expires_at_ns: int

    def to_public_dict(self, *, enforcement_mode: str, role_enforcement_status: str) -> dict[str, Any]:
        accounts = sorted(self.permitted_accounts)
        return {
            "authenticated": True,
            "principal_id": self.principal_id,
            "display_name": self.display_name,
            "role": self.role,
            "permitted_accounts": accounts,
            "expires_at_ns": self.expires_at_ns,
            "enforcement_mode": enforcement_mode,
            "role_enforcement_status": role_enforcement_status,
        }


class SessionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, OperatorSession] = {}

    def create_session(
        self,
        principal: PrincipalRecord,
        *,
        ttl_seconds: int,
        issued_at_ns: int | None = None,
    ) -> OperatorSession:
        now = issued_at_ns if issued_at_ns is not None else time.time_ns()
        token = secrets.token_urlsafe(32)
        session = OperatorSession(
            token=token,
            principal_id=principal.principal_id,
            role=principal.role.value,
            display_name=principal.display_name,
            permitted_accounts=principal.permitted_accounts,
            issued_at_ns=now,
            expires_at_ns=now + ttl_seconds * 1_000_000_000,
        )
        with self._lock:
            self._sessions[token] = session
        return session

    def get(self, token: str, *, now_ns: int | None = None) -> OperatorSession | None:
        current = now_ns if now_ns is not None else time.time_ns()
        with self._lock:
            session = self._sessions.get(token)
            if session is None:
                return None
            if current >= session.expires_at_ns:
                del self._sessions[token]
                return None
            return session

    def revoke(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)

    def reset_for_tests(self) -> None:
        with self._lock:
            self._sessions.clear()


_GLOBAL_SESSION_STORE = SessionStore()


def get_session_store() -> SessionStore:
    return _GLOBAL_SESSION_STORE
