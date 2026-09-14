"""QR-01 MATLAB toolbox honesty recorder (no MATLAB runtime required)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MATLAB_TOOLBOX_MANIFEST_SCHEMA_VERSION = "matlab_toolbox_manifest/1.0.0"
CLOUD_UNAVAILABLE_HOST_ID = "UNAVAILABLE"
REQUIRED_PRIMARY_PRODUCTS = (
    "MATLAB",
    "Econometrics Toolbox",
    "Statistics and Machine Learning Toolbox",
    "Optimization Toolbox",
    "Financial Toolbox",
)
PROHIBITED_CANONICAL_PRODUCTS = frozenset({"Datafeed Toolbox", "Database Toolbox"})
ALLOWED_CLASSES = frozenset(
    {
        "PRIMARY",
        "HIGH_VALUE_SPECIALIZED",
        "SPECIALIZED",
        "ON_DEMAND",
        "OPTIONAL",
        "PROHIBITED_AS_CANONICAL",
    }
)
ALLOWED_STATUSES = frozenset({"INSTALLED", "LICENSED_UNAVAILABLE", "UNAVAILABLE", "PROHIBITED"})
ALLOWED_SMOKE = frozenset({"NOT_RUN", "PASS", "BLOCKED_NO_MATLAB"})
REQUIRED_MANIFEST_KEYS = (
    "schema_version",
    "matlab_release",
    "recorded_at_ns",
    "recorded_host_id",
    "repository_head_sha",
    "toolboxes",
    "isolation",
    "smoke_status",
)


def matlab_environment_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "research" / "matlab" / "environment"


def toolbox_manifest_schema_path() -> Path:
    return matlab_environment_dir() / "toolbox_manifest.schema.json"


def toolbox_manifest_example_path() -> Path:
    return matlab_environment_dir() / "toolbox_manifest.example.json"


def load_toolbox_manifest_example() -> dict[str, Any]:
    payload = json.loads(toolbox_manifest_example_path().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MATLAB_TOOLBOX_EXAMPLE_INVALID")
    return payload


def validate_toolbox_manifest(manifest: dict[str, Any]) -> None:
    """Fail closed on dishonest INSTALLED claims, production coupling, or prohibited ingest."""
    missing = [key for key in REQUIRED_MANIFEST_KEYS if key not in manifest]
    if missing:
        raise ValueError(f"MATLAB_TOOLBOX_MANIFEST_MISSING_FIELDS:{','.join(missing)}")
    if manifest.get("schema_version") != MATLAB_TOOLBOX_MANIFEST_SCHEMA_VERSION:
        raise ValueError("MATLAB_TOOLBOX_SCHEMA_VERSION_MISMATCH")
    isolation = manifest.get("isolation")
    if not isinstance(isolation, dict):
        raise ValueError("MATLAB_TOOLBOX_ISOLATION_MISSING")
    if isolation.get("production_runtime") is not False:
        raise ValueError("MATLAB_PRODUCTION_RUNTIME_FORBIDDEN")
    if isolation.get("mode_authority") != "NONE":
        raise ValueError("MATLAB_MODE_AUTHORITY_MUST_BE_NONE")
    if isolation.get("paper_live_broker") != "DENIED":
        raise ValueError("MATLAB_PAPER_LIVE_BROKER_MUST_BE_DENIED")
    smoke = manifest.get("smoke_status")
    if smoke not in ALLOWED_SMOKE:
        raise ValueError("MATLAB_SMOKE_STATUS_INVALID")
    release = str(manifest.get("matlab_release") or "")
    if not release:
        raise ValueError("MATLAB_RELEASE_REQUIRED")
    if release == "UNAVAILABLE" and smoke == "PASS":
        raise ValueError("MATLAB_SMOKE_PASS_WITHOUT_RUNTIME")
    recorded_at = manifest.get("recorded_at_ns")
    if type(recorded_at) is not int or recorded_at < 0:
        raise ValueError("MATLAB_RECORDED_AT_NS_INVALID")
    toolboxes = manifest.get("toolboxes")
    if not isinstance(toolboxes, list) or not toolboxes:
        raise ValueError("MATLAB_TOOLBOXES_REQUIRED")
    products: list[str] = []
    for entry in toolboxes:
        if not isinstance(entry, dict):
            raise ValueError("MATLAB_TOOLBOX_ENTRY_INVALID")
        product = str(entry.get("product") or "")
        klass = entry.get("class")
        status = entry.get("status")
        if not product:
            raise ValueError("MATLAB_TOOLBOX_PRODUCT_REQUIRED")
        if klass not in ALLOWED_CLASSES:
            raise ValueError(f"MATLAB_TOOLBOX_CLASS_INVALID:{product}")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"MATLAB_TOOLBOX_STATUS_INVALID:{product}")
        if product in PROHIBITED_CANONICAL_PRODUCTS:
            if klass != "PROHIBITED_AS_CANONICAL" or status != "PROHIBITED":
                raise ValueError(f"MATLAB_PROHIBITED_TOOLBOX_NOT_LOCKED:{product}")
        if status == "INSTALLED" and release == "UNAVAILABLE":
            raise ValueError(f"MATLAB_INSTALLED_WITHOUT_RELEASE:{product}")
        products.append(product)
    for required in REQUIRED_PRIMARY_PRODUCTS:
        if required not in products:
            raise ValueError(f"MATLAB_PRIMARY_PRODUCT_MISSING:{required}")
    for prohibited in PROHIBITED_CANONICAL_PRODUCTS:
        if prohibited not in products:
            raise ValueError(f"MATLAB_PROHIBITED_PRODUCT_MISSING:{prohibited}")


def cloud_unavailable_toolbox_manifest() -> dict[str, Any]:
    """Committed cloud/CI posture: every entitled PRIMARY row is UNAVAILABLE."""
    return load_toolbox_manifest_example()


__all__ = [
    "CLOUD_UNAVAILABLE_HOST_ID",
    "MATLAB_TOOLBOX_MANIFEST_SCHEMA_VERSION",
    "cloud_unavailable_toolbox_manifest",
    "load_toolbox_manifest_example",
    "matlab_environment_dir",
    "toolbox_manifest_example_path",
    "toolbox_manifest_schema_path",
    "validate_toolbox_manifest",
]
