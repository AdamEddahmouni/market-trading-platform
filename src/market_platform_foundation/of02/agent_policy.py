"""Agent-enforced OF-02 prohibitions."""

from __future__ import annotations

from .errors import OF02Error, OF02ErrorCode


def prohibit_historical_fabrication() -> None:
    raise OF02Error(OF02ErrorCode.FABRICATION_PROHIBITED, "historical provenance must not be fabricated", {})


def prohibit_backdating() -> None:
    raise OF02Error(OF02ErrorCode.BACKDATE_PROHIBITED, "OF recorded_at must not be backdated", {})


def prohibit_direct_sql() -> None:
    raise OF02Error(OF02ErrorCode.DIRECT_SQL_PROHIBITED, "adapters must not write SQLite directly", {})


def prohibit_retry_id_regeneration() -> None:
    raise OF02Error(OF02ErrorCode.RETRY_IDENTITY_REGENERATION, "retry must not regenerate identities", {})


def prohibit_future_information() -> None:
    raise OF02Error(OF02ErrorCode.FUTURE_INFORMATION, "future-information leakage is prohibited", {})


def prohibit_history_rewrite() -> None:
    raise OF02Error(OF02ErrorCode.FABRICATION_PROHIBITED, "authoritative history must not be rewritten", {})


def prohibit_live_smoke_fabrication() -> None:
    raise OF02Error(OF02ErrorCode.LIVE_SMOKE_FABRICATED, "live provider smoke must not be fabricated", {})
