"""Item 9 prospective receipt discovery with historical-corpus isolation."""

from __future__ import annotations

from pathlib import Path

ITEM9_RECEIPT_GLOB = "*.json"

# Path segments that identify historical development storage (never Item 9 scan roots).
_HISTORICAL_DEVELOPMENT_MARKERS: frozenset[str] = frozenset(
    {
        "historical-development",
        "historical-development-corpus",
        "historical-rth-development",
        "historical_development",
    }
)

ITEM9_DISCOVERY_REFUSED_HISTORICAL_ROOT = "ITEM9_DISCOVERY_REFUSED_HISTORICAL_ROOT"
ITEM9_DISCOVERY_REFUSED_NOT_DIRECTORY = "ITEM9_DISCOVERY_REFUSED_NOT_DIRECTORY"


def is_historical_development_storage_path(path: Path) -> bool:
    """True when any path component names a historical development corpus root."""

    for part in path.parts:
        if part.lower() in _HISTORICAL_DEVELOPMENT_MARKERS:
            return True
    return False


def validate_item9_prospective_receipt_output_dir(receipt_dir: Path) -> dict[str, object]:
    """Fail closed before persisting Item 9 receipts under a historical development tree."""

    if is_historical_development_storage_path(receipt_dir):
        return {
            "ok": False,
            "reason_code": ITEM9_DISCOVERY_REFUSED_HISTORICAL_ROOT,
            "path": str(receipt_dir),
        }
    return {"ok": True, "reason_code": None, "path": str(receipt_dir)}


def iter_item9_prospective_receipt_paths(receipt_dir: Path) -> tuple[Path, ...]:
    """Enumerate governed Item 9 receipt JSON files (single directory, no historical roots)."""

    gate = validate_item9_prospective_receipt_output_dir(receipt_dir)
    if not gate["ok"]:
        raise ValueError(str(gate["reason_code"]))
    if not receipt_dir.is_dir():
        raise ValueError(ITEM9_DISCOVERY_REFUSED_NOT_DIRECTORY)
    return tuple(sorted(path for path in receipt_dir.glob(ITEM9_RECEIPT_GLOB) if path.is_file()))


def filter_item9_prospective_scan_roots(roots: tuple[Path, ...]) -> tuple[Path, ...]:
    """Drop historical development directories from operator-supplied scan roots."""

    return tuple(path for path in roots if not is_historical_development_storage_path(path))


__all__ = [
    "ITEM9_DISCOVERY_REFUSED_HISTORICAL_ROOT",
    "ITEM9_DISCOVERY_REFUSED_NOT_DIRECTORY",
    "ITEM9_RECEIPT_GLOB",
    "filter_item9_prospective_scan_roots",
    "is_historical_development_storage_path",
    "iter_item9_prospective_receipt_paths",
    "validate_item9_prospective_receipt_output_dir",
]
