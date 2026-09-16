"""Item 7 — fail-closed upstream writer for lawful SNAPSHOT_BBO capture envelopes.

Appends validated ``market_data.provider_envelope`` JSONL under the operator
``IMP_STATE_DIR`` capture root consumed by ``opend_capture_ledger``. Does not
mint forecasts, fabricate BBO, or claim empirical corpus readiness.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ...local_state.paths import state_dir
from ...market_data.capture import DEFAULT_MAX_RECORDS
from ...market_data.moomoo_snapshot_bbo import (
    BboClocks,
    BboDiagnostic,
    build_capture_envelope_from_vendor_snapshot,
)
from ..outcomes.opend_capture_ledger import iter_jsonl_envelopes

CANONICAL_CAPTURE_FILENAME = "item7-opend-prospective-capture.jsonl"
CANONICAL_REFUSAL_FILENAME = "item7-opend-prospective-capture.refusals.jsonl"
RECEIPT_ARTIFACT_KIND = "item7_opend_capture_append_receipt_v1"

DISPOSITION_APPENDED = "APPENDED"
DISPOSITION_REFUSED = "REFUSED"
DISPOSITION_DRY_RUN = "DRY_RUN_WOULD_APPEND"

REFUSAL_IMP_STATE_DIR_MISSING = "IMP_STATE_DIR_MISSING"
REFUSAL_PROBE_BLOCKED = "ITEM7_PROBE_BLOCKED"
REFUSAL_CAPTURE_BOUND_EXCEEDED = "CAPTURE_BOUND_EXCEEDED"


class Item7CaptureWriterError(RuntimeError):
    """Operator misconfiguration or hard refusal."""


@dataclass(frozen=True, slots=True)
class Item7CaptureAppendResult:
    disposition: str
    capture_path: str | None
    sequence: int | None
    refusal_reason: str | None
    envelope: dict[str, Any] | None
    diagnostic: dict[str, Any] | None
    receipt: dict[str, Any]
    auto_persist: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_kind": RECEIPT_ARTIFACT_KIND,
            "auto_persist": self.auto_persist,
            "capture_path": self.capture_path,
            "diagnostic": self.diagnostic,
            "disposition": self.disposition,
            "envelope_capability": (
                str(self.envelope.get("capability")) if self.envelope is not None else None
            ),
            "refusal_reason": self.refusal_reason,
            "sequence": self.sequence,
        }


def canonical_item7_opend_capture_path(
    *,
    capture_path: Path | None = None,
    require_imp_state_dir: bool = True,
) -> Path:
    """Resolve governed operator capture JSONL (under ``IMP_STATE_DIR/captures``)."""

    if capture_path is not None:
        return capture_path.expanduser().resolve()
    if require_imp_state_dir and not os.environ.get("IMP_STATE_DIR", "").strip():
        raise Item7CaptureWriterError(REFUSAL_IMP_STATE_DIR_MISSING)
    root = state_dir(create=True)
    return (root / "captures" / CANONICAL_CAPTURE_FILENAME).resolve()


def canonical_item7_refusal_path(capture_path: Path) -> Path:
    return capture_path.parent / CANONICAL_REFUSAL_FILENAME


def next_capture_sequence(capture_path: Path) -> int:
    if not capture_path.is_file():
        return 1
    max_seq = 0
    for _line_index, record, parse_error in iter_jsonl_envelopes(capture_path):
        if parse_error is not None or record is None:
            continue
        seq = record.get("sequence")
        if isinstance(seq, int) and seq > max_seq:
            max_seq = seq
    return max_seq + 1


def _count_jsonl_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _append_jsonl_line(path: Path, payload: dict[str, Any], *, max_records: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if _count_jsonl_lines(path) >= max_records:
        raise Item7CaptureWriterError(REFUSAL_CAPTURE_BOUND_EXCEEDED)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _receipt(
    *,
    disposition: str,
    capture_path: Path | None,
    sequence: int | None,
    refusal_reason: str | None,
    envelope: dict[str, Any] | None,
    diagnostic: BboDiagnostic | None,
    auto_persist: dict[str, Any] | None = None,
) -> Item7CaptureAppendResult:
    diag_dict = diagnostic.to_dict() if diagnostic is not None else None
    receipt_body = {
        "artifact_kind": RECEIPT_ARTIFACT_KIND,
        "auto_persist": auto_persist,
        "capture_path": str(capture_path) if capture_path is not None else None,
        "disposition": disposition,
        "refusal_reason": refusal_reason,
        "sequence": sequence,
    }
    return Item7CaptureAppendResult(
        disposition=disposition,
        capture_path=str(capture_path) if capture_path is not None else None,
        sequence=sequence,
        refusal_reason=refusal_reason,
        envelope=envelope,
        diagnostic=diag_dict,
        receipt=receipt_body,
        auto_persist=auto_persist,
    )


def append_vendor_snapshot_capture(
    row: Mapping[str, Any],
    *,
    clocks: BboClocks,
    capture_path: Path | None = None,
    require_imp_state_dir: bool = True,
    sequence: int | None = None,
    dry_run: bool = False,
    write_failure_receipt: bool = False,
    max_records: int = DEFAULT_MAX_RECORDS,
    auto_persist: bool = True,
    as_of_ns: int | None = None,
    session_start_ns: int | None = None,
    contributor_path: Path | None = None,
    forecast_path: Path | None = None,
    bind_expected_account_id: str | None = None,
    bind_expected_mode: str | None = None,
    register_ledger: bool = True,
) -> Item7CaptureAppendResult:
    """Build capture envelope from vendor snapshot row and append when lawful."""

    try:
        path = canonical_item7_opend_capture_path(
            capture_path=capture_path,
            require_imp_state_dir=require_imp_state_dir,
        )
    except Item7CaptureWriterError as exc:
        return _receipt(
            disposition=DISPOSITION_REFUSED,
            capture_path=None,
            sequence=None,
            refusal_reason=str(exc),
            envelope=None,
            diagnostic=None,
        )

    seq = sequence if sequence is not None else next_capture_sequence(path)
    mapping = build_capture_envelope_from_vendor_snapshot(row, clocks=clocks, sequence=seq)
    if mapping.envelope is None:
        result = _receipt(
            disposition=DISPOSITION_REFUSED,
            capture_path=path,
            sequence=None,
            refusal_reason=mapping.refusal_reason,
            envelope=None,
            diagnostic=mapping.diagnostic,
        )
        if write_failure_receipt and not dry_run:
            _append_jsonl_line(
                canonical_item7_refusal_path(path),
                result.to_dict(),
                max_records=max_records,
            )
        return result

    if dry_run:
        return _receipt(
            disposition=DISPOSITION_DRY_RUN,
            capture_path=path,
            sequence=seq,
            refusal_reason=None,
            envelope=mapping.envelope,
            diagnostic=mapping.diagnostic,
        )

    try:
        _append_jsonl_line(path, mapping.envelope, max_records=max_records)
    except Item7CaptureWriterError as exc:
        result = _receipt(
            disposition=DISPOSITION_REFUSED,
            capture_path=path,
            sequence=None,
            refusal_reason=str(exc),
            envelope=None,
            diagnostic=mapping.diagnostic,
        )
        if write_failure_receipt:
            _append_jsonl_line(
                canonical_item7_refusal_path(path),
                result.to_dict(),
                max_records=max_records,
            )
        return result

    persist_receipt: dict[str, Any] | None = None
    from .item7_opend_capture_persist import maybe_auto_persist_capture_append

    persist_result = maybe_auto_persist_capture_append(
        append_disposition=DISPOSITION_APPENDED,
        envelope=mapping.envelope,
        dry_run=dry_run,
        auto_persist=auto_persist,
        capture_path=path,
        as_of_ns=as_of_ns,
        session_start_ns=session_start_ns,
        contributor_path=contributor_path,
        forecast_path=forecast_path,
        bind_expected_account_id=bind_expected_account_id,
        bind_expected_mode=bind_expected_mode,
        register_ledger=register_ledger,
    )
    if persist_result is not None:
        persist_receipt = persist_result.to_dict()

    return _receipt(
        disposition=DISPOSITION_APPENDED,
        capture_path=path,
        sequence=seq,
        refusal_reason=None,
        envelope=mapping.envelope,
        diagnostic=mapping.diagnostic,
        auto_persist=persist_receipt,
    )


def append_from_probe_diagnostic(
    row: Mapping[str, Any],
    diagnostic: BboDiagnostic,
    *,
    capture_path: Path | None = None,
    require_imp_state_dir: bool = True,
    sequence: int | None = None,
    dry_run: bool = False,
    write_failure_receipt: bool = False,
    max_records: int = DEFAULT_MAX_RECORDS,
    auto_persist: bool = True,
    as_of_ns: int | None = None,
    session_start_ns: int | None = None,
    contributor_path: Path | None = None,
    forecast_path: Path | None = None,
    bind_expected_account_id: str | None = None,
    bind_expected_mode: str | None = None,
    register_ledger: bool = True,
) -> Item7CaptureAppendResult:
    """Append when probe succeeded with validated BBO; refuse blocked probes."""

    if diagnostic.probe_status != "OK":
        try:
            path = canonical_item7_opend_capture_path(
                capture_path=capture_path,
                require_imp_state_dir=require_imp_state_dir,
            )
        except Item7CaptureWriterError:
            path = None
        result = _receipt(
            disposition=DISPOSITION_REFUSED,
            capture_path=path,
            sequence=None,
            refusal_reason=diagnostic.block_reason or REFUSAL_PROBE_BLOCKED,
            envelope=None,
            diagnostic=diagnostic,
        )
        if write_failure_receipt and path is not None and not dry_run:
            _append_jsonl_line(
                canonical_item7_refusal_path(path),
                result.to_dict(),
                max_records=max_records,
            )
        return result

    clocks = diagnostic.clocks
    if clocks is None:
        return _receipt(
            disposition=DISPOSITION_REFUSED,
            capture_path=None,
            sequence=None,
            refusal_reason="SNAPSHOT_BBO_MISSING_PROBE_CLOCKS",
            envelope=None,
            diagnostic=diagnostic,
        )
    return append_vendor_snapshot_capture(
        row,
        clocks=clocks,
        capture_path=capture_path,
        require_imp_state_dir=require_imp_state_dir,
        sequence=sequence,
        dry_run=dry_run,
        write_failure_receipt=write_failure_receipt,
        max_records=max_records,
        auto_persist=auto_persist,
        as_of_ns=as_of_ns,
        session_start_ns=session_start_ns,
        contributor_path=contributor_path,
        forecast_path=forecast_path,
        bind_expected_account_id=bind_expected_account_id,
        bind_expected_mode=bind_expected_mode,
        register_ledger=register_ledger,
    )


__all__ = [
    "CANONICAL_CAPTURE_FILENAME",
    "CANONICAL_REFUSAL_FILENAME",
    "DISPOSITION_APPENDED",
    "DISPOSITION_DRY_RUN",
    "DISPOSITION_REFUSED",
    "Item7CaptureAppendResult",
    "Item7CaptureWriterError",
    "REFUSAL_IMP_STATE_DIR_MISSING",
    "append_from_probe_diagnostic",
    "append_vendor_snapshot_capture",
    "canonical_item7_opend_capture_path",
    "canonical_item7_refusal_path",
    "next_capture_sequence",
]
