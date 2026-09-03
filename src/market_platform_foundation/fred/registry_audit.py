"""Live Tier-1 registry validation against FRED production metadata."""

from __future__ import annotations

from typing import Any

from .registry import MacroDomain, MacroRegistryEntry, TIER1_REGISTRY
from .transport import FredTransportError
from .v1_client import FredV1Client

_AUDIT_STATUS = (
    "VERIFIED_LIVE",
    "VERIFIED_METADATA_ONLY",
    "MISMATCH",
    "DISCONTINUED",
    "MAPPING_UNRESOLVED",
    "RIGHTS_REVIEW",
    "DEFERRED",
)

_SA_MAP = {
    "SA": ("seasonally adjusted", "sa"),
    "NSA": ("not seasonally adjusted", "nsa"),
}

_FREQ_ALIASES = {
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
    "quarterly": "quarterly",
}


def _normalize_freq(value: str) -> str:
    text = value.strip().lower()
    for key, canonical in _FREQ_ALIASES.items():
        if key in text:
            return canonical
    return text


def _freq_compatible(registry_freq: str, fred_freq: str) -> bool:
    reg = _normalize_freq(registry_freq)
    live = _normalize_freq(fred_freq)
    return reg == live or reg in live or live in reg


def _sa_compatible(registry_sa: str, fred_sa: str) -> bool:
    aliases = _SA_MAP.get(registry_sa.upper(), (registry_sa.lower(),))
    fred_lower = fred_sa.lower()
    return any(alias in fred_lower for alias in aliases)


def _units_compatible(registry_units: str, fred_units: str) -> bool:
    reg = registry_units.lower()
    live = fred_units.lower()
    if reg == live:
        return True
    reg_tokens = {token for token in reg.replace(",", " ").split() if len(token) > 2}
    live_tokens = {token for token in live.replace(",", " ").split() if len(token) > 2}
    return bool(reg_tokens & live_tokens) or reg.split()[0] in live


def _series_metadata(v1: FredV1Client, series_id: str, cache: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if series_id in cache:
        return cache[series_id]
    try:
        payload = v1.series(series_id)
    except FredTransportError:
        cache[series_id] = {}
        return None
    rows = payload.get("seriess", [])
    if not rows or not isinstance(rows[0], dict):
        cache[series_id] = {}
        return None
    meta = rows[0]
    cache[series_id] = meta
    return meta


def _release_id_for_series(v1: FredV1Client, series_id: str, cache: dict[str, int | None]) -> int | None:
    if series_id in cache:
        return cache[series_id]
    try:
        payload = v1.series_release(series_id)
        releases = payload.get("releases", [])
        release_id = int(releases[0]["id"]) if releases and isinstance(releases[0], dict) else None
    except (FredTransportError, ValueError, TypeError, KeyError, IndexError):
        release_id = None
    cache[series_id] = release_id
    return release_id


def audit_registry_entry(
    v1: FredV1Client,
    entry: MacroRegistryEntry,
    *,
    series_cache: dict[str, dict[str, Any]],
    release_cache: dict[str, int | None],
    v2_release_series: dict[int, set[str]] | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    meta = _series_metadata(v1, entry.fred_series_id, series_cache)
    if not meta:
        return {
            "canonical_indicator_id": entry.canonical_indicator_id,
            "fred_series_id": entry.fred_series_id,
            "domain": entry.domain.value,
            "status": "MISMATCH",
            "issues": ["series_not_found"],
        }

    live_id = str(meta.get("id", ""))
    if live_id != entry.fred_series_id:
        issues.append("series_id_mismatch")

    if not _freq_compatible(entry.frequency, str(meta.get("frequency", ""))):
        issues.append("frequency_mismatch")

    if not _units_compatible(entry.units, str(meta.get("units", ""))):
        issues.append("units_mismatch")

    if not _sa_compatible(entry.seasonal_adjustment, str(meta.get("seasonal_adjustment", ""))):
        issues.append("seasonal_adjustment_mismatch")

    observation_end = str(meta.get("observation_end", ""))
    if observation_end and observation_end < "2020-01-01":
        issues.append("possibly_discontinued")

    live_release_id = _release_id_for_series(v1, entry.fred_series_id, release_cache)
    if entry.fred_release_id is not None and live_release_id is None:
        issues.append("release_mapping_unresolved")
    elif entry.fred_release_id is not None and live_release_id is not None:
        if entry.fred_release_id != live_release_id:
            issues.append(f"release_id_note:configured={entry.fred_release_id},series_release={live_release_id}")

    v2_verified = None
    if v2_release_series and entry.fred_release_id is not None:
        members = v2_release_series.get(entry.fred_release_id, set())
        if members:
            v2_verified = entry.fred_series_id in members
            if entry.v2_release_membership and not v2_verified:
                issues.append("v2_release_membership_not_confirmed")

    if entry.usage_rights == "redistribution_review_required" and not issues:
        status = "RIGHTS_REVIEW"
    elif "possibly_discontinued" in issues:
        status = "DISCONTINUED"
    elif "release_mapping_unresolved" in issues:
        status = "MAPPING_UNRESOLVED"
    elif issues:
        status = "MISMATCH"
    else:
        status = "VERIFIED_LIVE"

    return {
        "canonical_indicator_id": entry.canonical_indicator_id,
        "fred_series_id": entry.fred_series_id,
        "domain": entry.domain.value,
        "status": status,
        "live_title": str(meta.get("title", ""))[:120],
        "live_frequency": str(meta.get("frequency", "")),
        "live_units": str(meta.get("units", "")),
        "live_seasonal_adjustment": str(meta.get("seasonal_adjustment", "")),
        "live_release_id": live_release_id,
        "configured_release_id": entry.fred_release_id,
        "observation_start": str(meta.get("observation_start", "")),
        "observation_end": observation_end,
        "last_updated": str(meta.get("last_updated", "")),
        "revision_sensitive": entry.revision_sensitive,
        "v2_membership_verified": v2_verified,
        "copyright_id": entry.copyright_id,
        "usage_rights": entry.usage_rights,
        "issues": issues,
    }


def audit_tier1_registry(
    v1: FredV1Client,
    *,
    v2_release_series: dict[int, set[str]] | None = None,
) -> dict[str, Any]:
    series_cache: dict[str, dict[str, Any]] = {}
    release_cache: dict[str, int | None] = {}
    entries: list[dict[str, Any]] = []
    by_status: dict[str, int] = {status: 0 for status in _AUDIT_STATUS}
    by_domain: dict[str, dict[str, int]] = {}

    for entry in TIER1_REGISTRY:
        row = audit_registry_entry(
            v1,
            entry,
            series_cache=series_cache,
            release_cache=release_cache,
            v2_release_series=v2_release_series,
        )
        entries.append(row)
        status = str(row["status"])
        by_status[status] = by_status.get(status, 0) + 1
        domain = entry.domain.value
        bucket = by_domain.setdefault(
            domain,
            {"configured": 0, "verified_live": 0, "pit_capable": 0, "v2_verified": 0, "rights_review": 0, "errors": 0},
        )
        bucket["configured"] += 1
        if status == "VERIFIED_LIVE":
            bucket["verified_live"] += 1
        if entry.v1_pit_supported:
            bucket["pit_capable"] += 1
        if row.get("v2_membership_verified"):
            bucket["v2_verified"] += 1
        if entry.usage_rights == "redistribution_review_required":
            bucket["rights_review"] += 1
        if status in {"MISMATCH", "DISCONTINUED", "MAPPING_UNRESOLVED"}:
            bucket["errors"] += 1

    corrections: list[dict[str, Any]] = []
    for row in entries:
        issues = row.get("issues", [])
        if any("release_id_mismatch" in str(issue) for issue in issues):
            corrections.append(
                {
                    "canonical_indicator_id": row["canonical_indicator_id"],
                    "field": "fred_release_id",
                    "configured": row["configured_release_id"],
                    "observed": row["live_release_id"],
                }
            )

    return {
        "tier1_count": len(TIER1_REGISTRY),
        "entries": entries,
        "by_status": by_status,
        "by_domain": by_domain,
        "corrections_suggested": corrections,
        "series_metadata_calls": len(series_cache),
    }


def _release_series_members(v1: FredV1Client, release_id: int) -> set[str]:
    members: set[str] = set()
    offset = 0
    while True:
        payload = v1.release_series(release_id, limit=1000, offset=offset)
        rows = payload.get("seriess", [])
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            if isinstance(row, dict) and row.get("id"):
                members.add(str(row["id"]))
        if len(rows) < 1000:
            break
        offset += 1000
    return members


def build_v2_release_membership(v1: FredV1Client, release_ids: set[int]) -> dict[int, set[str]]:
    membership: dict[int, set[str]] = {}
    for release_id in sorted(release_ids):
        try:
            membership[release_id] = _release_series_members(v1, release_id)
        except FredTransportError:
            membership[release_id] = set()
    return membership


def domain_summary(by_domain: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    return {domain.lower(): stats for domain, stats in by_domain.items()}


__all__ = [
    "audit_registry_entry",
    "audit_tier1_registry",
    "build_v2_release_membership",
    "domain_summary",
]
