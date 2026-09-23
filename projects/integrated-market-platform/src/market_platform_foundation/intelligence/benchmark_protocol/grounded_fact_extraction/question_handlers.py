"""Question-class handlers — structural extraction only (no case_id branching)."""

from __future__ import annotations

import re
from typing import Any

from .claim_linkage import link_claim_to_evidence
from .evidence_projection import ProjectedArtifact

_SESSION_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_QUOTED_LITERAL_RE = re.compile(r"literal\s+\w+\s+value\s+'([^']+)'", re.IGNORECASE)
_INSTRUMENT_TICKER_RE = re.compile(r"\bfor\s+([A-Z]{1,5})\s+on\b", re.IGNORECASE)


def _fact_row(
    *,
    field: str,
    value: Any,
    artifact: ProjectedArtifact,
    source_path: str,
    confidence: str = "ADMITTED_ARTIFACT",
) -> dict[str, Any]:
    return link_claim_to_evidence(
        field=field,
        value=value,
        artifact=artifact,
        source_path=source_path,
        confidence=confidence,
    )


def _historical_session_map(payload: Any) -> dict[str, list[dict[str, Any]]] | None:
    if not isinstance(payload, dict):
        return None
    if not payload:
        return None
    if all(isinstance(v, list) for v in payload.values()):
        return {str(k): [r for r in v if isinstance(r, dict)] for k, v in payload.items()}
    return None


def _instrument_codes_in_historical(payload: Any) -> set[str]:
    codes: set[str] = set()
    session_map = _historical_session_map(payload)
    if not session_map:
        return codes
    for rows in session_map.values():
        for row in rows:
            code = str(row.get("code") or row.get("instrument_id") or row.get("symbol") or "")
            if code:
                codes.add(code.casefold())
            sym = code.split(".")[-1] if "." in code else code
            if sym:
                codes.add(sym.casefold())
    return codes


def handle_market_instrument(artifact: ProjectedArtifact, question_text: str) -> list[dict[str, Any]]:
    session_map = _historical_session_map(artifact.payload)
    if not session_map:
        return []
    first_session = sorted(session_map.keys())[0]
    rows = session_map[first_session]
    if not rows:
        return []
    code = rows[0].get("code") or rows[0].get("instrument_id") or rows[0].get("symbol")
    if code is None:
        return []
    return [
        _fact_row(
            field="instrument_code",
            value=str(code),
            artifact=artifact,
            source_path=f"session:{first_session};row:0;field:code",
        )
    ]


def handle_session_identity(artifact: ProjectedArtifact, question_text: str) -> list[dict[str, Any]]:
    session_map = _historical_session_map(artifact.payload)
    if not session_map:
        return []
    keys = sorted(session_map.keys())
    return [
        _fact_row(
            field="session_key_count",
            value=len(keys),
            artifact=artifact,
            source_path="root:session_keys",
        ),
        _fact_row(
            field="session_dates",
            value=keys,
            artifact=artifact,
            source_path="root:session_keys",
        ),
    ]


def handle_row_count(artifact: ProjectedArtifact, question_text: str) -> list[dict[str, Any]]:
    session_map = _historical_session_map(artifact.payload)
    if not session_map:
        return []
    match = _SESSION_DATE_RE.search(question_text)
    session_key = match.group(1) if match else sorted(session_map.keys())[0]
    rows = session_map.get(session_key)
    if rows is None:
        return []
    return [
        _fact_row(
            field="raw_row_count",
            value=len(rows),
            artifact=artifact,
            source_path=f"session:{session_key}",
        )
    ]


def handle_contamination_signal(artifact: ProjectedArtifact, question_text: str) -> list[dict[str, Any]]:
    session_map = _historical_session_map(artifact.payload)
    if not session_map:
        return []
    literal_match = _QUOTED_LITERAL_RE.search(question_text)
    literal = literal_match.group(1) if literal_match else None
    if literal is None:
        return []
    date_match = _SESSION_DATE_RE.search(question_text)
    session_key = date_match.group(1) if date_match else sorted(session_map.keys())[0]
    rows = session_map.get(session_key, [])
    count = sum(1 for row in rows if str(row.get("time_key")) == literal)
    return [
        _fact_row(
            field="malformed_time_key_rows",
            value=count,
            artifact=artifact,
            source_path=f"session:{session_key};filter:time_key={literal}",
        )
    ]


def _json_get(payload: Any, path: tuple[str, ...]) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise KeyError(path)
        current = current[key]
    return current


def handle_governed_manifest(artifact: ProjectedArtifact, question_text: str) -> list[dict[str, Any]]:
    lowered = question_text.casefold()
    if "dataset_id" in lowered:
        value = _json_get(artifact.payload, ("dataset", "dataset_id"))
        return [
            _fact_row(
                field="dataset_id",
                value=value,
                artifact=artifact,
                source_path="dataset:dataset_id",
            )
        ]
    return []


def handle_baseline_pack(artifact: ProjectedArtifact, question_text: str) -> list[dict[str, Any]]:
    if "baseline_strategies" in question_text.casefold():
        strategies = _json_get(artifact.payload, ("baseline_strategies",))
        if not isinstance(strategies, list):
            return []
        return [
            _fact_row(
                field="baseline_strategy_count",
                value=len(strategies),
                artifact=artifact,
                source_path="baseline_strategies",
            )
        ]
    return []


def handle_authority_class(artifact: ProjectedArtifact, question_text: str) -> list[dict[str, Any]]:
    if "corpus_evidence_authority" in question_text.casefold():
        value = _json_get(artifact.payload, ("corpus_evidence_authority",))
        return [
            _fact_row(
                field="corpus_evidence_authority",
                value=value,
                artifact=artifact,
                source_path="corpus_evidence_authority",
            )
        ]
    return []


def handle_validation_manifest(artifact: ProjectedArtifact, question_text: str) -> list[dict[str, Any]]:
    if "validation_dataset_id" in question_text.casefold():
        value = _json_get(artifact.payload, ("validation_dataset_manifest", "validation_dataset_id"))
        return [
            _fact_row(
                field="validation_dataset_id",
                value=value,
                artifact=artifact,
                source_path="validation_dataset_manifest:validation_dataset_id",
            )
        ]
    return []


def handle_parity_receipt(artifact: ProjectedArtifact, question_text: str) -> list[dict[str, Any]]:
    if "feature_row_count" in question_text.casefold():
        value = _json_get(artifact.payload, ("diagnostics", "feature_row_count"))
        return [
            _fact_row(
                field="feature_row_count",
                value=value,
                artifact=artifact,
                source_path="diagnostics:feature_row_count",
            )
        ]
    return []


def handle_provider_verification(artifact: ProjectedArtifact, question_text: str) -> list[dict[str, Any]]:
    lowered = question_text.casefold()
    if "moomoo" in lowered and "rows" in lowered:
        value = _json_get(artifact.payload, ("moomoo", "ROWS"))
        return [
            _fact_row(
                field="moomoo_rows",
                value=value,
                artifact=artifact,
                source_path="moomoo:ROWS",
            )
        ]
    return []


def handle_abstention(artifact: ProjectedArtifact, question_text: str) -> list[dict[str, Any]]:
    """Return empty facts when evidence cannot support the asked instrument/metric."""
    match = _INSTRUMENT_TICKER_RE.search(question_text)
    if not match:
        return []
    ticker = match.group(1).casefold()
    codes = _instrument_codes_in_historical(artifact.payload)
    if ticker in codes:
        return []
    return []


def handle_unanswerable_metric(artifact: ProjectedArtifact, question_text: str) -> list[dict[str, Any]]:
    """Metrics such as directional_accuracy are absent from static manifest artifacts."""
    if "directional_accuracy" in question_text.casefold():
        return []
    return []


QUESTION_CLASS_HANDLERS: dict[str, Any] = {
    "MARKET_INSTRUMENT": handle_market_instrument,
    "SESSION_IDENTITY": handle_session_identity,
    "ROW_COUNT": handle_row_count,
    "CONTAMINATION_SIGNAL": handle_contamination_signal,
    "GOVERNED_MANIFEST": handle_governed_manifest,
    "BASELINE_PACK": handle_baseline_pack,
    "AUTHORITY_CLASS": handle_authority_class,
    "VALIDATION_MANIFEST": handle_validation_manifest,
    "PARITY_RECEIPT": handle_parity_receipt,
    "PROVIDER_VERIFICATION": handle_provider_verification,
    "ABSTENTION": handle_abstention,
    "UNANSWERABLE_METRIC": handle_unanswerable_metric,
}


__all__ = ["QUESTION_CLASS_HANDLERS"]
