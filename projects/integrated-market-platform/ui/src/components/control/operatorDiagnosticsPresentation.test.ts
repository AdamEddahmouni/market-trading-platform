import { describe, expect, it } from "vitest";
import {
  buildOperatorSituation,
  buildOperatorTruthRows,
  explainTruthClass,
  formatItem9CorpusProgress,
  humanDiagnosticsHeadline,
  item9CorpusMeaning,
  mapItem9CorpusProgressTruth,
} from "./operatorDiagnosticsPresentation";
import type { OperatorDiagnostics } from "../../api/schemas";

const SAMPLE_DIAGNOSTICS: OperatorDiagnostics = {
  schema_version: "operator-diagnostics/1.0.0",
  severity: "DEGRADED",
  sections: {
    lifecycle: { status: "HEALTHY" },
    readiness: { status: "READY", checks: [], providers: [] },
    governance: {
      headline: "Runtime SHA mismatch for Item 9 authority.",
      live_execution_env: false,
      interventions: ["Align collector worktree."],
      forbidden: ["enable_live_execution"],
    },
    runtime: {
      git_sha: "78232b24e4a276c32da3420089c6e17a3fdb8342",
      item9_preflight: { disposition: "WRONG_RUNTIME" },
      item9_corpus_status: {
        availability: "AVAILABLE",
        report: {
          calibration_state: "NOT_CALIBRATED",
          fitting_allowed: false,
          sample_gate_progress: { distinct_rth_dates: "2/3" },
        },
      },
      runtime_resilience: {
        collector_process: { active_collector_detected: false, probe_status: "COMPLETED" },
        expected_cycle: { receipt_inventory: { availability: "AVAILABLE", receipt_file_count: 0 } },
        readiness_vs_liveness: {
          readiness: { item9_status: "PARTIAL_NOT_CALIBRATED", calibrated: false },
        },
      },
    },
    opportunity_surface: { feed_status: "READY" },
    cycle_recovery: { expected_cycle_failure: "NOT_OBSERVED" },
    evidence_gaps: [],
  },
  human_summary: ["fallback"],
};

describe("operatorDiagnosticsPresentation", () => {
  it("surfaces Item 9 corpus progress without fabricating 3/3", () => {
    const runtime = SAMPLE_DIAGNOSTICS.sections.runtime as Record<string, unknown>;
    const corpus = formatItem9CorpusProgress(runtime.item9_corpus_status as Record<string, unknown>);
    expect(corpus.distinctRthDates).toBe("2/3");
    expect(corpus.calibrationLabel).toBe("NOT CALIBRATED");
    expect(corpus.calibrationForbidden).toBe("CALIBRATION FORBIDDEN");
  });

  it("prefers governance headline over human_summary", () => {
    expect(humanDiagnosticsHeadline(SAMPLE_DIAGNOSTICS)).toMatch(/Runtime SHA mismatch/);
  });

  it("includes separate truth classes for lifecycle and Item 9 disposition", () => {
    const rows = buildOperatorTruthRows(SAMPLE_DIAGNOSTICS);
    expect(rows.find((row) => row.id === "item9-preflight")?.truth).toBe("BLOCKED");
    expect(rows.find((row) => row.id === "live-execution")?.detail).toMatch(/Live OFF/);
  });

  it("maps partial Item 9 corpus progress (2/3) to IDLE, not DEGRADED", () => {
    const runtime = SAMPLE_DIAGNOSTICS.sections.runtime as Record<string, unknown>;
    const corpusSection = runtime.item9_corpus_status as Record<string, unknown>;
    expect(mapItem9CorpusProgressTruth(corpusSection, "2/3")).toBe("IDLE");
    const rows = buildOperatorTruthRows(SAMPLE_DIAGNOSTICS);
    const corpusRow = rows.find((row) => row.id === "item9-corpus");
    expect(corpusRow?.truth).toBe("IDLE");
    expect(corpusRow?.kind).toBe("waiting");
    expect(corpusRow?.detail).toMatch(/2\/3 · NOT CALIBRATED · CALIBRATION FORBIDDEN/);
    expect(corpusRow?.meaning).toMatch(/still needs more distinct regular-trading-hours dates/);
    expect(corpusRow?.meaning).toMatch(/IDLE, not DEGRADED/);
    expect(corpusRow?.truth).not.toBe("DEGRADED");
  });

  it("explains Live OFF as a policy lock, not platform degradation", () => {
    const rows = buildOperatorTruthRows(SAMPLE_DIAGNOSTICS);
    const live = rows.find((row) => row.id === "live-execution");
    expect(live?.detail).toMatch(/Live OFF/);
    expect(live?.kind).toBe("policy");
    expect(live?.truth).toBe("POLICY");
    expect(live?.truth).not.toBe("BLOCKED");
    expect(live?.truth).not.toBe("DEGRADED");
    expect(explainTruthClass(live!.truth, live!.kind)).toMatch(/Intentional safety lock/);
    expect(explainTruthClass(live!.truth, live!.kind)).not.toMatch(/gate is cleared/);
  });

  it("reserves BLOCKED for real Item 9 gates such as WRONG_RUNTIME", () => {
    const preflight = buildOperatorTruthRows(SAMPLE_DIAGNOSTICS).find((row) => row.id === "item9-preflight");
    expect(preflight?.truth).toBe("BLOCKED");
    expect(explainTruthClass(preflight!.truth, preflight!.kind)).toMatch(/real gate/);
  });

  it("does not say Item 9 still needs dates when the 3/3 gate is complete", () => {
    const complete = formatItem9CorpusProgress({
      availability: "AVAILABLE",
      report: {
        calibration_state: "NOT_CALIBRATED",
        fitting_allowed: false,
        sample_gate_progress: { distinct_rth_dates: "3/3" },
      },
    });
    expect(complete.distinctRthDates).toBe("3/3");
    expect(complete.calibrationLabel).toBe("NOT CALIBRATED");
    expect(complete.calibrationForbidden).toBe("CALIBRATION FORBIDDEN");
    const meaning = item9CorpusMeaning(complete, "HEALTHY");
    expect(meaning).toMatch(/date gate is complete \(3\/3\)/);
    expect(meaning).not.toMatch(/still needs more/);
    expect(meaning).toMatch(/NOT CALIBRATED/);
    expect(meaning).toMatch(/CALIBRATION FORBIDDEN/);
  });

  it("treats calendar-incomplete Item 9 as waiting even when another row is blocked", () => {
    const situation = buildOperatorSituation(SAMPLE_DIAGNOSTICS);
    expect(situation.kind).toBe("impaired");
    expect(situation.explanation).toMatch(/2\/3/);
    expect(situation.explanation).toMatch(/Live OFF/);
  });

  it("classifies calendar-only incomplete corpus as waiting, not impaired", () => {
    const calendarOnly: OperatorDiagnostics = {
      ...SAMPLE_DIAGNOSTICS,
      severity: "OK",
      sections: {
        ...SAMPLE_DIAGNOSTICS.sections,
        governance: {
          ...(SAMPLE_DIAGNOSTICS.sections.governance as Record<string, unknown>),
          headline: "No blocking operator headline.",
        },
        runtime: {
          ...(SAMPLE_DIAGNOSTICS.sections.runtime as Record<string, unknown>),
          item9_preflight: { disposition: "NOT_RTH" },
        },
      },
    };
    const situation = buildOperatorSituation(calendarOnly);
    expect(situation.kind).toBe("waiting");
    expect(situation.title).toMatch(/calendar/i);
    expect(situation.explanation).toMatch(/IDLE, not DEGRADED/);
    expect(situation.explanation).toMatch(/Live OFF/);
  });

  it("maps 0/3 corpus progress to NOT_OBSERVED when receipts are missing", () => {
    const runtime = SAMPLE_DIAGNOSTICS.sections.runtime as Record<string, unknown>;
    const corpusSection = runtime.item9_corpus_status as Record<string, unknown>;
    expect(mapItem9CorpusProgressTruth(corpusSection, "0/3")).toBe("NOT_OBSERVED");
  });
});
