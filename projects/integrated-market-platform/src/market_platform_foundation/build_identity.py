"""Immutable build identity that does not depend on a live git checkout (AUD-037, AUD-040).

The serving tree is a copy of the application without ``.git`` metadata, so ``git_ref.read_git_head`` returns None
there. A release writes ``BUILD-IDENTITY.json`` at the application root when it is applied
(``tools/release/write_build_identity.py``, also called by ``tools/release_candidate/apply_release.py``). The
runtime reads it; it never guesses a revision.

Resolution order for the source revision:
  1. ``IMP_BUILD_REVISION`` (an explicit operator override; must be a 40-hex commit)
  2. ``BUILD-IDENTITY.json`` at the application root (or ``IMP_BUILD_IDENTITY_FILE``)
  3. git HEAD when the code runs from a checkout
  4. none: callers record the explicit ``UNAVAILABLE`` sentinel

A file that exists but is unreadable or malformed is reported as ``INVALID_BUILD_IDENTITY`` and never falls through
to git: a deployment that claims an identity it cannot prove must not borrow one from elsewhere.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from .git_ref import read_git_head

BUILD_IDENTITY_FILENAME = "BUILD-IDENTITY.json"
BUILD_IDENTITY_SCHEMA = "imp.build-identity/1"
ENV_REVISION = "IMP_BUILD_REVISION"
ENV_FILE = "IMP_BUILD_IDENTITY_FILE"
UNAVAILABLE = "UNAVAILABLE"

SOURCE_ENV = "ENV"
SOURCE_FILE = "BUILD_IDENTITY_FILE"
SOURCE_GIT = "GIT_CHECKOUT"
SOURCE_INVALID = "INVALID_BUILD_IDENTITY"
SOURCE_NONE = "UNAVAILABLE"

_REVISION = re.compile(r"[0-9a-f]{40}")
# Application root: src/market_platform_foundation/build_identity.py -> parents[2].
APPLICATION_ROOT = Path(__file__).resolve().parents[2]
_FILE_CACHE: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}


def valid_revision(value: Any) -> bool:
    return isinstance(value, str) and _REVISION.fullmatch(value) is not None


def identity_path(*, root: Path | None = None, environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    explicit = env.get(ENV_FILE)
    if explicit:
        return Path(explicit)
    return (root or APPLICATION_ROOT) / BUILD_IDENTITY_FILENAME


def _read_file(path: Path) -> dict[str, Any] | None:
    """Parsed identity file, or None when absent. Cached by (mtime, size); malformed content raises ValueError."""
    try:
        stat = path.stat()
    except OSError:
        return None
    key = (stat.st_mtime_ns, stat.st_size)
    cached = _FILE_CACHE.get(str(path))
    if cached is not None and cached[0] == key:
        return cached[1]
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"BUILD_IDENTITY_UNREADABLE:{type(exc).__name__}") from exc
    if not isinstance(body, dict) or body.get("schema") != BUILD_IDENTITY_SCHEMA:
        raise ValueError("BUILD_IDENTITY_SCHEMA_UNKNOWN")
    if not valid_revision(body.get("source_revision")):
        raise ValueError("BUILD_IDENTITY_REVISION_INVALID")
    _FILE_CACHE[str(path)] = (key, body)
    return body


def resolve_build_identity(*, root: Path | None = None, environ: Mapping[str, str] | None = None,
                           git_start: Path | None = None) -> dict[str, Any]:
    """Where the running code's source revision comes from. Never raises; never invents a revision."""
    env = os.environ if environ is None else environ
    override = env.get(ENV_REVISION)
    if override:
        if valid_revision(override):
            return dict(source_revision=override, build_id=None, release=None, revision_source=SOURCE_ENV)
        return dict(source_revision=None, build_id=None, release=None, revision_source=SOURCE_INVALID,
                    problem="IMP_BUILD_REVISION_NOT_A_COMMIT")
    path = identity_path(root=root, environ=env)
    try:
        body = _read_file(path)
    except ValueError as exc:
        return dict(source_revision=None, build_id=None, release=None, revision_source=SOURCE_INVALID,
                    problem=str(exc), identity_file=str(path))
    if body is not None:
        return dict(source_revision=body["source_revision"], build_id=body.get("build_id"),
                    release=body.get("release"), built_at=body.get("built_at"),
                    manifest_sha256=body.get("manifest_sha256"), revision_source=SOURCE_FILE,
                    identity_file=str(path))
    head = read_git_head(start=git_start) if git_start is not None else read_git_head()
    if valid_revision(head):
        return dict(source_revision=head, build_id=None, release=None, revision_source=SOURCE_GIT)
    return dict(source_revision=None, build_id=None, release=None, revision_source=SOURCE_NONE)


def source_revision(**kwargs: Any) -> str | None:
    """The 40-hex source revision of the running code, or None when it cannot be established."""
    return resolve_build_identity(**kwargs)["source_revision"]


def provenance_fields(**kwargs: Any) -> dict[str, Any]:
    """Additive per-record fields: source revision, build id and where the revision came from."""
    identity = resolve_build_identity(**kwargs)
    return {
        "git_sha": identity["source_revision"] or UNAVAILABLE,
        "build_id": identity.get("build_id") or UNAVAILABLE,
        "revision_source": identity["revision_source"],
    }


__all__ = [
    "BUILD_IDENTITY_FILENAME",
    "BUILD_IDENTITY_SCHEMA",
    "ENV_FILE",
    "ENV_REVISION",
    "UNAVAILABLE",
    "identity_path",
    "provenance_fields",
    "resolve_build_identity",
    "source_revision",
    "valid_revision",
]
