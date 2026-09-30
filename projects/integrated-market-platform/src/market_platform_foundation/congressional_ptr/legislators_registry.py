"""Cached public ``unitedstates/congress-legislators`` registry for member identity (Screener S14).

The ``OFFICIAL_ID`` identity rules need Bioguide ids with dated terms. The public
``unitedstates/congress-legislators`` project (CC0-1.0) publishes exactly that as
``legislators-current.json`` and ``legislators-historical.json``. This module keeps a
bounded local copy so no operator has to copy files by hand, and so no request ever
depends on GitHub being reachable:

* ``refresh`` downloads both files once, validates them (a list of members with
  Bioguide ids), keeps historical members whose service reaches the STOCK Act PTR era
  (a term ending on or after ``HISTORICAL_SINCE``), and writes them plus a manifest
  (source URLs, retrieval time, source SHA-256, ``Last-Modified``/``ETag``, publishing
  commit when GitHub answers, member counts) atomically — manifest last;
* ``load`` reads only the local copy. A missing or unreadable cache is a state, and
  identity resolution falls back to the registry-free rules; nothing is guessed.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from ..local_state.external_cache import read_manifest, write_json_atomic
from .identity import OfficialRegistry

SOURCE = "unitedstates/congress-legislators"
SOURCE_LICENSE = "CC0-1.0"
BASE_URL = "https://unitedstates.github.io/congress-legislators/"
FILES = ("legislators-current.json", "legislators-historical.json")
REVISION_URL = "https://api.github.com/repos/unitedstates/congress-legislators/commits?sha=gh-pages&per_page=1"
CACHE_RELATIVE = Path("registries") / "congress-legislators"
MANIFEST_NAME = "manifest.json"
HISTORICAL_SINCE = date(2012, 1, 1)
REFRESH_AFTER_S = 7 * 24 * 3600
MAX_BYTES = 64 * 1024 * 1024
USER_AGENT = "integrated-market-platform-public-records/1.0"

#: url -> (status, body, headers)
Fetcher = Callable[[str], tuple[int, bytes, dict[str, str]]]


class RegistryRefreshError(Exception):
    """A stable code only (never a URL or body)."""


def _fetch(url: str) -> tuple[int, bytes, dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read(MAX_BYTES + 1)
            headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
            return int(getattr(response, "status", 200)), body, headers
    except urllib.error.HTTPError as exc:
        return exc.code, b"", {}


def _members(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise RegistryRefreshError("REGISTRY_NOT_A_LIST")
    rows = [row for row in payload if isinstance(row, dict) and str((row.get("id") or {}).get("bioguide") or "").strip()]
    if not rows:
        raise RegistryRefreshError("REGISTRY_EMPTY")
    return rows


def _serves_since(row: dict[str, Any], since: date) -> bool:
    for term in row.get("terms") or []:
        try:
            if date.fromisoformat(str(term.get("end"))) >= since:
                return True
        except (TypeError, ValueError):
            continue
    return False


def refresh(cache_dir: Path, *, fetch: Fetcher = _fetch, now: Callable[[], datetime] = lambda: datetime.now(UTC)
            ) -> dict[str, Any]:
    """Download, validate, and atomically replace the local copy. Raises RegistryRefreshError."""

    files: dict[str, Any] = {}
    bodies: dict[str, list[dict[str, Any]]] = {}
    for name in FILES:
        try:
            status, body, headers = fetch(BASE_URL + name)
        except (urllib.error.URLError, OSError) as exc:
            raise RegistryRefreshError("REGISTRY_NETWORK_ERROR") from exc
        if status != 200:
            raise RegistryRefreshError(f"REGISTRY_HTTP_{status}")
        if len(body) > MAX_BYTES:
            raise RegistryRefreshError("REGISTRY_TOO_LARGE")
        try:
            rows = _members(json.loads(body.decode("utf-8")))
        except (UnicodeDecodeError, ValueError) as exc:
            raise RegistryRefreshError("REGISTRY_INVALID_JSON") from exc
        kept = rows if name == "legislators-current.json" else [row for row in rows if _serves_since(row, HISTORICAL_SINCE)]
        bodies[name] = kept
        files[name] = {"url": BASE_URL + name, "source_sha256": hashlib.sha256(body).hexdigest(), "source_bytes": len(body),
                       "source_members": len(rows), "kept_members": len(kept),
                       "last_modified": headers.get("last-modified"), "etag": headers.get("etag")}
    revision = None
    try:
        status, body, _ = fetch(REVISION_URL)
        if status == 200:
            head = json.loads(body.decode("utf-8"))
            if isinstance(head, list) and head and isinstance(head[0], dict):
                revision = {"commit": str(head[0].get("sha") or "") or None,
                            "committed_at": ((head[0].get("commit") or {}).get("committer") or {}).get("date")}
    except (urllib.error.URLError, OSError, ValueError):
        revision = None  # provenance nicety only; the content hashes above are authoritative
    cache_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in bodies.items():
        write_json_atomic(cache_dir / name, rows)
    manifest = {"schema_version": "imp-congress-registry/1.0.0", "source": SOURCE, "license": SOURCE_LICENSE,
                "retrieved_at": now().strftime("%Y-%m-%dT%H:%M:%SZ"), "revision": revision, "files": files,
                "historical_filter": f"historical members with a term ending on or after {HISTORICAL_SINCE.isoformat()}",
                "parse_state": "PARSED"}
    write_json_atomic(cache_dir / MANIFEST_NAME, manifest)
    return manifest


@dataclass(frozen=True, slots=True)
class CachedRegistry:
    registry: OfficialRegistry | None
    manifest: dict[str, Any] | None
    state: str                       # CURRENT | STALE | MISSING | UNREADABLE
    reason: str | None

    def describe(self) -> dict[str, Any]:
        manifest = self.manifest or {}
        return {"state": self.state, "reason": self.reason, "source": manifest.get("source"),
                "license": manifest.get("license"), "retrieved_at": manifest.get("retrieved_at"),
                "revision": (manifest.get("revision") or {}).get("commit"),
                "files": {name: {key: item.get(key) for key in ("source_sha256", "kept_members", "last_modified")}
                          for name, item in (manifest.get("files") or {}).items()}}


def manifest_state(cache_dir: Path, *, now: Callable[[], datetime] = lambda: datetime.now(UTC)
                   ) -> tuple[dict[str, Any] | None, str, str | None]:
    """(manifest, CURRENT | STALE | MISSING, reason) from the small manifest alone (no registry parse)."""

    manifest = read_manifest(cache_dir / MANIFEST_NAME)
    if manifest is None:
        return None, "MISSING", "REGISTRY_NOT_DOWNLOADED"
    try:
        retrieved = datetime.strptime(str(manifest.get("retrieved_at")), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        stale = (now() - retrieved).total_seconds() > REFRESH_AFTER_S
    except ValueError:
        stale = True
    return manifest, ("STALE" if stale else "CURRENT"), ("REFRESH_DUE" if stale else None)


def load(cache_dir: Path, *, now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> CachedRegistry:
    manifest, state, reason = manifest_state(cache_dir, now=now)
    if manifest is None:
        return CachedRegistry(None, None, state, reason)
    try:
        registry = OfficialRegistry.from_paths([cache_dir / name for name in FILES])
    except (OSError, ValueError):
        return CachedRegistry(None, manifest, "UNREADABLE", "REGISTRY_CACHE_UNREADABLE")
    if not registry.members:
        return CachedRegistry(None, manifest, "UNREADABLE", "REGISTRY_CACHE_EMPTY")
    registry = OfficialRegistry(registry.members, source=f"{SOURCE}@{manifest.get('retrieved_at')}")
    return CachedRegistry(registry, manifest, state, reason)


__all__ = ["CACHE_RELATIVE", "CachedRegistry", "FILES", "HISTORICAL_SINCE", "REFRESH_AFTER_S", "RegistryRefreshError",
           "SOURCE", "load", "manifest_state", "refresh"]
