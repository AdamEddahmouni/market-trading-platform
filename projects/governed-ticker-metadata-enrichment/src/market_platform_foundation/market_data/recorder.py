"""Bounded observational capture with session manifest."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..canonical import sha256_bytes
from .capture import CAPTURE_SCHEMA_VERSION, append_envelope, ProviderEnvelope


@dataclass
class ObservationalRecorder:
    capture_id: str
    root: Path
    max_records: int = 5000
    max_bytes: int = 50 * 1024 * 1024
    rotate_on_bound: bool = False
    events_path: Path = field(init=False)
    manifest_path: Path = field(init=False)
    started_ns: int = field(default_factory=time.time_ns)
    event_count: int = 0
    bytes_written: int = 0
    disconnects: int = 0
    reconnects: int = 0
    rotation_index: int = 0
    rotation_files: list[str] = field(default_factory=list)
    quality_summary: dict[str, int] = field(default_factory=dict)
    quote_count: int = 0
    trade_count: int = 0
    book_count: int = 0
    duplicate_count: int = 0
    sequence_anomalies: int = 0
    total_events: int = 0

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / f"{self.capture_id}.jsonl"
        self.manifest_path = self.root / f"{self.capture_id}.manifest.json"
        self.rotation_files = [self.events_path.name]

    def _rotate(self) -> None:
        self.rotation_index += 1
        self.events_path = self.root / f"{self.capture_id}.part{self.rotation_index}.jsonl"
        self.rotation_files.append(self.events_path.name)
        self.event_count = 0
        self.bytes_written = 0

    def append(self, record: dict[str, Any], admission_result: dict[str, Any]) -> None:
        if self.event_count >= self.max_records or self.bytes_written >= self.max_bytes:
            if self.rotate_on_bound:
                self._rotate()
            else:
                self.quality_summary["CAPTURE_BOUND_EXCEEDED"] = self.quality_summary.get("CAPTURE_BOUND_EXCEEDED", 0) + 1
                return
        envelope = ProviderEnvelope(
            provider=str(record.get("provider") or "moomoo"),
            instrument_id=str(record.get("instrument_id") or ""),
            capability=str(record.get("capability") or ""),
            provider_symbol=str(record.get("provider_symbol") or ""),
            sequence=record.get("sequence"),
            clocks=dict(record.get("clocks") or {}),
            raw_payload=dict(record.get("raw_payload") or {}),
            schema_version=CAPTURE_SCHEMA_VERSION,
            quality_flags=tuple(admission_result.get("quality_flags") or ()),
        )
        append_envelope(self.events_path, envelope, max_records=self.max_records)
        canonical_line = json.dumps(envelope.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
        self.bytes_written += len(canonical_line.encode("utf-8"))
        self.event_count += 1
        self.total_events += 1
        display = str(admission_result.get("admission", {}).get("display", "UNKNOWN"))
        self.quality_summary[display] = self.quality_summary.get(display, 0) + 1
        cap = str(record.get("capability") or "")
        if "L1" in cap:
            self.quote_count += 1
        elif "TICK" in cap:
            self.trade_count += 1
        elif "DEPTH" in cap or "ORDER_BOOK" in cap:
            self.book_count += 1
        if any(row.get("state") == "DUPLICATE" for row in admission_result.get("observations") or [] if isinstance(row, dict)):
            self.duplicate_count += 1
        if any(row.get("state") in {"GAP", "REGRESSION"} for row in admission_result.get("observations") or [] if isinstance(row, dict)):
            self.sequence_anomalies += 1

    def finalize(
        self,
        *,
        provider: str = "moomoo",
        instruments: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ended_ns = time.time_ns()
        manifest = {
            "book_count": self.book_count,
            "bytes_written": self.bytes_written,
            "capture_id": self.capture_id,
            "disconnects": self.disconnects,
            "duplicate_count": self.duplicate_count,
            "end_time_ns": ended_ns,
            "event_counts": self.total_events,
            "events_path": str(self.events_path.name),
            "instruments": instruments or [],
            "max_bytes": self.max_bytes,
            "max_records": self.max_records,
            "provider": provider,
            "quality_summary": dict(self.quality_summary),
            "quote_count": self.quote_count,
            "reconnects": self.reconnects,
            "rotation_files": list(self.rotation_files),
            "rotation_index": self.rotation_index,
            "schema_versions": [CAPTURE_SCHEMA_VERSION],
            "sequence_anomalies": self.sequence_anomalies,
            "start_time_ns": self.started_ns,
            "trade_count": self.trade_count,
        }
        if extra:
            manifest.update(extra)
        if self.events_path.is_file():
            manifest["events_sha256"] = sha256_bytes(self.events_path.read_bytes())
        self.manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest
