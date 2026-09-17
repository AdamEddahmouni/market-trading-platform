"""Deterministic historical bar normalization with attached provenance."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ....canonical import canonical_bytes, sha256_bytes
from ..bar_ohlcv_sources import normalize_moomoo_kline_row
from .historical_provenance import validate_historical_development_provenance


def normalize_historical_development_bars(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    provenance: Mapping[str, Any],
    fetched_at_ns: int,
) -> dict[str, Any]:
    """Normalize vendor rows; identical raw + provenance + code_sha → identical fingerprint."""

    gate = validate_historical_development_provenance(provenance)
    if not gate["ok"]:
        return {"ok": False, "reason_code": gate["reason_code"], "bars": (), "fingerprint": ""}
    instrument_id = str(provenance.get("instrument_id") or "")
    bars: list[dict[str, Any]] = []
    for row in raw_rows:
        normalized = normalize_moomoo_kline_row(
            row,
            instrument_id=instrument_id,
            fetched_at_ns=fetched_at_ns,
        )
        if normalized is None:
            continue
        bars.append(
            {
                **normalized,
                "historical_provenance_ref": {
                    "dataset_id": provenance.get("dataset_id"),
                    "dataset_version": provenance.get("dataset_version"),
                    "raw_payload_sha256": provenance.get("raw_payload_sha256"),
                    "corpus_evidence_authority": provenance.get("corpus_evidence_authority"),
                    "code_sha": provenance.get("code_sha"),
                },
            }
        )
    bars.sort(key=lambda row: (str(row.get("instrument_id") or ""), int(row["available_time"])))
    fingerprint = sha256_bytes(
        canonical_bytes(
            {
                "bars": bars,
                "provenance": dict(provenance),
            }
        )
    )
    return {
        "ok": True,
        "reason_code": None,
        "bars": tuple(bars),
        "fingerprint": fingerprint,
        "row_count": len(bars),
    }


__all__ = ["normalize_historical_development_bars"]
