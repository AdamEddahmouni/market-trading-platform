"""Research snapshot export.

Writes a timestamped JSON and CSV pair. The export carries the same missingness the
interface shows: a field with no value exports an empty CSV cell and a JSON ``null``
alongside its status and reason, never a zero.

Nothing credential-bearing is exported. A committed test asserts that.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

#: The export is a point-in-time research snapshot, not a modelling dataset.
EXPORT_KIND = "RESEARCH_SNAPSHOT"
EXPORT_NOTICE = (
    "Point-in-time research snapshot of what this screener displayed. It is NOT a "
    "backtest dataset, NOT a labelled training set, and contains no forward outcome."
)

#: Substrings that must never appear in an export key. Enforced at write time.
FORBIDDEN_KEY_SUBSTRINGS = (
    "password", "secret", "token", "apikey", "api_key", "credential", "auth",
)

CSV_COLUMNS = (
    "symbol",
    "data_mode",
    "mode_label",
    "case_id",
    "candidate_id",
    "event_timestamp",
    "provider",
    "discovery_profile",
    "market_data_mode",
    "first_seen_at",
    "snapshot_at",
    "stale",
    "stale_reason",
    "reference_price",
    "reference_price_status",
    "reference_price_missing_reason",
    "last",
    "last_status",
    "bid",
    "bid_status",
    "ask",
    "ask_status",
    "previous_close",
    "previous_close_status",
    "open",
    "open_status",
    "high",
    "high_status",
    "low",
    "low_status",
    "historical_close",
    "historical_close_status",
    "provider_volume",
    "provider_volume_status",
    "shortable",
    "shortable_status",
    "published_short_interest",
    "published_short_interest_status",
    "days_to_cover",
    "days_to_cover_status",
    "percentage_change",
    "percentage_change_status",
    "percentage_change_missing_reason",
    "relative_volume",
    "relative_volume_status",
    "float_shares",
    "float_shares_status",
    "short_float",
    "short_float_status",
    "short_ratio",
    "short_ratio_status",
    "shares_outstanding",
    "shares_outstanding_status",
    "borrow_fee",
    "borrow_fee_status",
    "borrow_availability",
    "borrow_availability_status",
    "catalyst",
    "catalyst_status",
    "news_count",
    "news_count_status",
    "latest_news_at",
    "latest_news_at_status",
    "latest_headline",
    "latest_headline_status",
    "sentiment",
    "sentiment_status",
    "sentiment_positive_count",
    "sentiment_positive_count_status",
    "sentiment_neutral_count",
    "sentiment_neutral_count_status",
    "sentiment_negative_count",
    "sentiment_negative_count_status",
    "sentiment_model_id",
    "sentiment_model_id_status",
    "pass_count",
    "fail_count",
    "unknown_count",
    "evidence_coverage",
    "research_detection",
    "outcome_status",
    "freshness",
    "global_preflight_status",
    "phase3a_request_id",
    "phase3a_result_id",
)


class CredentialInExportError(RuntimeError):
    """A key that looks credential-bearing reached the exporter."""


def _timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def _assert_no_credentials(payload: Any, path: str = "$") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).lower().replace("-", "_")
            for banned in FORBIDDEN_KEY_SUBSTRINGS:
                if banned in lowered:
                    raise CredentialInExportError(
                        f"refusing to export credential-shaped key {path}.{key!r}"
                    )
            _assert_no_credentials(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _assert_no_credentials(item, f"{path}[{index}]")


def _field(row: dict[str, Any], name: str) -> dict[str, Any]:
    return row.get("fields", {}).get(name) or {}


def build_export(
    snapshot: dict[str, Any], details: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Assemble the export payload from a screener snapshot plus optional details."""
    return {
        "schema_version": SCHEMA_VERSION,
        "export_kind": EXPORT_KIND,
        "notice": EXPORT_NOTICE,
        "exported_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "header": snapshot.get("header"),
        "boundary_time": snapshot.get("boundary_time"),
        "policy_version": snapshot.get("policy_version"),
        "evaluation_version": snapshot.get("evaluation_version"),
        "global_preflight_verdict": snapshot.get("global_preflight_verdict"),
        "row_count": len(snapshot.get("rows", [])),
        "rows": snapshot.get("rows", []),
        "details": details or {},
    }


def csv_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten to CSV records. Missing stays empty; it never becomes ``0``."""
    out: list[dict[str, Any]] = []
    for row in snapshot.get("rows", []):
        counts = row["phase3a"]["counts"]
        record: dict[str, Any] = {
            "symbol": row["symbol"],
            "data_mode": row["data_mode"],
            "mode_label": row.get("mode_label"),
            "case_id": row.get("case_id") or "",
            "candidate_id": row.get("candidate_id") or "",
            "event_timestamp": row.get("last_updated") or "",
            "provider": _field(row, "percentage_change").get("provider")
            or row.get("provider")
            or "",
            "pass_count": counts.get("PASS", 0),
            "fail_count": counts.get("FAIL", 0),
            "unknown_count": counts.get("UNKNOWN", 0),
            "evidence_coverage": row["evidence_coverage"]["label"],
            "research_detection": row["research_detection"]["status"],
            "outcome_status": row["outcome"]["status"],
            "freshness": row["freshness"],
            "global_preflight_status": row.get("global_preflight_status") or "",
            "phase3a_request_id": "",
            "phase3a_result_id": "",
            # Current-mode columns. Frozen rows simply leave these empty.
            "discovery_profile": row.get("discovery_profile") or "",
            "market_data_mode": row.get("market_data_mode") or "",
            "first_seen_at": row.get("first_seen_at") or "",
            "snapshot_at": row.get("snapshot_at") or "",
            "stale": "" if row.get("stale") is None else str(bool(row.get("stale"))),
            "stale_reason": row.get("stale_reason") or "",
        }
        for name in (
            "reference_price", "percentage_change", "relative_volume", "float_shares",
            "short_float", "short_ratio", "shares_outstanding",
            "borrow_fee", "borrow_availability", "catalyst", "news_count", "sentiment",
            "sentiment_positive_count", "sentiment_neutral_count", "sentiment_negative_count",
            "sentiment_model_id", "latest_news_at", "latest_headline",
            "last", "bid", "ask", "previous_close", "open", "high", "low",
            "historical_close", "provider_volume", "shortable",
            "published_short_interest", "days_to_cover",
        ):
            field = _field(row, name)
            record[name] = "" if field.get("value") is None else field["value"]
            record[f"{name}_status"] = field.get("status", "")
            reason_key = f"{name}_missing_reason"
            if reason_key in CSV_COLUMNS:
                record[reason_key] = field.get("missing_reason") or ""
        out.append({column: record.get(column, "") for column in CSV_COLUMNS})
    return out


def write_export(
    snapshot: dict[str, Any],
    output_dir: Path,
    *,
    details: dict[str, dict[str, Any]] | None = None,
    stem: str | None = None,
) -> dict[str, str]:
    """Write ``<stem>.json`` and ``<stem>.csv``. Returns the written paths."""
    payload = build_export(snapshot, details)
    _assert_no_credentials(payload)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    mode = (snapshot.get("header") or {}).get("mode", "SNAPSHOT")
    name = stem or f"research-snapshot-{mode.lower()}-{_timestamp()}"

    json_path = output_dir / f"{name}.json"
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )

    csv_path = output_dir / f"{name}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        writer.writerows(csv_rows(snapshot))

    return {"json": str(json_path), "csv": str(csv_path), "stem": name}


__all__ = [
    "CSV_COLUMNS",
    "EXPORT_KIND",
    "EXPORT_NOTICE",
    "FORBIDDEN_KEY_SUBSTRINGS",
    "SCHEMA_VERSION",
    "CredentialInExportError",
    "build_export",
    "csv_rows",
    "write_export",
]
