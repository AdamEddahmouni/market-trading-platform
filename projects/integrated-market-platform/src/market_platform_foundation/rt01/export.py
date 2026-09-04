"""RT-01 trace export and readback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .span import TraceSpan


def export_document(
    spans: list[TraceSpan],
    *,
    counts: dict[str, int] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema_version": "rt01.trace_export/1.0.0",
        "span_count": len(spans),
        "spans": [span.to_dict() for span in spans],
    }
    if counts is not None:
        doc["collector_counts"] = dict(counts)
    if metadata is not None:
        doc["metadata"] = dict(metadata)
    return doc


def write_export(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_export(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def spans_from_export(document: dict[str, Any]) -> list[TraceSpan]:
    rows = document.get("spans")
    if not isinstance(rows, list):
        return []
    return [TraceSpan.from_dict(row) for row in rows if isinstance(row, dict)]


__all__ = ["export_document", "read_export", "spans_from_export", "write_export"]
