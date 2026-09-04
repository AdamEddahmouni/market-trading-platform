"""Principal registry for multi-user authorization (TD-005)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .auth_config import AuthConfigError, load_principals_document
from .roles import OperatorRole

ALL_ACCOUNTS = "*"
PRINCIPALS_SCHEMA = "platform/principals/1.0.0"


class PrincipalRegistryError(ValueError):
    """Raised when principal configuration is invalid."""


@dataclass(frozen=True)
class PrincipalRecord:
    principal_id: str
    display_name: str
    role: OperatorRole
    permitted_accounts: frozenset[str]
    secret_digest: str | None = None

    def permits_account(self, account_id: str) -> bool:
        if ALL_ACCOUNTS in self.permitted_accounts:
            return True
        return account_id in self.permitted_accounts

    def to_public_dict(self) -> dict[str, Any]:
        accounts = sorted(self.permitted_accounts)
        return {
            "principal_id": self.principal_id,
            "display_name": self.display_name,
            "role": self.role.value,
            "permitted_accounts": accounts,
        }


def _digest_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def parse_principal_entry(entry: dict[str, Any]) -> PrincipalRecord:
    principal_id = str(entry.get("principal_id", "")).strip()
    if not principal_id:
        raise PrincipalRegistryError("PRINCIPAL_ID_REQUIRED")
    display_name = str(entry.get("display_name", principal_id)).strip() or principal_id
    role_raw = str(entry.get("role", OperatorRole.VIEWER.value)).upper()
    try:
        role = OperatorRole(role_raw)
    except ValueError:
        raise PrincipalRegistryError(f"UNKNOWN_OPERATOR_ROLE: {role_raw}")
    accounts_raw = entry.get("permitted_accounts") or entry.get("accounts") or [ALL_ACCOUNTS]
    if not isinstance(accounts_raw, list) or not accounts_raw:
        raise PrincipalRegistryError("PERMITTED_ACCOUNTS_REQUIRED")
    permitted = frozenset(str(item).strip() for item in accounts_raw if str(item).strip())
    secret = entry.get("secret")
    secret_digest = _digest_secret(str(secret)) if secret else None
    if secret_digest is None:
        raise PrincipalRegistryError(f"PRINCIPAL_SECRET_REQUIRED: {principal_id}")
    return PrincipalRecord(
        principal_id=principal_id,
        display_name=display_name,
        role=role,
        permitted_accounts=permitted,
        secret_digest=secret_digest,
    )


def load_principal_registry(path: str) -> dict[str, PrincipalRecord]:
    document = load_principals_document(path)
    entries = document.get("principals")
    if not isinstance(entries, list) or not entries:
        raise PrincipalRegistryError("PRINCIPALS_LIST_REQUIRED")
    registry: dict[str, PrincipalRecord] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise PrincipalRegistryError("PRINCIPAL_ENTRY_MUST_BE_OBJECT")
        record = parse_principal_entry(entry)
        if record.principal_id in registry:
            raise PrincipalRegistryError(f"DUPLICATE_PRINCIPAL_ID: {record.principal_id}")
        registry[record.principal_id] = record
    return registry


def verify_principal_secret(record: PrincipalRecord, secret: str) -> bool:
    if record.secret_digest is None:
        return False
    return record.secret_digest == _digest_secret(secret)
