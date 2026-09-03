"""Reader for an already-parsed synthetic structural manifest."""

from __future__ import annotations


class ManifestOnlyReader:
    """Expose keys from synthetic structure without filesystem discovery."""

    def read(self, manifest: dict[str, object]) -> list[str]:
        if manifest.get("fixture_kind") != "SYNTHETIC_STRUCTURE_ONLY":
            raise ValueError("fixture_kind must be SYNTHETIC_STRUCTURE_ONLY")
        return sorted(manifest)

