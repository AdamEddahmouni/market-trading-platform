"""MODE A — Frozen Research Cases.

Loads the 13 real Batch 01 cases together with their frozen Batch 08 Phase 3A requests,
results and metrics, and the Batch 09 registry-revision preview. Nothing is recomputed:
every rule outcome shown is the byte-for-byte outcome that was frozen at
``2026-07-18T13:37:55.017661Z``.

This module contains no metric formula and no rule logic. It reads, labels and explains.
"""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import reasons
from .paths import FrozenLayout, read_text
from .truth import DataMode, Freshness, FieldValue, ValueStatus, known, missing

#: The literal mode label shown in the header for this source.
FROZEN_MODE_LABEL = "FROZEN RESEARCH — 2026-07-18"

#: The literal banner required whenever Batch 09 preview material is displayed.
PREVIEW_BANNER = "REGISTRY REVISION PREVIEW — NOT CANONICALLY PUBLISHED"

#: Outcomes that mean the rule was actually supported by admissible evidence.
EVIDENCE_SUPPORTED_OUTCOMES = ("PASS", "FAIL")

#: Maximum chart points sent to the browser. Downsampling is by stride, never by
#: smoothing, so every plotted point is a real provider bar close.
MAX_CHART_POINTS = 400


class FrozenResearchUnavailable(RuntimeError):
    """The private frozen artifact root is not present on this machine."""


def _load_json(path: Path) -> Any:
    return json.loads(read_text(path))


class FrozenResearchSource:
    """Read-only view over the Batch 08 freeze plus the Batch 09 preview."""

    def __init__(self, layout: FrozenLayout | None = None) -> None:
        self.layout = layout or FrozenLayout()
        self._summary: dict[str, Any] | None = None
        self._results: dict[str, dict[str, Any]] = {}
        self._metrics: dict[str, dict[str, Any]] = {}
        self._detection: dict[str, dict[str, Any]] = {}
        self._preview_summary: dict[str, Any] | None = None
        self._loaded = False

    # ---------------------------------------------------------------- loading

    @property
    def available(self) -> bool:
        return self.layout.available

    def load(self) -> None:
        """Load every frozen artifact once. Subsequent calls are no-ops."""
        if self._loaded:
            return
        if not self.available:
            raise FrozenResearchUnavailable(
                f"frozen research artifacts not found under {self.layout.root}"
            )
        self._summary = _load_json(self.layout.batch_summary)
        for case in self._summary["cases"]:
            case_id = case["case_id"]
            self._results[case_id] = _load_json(self.layout.results_dir / f"{case_id}.json")
            metric_path = self.layout.metrics_dir / f"{case_id}.json"
            if metric_path.is_file():
                self._metrics[case_id] = _load_json(metric_path)
        if self.layout.detection_preview.is_file():
            for entry in _load_json(self.layout.detection_preview):
                self._detection[entry["case_id"]] = entry
        if self.layout.preview_summary.is_file():
            self._preview_summary = _load_json(self.layout.preview_summary)
        self._loaded = True

    # ------------------------------------------------------------- accessors

    @property
    def summary(self) -> dict[str, Any]:
        self.load()
        assert self._summary is not None
        return self._summary

    @property
    def boundary_time(self) -> str:
        return self.summary["boundary_time"]

    @property
    def cases(self) -> list[dict[str, Any]]:
        return list(self.summary["cases"])

    @property
    def rule_matrix(self) -> dict[str, dict[str, Any]]:
        return {entry["rule_id"]: entry for entry in self.summary["rule_matrix"]}

    @property
    def canonical_rule_order(self) -> list[str]:
        """The 25 enabled rule IDs in the canonical policy order."""
        first = self._results[self.cases[0]["case_id"]]
        return list(first["enabled_rule_ids"])

    def case_for_symbol(self, symbol: str) -> dict[str, Any] | None:
        wanted = symbol.upper()
        for case in self.cases:
            if case["symbol"] == wanted:
                return case
        return None

    # --------------------------------------------------------------- helpers

    def _phase3a_counts(self, case_id: str) -> dict[str, int]:
        counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0, "CONFLICTED": 0,
                  "INSUFFICIENT_DATA": 0, "NOT_APPLICABLE": 0}
        for rule in self._results[case_id]["rule_results"]:
            counts[rule["outcome"]] = counts.get(rule["outcome"], 0) + 1
        return counts

    def _detection_status(self, case_id: str) -> tuple[str, list[str]]:
        entry = self._detection.get(case_id)
        if entry is None:
            return "UNEVALUABLE", ["No Batch 09 detection preview entry exists for this case."]
        return entry["research_detection_status"], reasons.explain_detection(
            entry.get("research_detection_reason")
        )

    def _outcome_status(self) -> tuple[str, list[str]]:
        """Outcome is INCOMPLETE for every case: no forward window was acquired."""
        codes = (self._preview_summary or {}).get("skipped_diagnostic_codes") or [
            "RESEARCH_CASE_OUTCOME_MISSING",
            "RESEARCH_CASE_STATUS_INCOMPLETE",
        ]
        return "INCOMPLETE", reasons.explain_skip(codes)

    def _blocking_for_rule(self, rule_id: str) -> tuple[list[str], list[str], str]:
        entry = self.rule_matrix.get(rule_id, {})
        codes = list(entry.get("blocking_reason_codes") or ())
        return codes, reasons.explain_blocking(codes), entry.get(
            "batch07_admissibility_status", "UNKNOWN"
        )

    # --------------------------------------------------------- screener rows

    def _percentage_change_field(self, case: dict[str, Any]) -> FieldValue:
        metric = self._metrics.get(case["case_id"])
        if metric is None:
            return missing(
                ValueStatus.UNAVAILABLE,
                "No frozen PERCENTAGE_RETURN metric record exists for this case.",
                reason_code="METRIC_RECORD_ABSENT",
                data_mode=DataMode.FROZEN_RESEARCH,
                freshness=Freshness.FROZEN,
            )
        return known(
            round(float(metric["value"]), 4),
            unit=metric["unit"],
            provider=metric["provider"],
            event_time=metric["as_of"],
            freshness=Freshness.FROZEN,
            data_mode=DataMode.FROZEN_RESEARCH,
            evidence_id=metric["deterministic_id"],
            readiness=metric["quality"]["state"],
        )

    def _blocked_field(self, rule_id: str, label_code: str) -> FieldValue:
        codes, sentences, _status = self._blocking_for_rule(rule_id)
        sentence = " ".join(sentences) if sentences else (
            "No admissible evidence supports this field at the detection boundary."
        )
        return missing(
            ValueStatus.UNKNOWN,
            sentence,
            reason_code=codes[0] if codes else label_code,
            data_mode=DataMode.FROZEN_RESEARCH,
            freshness=Freshness.NOT_APPLICABLE,
        )

    def _not_collected(self, sentence: str, code: str) -> FieldValue:
        return missing(
            ValueStatus.NOT_COLLECTED,
            sentence,
            reason_code=code,
            data_mode=DataMode.FROZEN_RESEARCH,
            freshness=Freshness.NOT_APPLICABLE,
        )

    def screener_row(self, case: dict[str, Any]) -> dict[str, Any]:
        """One screener table row. Every cell is a :class:`FieldValue`."""
        case_id = case["case_id"]
        counts = self._phase3a_counts(case_id)
        supported = sum(counts[outcome] for outcome in EVIDENCE_SUPPORTED_OUTCOMES)
        detection_status, detection_reasons = self._detection_status(case_id)
        outcome_status, outcome_reasons = self._outcome_status()
        total_rules = len(self._results[case_id]["rule_results"])

        fields = {
            "reference_price": self._blocked_field(
                "PRICE_RANGE", "ABSOLUTE_PRICE_LEVEL_BLOCKED_BY_BATCH07"
            ),
            "percentage_change": self._percentage_change_field(case),
            "relative_volume": self._blocked_field(
                "RELATIVE_VOLUME_MINIMUM", "VOLUME_SEMANTICS_BLOCKED_BY_BATCH07"
            ),
            "float_shares": self._not_collected(
                "No float provider was configured for this collection; float was never "
                "collected at the detection boundary.",
                "FLOAT_NOT_COLLECTED",
            ),
            "short_float": self._not_collected(
                "No short-interest provider was configured; short float was never collected.",
                "SHORT_FLOAT_NOT_COLLECTED",
            ),
            "borrow_fee": self._not_collected(
                "No borrow-fee provider was configured; borrow fee was never collected.",
                "BORROW_FEE_NOT_COLLECTED",
            ),
            "borrow_availability": self._not_collected(
                "No borrow-availability provider was configured; borrow availability was "
                "never collected.",
                "BORROW_AVAILABILITY_NOT_COLLECTED",
            ),
            "catalyst": self._not_collected(
                "No news, filing or corporate-action evidence was collected at the "
                "detection boundary.",
                "CATALYST_NOT_COLLECTED",
            ),
            "sentiment": self._not_collected(
                "No sentiment source is configured, and no current research supports a "
                "sentiment field as evidence.",
                "SENTIMENT_NOT_CONFIGURED",
            ),
        }

        return {
            "symbol": case["symbol"],
            "case_id": case_id,
            "candidate_id": case["candidate_evaluation_id"],
            "data_mode": str(DataMode.FROZEN_RESEARCH),
            "mode_label": FROZEN_MODE_LABEL,
            "fields": {name: value.as_dict() for name, value in fields.items()},
            "phase3a": {
                "counts": counts,
                "total_rules": total_rules,
                "summary": f"{counts['PASS']} PASS / {counts['FAIL']} FAIL / "
                           f"{counts['UNKNOWN']} UNKNOWN",
            },
            "research_detection": {
                "status": detection_status,
                "reasons": detection_reasons,
                "preview_banner": PREVIEW_BANNER,
            },
            "outcome": {"status": outcome_status, "reasons": outcome_reasons},
            "evidence_coverage": {
                "supported": supported,
                "total": total_rules,
                "label": f"{supported} / {total_rules} rules supported",
            },
            "freshness": str(Freshness.FROZEN),
            "last_updated": case["boundary_time"],
            "global_preflight_status": case["global_preflight_status"],
        }

    def screener_rows(self) -> list[dict[str, Any]]:
        self.load()
        rows = [self.screener_row(case) for case in self.cases]
        rows.sort(key=lambda row: row["symbol"])
        return rows

    # ------------------------------------------------------------- rule table

    def rule_table(self, case_id: str) -> list[dict[str, Any]]:
        """All 25 rules in canonical order with observed value, threshold and reason."""
        self.load()
        result = self._results[case_id]
        by_id = {rule["rule_id"]: rule for rule in result["rule_results"]}
        rows: list[dict[str, Any]] = []
        for rule_id in self.canonical_rule_order:
            rule = by_id[rule_id]
            codes, sentences, admissibility = self._blocking_for_rule(rule_id)
            observed = rule["observed_value"]
            threshold_values = rule.get("threshold_values") or []
            threshold = ""
            if threshold_values:
                joined = ", ".join(threshold_values)
                operator = rule.get("operator") or ""
                unit = rule.get("threshold_unit") or ""
                threshold = " ".join(part for part in (operator, joined, unit) if part)
            evidence_ids = list(rule.get("input_metric_ids") or []) + list(
                rule.get("input_observation_ids") or []
            ) + list(rule.get("readiness_snapshot_ids") or [])
            reason = reasons.explain_evaluation(rule.get("explanation_code"))
            if rule["outcome"] not in EVIDENCE_SUPPORTED_OUTCOMES and sentences:
                reason = f"{reason} {' '.join(sentences)}"
            rows.append(
                {
                    "rule_id": rule_id,
                    "rule_version": rule["rule_version"],
                    "category": rule["category"],
                    "outcome": rule["outcome"],
                    "observed_value": observed,
                    "observed_unit": rule.get("observed_unit"),
                    "observed_display": (
                        f"{observed} {rule['observed_unit']}".strip()
                        if observed is not None
                        else "—"
                    ),
                    "threshold": threshold or "—",
                    "evidence_ids": evidence_ids,
                    "evidence_display": f"{len(evidence_ids)} evidence ID(s)"
                    if evidence_ids
                    else "—",
                    "explanation_code": rule.get("explanation_code"),
                    "reason": reason,
                    "blocking_reason_codes": codes,
                    "batch07_admissibility_status": admissibility,
                    "quality_state": rule["quality"]["state"],
                }
            )
        return rows

    # ----------------------------------------------------------------- chart

    def chart(self, symbol: str) -> dict[str, Any]:
        """Detection-context closes only. The forward window is unreachable by design."""
        self.load()
        path = self.layout.detection_context_csv(symbol)
        if not path.is_file():
            return {
                "available": False,
                "reason": f"No detection-context artifact exists for {symbol}.",
                "points": [],
            }
        points: list[dict[str, Any]] = []
        with path.open(newline="", encoding="utf-8") as handle:
            for record in csv.DictReader(handle):
                points.append(
                    {"t": record["timestamp_utc"], "close": float(record["close"])}
                )
        stride = max(1, len(points) // MAX_CHART_POINTS)
        sampled = points[::stride]
        if points and sampled[-1] is not points[-1]:
            sampled.append(points[-1])
        return {
            "available": True,
            "symbol": symbol,
            "provider": "IBKR",
            "series_label": "Detection-context close (raw provider bars)",
            "request_name": "DETECTION_CONTEXT_PRECEDING_24H",
            "points": sampled,
            "point_count_total": len(points),
            "point_count_plotted": len(sampled),
            "boundary_time": self.boundary_time,
            "boundary_label": "Detection Boundary",
            "forward_window_shown": False,
            "notes": [
                "Prices are the provider's split-adjusted close series. Absolute price "
                "levels are NOT admissible for rule evaluation; only price ratios are.",
                "Volume is not plotted: the provider's historical volume unit and "
                "corporate-action treatment are unresolved.",
                "No forward or outcome region is drawn. None was read.",
            ],
        }

    # ---------------------------------------------------------------- detail

    def detail(self, symbol: str) -> dict[str, Any] | None:
        self.load()
        case = self.case_for_symbol(symbol)
        if case is None:
            return None
        case_id = case["case_id"]
        row = self.screener_row(case)
        result = self._results[case_id]
        metric = self._metrics.get(case_id)
        return {
            "identity": {
                "symbol": case["symbol"],
                "case_id": case_id,
                "candidate_id": case["candidate_evaluation_id"],
                "boundary_time": case["boundary_time"],
                "boundary_id": case["boundary_id"],
                "provider": (metric or {}).get("provider", "IBKR"),
                "data_mode": str(DataMode.FROZEN_RESEARCH),
                "mode_label": FROZEN_MODE_LABEL,
                "asset_class": result["asset_class"],
            },
            "provenance": {
                "phase3a_request_id": case["phase3a_request_id"],
                "phase3a_result_id": case["phase3a_result_id"],
                "phase3a_request_sha256": case["phase3a_request_artifact"]["sha256"],
                "phase3a_result_sha256": case["phase3a_result_artifact"]["sha256"],
                "evidence_association_id": case["evidence_association_id"],
                "batch07_readiness_record_id": case["batch07_readiness_record_id"],
                "readiness_ids": case["readiness_ids"],
                "admissible_evidence_ids": case["admissible_evidence_ids"],
                "metric_ids": case["metric_ids"],
                "policy_version": case["phase3a_policy_version"],
                "evaluation_version": case["phase3a_evaluation_version"],
                "freeze_policy_version": case["freeze_policy_version"],
                "freeze_status": case["freeze_status"],
                "leakage_audit_status": case["leakage_audit_status"],
                "global_preflight_status": case["global_preflight_status"],
                "schema_version": case["schema_version"],
                "forward_ohlcv_accessed": case["forward_ohlcv_accessed"],
                "outcome_accessed": case["outcome_accessed"],
                "phase3b_published": case["phase3b_published"],
                "phase3e_started": case["phase3e_started"],
                "detection_context_artifact_name": case["detection_context_artifact_name"],
                "detection_context_artifact_sha256": case[
                    "detection_context_artifact_sha256"
                ],
            },
            "market_data": row["fields"],
            "metric_record": None
            if metric is None
            else {
                "metric_name": metric["metric_name"],
                "value": metric["value"],
                "unit": metric["unit"],
                "price_field": metric["price_field"],
                "provider": metric["provider"],
                "provider_scope": metric["provider_scope"],
                "source_interval": metric["source_interval"],
                "calculation_policy_version": metric["calculation_policy_version"],
                "deterministic_id": metric["deterministic_id"],
                "input_bar_boundaries": metric["input_bar_boundaries"],
                "quality_state": metric["quality"]["state"],
            },
            "rules": self.rule_table(case_id),
            "phase3a": row["phase3a"],
            "research_detection": row["research_detection"],
            "outcome": row["outcome"],
            "evidence_coverage": row["evidence_coverage"],
            "blocked_evidence_dependencies": case["blocked_evidence_dependencies"],
            "blocking_reason_codes": case["blocking_reason_codes"],
            "blocking_reason_sentences": reasons.explain_blocking(
                case["blocking_reason_codes"]
            ),
        }

    # -------------------------------------------------------- research summary

    def research_summary(self) -> dict[str, Any]:
        self.load()
        summary = self.summary
        totals = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
        for case in self.cases:
            counts = self._phase3a_counts(case["case_id"])
            for key in totals:
                totals[key] += counts[key]

        by_category: dict[str, dict[str, int]] = {}
        pct_change: dict[str, list[str]] = {"PASS": [], "FAIL": [], "UNKNOWN": []}
        evaluable_rules: list[str] = []
        for rule_id, entry in self.rule_matrix.items():
            outcomes = {outcome for _case, outcome in entry["outcomes_by_case"]}
            if outcomes and outcomes.isdisjoint({"UNKNOWN", "CONFLICTED", "INSUFFICIENT_DATA"}):
                evaluable_rules.append(rule_id)
            bucket = by_category.setdefault(
                entry["category"], {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
            )
            for outcome, count in entry["outcome_counts"]:
                bucket[outcome] = bucket.get(outcome, 0) + count
            if rule_id == "PERCENTAGE_CHANGE_MINIMUM":
                for case_id, outcome in entry["outcomes_by_case"]:
                    symbol = case_id.split("_")[1]
                    pct_change.setdefault(outcome, []).append(symbol)

        detection_counts: dict[str, int] = {}
        for case in self.cases:
            status, _ = self._detection_status(case["case_id"])
            detection_counts[status] = detection_counts.get(status, 0) + 1

        return {
            "boundary_time": summary["boundary_time"],
            "mode_label": FROZEN_MODE_LABEL,
            "case_count": len(self.cases),
            "evaluation_count": summary["results_frozen"],
            "rule_case_pairs": len(self.cases) * len(self.canonical_rule_order),
            "outcome_totals": totals,
            "by_category": by_category,
            "evaluable_rules_across_all_cases": sorted(evaluable_rules),
            "percentage_change_split": {
                key: sorted(value) for key, value in pct_change.items() if value
            },
            "research_detection_counts": detection_counts,
            "outcome_counts": {"INCOMPLETE": len(self.cases)},
            "global_preflight_verdict": summary["global_preflight_verdict"],
            "leakage_audits_passed": summary["leakage_audits_passed"],
            "phase3b_published": any(case["phase3b_published"] for case in self.cases),
            "phase3e_started": any(case["phase3e_started"] for case in self.cases),
            "preview_banner": PREVIEW_BANNER,
            "preview_summary": self._preview_summary,
            "notes": [
                "UNKNOWN means insufficient admissible evidence, not failure. A rule that "
                "could not be evaluated is skipped, not counted against the case.",
                "No forward outcome window has been "
                "acquired, so no case can be scored as a successful or failed prediction.",
                "The global acquisition preflight remains "
                f"{summary['global_preflight_verdict']}; every record echoes it.",
            ],
        }

    # Backward-compatible internal name for earlier application callers.
    professor_summary = research_summary


@lru_cache(maxsize=4)
def _cached_source(root: str) -> FrozenResearchSource:
    return FrozenResearchSource(FrozenLayout(Path(root)))


def get_frozen_source(root: Path | None = None) -> FrozenResearchSource:
    """Cached frozen source. Frozen artifacts are immutable, so caching is safe."""
    layout = FrozenLayout(root)
    return _cached_source(str(layout.root))


__all__ = [
    "EVIDENCE_SUPPORTED_OUTCOMES",
    "FROZEN_MODE_LABEL",
    "MAX_CHART_POINTS",
    "PREVIEW_BANNER",
    "FrozenResearchSource",
    "FrozenResearchUnavailable",
    "get_frozen_source",
]
