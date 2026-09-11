"""FTEP-V1 protocol reference loading and document hash verification."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from market_platform_foundation.canonical import load_json_strict, sha256_bytes

from ...local_state.paths import REPO_ROOT

PROTOCOL_REF_FILENAME = "PROTOCOL_REF.json"


def campaigns_root() -> Path:
    override = os.environ.get("IMP_FORWARD_TEST_CAMPAIGNS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "artifacts" / "forward-test-campaigns"


class ProtocolRefError(ValueError):
    """Protocol reference boundary failure."""


@dataclass(frozen=True, slots=True)
class ProtocolRef:
    raw: dict[str, Any]
    path: Path

    @property
    def protocol_id(self) -> str:
        return str(self.raw.get("protocol_id") or "")

    @property
    def protocol_doc_sha256(self) -> str:
        return str(
            self.raw.get("protocol_doc_sha256")
            or self.raw.get("sha256")
            or ""
        ).upper()

    @property
    def protocol_doc_path(self) -> str:
        return str(self.raw.get("protocol_doc_path") or "")


def protocol_ref_path(
    campaign_slug: str,
    *,
    campaigns_root_override: Path | None = None,
) -> Path:
    root = campaigns_root_override or campaigns_root()
    return root / campaign_slug / PROTOCOL_REF_FILENAME


def compute_protocol_doc_sha256(doc_path: Path) -> str:
    if not doc_path.is_file():
        raise ProtocolRefError("PROTOCOL_REF_DOC_NOT_FOUND")
    return sha256_bytes(doc_path.read_bytes())


def resolve_protocol_doc_path(ref: ProtocolRef) -> Path:
    doc_path = Path(ref.protocol_doc_path)
    if doc_path.is_absolute():
        return doc_path
    return (REPO_ROOT / doc_path).resolve()


def load_protocol_ref(
    campaign_slug: str,
    *,
    campaigns_root_override: Path | None = None,
) -> ProtocolRef:
    path = protocol_ref_path(campaign_slug, campaigns_root_override=campaigns_root_override)
    if not path.is_file():
        raise ProtocolRefError("PROTOCOL_REF_NOT_FOUND")
    loaded = load_json_strict(path)
    if not isinstance(loaded, dict):
        raise ProtocolRefError("PROTOCOL_REF_INVALID")
    return ProtocolRef(raw=dict(loaded), path=path)


def verify_protocol_ref(
    campaign_slug: str,
    *,
    campaigns_root_override: Path | None = None,
) -> ProtocolRef:
    ref = load_protocol_ref(campaign_slug, campaigns_root_override=campaigns_root_override)
    if not ref.protocol_doc_path:
        raise ProtocolRefError("PROTOCOL_REF_MISSING:protocol_doc_path")
    expected = ref.protocol_doc_sha256
    if not expected:
        raise ProtocolRefError("PROTOCOL_REF_MISSING:protocol_doc_sha256")
    doc_path = resolve_protocol_doc_path(ref)
    computed = compute_protocol_doc_sha256(doc_path)
    if computed != expected:
        raise ProtocolRefError("PROTOCOL_REF_DOC_SHA256_MISMATCH")
    return ref


def assert_protocol_ref_valid(
    campaign_slug: str,
    *,
    campaigns_root_override: Path | None = None,
) -> ProtocolRef:
    return verify_protocol_ref(campaign_slug, campaigns_root_override=campaigns_root_override)


def write_test_protocol_ref(
    campaigns_root: Path,
    *,
    campaign_slug: str,
    protocol_doc_path: str | None = None,
) -> ProtocolRef:
    doc_rel = protocol_doc_path or "docs/engineering/FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md"
    doc_path = (REPO_ROOT / doc_rel).resolve()
    doc_sha256 = compute_protocol_doc_sha256(doc_path)
    payload = {
        "protocol_id": "FTEP-V1/0.1.0-PREREG",
        "protocol_version": "0.1.0-PREREG",
        "protocol_doc_path": doc_rel.replace("\\", "/"),
        "protocol_doc_sha256": doc_sha256,
        "sha256": doc_sha256,
        "campaign_slug": campaign_slug,
    }
    path = campaigns_root / campaign_slug / PROTOCOL_REF_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return load_protocol_ref(campaign_slug, campaigns_root_override=campaigns_root)
