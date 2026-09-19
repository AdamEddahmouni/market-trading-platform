import type { OperatorDiagnostics, OperatorLifecycleStatus, OperatorReadiness } from "../../api/schemas";
import type { SemanticTone } from "../../state/semanticState";
import { matchKnownDataIncident } from "../operator-shared/knownDataIncidents";

/** Canonical operator truth tokens — do not collapse into generic pass/fail. */
export type OperatorTruthClass =
  | "HEALTHY"
  | "DEGRADED"
  | "BLOCKED"
  | "IDLE"
  | "UNKNOWN"
  | "UNAVAILABLE"
  | "NOT_OBSERVED";

export type OperatorTruthRow = {
  id: string;
  label: string;
  truth: OperatorTruthClass;
  detail: string;
  tone: SemanticTone;
};

export function diagnosticsSection<T extends Record<string, unknown>>(
  diagnostics: OperatorDiagnostics | null | undefined,
  key: string,
): T | undefined {
  const raw = diagnostics?.sections?.[key];
  if (!raw || typeof raw !== "object") return undefined;
  return raw as T;
}

export function diagnosticsRuntimeSection(diagnostics: OperatorDiagnostics | null | undefined) {
  return diagnosticsSection<{
    git_sha?: string;
    item9_preflight?: Record<string, unknown>;
    item9_corpus_status?: Record<string, unknown>;
    runtime_resilience?: Record<string, unknown>;
  }>(diagnostics, "runtime");
}

export function diagnosticsReadiness(
  diagnostics: OperatorDiagnostics | null | undefined,
): OperatorReadiness | undefined {
  const row = diagnosticsSection<OperatorReadiness>(diagnostics, "readiness");
  if (!row?.status) return undefined;
  return row;
}

export function diagnosticsLifecycle(
  diagnostics: OperatorDiagnostics | null | undefined,
): OperatorLifecycleStatus | undefined {
  const row = diagnosticsSection<OperatorLifecycleStatus>(diagnostics, "lifecycle");
  if (!row?.status) return undefined;
  return row;
}

export function diagnosticsOpportunitySurface(diagnostics: OperatorDiagnostics | null | undefined) {
  return diagnosticsSection<{
    feed_status?: string;
    unready_reason?: string | null;
    quality_summary?: { state?: string };
  }>(diagnostics, "opportunity_surface");
}

export function diagnosticsGovernance(diagnostics: OperatorDiagnostics | null | undefined) {
  return diagnosticsSection<{
    headline?: string;
    forbidden?: string[];
    interventions?: string[];
    allowed_read_only?: string[];
    live_execution_env?: boolean;
    paper_execution_env?: boolean;
  }>(diagnostics, "governance");
}

export function mapSeverityTone(severity: string | undefined): SemanticTone {
  switch ((severity ?? "").toUpperCase()) {
    case "OK":
    case "HEALTHY":
      return "live";
    case "DEGRADED":
      return "caution";
    case "STOPPED":
    case "ACTION_REQUIRED":
      return "critical";
    default:
      return "neutral";
  }
}

export function mapItem9DispositionTruth(disposition: string | undefined): OperatorTruthClass {
  const token = (disposition ?? "UNKNOWN").toUpperCase();
  if (token === "READY_TO_COLLECT") return "HEALTHY";
  if (token === "NOT_RTH") return "IDLE";
  if (token === "WRONG_RUNTIME" || token === "OUTPUT_PATH_INVALID") return "BLOCKED";
  if (token === "PROVIDER_UNAVAILABLE") return "UNAVAILABLE";
  if (token === "ACTIVE_COLLECTOR_EXISTS") return "DEGRADED";
  return "UNKNOWN";
}

export function formatItem9CorpusProgress(
  corpusSection: Record<string, unknown> | undefined,
): { distinctRthDates: string; calibrationLabel: string; calibrationForbidden: string } {
  const availability = String(corpusSection?.availability ?? "NOT_OBSERVED").toUpperCase();
  if (availability !== "AVAILABLE") {
    return {
      distinctRthDates: "NOT_OBSERVED",
      calibrationLabel: "NOT CALIBRATED",
      calibrationForbidden: "CALIBRATION FORBIDDEN",
    };
  }
  const report = corpusSection?.report as Record<string, unknown> | undefined;
  const progress = report?.sample_gate_progress as Record<string, string> | undefined;
  const distinct = progress?.distinct_rth_dates ?? "NOT_OBSERVED";
  const calibrationState = String(report?.calibration_state ?? "NOT_CALIBRATED").replace(/_/g, " ");
  const fittingAllowed = report?.fitting_allowed === true;
  return {
    distinctRthDates: distinct,
    calibrationLabel: calibrationState.toUpperCase(),
    calibrationForbidden: fittingAllowed ? "CALIBRATION NOT PERMITTED BY UI" : "CALIBRATION FORBIDDEN",
  };
}

export function buildOperatorTruthRows(diagnostics: OperatorDiagnostics | null | undefined): OperatorTruthRow[] {
  if (!diagnostics) return [];

  const lifecycle = diagnosticsLifecycle(diagnostics);
  const readiness = diagnosticsReadiness(diagnostics);
  const runtime = diagnosticsRuntimeSection(diagnostics);
  const resilience = runtime?.runtime_resilience ?? {};
  const item9Preflight = runtime?.item9_preflight ?? {};
  const corpus = formatItem9CorpusProgress(runtime?.item9_corpus_status);
  const governance = diagnosticsGovernance(diagnostics);
  const cycle = diagnosticsSection<{
    expected_cycle_failure?: string;
    recovery_observed?: string;
    missing_receipt_epochs?: Array<Record<string, string>>;
    gap_note?: string;
  }>(diagnostics, "cycle_recovery");
  const evidenceGaps = diagnosticsSection<
    Array<{ domain?: string; gap_class?: string; detail?: string }>
  >(diagnostics, "evidence_gaps");

  const lifecycleStatus = String(lifecycle?.status ?? "UNKNOWN").toUpperCase();
  const lifecycleTruth: OperatorTruthClass =
    lifecycleStatus === "HEALTHY" || lifecycleStatus === "READY" || lifecycleStatus === "RUNNING"
      ? "HEALTHY"
      : lifecycleStatus === "STOPPED"
        ? "BLOCKED"
        : lifecycleStatus === "PARTIAL" || lifecycleStatus === "DEGRADED"
          ? "DEGRADED"
          : "UNKNOWN";

  const readinessStatus = String(readiness?.status ?? "UNKNOWN").toUpperCase();
  const readinessTruth: OperatorTruthClass =
    readinessStatus === "READY" ? "HEALTHY" : readinessStatus === "ACTION_REQUIRED" ? "DEGRADED" : "UNKNOWN";

  const collector = (resilience.collector_process ?? {}) as Record<string, unknown>;
  const collectorDetected = collector.active_collector_detected === true;
  const collectorTruth: OperatorTruthClass = collectorDetected
    ? "HEALTHY"
    : String(item9Preflight.disposition) === "NOT_RTH"
      ? "IDLE"
      : "NOT_OBSERVED";

  const liveTruth: OperatorTruthClass = governance?.live_execution_env ? "DEGRADED" : "BLOCKED";

  const cycleFailure = String(cycle?.expected_cycle_failure ?? "NOT_OBSERVED").toUpperCase();
  const cycleTruth: OperatorTruthClass =
    cycleFailure === "OBSERVED" ? "DEGRADED" : cycleFailure === "NOT_OBSERVED" ? "NOT_OBSERVED" : "UNKNOWN";

  const gapDetail =
    evidenceGaps?.map((gap) => `${gap.domain ?? "gap"}:${gap.gap_class ?? "UNKNOWN"}`).join("; ") ||
    "No composed evidence gaps.";

  const incident = matchKnownDataIncident(
    JSON.stringify(cycle?.missing_receipt_epochs ?? []) + (cycle?.gap_note ?? ""),
  );

  return [
    {
      id: "imp-lifecycle",
      label: "IMP platform lifecycle",
      truth: lifecycleTruth,
      detail: `Lifecycle status ${lifecycleStatus}.`,
      tone: lifecycleTruth === "HEALTHY" ? "live" : lifecycleTruth === "BLOCKED" ? "critical" : "caution",
    },
    {
      id: "operator-readiness",
      label: "Operator readiness",
      truth: readinessTruth,
      detail: `Readiness status ${readinessStatus}.`,
      tone: readinessTruth === "HEALTHY" ? "live" : "caution",
    },
    {
      id: "runtime-sha",
      label: "Runtime git SHA",
      truth: runtime?.git_sha ? "HEALTHY" : "UNAVAILABLE",
      detail: runtime?.git_sha ? String(runtime.git_sha) : "Diagnostics did not include runtime SHA.",
      tone: "neutral",
    },
    {
      id: "item9-preflight",
      label: "Item 9 preflight disposition",
      truth: mapItem9DispositionTruth(String(item9Preflight.disposition)),
      detail: String(item9Preflight.disposition ?? "UNKNOWN"),
      tone: mapItem9DispositionTruth(String(item9Preflight.disposition)) === "BLOCKED" ? "critical" : "caution",
    },
    {
      id: "item9-corpus",
      label: "Distinct admitted RTH dates",
      truth: corpus.distinctRthDates.includes("/") ? "DEGRADED" : "NOT_OBSERVED",
      detail: `${corpus.distinctRthDates} · ${corpus.calibrationLabel} · ${corpus.calibrationForbidden}`,
      tone: "caution",
    },
    {
      id: "collector",
      label: "Prospective collector process",
      truth: collectorTruth,
      detail: collectorDetected
        ? "Active collector process detected (summarized — no raw command lines)."
        : `Probe ${String(collector.probe_status ?? item9Preflight.disposition ?? "NOT_OBSERVED")}.`,
      tone: collectorDetected ? "live" : "neutral",
    },
    {
      id: "live-execution",
      label: "Live real-money execution",
      truth: liveTruth,
      detail: governance?.live_execution_env ? "Live execution env flag is on — still governed." : "Live OFF",
      tone: governance?.live_execution_env ? "critical" : "neutral",
    },
    {
      id: "expected-cycle",
      label: "Expected cycle failure",
      truth: cycleTruth,
      detail: cycle?.gap_note ?? "Cycle ledger not observed.",
      tone: cycleTruth === "DEGRADED" ? "caution" : "neutral",
    },
    {
      id: "evidence-gaps",
      label: "Evidence gaps (composed)",
      truth: evidenceGaps?.length ? "DEGRADED" : "NOT_OBSERVED",
      detail: gapDetail,
      tone: evidenceGaps?.length ? "caution" : "neutral",
    },
    ...(incident
      ? [
          {
            id: "known-outage",
            label: incident.title,
            truth: "DEGRADED" as OperatorTruthClass,
            detail: incident.detail,
            tone: incident.tone,
          },
        ]
      : []),
  ];
}

export function humanDiagnosticsHeadline(diagnostics: OperatorDiagnostics | null | undefined): string {
  const governance = diagnosticsGovernance(diagnostics);
  if (governance?.headline) return governance.headline;
  const questions = diagnostics?.operator_questions as Record<string, { answer?: unknown }> | undefined;
  const q16 = questions?.q16_human_headline?.answer;
  if (typeof q16 === "string" && q16.trim()) return q16;
  return diagnostics?.human_summary?.[0] ?? "Operator diagnostics unavailable.";
}
