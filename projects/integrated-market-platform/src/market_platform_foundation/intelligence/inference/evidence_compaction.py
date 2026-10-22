"""Reversible column dictionaries; facts, clocks, ownership and ordering remain exact."""
from __future__ import annotations

import hashlib
import json
from typing import Any

VERSION = "ai-screener-evidence-columns/1.0.0"
OPTIMIZER_VERSION = "ai-screener-efficiency/1.0.0"


def semantic_hash(value: Any) -> str:
    def normalize(item):
        if isinstance(item, dict):
            return {key: normalize(val) for key, val in item.items()}
        if isinstance(item, list):
            return [normalize(val) for val in item]
        if isinstance(item, float) and item.is_integer():
            return int(item)
        return item
    encoded = json.dumps(normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compact(manifest: dict) -> dict:
    candidates = manifest["candidates"]
    columns = sorted({key for c in candidates for key in c} - {"current_market_evidence", "reference_evidence"})
    evidence_columns = sorted({key for c in candidates for name in ("current_market_evidence", "reference_evidence")
                               for e in c[name] for key in e})
    def row(item, fields):
        # Missing and null are distinct. The absent column indices are carried separately.
        return [[item.get(key) for key in fields], [i for i,key in enumerate(fields) if key not in item]]
    rows = [[row(c, columns), [row(e, evidence_columns) for e in c["current_market_evidence"]],
             [row(e, evidence_columns) for e in c["reference_evidence"]]] for c in candidates]
    return {"encoding": VERSION, "scope": manifest["scope"], "decision_cutoff": manifest["decision_cutoff"],
            "columns": columns, "evidence_columns": evidence_columns, "rows": rows}


def reconstruct(packed: dict) -> dict:
    if packed["encoding"] != VERSION:
        raise ValueError("COMPACTION_VERSION_UNSUPPORTED")
    def item(row, columns):
        values, absent = row
        if len(values) != len(columns) or len(set(columns)) != len(columns):
            raise ValueError("COMPACTION_ROW_INVALID")
        return {key: value for i,(key,value) in enumerate(zip(columns,values)) if i not in absent}
    candidates = []
    for identity, current, reference in packed["rows"]:
        c = item(identity, packed["columns"])
        c["current_market_evidence"] = [item(e, packed["evidence_columns"]) for e in current]
        c["reference_evidence"] = [item(e, packed["evidence_columns"]) for e in reference]
        candidates.append(c)
    return {"scope": packed["scope"], "decision_cutoff": packed["decision_cutoff"], "candidates": candidates}


def verify(manifest: dict, packed: dict) -> bool:
    try:
        return semantic_hash(manifest) == semantic_hash(reconstruct(packed))
    except (KeyError, TypeError, ValueError):
        return False
