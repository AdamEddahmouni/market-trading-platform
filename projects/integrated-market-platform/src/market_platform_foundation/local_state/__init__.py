"""Durable local operator state (PLATFORM-STATE-001)."""

from .connection import CorruptStateError, LocalStateConnection
from .migrations import SchemaVersionError
from .paths import persistence_enabled, state_dir
from .repository import LocalStateRepository
from .schema import SCHEMA_VERSION
from .startup import open_local_state, persist_ledger, reset_local_state_for_tests, startup_report

__all__ = [
    "CorruptStateError",
    "LocalStateConnection",
    "LocalStateRepository",
    "SCHEMA_VERSION",
    "SchemaVersionError",
    "open_local_state",
    "persist_ledger",
    "persistence_enabled",
    "reset_local_state_for_tests",
    "startup_report",
    "state_dir",
]
