"""Mongo persistence configuration for XA catalog (IMP-XA-04)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping

DEFAULT_MONGODB_DATABASE = "imp_xa_catalog"
DEFAULT_SERVER_SELECTION_TIMEOUT_MS = 2000
TEST_DATABASE_PREFIX = "imp_xa_test_"

_CREDENTIAL_URI_PATTERN = re.compile(
    r"(mongodb(?:\+srv)?://)([^/@]+@)",
    flags=re.IGNORECASE,
)


def redact_mongo_uri(uri: str) -> str:
    if not uri:
        return uri
    return _CREDENTIAL_URI_PATTERN.sub(r"\1[REDACTED]@", uri)


@dataclass(frozen=True, slots=True)
class MongoCatalogRepositoryConfig:
    uri: str
    database_name: str = DEFAULT_MONGODB_DATABASE
    server_selection_timeout_ms: int = DEFAULT_SERVER_SELECTION_TIMEOUT_MS
    application_name: str | None = "imp-xa-catalog"

    def __post_init__(self) -> None:
        if not self.uri or not str(self.uri).strip():
            raise ValueError("MONGODB_URI_REQUIRED")
        if not self.database_name or not str(self.database_name).strip():
            raise ValueError("MONGODB_DATABASE_REQUIRED")
        if self.server_selection_timeout_ms <= 0:
            raise ValueError("MONGODB_SERVER_SELECTION_TIMEOUT_INVALID")

    @classmethod
    def from_test_env(cls, environ: Mapping[str, str] | None = None) -> MongoCatalogRepositoryConfig:
        env = environ or os.environ
        uri = str(env.get("IMP_TEST_MONGODB_URI", "")).strip()
        if not uri:
            raise ValueError("IMP_TEST_MONGODB_URI_REQUIRED")
        database = str(env.get("IMP_TEST_MONGODB_DATABASE", "")).strip()
        if not database:
            raise ValueError("IMP_TEST_MONGODB_DATABASE_REQUIRED")
        if not database.startswith(TEST_DATABASE_PREFIX):
            raise ValueError("IMP_TEST_MONGODB_DATABASE_PREFIX_REQUIRED")
        return cls(uri=uri, database_name=database)

    def __repr__(self) -> str:
        return (
            f"MongoCatalogRepositoryConfig(uri={redact_mongo_uri(self.uri)!r}, "
            f"database_name={self.database_name!r}, "
            f"server_selection_timeout_ms={self.server_selection_timeout_ms!r}, "
            f"application_name={self.application_name!r})"
        )


def assert_safe_test_database_name(database_name: str) -> None:
    if not database_name.startswith(TEST_DATABASE_PREFIX):
        raise ValueError("TEST_DATABASE_PREFIX_REQUIRED")


__all__ = [
    "DEFAULT_MONGODB_DATABASE",
    "DEFAULT_SERVER_SELECTION_TIMEOUT_MS",
    "MongoCatalogRepositoryConfig",
    "TEST_DATABASE_PREFIX",
    "assert_safe_test_database_name",
    "redact_mongo_uri",
]
