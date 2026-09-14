"""Stub adapters against non-empirical research export fixtures (Track D owns real export)."""

from __future__ import annotations

from typing import Any

from ..errors import Wave1HarnessError


def validation_manifest_from_export(export_manifest: dict[str, Any]) -> dict[str, Any] | None:
    """Return embedded validation dataset manifest when present on the export stub."""
    direct = export_manifest.get("validation_dataset_manifest")
    if isinstance(direct, dict):
        return direct
    meta = export_manifest.get("metadata")
    if isinstance(meta, dict):
        nested = meta.get("validation_dataset_manifest")
        if isinstance(nested, dict):
            return nested
    return None


def examples_from_export_stub(export_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Load example rows shipped alongside a non-empirical export stub."""
    rows = export_manifest.get("wave1_examples")
    if isinstance(rows, list):
        return [dict(row) for row in rows]
    dataset = export_manifest.get("dataset_manifest")
    if isinstance(dataset, dict):
        member_files = dataset.get("member_files")
        if isinstance(member_files, list):
            for entry in member_files:
                if isinstance(entry, dict) and entry.get("role") == "WAVE1_EXAMPLES":
                    inline = entry.get("inline_rows")
                    if isinstance(inline, list):
                        return [dict(row) for row in inline]
    raise Wave1HarnessError(
        "W1_EXPORT_STUB_EXAMPLES_MISSING",
        details={"export_fingerprint": export_manifest.get("export_fingerprint")},
    )
