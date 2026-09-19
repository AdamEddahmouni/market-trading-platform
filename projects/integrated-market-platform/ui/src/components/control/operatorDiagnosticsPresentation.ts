import type { OperatorDiagnostics, OperatorLifecycleStatus, OperatorReadiness } from "../../api/schemas";
import type { SemanticTone } from "../../state/semanticState";
import { matchKnownDataIncident } from "../operator-shared/knownDataIncidents";
import { preferItem9OperatorTruth } from "./consumeOperatorTruth";

/** Canonical operator truth tokens — do not collapse into generic pass/fail. */
export type OperatorTruthClass =
  | "HEALTHY"
  | "DEGRADED"
  | "BLOCKED"
  | "POLICY"
  | "IDLE"
  | "UNKNOWN"
  | "UNAVAILABLE"
  | "NOT_OBSERVED";

export type OperatorRowKind = "ok" | "waiting" | "policy" | "fault" | "unknown";

export type OperatorTruthRow = {
  id: string;
  label: string;
  truth: OperatorTruthClass;
  detail: string;
  /** Plain-language meaning for a trader who does not know IMP internals. */
  meaning: string;
  kind: OperatorRowKind;
  tone: SemanticTone;
};

export type OperatorSituation = {
  kind: "waiting" | "impaired" | "healthy" | "unavailable";
  title: string;
  explanation: string;
};

export function explainTruthClass(truth: OperatorTruthClass, kind?: OperatorRowKind): string {
  if (kind === "policy" || truth === "POLICY") {
    return "Intentional safety lock — not a crash and not a repair item.";
  }
  switch (truth) {
    case "HEALTHY":
      return "Working as expected.";
    case "IDLE":
      return "Waiting — a calendar or schedule gate, not a broken platform.";
    case "DEGRADED":
      return "Impaired — something that should be working is not.";
    case "BLOCKED":
      return "Stopped by a real gate — this path cannot proceed until that gate is cleared.";
    case "UNAVAILABLE":
      return "This fact could not be read from the platform snapshot. Treat as unknown, not healthy.";
    case "NOT_OBSERVED":
      return "No observation yet. Absence of evidence is not a passing result.";
    case "UNKNOWN":
    default:
      return "Not classified. Treat as unverified, not healthy.";
  }
}

export function truthTone(truth: OperatorTruthClass): SemanticTone {
  switch (truth) {
    case "HEALTHY":
      return "live";
    case "DEGRADED":
    case "UNAVAILABLE":
      return "caution";
    case "BLOCKED":
      return "critical";
    case "POLICY":
      return "neutral";
    case "IDLE":
    case "NOT_OBSERVED":
    case "UNKNOWN":
    default:
      return "neutral";
  }
}

export function classifyOperatorRow(row: {
  id: string;
  truth: OperatorTruthClass;
  detail: string;
}): OperatorRowKind {
  if (row.id === "live-execution") {
    return /Live OFF/i.test(row.detail) || row.truth === "POLICY" ? "policy" : "fault";
  }
  if (row.truth === "POLICY") return "policy";
  if (row.truth === "IDLE") return "waiting";
  if (row.truth === "HEALTHY") return "ok";
  if (row.truth === "DEGRADED" || row.truth === "BLOCKED" || row.truth === "UNAVAILABLE") {
    return "fault";
  }
  return "unknown";
}

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

export function parseItem9SampleGateFraction(
  distinctRthDates: string,
): { admitted: number; required: number } | null {
  const trimmed = distinctRthDates.trim();
  const match = /^(\d+)\s*\/\s*(\d+)$/.exec(trimmed);
  if (!match) return null;
  const admitted = Number(match[1]);
  const required = Number(match[2]);
  if (!Number.isFinite(admitted) || !Number.isFinite(required) || required <= 0) return null;
  return { admitted, required };
}

/**
 * Item 9 n/m progress is calendar/methodology state — not platform degradation.
 * Partial admission (e.g. 2/3) is IDLE; missing corpus is NOT_OBSERVED / UNAVAILABLE.
 */
export function mapItem9CorpusProgressTruth(
  corpusSection: Record<string, unknown> | undefined,
  distinctRthDates: string,
): OperatorTruthClass {
  const availability = String(corpusSection?.availability ?? "NOT_OBSERVED").toUpperCase();
  if (availability !== "AVAILABLE") {
    return availability === "UNAVAILABLE" ? "UNAVAILABLE" : "NOT_OBSERVED";
  }

  const token = distinctRthDates.trim().toUpperCase();
  if (token === "NOT_OBSERVED" || token === "UNKNOWN" || token === "UNAVAILABLE") {
    return token === "UNAVAILABLE" ? "UNAVAILABLE" : "NOT_OBSERVED";
  }

  const fraction = parseItem9SampleGateFraction(distinctRthDates);
  if (!fraction) return "UNKNOWN";

  if (fraction.admitted === 0) return "NOT_OBSERVED";
  if (fraction.admitted < fraction.required) return "IDLE";
  if (fraction.admitted === fraction.required) return "HEALTHY";
  return "UNKNOWN";
}

export function item9CorpusProgressIsCalendarIncomplete(
  diagnostics: OperatorDiagnostics | null | undefined,
): boolean {
  const runtime = diagnosticsRuntimeSection(diagnostics);
  const corpus = formatItem9CorpusProgress(runtime?.item9_corpus_status);
  const local = mapItem9CorpusProgressTruth(runtime?.item9_corpus_status, corpus.distinctRthDates);
  return preferItem9OperatorTruth(diagnostics, "item9-corpus", local) === "IDLE";
}

export function formatItem9CorpusProgress(
  corpusSection: Record<string, unknown> | undefined,
): {
  distinctRthDates: string;
  calibrationLabel: string;
  calibrationForbidden: string;
  receiptScopeNote: string;
} {
  const availability = String(corpusSection?.availability ?? "NOT_OBSERVED").toUpperCase();
  const scope = String(corpusSection?.receipt_scope ?? "UNKNOWN");
  const scopeNote =
    scope === "FROZEN_COLLECTOR_WORKTREE_READ_ONLY"
      ? "Read-only corpus gate from frozen collector receipts (.imp-actual-01-phase-d)."
      : scope === "RUNTIME_IMP_ROOT_READ_ONLY"
        ? "Read-only corpus gate from this API checkout receipt dir (may differ from frozen collector)."
        : "Corpus receipt scope not observed.";

  if (availability !== "AVAILABLE") {
    return {
      distinctRthDates: "NOT_OBSERVED",
      calibrationLabel: "NOT CALIBRATED",
      calibrationForbidden: "CALIBRATION FORBIDDEN",
      receiptScopeNote: scopeNote,
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
    receiptScopeNote: scopeNote,
  };
}

export function item9CorpusMeaning(
  corpus: ReturnType<typeof formatItem9CorpusProgress>,
  corpusTruth: OperatorTruthClass,
): string {
  const tokens = `Canonical tokens: Item 9 ${corpus.distinctRthDates}, ${corpus.calibrationLabel}, ${corpus.calibrationForbidden}.`;
  if (corpusTruth === "HEALTHY") {
    return `The distinct regular-trading-hours date gate is complete (${corpus.distinctRthDates}). ${tokens} That does not by itself make the strategy CALIBRATED.`;
  }
  if (corpusTruth === "IDLE") {
    return `Paper fill calibration still needs more distinct regular-trading-hours dates. ${tokens} Incomplete dates are IDLE, not DEGRADED.`;
  }
  if (corpusTruth === "NOT_OBSERVED" || corpusTruth === "UNAVAILABLE") {
    return `Item 9 date progress is ${corpus.distinctRthDates}. ${tokens} Missing corpus is not a passing 3/3.`;
  }
  return `${tokens} Treat this progress as unverified, not healthy.`;
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
  const evidenceGapsRaw = diagnostics?.sections?.evidence_gaps;
  const evidenceGaps = Array.isArray(evidenceGapsRaw)
    ? (evidenceGapsRaw as Array<{ domain?: string; gap_class?: string; detail?: string }>)
    : undefined;

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
    readinessStatus === "READY"
      ? "HEALTHY"
      : readinessStatus === "ACTION_REQUIRED"
        ? "DEGRADED"
        : readinessStatus === "BLOCKED"
          ? "BLOCKED"
          : "UNKNOWN";

  const collector = (resilience.collector_process ?? {}) as Record<string, unknown>;
  const collectorDetected = collector.active_collector_detected === true;
  const collectorTruth: OperatorTruthClass = collectorDetected
    ? "HEALTHY"
    : String(item9Preflight.disposition) === "NOT_RTH"
      ? "IDLE"
      : "NOT_OBSERVED";

  const liveTruth: OperatorTruthClass = governance?.live_execution_env ? "DEGRADED" : "POLICY";

  const cycleFailure = String(cycle?.expected_cycle_failure ?? "NOT_OBSERVED").toUpperCase();
  const cycleTruth: OperatorTruthClass =
    cycleFailure === "OBSERVED" ? "DEGRADED" : cycleFailure === "NOT_OBSERVED" ? "NOT_OBSERVED" : "UNKNOWN";

  const gapDetail =
    evidenceGaps?.map((gap) => `${gap.domain ?? "gap"}:${gap.gap_class ?? "UNKNOWN"}`).join("; ") ||
    "No composed evidence gaps.";

  const incident = matchKnownDataIncident(
    JSON.stringify(cycle?.missing_receipt_epochs ?? []) + (cycle?.gap_note ?? ""),
  );

  const corpusTruth = preferItem9OperatorTruth(
    diagnostics,
    "item9-corpus",
    mapItem9CorpusProgressTruth(runtime?.item9_corpus_status, corpus.distinctRthDates),
  );
  const preflightTruth = preferItem9OperatorTruth(
    diagnostics,
    "item9-preflight",
    mapItem9DispositionTruth(String(item9Preflight.disposition)),
  );
  const preflightToken = String(item9Preflight.disposition ?? "UNKNOWN");
  const liveOff = !governance?.live_execution_env;

  const rows: OperatorTruthRow[] = [
    {
      id: "imp-lifecycle",
      label: "IMP platform lifecycle",
      truth: lifecycleTruth,
      detail: `Lifecycle status ${lifecycleStatus}.`,
      meaning: "Whether local platform services are running. This is workstation health, not trading skill.",
      kind: "unknown",
      tone: truthTone(lifecycleTruth),
    },
    {
      id: "operator-readiness",
      label: "Operator readiness",
      truth: readinessTruth,
      detail: `Readiness status ${readinessStatus}.`,
      meaning: "Whether setup checks passed so this workstation can operate. A calendar wait is not a failed setup.",
      kind: "unknown",
      tone: truthTone(readinessTruth),
    },
    {
      id: "runtime-sha",
      label: "Runtime git SHA",
      truth: runtime?.git_sha ? "HEALTHY" : "UNAVAILABLE",
      detail: runtime?.git_sha ? String(runtime.git_sha) : "Diagnostics did not include runtime SHA.",
      meaning: "Exact software revision the API is running. Copy it when comparing collectors — do not infer health from the hash.",
      kind: "unknown",
      tone: "neutral",
    },
    {
      id: "item9-preflight",
      label: "Item 9 preflight disposition",
      truth: preflightTruth,
      detail: preflightToken,
      meaning:
        preflightTruth === "IDLE"
          ? `Regular trading hours are closed (${preflightToken}). Collection waits for the next US cash session — IDLE, not DEGRADED.`
          : preflightTruth === "BLOCKED"
            ? `Item 9 collection is blocked (${preflightToken}). This is a gate failure, not a calendar wait.`
            : `Item 9 preflight token ${preflightToken}. ${explainTruthClass(preflightTruth)}`,
      kind: "unknown",
      tone: preflightTruth === "IDLE" ? "neutral" : truthTone(preflightTruth),
    },
    {
      id: "item9-corpus",
      label: "Distinct admitted RTH dates",
      truth: corpusTruth,
      detail: `${corpus.distinctRthDates} · ${corpus.calibrationLabel} · ${corpus.calibrationForbidden}. ${corpus.receiptScopeNote}`,
      meaning: item9CorpusMeaning(corpus, corpusTruth),
      kind: "unknown",
      tone: truthTone(corpusTruth),
    },
    {
      id: "collector",
      label: "Prospective collector process",
      truth: collectorTruth,
      detail: collectorDetected
        ? "Active collector process detected (summarized — no raw command lines)."
        : `Probe ${String(collector.probe_status ?? item9Preflight.disposition ?? "NOT_OBSERVED")}.`,
      meaning: collectorDetected
        ? "A governed collector process is running. This screen does not start or stop it."
        : "No active collector was observed. Off-hours that is expected (waiting), not a crash.",
      kind: "unknown",
      tone: collectorDetected ? "live" : "neutral",
    },
    {
      id: "live-execution",
      label: "Live real-money execution",
      truth: liveTruth,
      detail: liveOff ? "Live OFF" : "Live execution env flag is on — still governed.",
      meaning: liveOff
        ? "Intentional safety lock. Canonical token: Live OFF. Observational live data never places broker orders."
        : "A live-execution environment flag is on. Still subject to platform gates — this is not a go-live.",
      kind: "unknown",
      tone: liveOff ? "neutral" : "critical",
    },
    {
      id: "expected-cycle",
      label: "Expected cycle failure",
      truth: cycleTruth,
      detail: cycle?.gap_note ?? "Cycle ledger not observed.",
      meaning:
        cycleTruth === "DEGRADED"
          ? "A scheduled evidence cycle did not complete as expected. That is a recorded gap, not a passing wait."
          : "No expected-cycle failure is on this snapshot. Missing ledger is NOT_OBSERVED, not healthy.",
      kind: "unknown",
      tone: truthTone(cycleTruth),
    },
    {
      id: "evidence-gaps",
      label: "Evidence gaps (composed)",
      truth: evidenceGaps?.length ? "DEGRADED" : "NOT_OBSERVED",
      detail: gapDetail,
      meaning: evidenceGaps?.length
        ? "Composed evidence gaps are listed below. They stay explicit; the UI does not upgrade them to passing."
        : "No composed evidence gaps in this snapshot.",
      kind: "unknown",
      tone: evidenceGaps?.length ? "caution" : "neutral",
    },
    ...(incident
      ? [
          {
            id: "known-outage",
            label: incident.title,
            truth: "DEGRADED" as OperatorTruthClass,
            detail: incident.detail,
            meaning: "A known data incident matched this snapshot. Treat the named outage as impaired, not a calendar wait.",
            kind: "fault" as OperatorRowKind,
            tone: incident.tone,
          },
        ]
      : []),
  ];

  return rows.map((row) => ({
    ...row,
    kind: classifyOperatorRow(row),
  }));
}

export function buildOperatorSituation(
  diagnostics: OperatorDiagnostics | null | undefined,
): OperatorSituation {
  if (!diagnostics) {
    return {
      kind: "unavailable",
      title: "Platform snapshot unavailable",
      explanation:
        "Control cannot explain operating state until the operator diagnostics snapshot responds. This is a load failure, not a calendar wait.",
    };
  }

  const rows = buildOperatorTruthRows(diagnostics);
  const corpus = rows.find((row) => row.id === "item9-corpus");
  const live = rows.find((row) => row.id === "live-execution");
  const hasFault = rows.some((row) => row.kind === "fault");

  if (hasFault) {
    const firstFault = rows.find((row) => row.kind === "fault");
    return {
      kind: "impaired",
      title: "Something needs attention",
      explanation: `${firstFault?.meaning ?? "A platform fact is impaired."} Item 9 calendar progress stays separate from this fault: ${corpus?.detail ?? "NOT_OBSERVED"}. ${live?.detail === "Live OFF" ? "Live OFF." : ""}`.trim(),
    };
  }

  if (corpus?.kind === "waiting") {
    return {
      kind: "waiting",
      title: "Waiting on the trading calendar",
      explanation: `Item 9 is ${corpus.detail} That wait is IDLE, not DEGRADED. ${live?.detail === "Live OFF" ? "Live OFF." : ""} You do not need to “fix” the workstation for the missing dates.`.replace(
        /\s+/g,
        " ",
      ),
    };
  }

  return {
    kind: "healthy",
    title: "No blocking platform faults",
    explanation: `Readiness and lifecycle are not raising a repair item. ${live?.detail === "Live OFF" ? "Live OFF remains the safety lock." : ""} Canonical Item 9 tokens stay on this page.`.replace(
      /\s+/g,
      " ",
    ),
  };
}

export function humanDiagnosticsHeadline(diagnostics: OperatorDiagnostics | null | undefined): string {
  const governance = diagnosticsGovernance(diagnostics);
  if (governance?.headline) return governance.headline;
  const questions = diagnostics?.operator_questions as Record<string, { answer?: unknown }> | undefined;
  const q16 = questions?.q16_human_headline?.answer;
  if (typeof q16 === "string" && q16.trim()) return q16;
  return diagnostics?.human_summary?.[0] ?? "Operator diagnostics unavailable.";
}
