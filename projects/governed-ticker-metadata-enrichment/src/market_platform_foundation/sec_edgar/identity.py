"""CIK / ticker / accession identity. Fail closed rather than guess."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def pad_cik(value: str | int) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        raise ValueError("CIK_INVALID")
    return digits.zfill(10)


def normalize_accession(value: str) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) != 18:
        hyphenated = str(value).strip()
        if len(hyphenated) == 20 and hyphenated.count("-") == 2:
            return hyphenated
        raise ValueError(f"ACCESSION_INVALID:{value}")
    return f"{digits[:10]}-{digits[10:12]}-{digits[12:]}"


@dataclass(frozen=True, slots=True)
class EntityResolution:
    cik: str
    instrument_id: str
    entity_name: str
    tickers: tuple[str, ...]
    quality_flags: tuple[str, ...] = ()


class EntityMap:
    def __init__(self, records: tuple[dict[str, Any], ...]) -> None:
        self._records = records

    @classmethod
    def from_path(cls, path: Path) -> "EntityMap":
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("records") if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ValueError("ENTITY_MAP_INVALID")
        normalized = []
        for row in records:
            if not isinstance(row, dict):
                continue
            normalized.append(row)
        return cls(tuple(normalized))

    def resolve(self, *, cik: str, as_of: str) -> EntityResolution:
        padded = pad_cik(cik)
        for row in self._records:
            if pad_cik(str(row.get("cik", ""))) != padded:
                continue
            valid_from = str(row.get("valid_from") or "")
            valid_to = str(row.get("valid_to") or "")
            if valid_from and as_of < valid_from:
                continue
            if valid_to and as_of >= valid_to:
                continue
            tickers = tuple(str(t) for t in (row.get("tickers") or ()))
            return EntityResolution(
                cik=padded,
                instrument_id=str(row.get("instrument_id") or ""),
                entity_name=str(row.get("entity_name") or ""),
                tickers=tickers,
            )
        return EntityResolution(
            cik=padded,
            instrument_id="",
            entity_name="",
            tickers=(),
            quality_flags=("UNKNOWN_ENTITY",),
        )
