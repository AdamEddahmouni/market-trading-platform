"""FTEP profile document references (composition only; rules remain in markdown docs)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from market_platform_foundation.canonical import sha256_bytes

from ...local_state.paths import REPO_ROOT

_CLASSIFICATION_RE = re.compile(r"\*\*Classification:\*\*\s*`([^`]+)`")

_PROFILE_DOC_PATHS: dict[str, str] = {
    "FTEP_CORE_V1": "docs/engineering/ftep/FTEP_CORE_V1.md",
    "FUTURES_PROFILE_V1": "docs/engineering/ftep/assets/FUTURES_PROFILE_V1.md",
    "US_EQUITY_PROFILE_V1": "docs/engineering/ftep/assets/US_EQUITY_PROFILE_V1.md",
    "NEWS_CATALYST_PROFILE_V1": (
        "docs/engineering/ftep/strategies/NEWS_CATALYST_PROFILE_V1.md"
    ),
    "CATALYST_TAXONOMY_CONTRACT_V1": (
        "docs/engineering/ftep/strategies/CATALYST_TAXONOMY_CONTRACT_V1.md"
    ),
}

_FTEP_V1_001_STACK: tuple[str, ...] = (
    "FTEP_CORE_V1",
    "FUTURES_PROFILE_V1",
    "NEWS_CATALYST_PROFILE_V1",
)

_FTEP_V1_002_STACK: tuple[str, ...] = (
    "FTEP_CORE_V1",
    "US_EQUITY_PROFILE_V1",
    "NEWS_CATALYST_PROFILE_V1",
    "CATALYST_TAXONOMY_CONTRACT_V1",
)


class FtepProfileRefError(ValueError):
    """Profile reference boundary failure."""


@dataclass(frozen=True, slots=True)
class FtepProfileRef:
    profile_version_id: str
    doc_path: Path
    classification: str | None
    doc_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_version_id": self.profile_version_id,
            "doc_path": self.doc_path.as_posix(),
            "classification": self.classification,
            "doc_sha256": self.doc_sha256,
        }


def profile_doc_path(profile_version_id: str, *, repo_root: Path | None = None) -> Path:
    relative = _PROFILE_DOC_PATHS.get(profile_version_id)
    if relative is None:
        raise FtepProfileRefError(f"unknown FTEP profile version id: {profile_version_id}")
    root = repo_root or REPO_ROOT
    return (root / relative).resolve()


def _parse_classification(text: str) -> str | None:
    match = _CLASSIFICATION_RE.search(text)
    if not match:
        return None
    return match.group(1).strip()


def load_ftep_profile_ref(
    profile_version_id: str,
    *,
    repo_root: Path | None = None,
) -> FtepProfileRef:
    path = profile_doc_path(profile_version_id, repo_root=repo_root)
    if not path.is_file():
        raise FtepProfileRefError(f"FTEP profile document missing: {path}")
    raw = path.read_bytes()
    return FtepProfileRef(
        profile_version_id=profile_version_id,
        doc_path=path,
        classification=_parse_classification(raw.decode("utf-8")),
        doc_sha256=sha256_bytes(raw).upper(),
    )


def load_ftep_v1_001_profile_stack(
    *,
    repo_root: Path | None = None,
) -> tuple[FtepProfileRef, ...]:
    """Core → asset-class → strategy profile refs for the ES-news first campaign."""
    return tuple(
        load_ftep_profile_ref(profile_id, repo_root=repo_root)
        for profile_id in _FTEP_V1_001_STACK
    )


def load_ftep_v1_002_profile_stack(
    *,
    repo_root: Path | None = None,
) -> tuple[FtepProfileRef, ...]:
    """Core → US equity asset profile → news/catalyst strategy + taxonomy contract."""
    return tuple(
        load_ftep_profile_ref(profile_id, repo_root=repo_root)
        for profile_id in _FTEP_V1_002_STACK
    )


def profile_stack_to_manifest_bindings(
    stack: tuple[FtepProfileRef, ...],
) -> dict[str, Any]:
    """Manifest-shaped binding map without duplicating profile rule text."""
    return {
        "ftep_core_version": next(
            (row.profile_version_id for row in stack if row.profile_version_id == "FTEP_CORE_V1"),
            None,
        ),
        "asset_profile_version": next(
            (
                row.profile_version_id
                for row in stack
                if row.profile_version_id
                in {"FUTURES_PROFILE_V1", "US_EQUITY_PROFILE_V1"}
            ),
            None,
        ),
        "catalyst_taxonomy_version": next(
            (
                row.profile_version_id
                for row in stack
                if row.profile_version_id == "CATALYST_TAXONOMY_CONTRACT_V1"
            ),
            None,
        ),
        "strategy_profile_version": next(
            (
                row.profile_version_id
                for row in stack
                if row.profile_version_id == "NEWS_CATALYST_PROFILE_V1"
            ),
            None,
        ),
        "profile_doc_bindings": [row.to_dict() for row in stack],
    }
